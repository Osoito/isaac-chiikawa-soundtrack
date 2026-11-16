"""Build the mod's ogg files from the FLAC masters.

  python build/build_audio.py            # build everything
  python build/build_audio.py --jingles  # rebuild only the 22 jingle clips (fast)

Stage 1 trims each master's leading/trailing silence into build/.cache/<slug>.wav.
Every later step -- the looping ogg and all jingle cuts -- derives from that trimmed
wav, so a cut offset reported on the audition page means the same thing everywhere.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tracks as T
from ffio import decode_mono, duration, ebur128, ffmpeg, rms_envelope, window_energy

CACHE = T.ROOT / "build" / ".cache"

# Trim anything quieter than this at the very start and end of a master.
TRIM_THRESHOLD = "-50dB"

# Jingle envelope shaping.
FADE_IN = 0.10
FADE_OUT = 0.40

# Keep automatic cut windows away from the extreme edges of a master.
EDGE_GUARD = 0.5
# Minimum silence-free gap between two automatically chosen windows of the same master.
WINDOW_GAP = 1.0


def trim_master(key):
    """FLAC -> silence-trimmed wav in the cache. Returns the wav path."""
    src = T.master_path(key)
    if not src.exists():
        sys.exit(f"error: master not found: {src}")
    dst = CACHE / f"{T.master_slug(key)}.wav"
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return dst
    trim = (
        f"silenceremove=start_periods=1:start_threshold={TRIM_THRESHOLD}"
        ":start_silence=0:detection=peak"
    )
    ffmpeg("-i", str(src), "-map", "a:0",
           "-af", f"{trim},areverse,{trim},areverse",
           "-c:a", "pcm_s16le", str(dst))
    return dst


def reachable_lufs(lufs, peak):
    """Loudest level this material reaches within the limiting budget."""
    headroom = T.TRUE_PEAK_CEILING - peak
    return lufs + headroom + T.LIMIT_BUDGET_DB


def choose_target(measurements):
    """Derive the loop target from the masters themselves.

    The quietest-headroom track sets the ceiling for everyone: aiming higher than it can
    reach would either leave it behind or squash it. Capped at vanilla's level.
    """
    reachable = [reachable_lufs(l, p) for l, p in measurements.values()
                 if l == l and l != float("-inf")]
    if not reachable:
        return T.LOUDNESS_CAP_LUFS
    return min(min(reachable), T.LOUDNESS_CAP_LUFS)


def gain_filter(lufs, peak, target_lufs):
    """Filter chain bringing measured audio to `target_lufs` under the peak ceiling.

    Gain first, then a limiter to catch whatever the gain pushes over the ceiling.
    Returns (filter string, applied gain dB, expected peak reduction dB) -- the last
    value is how much work the limiter has to do, i.e. how squashed the result may be.
    """
    if lufs != lufs or lufs == float("-inf"):
        return None, 0.0, 0.0
    gain = target_lufs - lufs
    limiting = max(0.0, (peak + gain) - T.TRUE_PEAK_CEILING)
    chain = (
        f"volume={gain:.2f}dB,"
        f"alimiter=limit={T.TRUE_PEAK_CEILING}dB:attack=5:release=50:level=disabled"
    )
    return chain, gain, limiting


def encode_loop(key, wav, lufs, peak, target):
    out = T.OGG_DIR / f"{T.master_slug(key)}.ogg"
    target = T.LOUDNESS_OVERRIDE.get(key, target)
    chain, gain, limiting = gain_filter(lufs, peak, target)
    args = ["-i", str(wav), "-map", "a:0"]
    if chain:
        args += ["-af", chain]
    args += ["-c:a", "libvorbis", "-q:a", T.VORBIS_QUALITY, str(out)]
    ffmpeg(*args)
    return out, gain, limiting


def pick_cut_points(key, wav, slots):
    """Choose a distinct, energetic window for each jingle slot cut from this master.

    Slots with an explicit `start` in tracks.py keep it and reserve that region so an
    automatic pick cannot land on top of them.
    """
    total = duration(wav)
    env, hop_s = rms_envelope(decode_mono(wav), 8000)
    taken = np.zeros(len(env), dtype=bool)
    chosen = {}

    def reserve(start, length):
        a = max(0, int((start - WINDOW_GAP) / hop_s))
        b = min(len(taken), int((start + length + WINDOW_GAP) / hop_s) + 1)
        taken[a:b] = True

    pinned = [n for n in slots if T.JINGLES[n]["start"] is not None]
    auto = [n for n in slots if T.JINGLES[n]["start"] is None]

    for n in pinned:
        spec = T.JINGLES[n]
        start = float(spec["start"])
        if start + spec["length"] > total + 1e-6:
            sys.exit(
                f"error: jingle {n} ({T.slot_name(n)}) starts at {start:.2f}s with "
                f"length {spec['length']:.2f}s, past the end of {T.master_slug(key)} "
                f"({total:.2f}s)"
            )
        chosen[n] = start
        reserve(start, spec["length"])

    for n in auto:
        spec = T.JINGLES[n]
        win_hops = max(1, int(spec["length"] / hop_s))
        energy = window_energy(env, win_hops)
        if len(energy) == 0:
            sys.exit(
                f"error: master {T.master_slug(key)} ({total:.2f}s) is shorter than the "
                f"{spec['length']:.2f}s needed by jingle {n} ({T.slot_name(n)})"
            )

        lo, hi = spec["search"] or (EDGE_GUARD, total - spec["length"] - EDGE_GUARD)
        lo_h = max(0, int(lo / hop_s))
        hi_h = min(len(energy), int(hi / hop_s) + 1)
        if hi_h <= lo_h:  # master too short for the guard; fall back to the whole file
            lo_h, hi_h = 0, len(energy)

        score = energy.copy()
        # Disqualify windows that overlap an already-claimed region or the guard band.
        blocked = np.array([taken[i:i + win_hops].any() for i in range(len(energy))])
        score[blocked] = -1.0
        mask = np.full(len(energy), -1.0)
        mask[lo_h:hi_h] = score[lo_h:hi_h]

        if mask.max() < 0:  # everything blocked: relax the no-overlap rule
            mask = energy.copy()

        start = float(np.argmax(mask) * hop_s)
        chosen[n] = start
        reserve(start, spec["length"])

    return chosen, total


def render_clip(wav, start, length, out, jingle_target, tag="tmp"):
    """Cut, shape and level one clip. Shared by the build and the audition page.

    Two passes: the raw cut lands in a temporary wav so its loudness can be measured
    before the level is set. Cutting the loudest window of a master means the clip is
    otherwise several LU hotter than the floor music it interrupts.
    """
    fade_out_at = max(0.0, length - FADE_OUT)
    cut = CACHE / f"cut_{tag}.wav"

    ffmpeg("-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(wav), "-map", "a:0",
           "-af", f"afade=t=in:st=0:d={FADE_IN},"
                  f"afade=t=out:st={fade_out_at:.3f}:d={FADE_OUT}",
           "-c:a", "pcm_s16le", str(cut))

    lufs, peak = ebur128(cut)
    # Never push a jingle past what its own headroom allows, so a short clip cannot be
    # squashed harder than the loops it sits beside.
    target = min(jingle_target, reachable_lufs(lufs, peak))
    chain, gain, limiting = gain_filter(lufs, peak, target)
    args = ["-i", str(cut), "-map", "a:0"]
    if chain:
        args += ["-af", chain]
    args += ["-c:a", "libvorbis", "-q:a", T.VORBIS_QUALITY, str(out)]
    ffmpeg(*args)
    cut.unlink(missing_ok=True)
    return out, gain, limiting


def phrase_windows(wav, min_len, max_len, count, avoid=(), hop_s=0.05):
    """Windows that begin and end on musical phrase boundaries.

    The default cut heuristic maximises RMS, which by construction lands in the middle
    of the loudest phrase -- often mid-vocal, so the clip has no beginning or end. This
    instead looks for energy dips, treats the rise out of one as a phrase start, and
    ends the window at the next dip. Returns [(start, length, score)] best first.

    `avoid` is a list of (start, end) ranges already claimed by other clips.
    """
    env, _ = rms_envelope(decode_mono(wav, 8000), 8000, hop_s=hop_s)
    db = 20 * np.log10(np.maximum(env, 1e-6))
    db -= db.max()
    smooth = np.convolve(db, np.ones(5) / 5, mode="same")
    total = len(smooth) * hop_s

    # A frame is a dip if it is the quietest point in a +/- 0.5 s neighbourhood and
    # sits meaningfully below the track's typical level.
    half = max(1, int(0.5 / hop_s))
    typical = float(np.median(smooth))
    dips = []
    for i in range(half, len(smooth) - half):
        window = smooth[i - half:i + half + 1]
        if smooth[i] <= window.min() + 0.01 and smooth[i] < typical - 3.0:
            if not dips or (i - dips[-1]) * hop_s > 0.8:
                dips.append(i)

    candidates = []
    for a in dips:
        start = (a + 1) * hop_s          # begin on the rise out of the dip, not in it
        for b in dips:
            length = (b - a) * hop_s
            if not (min_len <= length <= max_len):
                continue
            end = start + length
            if end > total - 0.2:
                continue
            if any(start < ae and end > as_ for as_, ae in avoid):
                continue
            body = smooth[a:b]
            if len(body) == 0:
                continue
            # Prefer a deep start dip, a deep end dip, and loud material between them.
            score = (float(body.mean())
                     - 0.5 * smooth[a] - 0.5 * smooth[b])
            candidates.append((start, round(length, 2), score))

    candidates.sort(key=lambda c: -c[2])
    chosen = []
    for start, length, score in candidates:
        if any(start < s + l and start + length > s for s, l, _ in chosen):
            continue
        chosen.append((start, length, score))
        if len(chosen) >= count:
            break
    return chosen


def encode_jingle(n, wav, start, jingle_target):
    return render_clip(wav, start, T.JINGLES[n]["length"],
                       T.OGG_DIR / f"{T.jingle_slug(n)}.ogg", jingle_target,
                       tag=T.jingle_slug(n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jingles", action="store_true",
                    help="rebuild only the jingle clips")
    args = ap.parse_args()

    T.validate()
    CACHE.mkdir(parents=True, exist_ok=True)
    T.OGG_DIR.mkdir(parents=True, exist_ok=True)

    wavs = {}
    for key in T.used_masters():
        wavs[key] = trim_master(key)

    measured = {key: ebur128(wav) for key, wav in wavs.items()}
    target = choose_target(measured)
    jingle_target = target + T.JINGLE_OFFSET_LU
    binding = min(measured, key=lambda k: reachable_lufs(*measured[k]))
    print(f"target:  {target:.1f} LUFS for loops, {jingle_target:.1f} for jingles "
          f"(limited by {T.master_slug(binding)}, "
          f"budget {T.LIMIT_BUDGET_DB:.0f} dB)")

    squashed = []

    if not args.jingles:
        for key in T.used_masters():
            lufs, peak = measured[key]
            _, gain, limiting = encode_loop(key, wavs[key], lufs, peak, target)
            if limiting > T.LIMIT_BUDGET_DB + 0.1:
                squashed.append((T.master_slug(key), gain, limiting))
        print(f"loops:   {len(T.used_masters())} ogg files")

    cut_points = {}
    by_master = T.jingles_by_master()
    for key, slots in by_master.items():
        chosen, total = pick_cut_points(key, wavs[key], slots)
        for n, start in chosen.items():
            encode_jingle(n, wavs[key], start, jingle_target)
            cut_points[str(n)] = {
                "slot": T.slot_name(n),
                "master": key,
                "master_slug": T.master_slug(key),
                "master_duration": round(total, 3),
                "start": round(start, 3),
                "length": T.JINGLES[n]["length"],
                "pinned": T.JINGLES[n]["start"] is not None,
            }

    jingle_count = len(cut_points)
    cut_points["_meta"] = {
        "loop_target_lufs": round(target, 2),
        "jingle_target_lufs": round(jingle_target, 2),
        "limit_budget_db": T.LIMIT_BUDGET_DB,
        "true_peak_ceiling": T.TRUE_PEAK_CEILING,
        "binding_master": T.master_slug(binding),
    }
    T.CUT_POINTS_PATH.write_text(
        json.dumps(cut_points, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"jingles: {jingle_count} ogg files")
    print(f"cut points -> {T.CUT_POINTS_PATH.relative_to(T.ROOT)}")

    if squashed:
        print("\nover the limiting budget -- pin a lower target in "
              "tracks.LOUDNESS_OVERRIDE if these sound squashed:")
        for slug, gain, limiting in sorted(squashed, key=lambda r: -r[2]):
            print(f"  {slug:<12} {gain:+.1f} dB gain, {limiting:.1f} dB into the limiter")


if __name__ == "__main__":
    main()
