"""Layer 1 verification: machine checks on the built ogg files. No ears, no game.

  python build/verify.py

Exits non-zero if any FAIL is reported. WARNs are advisory and do not block.
See §7 of docs/design.md
"""

import configparser
import json
import math
import sys
from pathlib import Path
from xml.etree import ElementTree

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tracks as T
from ffio import decode_mono, ebur128, probe

OPTIONS_INI = (
    Path.home() / "Documents" / "My Games" / "Binding of Isaac Repentance+" / "options.ini"
)

DURATION_TOLERANCE = 0.05   # seconds
LOUDNESS_SPREAD = 1.5       # LU, tracks of one kind against each other
DEAD_CLIP_MARGIN = 9.0      # dB below the source master before a clip reads as "dead"
TAIL_DROP = 10.0            # dB the fade-out must pull the last 100 ms below clip level
FADE_OUT = 0.40             # must match build_audio.FADE_OUT
FADE_IN = 0.10

# Measured over the vanilla Rebirth oggs bundled with Soundtrack Menu; see tracks.py.
VANILLA_LOOP_LUFS = -11.6
VANILLA_JINGLE_LUFS = -14.5

results = []


def record(level, check, detail):
    results.append((level, check, detail))


def rms_db(samples):
    if len(samples) == 0:
        return float("-inf")
    value = float(np.sqrt(np.mean(samples.astype("f8") ** 2)))
    return 20 * math.log10(value) if value > 0 else float("-inf")


# --------------------------------------------------------------------------------------

def check_metadata():
    path = T.MOD_ROOT / "metadata.xml"
    if not path.exists():
        record("FAIL", "mod/metadata", "mod/metadata.xml is missing")
        return
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as e:
        record("FAIL", "mod/metadata", f"metadata.xml is not well-formed: {e}")
        return
    directory = (root.findtext("directory") or "").strip()
    if directory != T.MOD_DIR_NAME:
        record("FAIL", "mod/metadata",
               f"<directory> is {directory!r}, but the mod installs to "
               f"{T.MOD_DIR_NAME!r}")
    if not (root.findtext("name") or "").strip():
        record("FAIL", "mod/metadata", "<name> is empty")


def check_xml_references():
    """Every path in music.xml resolves to a non-empty file, and nothing is orphaned."""
    root = ElementTree.parse(T.XML_PATH).getroot()
    referenced = set()
    names = []
    for track in root.findall("track"):
        names.append(track.get("name"))
        referenced.add(track.get("path"))

    if len(names) != T.TOTAL_SLOTS:
        record("FAIL", "xml/track-count",
               f"{len(names)} tracks in music.xml, expected {T.TOTAL_SLOTS}")
    if len(set(names)) != len(names):
        record("FAIL", "xml/duplicate-name", "music.xml has a duplicated track name")

    expected = {T.track_name(n) for n in range(1, T.TOTAL_SLOTS + 1)}
    wrong = set(names) - expected
    if wrong:
        record("FAIL", "xml/track-name",
               "names not in the canonical slot list: " + ", ".join(sorted(wrong)))

    for path in sorted(referenced):
        f = T.OGG_DIR / path
        if not f.exists():
            record("FAIL", "ogg/missing", f"{path} referenced by music.xml but not built")
        elif f.stat().st_size == 0:
            record("FAIL", "ogg/empty", f"{path} is zero bytes")

    on_disk = {f.name for f in T.OGG_DIR.glob("*.ogg")}
    orphans = on_disk - referenced
    if orphans:
        record("WARN", "ogg/orphan",
               "built but unreferenced: " + ", ".join(sorted(orphans)))

    return referenced


def check_codec_and_duration(referenced):
    for path in sorted(referenced):
        f = T.OGG_DIR / path
        if not f.exists():
            continue
        info = probe(f)
        codec = info["streams"][0]["codec_name"] if info.get("streams") else None
        if codec != "vorbis":
            record("FAIL", "ogg/codec", f"{path} is {codec!r}, expected 'vorbis'")

    for n in sorted(T.JINGLES):
        f = T.OGG_DIR / T.ogg_name(n)
        if not f.exists():
            continue
        want = T.JINGLES[n]["length"]
        got = float(probe(f)["format"]["duration"])
        if abs(got - want) > DURATION_TOLERANCE:
            record("FAIL", "jingle/duration",
                   f"[{n}] {T.slot_name(n)}: {got:.3f}s, declared {want:.3f}s")


def check_jingle_signal():
    # Compare against the *built* loop, not the raw master: both sides must be past
    # loudness normalisation or the delta just measures the normalisation gain.
    master_rms = {}
    for key in T.used_masters():
        loop = T.OGG_DIR / f"{T.master_slug(key)}.ogg"
        if loop.exists():
            master_rms[key] = rms_db(decode_mono(loop))

    loudness = {}
    for n in sorted(T.JINGLES):
        slot = T.slot_name(n)
        f = T.OGG_DIR / T.ogg_name(n)
        if not f.exists():
            continue

        lufs, peak = ebur128(f)
        loudness[n] = lufs

        if peak == peak and peak > T.TRUE_PEAK_CEILING + 0.2:
            record("FAIL", "jingle/clipping",
                   f"[{n}] {slot}: true peak {peak:+.1f} dBTP > {T.TRUE_PEAK_CEILING}")

        samples = decode_mono(f, sr=8000)
        sr = 8000

        # Onset: the window just after the fade-in must carry signal, otherwise the cut
        # landed in a musical gap and the jingle reads as "nothing played".
        head = samples[int(FADE_IN * sr):int((FADE_IN + 0.2) * sr)]
        if rms_db(head) < -60:
            record("FAIL", "jingle/silent-onset",
                   f"[{n}] {slot}: first 200 ms after the fade-in is silent")

        # Whole-clip level against the source master: catches a cut into a quiet passage.
        key = T.JINGLES[n]["master"]
        if key in master_rms:
            delta = rms_db(samples) - master_rms[key]
            if delta < -DEAD_CLIP_MARGIN:
                record("WARN", "jingle/quiet-cut",
                       f"[{n}] {slot}: {delta:+.1f} dB vs {T.master_slug(key)} average "
                       f"-- cut may have landed in a quiet passage")

        # The fade-out must actually shape the tail: no hard-cut click at the end.
        # Testing for a monotonic decay across the whole fade window is the wrong
        # metric -- a musical swell inside the window can still net-rise early on
        # while the fade is working perfectly. What matters is where it ends up.
        last = rms_db(samples[-int(0.1 * sr):])
        body = rms_db(samples)
        if last > body - TAIL_DROP:
            record("WARN", "jingle/tail-shape",
                   f"[{n}] {slot}: ends at {last:.1f} dB against a clip level of "
                   f"{body:.1f} dB -- only {body - last:.1f} dB down, may click")

    usable = {n: v for n, v in loudness.items() if v == v and v != float("-inf")}
    if len(usable) >= 2:
        lo_n, lo = min(usable.items(), key=lambda kv: kv[1])
        hi_n, hi = max(usable.items(), key=lambda kv: kv[1])
        if hi - lo > 2 * LOUDNESS_SPREAD:
            record("WARN", "jingle/loudness-spread",
                   f"{hi - lo:.1f} LU between [{lo_n}] {T.slot_name(lo_n)} ({lo:.1f}) "
                   f"and [{hi_n}] {T.slot_name(hi_n)} ({hi:.1f})")
        else:
            record("OK", "jingle/loudness-spread", f"{hi - lo:.1f} LU across 22 jingles")
    return loudness


def check_loop_levels():
    """Loops must be consistent with each other and with the vanilla soundtrack.

    Inconsistency here is the most audible failure mode in the whole mod: it changes
    the volume every time the player walks onto a new floor.
    """
    levels = {}
    for key in T.used_masters():
        f = T.OGG_DIR / f"{T.master_slug(key)}.ogg"
        if not f.exists():
            continue
        lufs, peak = ebur128(f)
        if lufs == lufs and lufs != float("-inf"):
            levels[key] = lufs
        if peak == peak and peak > T.TRUE_PEAK_CEILING + 0.2:
            record("FAIL", "loop/clipping",
                   f"{T.master_slug(key)}: true peak {peak:+.1f} dBTP "
                   f"> {T.TRUE_PEAK_CEILING}")

    if len(levels) < 2:
        record("WARN", "loop/loudness", "not enough loops measured")
        return levels

    lo_k, lo = min(levels.items(), key=lambda kv: kv[1])
    hi_k, hi = max(levels.items(), key=lambda kv: kv[1])
    level = "OK" if hi - lo <= 2 * LOUDNESS_SPREAD else "WARN"
    record(level, "loop/loudness-spread",
           f"{hi - lo:.1f} LU across {len(levels)} loops "
           f"({T.master_slug(lo_k)} {lo:.1f} .. {T.master_slug(hi_k)} {hi:.1f})")

    mean = sum(levels.values()) / len(levels)
    delta = mean - VANILLA_LOOP_LUFS
    level = "OK" if abs(delta) <= 2.0 else "WARN"
    record(level, "loop/vs-vanilla",
           f"{mean:.1f} LUFS against vanilla Rebirth {VANILLA_LOOP_LUFS} "
           f"({delta:+.1f} LU)")
    return levels


def check_channel_balance(loop_levels, jingle_loudness):
    """On Repentance+ jingles play on the SFX channel and music on the music channel."""
    loops = list(loop_levels.values())
    usable = [v for v in jingle_loudness.values() if v == v and v != float("-inf")]
    if not loops or not usable:
        record("WARN", "mix/balance", "not enough measurements to compare channels")
        return

    loop_mean = sum(loops) / len(loops)
    jingle_mean = sum(usable) / len(usable)
    on_file = jingle_mean - loop_mean
    vanilla_rel = VANILLA_JINGLE_LUFS - VANILLA_LOOP_LUFS
    level = "OK" if abs(on_file - vanilla_rel) <= 2.0 else "WARN"
    record(level, "mix/file-levels",
           f"loops {loop_mean:.1f} LUFS, jingles {jingle_mean:.1f} LUFS "
           f"({on_file:+.1f} LU; vanilla is {vanilla_rel:+.1f} LU)")

    if not OPTIONS_INI.exists():
        record("WARN", "mix/options", f"{OPTIONS_INI} not found; cannot check sliders")
        return

    # options.ini carries its own [Options] header, so the keys are not at top level.
    # Search every section rather than assuming one, and fail loudly if a key is absent
    # -- silently falling back to a default is how this check missed a muted slider.
    parser = configparser.ConfigParser()
    parser.read_string(OPTIONS_INI.read_text(encoding="utf-8", errors="replace"))

    def option(key):
        for section in parser.sections():
            if parser.has_option(section, key):
                return parser.get(section, key)
        return None

    raw = {k: option(k) for k in ("musicvolume", "sfxvolume", "musicenabled")}
    absent = [k for k, v in raw.items() if v is None]
    if absent:
        record("WARN", "mix/options",
               f"options.ini has no {', '.join(absent)}; cannot check the mix")
        return

    music = float(raw["musicvolume"])
    sfx = float(raw["sfxvolume"])

    if raw["musicenabled"].strip() in ("0", "false"):
        record("FAIL", "mix/music-off",
               "MusicEnabled=0 in options.ini -- music is switched off entirely, so the "
               "mod will be silent until it is turned back on in the game's options")
        return
    if music <= 0:
        record("FAIL", "mix/music-muted",
               f"MusicVolume={music:.2f} in options.ini -- floor music is inaudible, "
               f"so no listening test is meaningful until it is raised")
        return

    delta = (jingle_mean + 20 * math.log10(sfx)) - (loop_mean + 20 * math.log10(music))
    level = "OK" if abs(delta) <= 6 else "WARN"
    record(level, "mix/balance",
           f"MusicVolume={music:.2f} SFXVolume={sfx:.2f} -> jingles land {delta:+.1f} dB "
           f"relative to floor music in game")


def main():
    T.validate()
    if not T.XML_PATH.exists():
        sys.exit("error: mod/content/music.xml not built; run build/build_xml.py first")

    check_metadata()
    referenced = check_xml_references()
    check_codec_and_duration(referenced)
    loop_levels = check_loop_levels()
    loudness = check_jingle_signal()
    check_channel_balance(loop_levels, loudness)

    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]

    # Machine-readable copy so audition.py can flag the affected rows.
    report = {"results": [{"level": lv, "check": ck, "detail": dt}
                          for lv, ck, dt in results]}
    (T.ROOT / "build" / "verify_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    for level, check, detail in results:
        print(f"{level:<4} {check:<24} {detail}")

    print(f"\n{len(fails)} fail, {len(warns)} warn, "
          f"{len(results) - len(fails) - len(warns)} ok")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
