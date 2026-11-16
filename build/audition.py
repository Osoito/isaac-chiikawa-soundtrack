"""Layer 2: build the jingle audition page.

  python build/audition.py

Emits a self-contained HTML page with every jingle embedded, each shown against a
waveform of the master it was cut from. Listening here and adjusting a `start` value in
tracks.py is the iteration loop; the game is only for final acceptance.
"""

import argparse
import base64
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tracks as T
from ffio import decode_mono, duration, ffmpeg, rms_envelope

CACHE = T.ROOT / "build" / ".cache"
OUT = T.ROOT / "build" / "audition.html"

CONTEXT_PAD = 4.0      # seconds of master heard either side of the cut
CONTEXT_QUALITY = "1"  # lower than the shipped clips; this is for orientation only
WAVE_POINTS = 460


def b64(path, mime="audio/ogg"):
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def waveform(wav, points=WAVE_POINTS):
    """Normalised 0..1 envelope resampled to a fixed number of points."""
    samples = decode_mono(wav, sr=8000)
    env, _ = rms_envelope(samples, 8000, hop_s=0.02)
    if len(env) < points:
        env = np.pad(env, (0, points - len(env)))
    idx = np.linspace(0, len(env), points + 1).astype(int)
    coarse = np.array([env[a:b].max() if b > a else 0.0
                       for a, b in zip(idx[:-1], idx[1:])])
    peak = coarse.max()
    return coarse / peak if peak > 0 else coarse


def wave_svg(env, total, start, length, ctx_start, ctx_end):
    """Mirrored waveform with the cut window marked, in a 0..1000 x 0..100 viewBox."""
    n = len(env)
    step = 1000 / n
    bars = []
    for i, v in enumerate(env):
        h = max(1.2, v * 46)
        x = i * step
        bars.append(f'<rect x="{x:.2f}" y="{50 - h:.2f}" width="{step * 0.72:.2f}" '
                    f'height="{h * 2:.2f}" rx="{min(step * 0.36, 0.9):.2f}"/>')

    def px(t):
        return max(0.0, min(1000.0, t / total * 1000)) if total > 0 else 0.0

    cx, cw = px(ctx_start), px(ctx_end) - px(ctx_start)
    hx, hw = px(start), px(start + length) - px(start)
    return (
        f'<svg class="wave" viewBox="0 0 1000 100" preserveAspectRatio="none" '
        f'aria-hidden="true">'
        f'<rect class="ctx" x="{cx:.2f}" y="0" width="{cw:.2f}" height="100"/>'
        f'<rect class="cut" x="{hx:.2f}" y="0" width="{hw:.2f}" height="100"/>'
        f'<g class="bars">{"".join(bars)}</g>'
        f'<line class="head" x1="0" y1="0" x2="0" y2="100"/>'
        f'</svg>'
    )


def build_context(n, wav, start, length, total):
    """Cut a padded excerpt so the ear can judge where the clip begins and ends."""
    a = max(0.0, start - CONTEXT_PAD)
    b = min(total, start + length + CONTEXT_PAD)
    out = CACHE / f"ctx_{T.jingle_slug(n)}.ogg"
    ffmpeg("-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(wav), "-map", "a:0",
           "-c:a", "libvorbis", "-q:a", CONTEXT_QUALITY, str(out))
    return out, a, b


def load_flags():
    """slot number -> [warning text], from verify.py's report."""
    path = T.ROOT / "build" / "verify_report.json"
    flags = {}
    if not path.exists():
        return flags
    for row in json.loads(path.read_text(encoding="utf-8"))["results"]:
        if row["level"] not in ("WARN", "FAIL"):
            continue
        m = re.match(r"\[(\d+)\]\s*(.*)", row["detail"])
        if m:
            flags.setdefault(int(m.group(1)), []).append(
                (row["level"], row["check"].split("/")[-1], m.group(2)))
    return flags


def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# --------------------------------------------------------------------------------------

CSS = """
:root {
  --ground:#F1F2EC; --surface:#FBFBF7; --sunken:#E6E8DE;
  --ink:#22241E; --muted:#6C6F62; --line:#D6D9CC;
  --accent:#3F7D5A; --accent-soft:#3F7D5A26; --ctx:#8C907E1F;
  --flag:#A85B27; --flag-soft:#A85B2718;
  --shadow:0 1px 2px #22241E0F, 0 8px 24px #22241E0A;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:#161814; --surface:#1E211B; --sunken:#12140F;
    --ink:#E7E8DF; --muted:#9CA08F; --line:#333729;
    --accent:#79C295; --accent-soft:#79C29524; --ctx:#9CA08F14;
    --flag:#D98B4E; --flag-soft:#D98B4E1A;
    --shadow:0 1px 2px #0006, 0 8px 24px #0004;
  }
}
:root[data-theme="dark"] {
  --ground:#161814; --surface:#1E211B; --sunken:#12140F;
  --ink:#E7E8DF; --muted:#9CA08F; --line:#333729;
  --accent:#79C295; --accent-soft:#79C29524; --ctx:#9CA08F14;
  --flag:#D98B4E; --flag-soft:#D98B4E1A;
  --shadow:0 1px 2px #0006, 0 8px 24px #0004;
}

* { box-sizing:border-box; }
body {
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"IBM Plex Sans","Segoe UI",system-ui,sans-serif;
  font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
.page { max-width:1080px; margin:0 auto; padding:40px 24px 80px; }

header { margin-bottom:28px; }
h1 {
  font-family:"Familjen Grotesk","IBM Plex Sans",sans-serif;
  font-size:clamp(28px,4vw,40px); font-weight:700; letter-spacing:-.02em;
  margin:0 0 6px; text-wrap:balance;
}
.lede { color:var(--muted); max-width:64ch; margin:0 0 20px; }
.lede code {
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:.9em;
  background:var(--sunken); padding:1px 5px; border-radius:4px;
}

.stats { display:flex; flex-wrap:wrap; gap:10px; }
.stat {
  background:var(--surface); border:1px solid var(--line); border-radius:8px;
  padding:8px 14px; display:flex; gap:10px; align-items:baseline;
}
.stat b {
  font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums; font-size:17px; font-weight:600;
}
.stat span { color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; }

.rows { display:flex; flex-direction:column; gap:12px; margin-top:28px; }

.row {
  background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:14px 16px 12px; box-shadow:var(--shadow);
  display:grid; grid-template-columns:auto 1fr auto; gap:4px 16px;
  align-items:center;
}
.row.flagged { border-color:var(--flag); background:linear-gradient(var(--flag-soft),var(--flag-soft)) var(--surface); }
.row.playing { border-color:var(--accent); }

.slot {
  grid-row:1/3; align-self:start;
  font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums; font-size:20px; font-weight:600;
  color:var(--accent); min-width:2.4ch; text-align:right; padding-top:1px;
}
.name { font-weight:600; letter-spacing:-.01em; }
.zh { color:var(--muted); font-size:13.5px; }
.meta {
  grid-row:1/3; align-self:start; text-align:right;
  font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums; font-size:12px; color:var(--muted);
  white-space:nowrap; line-height:1.7;
}
.meta b { color:var(--ink); font-weight:600; }

.strip { grid-column:1/-1; margin-top:10px; display:flex; gap:12px; align-items:center; }
.controls { display:flex; gap:6px; flex-shrink:0; }
button {
  font:inherit; font-size:12.5px; font-weight:600;
  color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:6px;
  padding:6px 11px; cursor:pointer; white-space:nowrap;
  display:flex; align-items:center; gap:6px;
}
button:hover { border-color:var(--accent); color:var(--accent); }
button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
button[aria-pressed="true"] { background:var(--accent); border-color:var(--accent); color:var(--surface); }
button .gl { font-size:9px; line-height:1; }

.wavebox {
  flex:1; height:56px; background:var(--sunken);
  border:1px solid var(--line); border-radius:6px; overflow:hidden; position:relative;
}
.wave { display:block; width:100%; height:100%; }
.wave .bars rect { fill:var(--muted); opacity:.5; }
.wave .ctx { fill:var(--ctx); }
.wave .cut { fill:var(--accent-soft); }
.wave .head { stroke:var(--accent); stroke-width:3; opacity:0; }
.row.playing .wave .head { opacity:1; }

.flag {
  grid-column:1/-1; margin-top:9px; padding-top:9px; border-top:1px solid var(--line);
  color:var(--flag); font-size:12.5px; display:flex; gap:8px; align-items:baseline;
}
.flag code {
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:11px;
  text-transform:uppercase; letter-spacing:.06em; flex-shrink:0;
}

footer { margin-top:36px; color:var(--muted); font-size:13px; max-width:64ch; }
footer code {
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:.9em;
  background:var(--sunken); padding:1px 5px; border-radius:4px;
}

@media (max-width:720px) {
  .row { grid-template-columns:auto 1fr; }
  .meta { grid-row:3; grid-column:1/-1; text-align:left; }
  .strip { flex-direction:column; align-items:stretch; }
}
@media (prefers-reduced-motion:reduce) { * { transition:none !important; } }
"""

JS = """
(function () {
  var rows = Array.prototype.slice.call(document.querySelectorAll('.row'));
  var current = null;

  function stop() {
    if (!current) return;
    current.audio.pause();
    current.audio.currentTime = 0;
    current.row.classList.remove('playing');
    current.btn.setAttribute('aria-pressed', 'false');
    cancelAnimationFrame(current.raf);
    current = null;
  }

  function play(row, btn, src, from, span, total) {
    var wasSame = current && current.btn === btn;
    stop();
    if (wasSame) return;

    var audio = new Audio(src);
    var head = row.querySelector('.head');
    var state = { row: row, btn: btn, audio: audio, raf: 0 };
    current = state;

    row.classList.add('playing');
    btn.setAttribute('aria-pressed', 'true');

    function tick() {
      var x = (from + audio.currentTime) / total * 1000;
      head.setAttribute('x1', x);
      head.setAttribute('x2', x);
      state.raf = requestAnimationFrame(tick);
    }
    audio.addEventListener('ended', stop);
    audio.play().then(tick, function () { stop(); });
  }

  rows.forEach(function (row) {
    var total = parseFloat(row.dataset.total);
    row.querySelectorAll('button[data-src]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        play(row, btn, btn.dataset.src,
             parseFloat(btn.dataset.from), parseFloat(btn.dataset.span), total);
      });
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') stop();
  });
})();
"""


def page(title, heading, lede, stats, rows, footer):
    stat_html = "".join(
        f'<div class="stat"><b>{esc(str(v))}</b><span>{esc(k)}</span></div>'
        for k, v in stats)
    return f"""<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@500;700&family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>

<div class="page">
  <header>
    <h1>{esc(heading)}</h1>
    <p class="lede">{lede}</p>
    <div class="stats">{stat_html}</div>
  </header>

  <main class="rows">{''.join(rows)}
  </main>

  <footer>{footer}</footer>
</div>

<script>{JS}</script>
"""


def candidates_page(slot, count=6):
    """Alternative windows for one jingle, so a cut can be chosen by ear rather than
    guessed at. Uses phrase-boundary detection, not the RMS heuristic that picks the
    shipped cuts -- the whole point is to get starts and ends that sit on a musical
    seam."""
    import build_audio as B

    cuts = json.loads(T.CUT_POINTS_PATH.read_text(encoding="utf-8"))
    meta = cuts.pop("_meta", {})
    target = meta.get("jingle_target_lufs", -22.0)

    key = T.JINGLES[slot]["master"]
    wav = CACHE / f"{T.master_slug(key)}.wav"
    total = duration(wav)
    env = waveform(wav)

    # Everything else cut from this master is off limits, or the jingles overlap.
    avoid = [(cuts[str(n)]["start"], cuts[str(n)]["start"] + cuts[str(n)]["length"])
             for n in T.JINGLES if n != slot and T.JINGLES[n]["master"] == key
             and str(n) in cuts]

    current = cuts.get(str(slot))
    options = []
    if current:
        options.append(("current", current["start"], current["length"]))
    for i, (start, length, _) in enumerate(
            B.phrase_windows(wav, 2.5, 6.0, count, avoid=avoid)):
        options.append((chr(ord("A") + i), start, length))

    rows = []
    for label, start, length in options:
        tag = f"cand_{slot}_{label}"
        clip = CACHE / f"{tag}.ogg"
        B.render_clip(wav, start, length, clip, target, tag=tag)
        ctx, ctx_a, ctx_b = build_context_at(tag, wav, start, length, total)
        svg = wave_svg(env, total, start, length, ctx_a, ctx_b)
        is_current = label == "current"
        rows.append(f"""
      <article class="row{' flagged' if is_current else ''}" data-total="{total}">
        <div class="slot">{esc(label if not is_current else '=')}</div>
        <div class="name">{'What is shipping now' if is_current
                           else f'Option {label}'}</div>
        <div class="meta">
          <b>start={start:.2f}</b><br>
          {mmss(start)} &ndash; {mmss(start + length)}<br>
          length {length:g}s
        </div>
        <div class="zh">{'当前版本，供对照' if is_current
                         else '起止都落在乐句边界上'}</div>
        <div class="strip">
          <div class="controls">
            <button data-src="{b64(clip)}" data-from="{start}" data-span="{length}"
                    aria-pressed="false">
              <span class="gl">&#9654;</span>clip {length:g}s</button>
            <button data-src="{b64(ctx)}" data-from="{ctx_a}"
                    data-span="{ctx_b - ctx_a:.3f}" aria-pressed="false">
              <span class="gl">&#9654;</span>context</button>
          </div>
          <div class="wavebox">{svg}</div>
        </div>
      </article>""")

    name = T.slot_name(slot)
    html = page(
        title=f"Slot {slot} Cut Options",
        heading=f"Slot {slot} — {name}",
        lede=f"Alternative windows in <code>{esc(T.master_slug(key))}</code>, each "
             f"starting on the rise out of an energy dip and ending at the next one, "
             f"so the clip has a beginning and an end instead of landing mid-phrase. "
             f"The orange row is what ships today. Reply with the letter you want.",
        stats=[("options", len(options) - (1 if current else 0)),
               ("source", T.master_slug(key)),
               ("master", f"{total:.1f}s")],
        rows=rows,
        footer=f"Chosen by phrase-boundary detection "
               f"(<code>build_audio.phrase_windows</code>), not the RMS heuristic that "
               f"picked the shipped cuts. To apply one, its <code>start</code> and "
               f"<code>length</code> go into <code>JINGLES[{slot}]</code> in "
               f"<code>build/tracks.py</code>. Press <code>Esc</code> to stop playback.")

    out = T.ROOT / "build" / f"candidates_{slot}.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out.relative_to(T.ROOT)} "
          f"({out.stat().st_size / 1024 / 1024:.1f} MB, {len(options)} options)")


def build_context_at(tag, wav, start, length, total):
    a = max(0.0, start - CONTEXT_PAD)
    b = min(total, start + length + CONTEXT_PAD)
    out = CACHE / f"ctx_{tag}.ogg"
    ffmpeg("-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(wav), "-map", "a:0",
           "-c:a", "libvorbis", "-q:a", CONTEXT_QUALITY, str(out))
    return out, a, b


def main():
    T.validate()
    if not T.CUT_POINTS_PATH.exists():
        sys.exit("error: run build/build_audio.py first")

    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=int, metavar="SLOT",
                    help="build a page of alternative cuts for one jingle slot")
    args = ap.parse_args()
    if args.candidates:
        if args.candidates not in T.JINGLES:
            sys.exit(f"error: slot {args.candidates} is not a jingle")
        return candidates_page(args.candidates)

    cuts = json.loads(T.CUT_POINTS_PATH.read_text(encoding="utf-8"))
    meta = cuts.pop("_meta", {})
    flags = load_flags()
    waves = {}

    rows = []
    for n in sorted(T.JINGLES):
        cut = cuts[str(n)]
        key = cut["master"]
        wav = CACHE / f"{T.master_slug(key)}.wav"
        total = cut["master_duration"]
        start, length = cut["start"], cut["length"]

        if key not in waves:
            waves[key] = waveform(wav)

        ctx_file, ctx_a, ctx_b = build_context(n, wav, start, length, total)
        clip = T.OGG_DIR / T.ogg_name(n)

        svg = wave_svg(waves[key], total, start, length, ctx_a, ctx_b)
        flag_html = ""
        for level, check, text in flags.get(n, []):
            flag_html += (f'<div class="flag"><code>{esc(check)}</code>'
                          f'<span>{esc(text)}</span></div>')

        rows.append(f"""
      <article class="row{' flagged' if n in flags else ''}" data-total="{total}">
        <div class="slot">{n}</div>
        <div class="name">{esc(T.slot_name(n))}</div>
        <div class="meta">
          <b>{esc(T.master_slug(key))}</b><br>
          {mmss(start)} &ndash; {mmss(start + length)}<br>
          of {mmss(total)}
        </div>
        <div class="zh">{esc(T.JINGLES[n]['zh'])} &middot; {esc(T.JINGLES[n]['trigger'])}</div>
        <div class="strip">
          <div class="controls">
            <button data-src="{b64(clip)}" data-from="{start}" data-span="{length}"
                    aria-pressed="false">
              <span class="gl">&#9654;</span>clip {length:g}s</button>
            <button data-src="{b64(ctx_file)}" data-from="{ctx_a}"
                    data-span="{ctx_b - ctx_a:.3f}" aria-pressed="false">
              <span class="gl">&#9654;</span>context</button>
          </div>
          <div class="wavebox">{svg}</div>
        </div>
        {flag_html}
      </article>""")

    flagged = len(flags)
    html = f"""<title>Chiikawa Jingle Cuts</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@500;700&family=IBM+Plex+Mono:wght@500;600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style>

<div class="page">
  <header>
    <h1>Chiikawa Jingle Cuts</h1>
    <p class="lede">Twenty-two one-shot stings, each cut automatically from the loudest
    phrase of its source track. Play the clip, then play the context to hear the four
    seconds either side of it. The green band marks where the cut sits in the master.
    To move one, quote its number and where it should go.</p>
    <div class="stats">
      <div class="stat"><b>{len(T.JINGLES)}</b><span>jingles</span></div>
      <div class="stat"><b>{len(T.jingles_by_master())}</b><span>source tracks</span></div>
      <div class="stat"><b>{flagged}</b><span>flagged</span></div>
      <div class="stat"><b>{meta.get("jingle_target_lufs", "?")}</b><span>LUFS target</span></div>
    </div>
  </header>

  <main class="rows">{''.join(rows)}
  </main>

  <footer>
    Cut points live in <code>build/tracks.py</code> as the <code>start</code> field of
    each jingle; <code>null</code> means the offset was chosen automatically. Changing
    one and running <code>python build/build_audio.py --jingles</code> rebuilds only the
    clips. Press <code>Esc</code> to stop playback.
  </footer>
</div>

<script>{JS}</script>
"""

    OUT.write_text(html, encoding="utf-8")
    size = OUT.stat().st_size / 1024 / 1024
    print(f"wrote {OUT.relative_to(T.ROOT)} ({size:.1f} MB, "
          f"{len(T.JINGLES)} clips, {flagged} flagged)")


if __name__ == "__main__":
    main()
