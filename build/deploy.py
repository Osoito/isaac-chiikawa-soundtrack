"""Install the built mod into the game's mods folder.

  python build/deploy.py             # dev build, includes the console test harness
  python build/deploy.py --release   # strips the dev harness
  python build/deploy.py --dry-run   # show what would be copied
  python build/deploy.py --mods-dir "..."   # override auto-detection

Refuses to write over a folder this project did not create, so an existing subscribed
mod of the same name cannot be clobbered by accident.
"""

import argparse
import re
import shutil
import sys
from pathlib import Path
from xml.etree import ElementTree

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tracks as T

MARKER = ".chiikawa-build"

# Files that exist only to make in-game verification possible (spec §7 Layer 3).
DEV_ONLY = {"dev_jingle_test.lua", "dev_slots.lua"}

# The marker is a build artifact; a published mod should not carry one.
RELEASE_EXCLUDES = DEV_ONLY | {MARKER}

STEAM_HINTS = [
    r"HKCU:\Software\Valve\Steam",
]
FALLBACK_LIBRARIES = [
    Path("C:/Program Files (x86)/Steam"),
    Path("D:/Steam"),
    Path("D:/SteamLibrary"),
    Path("D:/softwares/Steam"),
]
GAME_SUBPATH = Path("steamapps/common/The Binding of Isaac Rebirth")


def find_mods_dir():
    candidates = []

    # Steam records its install root in the registry on Windows.
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            candidates.append(Path(winreg.QueryValueEx(k, "SteamPath")[0]))
    except Exception:
        pass
    candidates += FALLBACK_LIBRARIES

    for root in candidates:
        mods = root / GAME_SUBPATH / "mods"
        if mods.is_dir():
            return mods
    return None


def collect(release):
    """Relative paths to copy, in a deterministic order."""
    files = []
    for path in sorted(T.MOD_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(T.MOD_ROOT)
        if release and rel.name in RELEASE_EXCLUDES:
            continue
        files.append(rel)
    return files


# Fields the Steam uploader owns once a mod is published: it assigns <id> on first
# upload and bumps <version> on every upload. Deploying the repo copy over the installed
# one would discard both -- dropping the id makes the next upload create a second,
# unrelated Workshop item, and resetting the version makes the published version number
# go backwards. They are pulled back into the source instead, so neither is something to
# remember.
PUBLISHER_OWNED = ("id", "version")


def read_field(metadata_path, field):
    if not metadata_path.exists():
        return None
    try:
        root = ElementTree.parse(metadata_path).getroot()
    except ElementTree.ParseError:
        return None
    return (root.findtext(field) or "").strip() or None


def preserve_published_fields(target):
    """Carry the uploader's <id> and <version> back into the repo before overwriting."""
    source = T.MOD_ROOT / "metadata.xml"
    # newline="" both ways: this function patches two fields, so it has no business
    # rewriting the file's line endings. The uploader writes a mix of CRLF and LF and
    # text mode would silently normalise all of them, leaving a permanent diff.
    with open(source, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    pulled = {}

    for field in PUBLISHER_OWNED:
        installed = read_field(target / "metadata.xml", field)
        if not installed or read_field(source, field) == installed:
            continue
        pattern = rf"<{field}>[^<]*</{field}>"
        replacement = f"<{field}>{installed}</{field}>"
        if re.search(pattern, text):
            text = re.sub(pattern, replacement, text, count=1)
        else:
            # <id> is absent until the first upload. Insert it where the uploader and
            # published mods put it -- directly after <directory> -- so the repo copy
            # and the installed copy do not differ by element order forever after.
            text = re.sub(r"(</directory>)", rf"\1\n    {replacement}", text, count=1)
        pulled[field] = installed

    if pulled:
        with open(source, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    return pulled


def mod_name(metadata_path):
    if not metadata_path.exists():
        return None
    try:
        return (ElementTree.parse(metadata_path).getroot().findtext("name") or "").strip()
    except ElementTree.ParseError:
        return None


def is_ours(target):
    """A release build carries no marker, so fall back to matching the mod's name.

    Without this, redeploying over our own release build would be refused as if it
    were somebody else's subscribed mod.
    """
    if (target / MARKER).exists():
        return True
    installed = mod_name(target / "metadata.xml")
    return installed is not None and installed == mod_name(T.MOD_ROOT / "metadata.xml")


def preflight(files):
    """Fail loudly rather than installing a mod that will silently misbehave."""
    problems = []
    if not (T.MOD_ROOT / "metadata.xml").exists():
        problems.append("mod/metadata.xml is missing")
    if not T.XML_PATH.exists():
        problems.append("mod/content/music.xml is missing; run build/build_xml.py")

    oggs = [f for f in files if f.suffix == ".ogg"]
    if not oggs:
        problems.append("no ogg files; run build/build_audio.py")

    expected = {T.ogg_name(n) for n in range(1, T.TOTAL_SLOTS + 1)}
    present = {f.name for f in oggs}
    missing = expected - present
    if missing:
        problems.append(f"{len(missing)} ogg files referenced by music.xml are missing: "
                        + ", ".join(sorted(missing)[:5]))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", action="store_true",
                    help="exclude the dev console harness")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mods-dir", type=Path, default=None)
    ap.add_argument("--force", action="store_true",
                    help="overwrite a target folder this project did not create")
    args = ap.parse_args()

    T.validate()

    mods = args.mods_dir or find_mods_dir()
    if mods is None:
        sys.exit("error: could not find the Isaac mods folder; pass --mods-dir")
    if not mods.is_dir():
        sys.exit(f"error: not a directory: {mods}")

    files = collect(args.release)
    problems = preflight(files)
    if problems:
        sys.exit("error: " + "\n       ".join(problems))

    target = mods / T.MOD_DIR_NAME
    if target.exists() and not is_ours(target) and not args.force:
        sys.exit(f"error: {target} exists but was not created by this project.\n"
                 f"       Refusing to overwrite it. Pass --force if that is intended.")

    pulled = None
    if target.exists() and not args.dry_run:
        pulled = preserve_published_fields(target)
        for field, value in pulled.items():
            print(f"pulled <{field}> {value} back into mod/metadata.xml")

    total = sum((T.MOD_ROOT / f).stat().st_size for f in files)
    kind = "release" if args.release else "dev"
    print(f"{kind} build -> {target}")
    print(f"{len(files)} files, {total / 1024 / 1024:.1f} MB")

    if args.dry_run:
        for f in files:
            print(f"  {f.as_posix()}")
        return

    if target.exists():
        shutil.rmtree(target)
    for rel in files:
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(T.MOD_ROOT / rel, dst)
    if not args.release:
        (target / MARKER).write_text(
            "Created by IssacChiikawaMusicMod/build/deploy.py. "
            "Safe to delete with the mod.\n", encoding="utf-8")

    print("installed")
    if not args.release:
        print("dev harness active: chiikawa_check | chiikawa_jingle all | "
              "chiikawa_music <slot>")


if __name__ == "__main__":
    main()
