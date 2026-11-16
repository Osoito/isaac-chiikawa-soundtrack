"""ffmpeg/ffprobe discovery and small audio-analysis helpers shared by the build scripts."""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

_WINGET_FF = (
    Path.home()
    / "AppData/Local/Microsoft/WinGet/Packages"
    / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "ffmpeg-7.1-full_build/bin"
)


def _find(name):
    found = shutil.which(name)
    if found:
        return found
    candidate = _WINGET_FF / f"{name}.exe"
    if candidate.exists():
        return str(candidate)
    sys.exit(f"error: {name} not found on PATH or at {candidate}")


FFMPEG = _find("ffmpeg")
FFPROBE = _find("ffprobe")


def run(args, **kw):
    """Run a command, raising with captured stderr on failure."""
    proc = subprocess.run(args, capture_output=True, **kw)
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace")[-2000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {args[0]}\n{tail}")
    return proc


def ffmpeg(*args):
    return run([FFMPEG, "-hide_banner", "-v", "error", "-y", *args])


def probe(path):
    """Return the ffprobe JSON for the first audio stream plus format info."""
    proc = run([
        FFPROBE, "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels:format=duration,size",
        "-of", "json", str(path),
    ])
    return json.loads(proc.stdout.decode("utf-8"))


def duration(path):
    return float(probe(path)["format"]["duration"])


def ebur128(path):
    """Return (integrated LUFS, true peak dBTP). NaN when ffmpeg cannot measure."""
    proc = run([FFMPEG, "-hide_banner", "-nostats", "-i", str(path),
                "-af", "ebur128=peak=true", "-f", "null", "-"])
    text = proc.stderr.decode("utf-8", "replace")
    tail = text[text.rfind("Summary:"):] if "Summary:" in text else text
    lufs = re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", tail)
    peak = re.search(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", tail)

    def num(m):
        if not m:
            return float("nan")
        return float("-inf") if m.group(1) == "-inf" else float(m.group(1))

    return num(lufs), num(peak)


def decode_mono(path, sr=8000):
    """Decode to a mono float32 numpy array at `sr` Hz. Used for envelope analysis only."""
    proc = run([
        FFMPEG, "-hide_banner", "-v", "error",
        "-i", str(path),
        "-map", "a:0", "-ac", "1", "-ar", str(sr),
        "-f", "f32le", "-",
    ])
    return np.frombuffer(proc.stdout, dtype="<f4")


def rms_envelope(samples, sr, hop_s=0.02):
    """Short-term RMS per hop. Returns (envelope, hop_s)."""
    hop = max(1, int(sr * hop_s))
    n = len(samples) // hop
    if n == 0:
        return np.zeros(1, dtype="f8"), hop_s
    frames = samples[: n * hop].reshape(n, hop).astype("f8")
    return np.sqrt((frames ** 2).mean(axis=1)), hop_s


def window_energy(env, win_hops):
    """Mean envelope value over a sliding window of `win_hops`, aligned to window start.

    Returns an array of length len(env) - win_hops + 1 (empty if the window doesn't fit).
    """
    if win_hops <= 0 or win_hops > len(env):
        return np.zeros(0, dtype="f8")
    csum = np.concatenate([[0.0], np.cumsum(env)])
    return (csum[win_hops:] - csum[:-win_hops]) / win_hops
