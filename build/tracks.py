"""Single source of truth for the Chiikawa soundtrack mod.

Pure data plus validation. No file or process I/O lives here, so the mapping can be
edited and checked without touching audio.

See docs/design.md
"""

from pathlib import Path

SOUNDTRACK = "Chiikawa"
MOD_DIR_NAME = "chiikawa soundtrack"

ROOT = Path(__file__).resolve().parent.parent
MASTER_DIR = ROOT / "audio_master"
MOD_ROOT = ROOT / "mod"
OGG_SUBDIR = f"music/{SOUNDTRACK}/"
OGG_DIR = MOD_ROOT / "resources" / "music" / SOUNDTRACK
XML_PATH = MOD_ROOT / "content" / "music.xml"
CUT_POINTS_PATH = ROOT / "build" / "cut_points.json"

VORBIS_QUALITY = "5"

# --------------------------------------------------------------------------------------
# Loudness targets
# --------------------------------------------------------------------------------------
# The masters were ripped from video at wildly different mix levels -- as built from raw
# cuts they span 15.4 LU, so walking from one floor to the next audibly changes volume.
# Everything is therefore normalised to a target anchored on the game's own soundtrack.
#
# Reference, measured with ebur128 over the vanilla Rebirth oggs that Soundtrack Menu
# bundles (mods/musicpicker_1933285222/resources/music/Rebirth/):
#   12 floor and boss loops: mean -11.6 LUFS, spread 9.6 LU, true peaks up to +2.6 dBTP
#    5 jingles:              mean -14.5 LUFS
# Vanilla jingles sit about 3 LU *below* its loops; matching that relationship keeps the
# mod from feeling louder or quieter than the soundtrack it sits next to in the menu.

VANILLA_LOOP_LUFS = -11.6
VANILLA_JINGLE_LUFS = -14.5
JINGLE_OFFSET_LU = VANILLA_JINGLE_LUFS - VANILLA_LOOP_LUFS   # -2.9

# Vanilla routinely exceeds 0 dBTP; we stay under it rather than copy that.
TRUE_PEAK_CEILING = -1.0

# Reaching vanilla's level is not achievable here without damage. The masters are
# dynamic anime BGM sitting around -22 LUFS; vanilla is a heavily limited -11.6 LUFS
# master. Pushing ours that far needs ~10 dB of limiting on the peakiest tracks, which
# audibly squashes them. So the target is derived from the material instead: the loudest
# level every track can reach while the limiter does no more than LIMIT_BUDGET_DB of
# work. Consistency between floors is what actually matters; absolute level is one
# in-game slider away.
LIMIT_BUDGET_DB = 3.0
LOUDNESS_CAP_LUFS = VANILLA_LOOP_LUFS   # never aim louder than the game's own music

# Per-master target override in LUFS, for when the derived target is wrong for one
# track. `verify.py` reports each track's final level and limiting.
LOUDNESS_OVERRIDE = {}

# --------------------------------------------------------------------------------------
# Source masters
# --------------------------------------------------------------------------------------
# key -> (master filename in audio_master/, output slug, character note)

MASTERS = {
    "A": ("地下室层.flac", "basement", "bright, everyday"),
    "B": ("燃烧层.flac", "burning", "short, agitated"),
    "C": ("水下层.flac", "underwater", "aquatic"),
    "D": ("子宫.flac", "womb", "organic"),
    "E": ("阴间.flac", "sheol", "short, dark"),
    "F": ("商店.flac", "shop", "light, cheerful"),
    "G": ("游戏房.flac", "arcade", "upbeat"),
    "H": ("宝藏房.flac", "treasure", "mysterious"),
    "I": ("矿井层.flac", "mines", "subterranean"),
    "J": ("陵墓层.flac", "mausoleum", "somber"),
    "K": ("家层和卧室.flac", "home", "warm, home"),
    "L": ("塞壬boss曲.flac", "boss_siren", "combat"),
    "M": ("精神错乱.flac", "delirium", "chaotic"),
    "N": ("超级撒旦.flac", "mega_satan", "heavy combat"),
    "O": ("祸兽.flac", "beast", "final battle"),
    "P": ("见证者.flac", "witness", "combat"),
}


def master_path(key):
    return MASTER_DIR / MASTERS[key][0]


def master_slug(key):
    return MASTERS[key][1]


# --------------------------------------------------------------------------------------
# The 85 controllable slots
# --------------------------------------------------------------------------------------
# Copied verbatim from musicpicker_1933285222/soundtrackmenu.lua: the `tracktypes` table
# (entries 1-50) followed by the REPENTANCE-only table.insert calls (entries 51-85).
# Soundtrack Menu resolves a mod's track as Isaac.GetMusicIdByName(SOUNDTRACK .. " " ..
# tracktypes[j]), so these strings must match byte for byte.

SLOT_NAMES = [
    "Basement",                                     # 1
    "Cellar",                                       # 2
    "Burning Basement",                             # 3
    "Caves",                                        # 4
    "Catacombs",                                    # 5
    "Flooded Caves",                                # 6
    "Depths",                                       # 7
    "Necropolis",                                   # 8
    "Dank Depths",                                  # 9
    "Womb/Utero",                                   # 10
    "Scarred Womb",                                 # 11
    "Blue Womb",                                    # 12
    "Sheol",                                        # 13
    "Cathedral",                                    # 14
    "Dark Room",                                    # 15
    "Chest",                                        # 16
    "Void",                                         # 17
    "Library Room",                                 # 18
    "Devil Room appear (jingle)",                   # 19
    "Devil Room",                                   # 20
    "Holy Room Find (jingle)",                      # 21
    "Angel Room",                                   # 22
    "Shop Room",                                    # 23
    "Arcade Room",                                  # 24
    "Secret Room Find (jingle)",                    # 25
    "Secret Room",                                  # 26
    "Treasure Room Entry (jingle) 1",               # 27
    "Treasure Room Entry (jingle) 2",               # 28
    "Treasure Room Entry (jingle) 3",               # 29
    "Treasure Room Entry (jingle) 4",               # 30
    "Boss Room (empty)",                            # 31
    "Challenge Room Entry (jingle)",                # 32
    "Challenge Room (fight)",                       # 33
    "Challenge Room Outro (jingle)",                # 34
    "Boss (jingle)",                                # 35
    "Boss",                                         # 36
    "Boss (alternate)",                             # 37
    "Boss (Depths - Mom)",                          # 38
    "Boss (Womb - Mom's Heart)",                    # 39
    "Boss (Cathedral - Isaac)",                     # 40
    "Boss (Sheol - Satan)",                         # 41
    "Boss (Dark Room)",                             # 42
    "Boss (Chest - ???)",                           # 43
    "Boss (Blue Womb - Hush)",                      # 44
    "Boss (Ultra Greed)",                           # 45
    "Boss (Void)",                                  # 46
    "Boss Death (jingle)",                          # 47
    "Boss Death Alternate (jingle)",                # 48
    "Boss Hush Death (jingle)",                     # 49
    "Boss (Mega Satan)",                            # 50
    "Utero",                                        # 51
    "Downpour",                                     # 52
    "Dross",                                        # 53
    "Mines",                                        # 54
    "Ashpit",                                       # 55
    "Mausoleum",                                    # 56
    "Gehenna",                                      # 57
    "Corpse",                                       # 58
    "Home",                                         # 59
    "Abandoned Mineshaft",                          # 60
    "Mineshaft Escape",                             # 61
    "Planetarium",                                  # 62
    "Secret Room Alt",                              # 63
    "Secret Room Alt Alt",                          # 64
    "Boss Rush",                                    # 65
    "Boss Rush (jingle)",                           # 66
    "Boss Room (empty, twisted)",                   # 67
    "Mom's Shadow Intro",                           # 68
    "Strange Door (jingle)",                        # 69
    "Echoes Reverse",                               # 70
    "Boss (alternate alternate)",                   # 71
    "Boss (Mother)",                                # 72
    "Dogma Intro",                                  # 73
    "Boss (Dogma)",                                 # 74
    "Boss (Beast)",                                 # 75
    "Boss Death Alternate Alternate (jingle)",      # 76
    "Boss Mother Death (jingle)",                   # 77
    "Boss Dogma Death (jingle)",                    # 78
    "Boss Beast Death (jingle)",                    # 79
    "Downpour (reversed)",                          # 80
    "Dross (reversed)",                             # 81
    "Genesis (reversed)",                           # 82
    "Game Over (jingle)",                           # 83
    "Game Over",                                    # 84
    "Boss (Hush Phase 1)",                          # 85
]

TOTAL_SLOTS = 85


def slot_name(n):
    """1-indexed slot number -> canonical Soundtrack Menu track type name."""
    return SLOT_NAMES[n - 1]


def track_name(n):
    """1-indexed slot number -> the name written into music.xml."""
    return f"{SOUNDTRACK} {slot_name(n)}"


# --------------------------------------------------------------------------------------
# Loop slots: slot number -> master key
# --------------------------------------------------------------------------------------

LOOPS = {
    1: "A",   # Basement
    2: "A",   # Cellar
    3: "B",   # Burning Basement
    4: "I",   # Caves
    5: "I",   # Catacombs
    6: "C",   # Flooded Caves
    7: "J",   # Depths
    8: "J",   # Necropolis
    9: "J",   # Dank Depths
    10: "D",  # Womb/Utero
    11: "D",  # Scarred Womb
    12: "E",  # Blue Womb
    13: "E",  # Sheol
    14: "K",  # Cathedral
    15: "E",  # Dark Room
    16: "K",  # Chest
    # The Void floor must not share a master with the Delirium fight that happens on
    # it, or its ordinary rooms play boss music. This was the only floor/boss pair in
    # the mapping that collided; the other twelve were already distinct.
    17: "O",  # Void
    18: "H",  # Library Room          <- user-fixed
    20: "E",  # Devil Room
    22: "K",  # Angel Room
    23: "F",  # Shop Room
    24: "G",  # Arcade Room
    26: "H",  # Secret Room
    31: "K",  # Boss Room (empty)
    33: "L",  # Challenge Room (fight)
    36: "L",  # Boss                  <- user-fixed
    37: "P",  # Boss (alternate)
    38: "N",  # Boss (Depths - Mom)
    39: "N",  # Boss (Womb - Mom's Heart)
    40: "P",  # Boss (Cathedral - Isaac)
    41: "N",  # Boss (Sheol - Satan)
    42: "N",  # Boss (Dark Room) = The Lamb
    43: "P",  # Boss (Chest - ???)
    44: "P",  # Boss (Blue Womb - Hush)   <- user-fixed
    45: "M",  # Boss (Ultra Greed)
    # `beast` is the longest master by a wide margin and was carrying a single slot.
    # Delirium and the Beast are endgame bosses on different run paths, so sharing it
    # is not audible in one playthrough.
    46: "M",  # Boss (Void) = Delirium
    50: "N",  # Boss (Mega Satan)
    51: "D",  # Utero
    52: "C",  # Downpour
    53: "C",  # Dross
    54: "I",  # Mines
    55: "I",  # Ashpit
    56: "J",  # Mausoleum
    57: "J",  # Gehenna
    58: "C",  # Corpse
    59: "K",  # Home
    60: "H",  # Abandoned Mineshaft
    61: "M",  # Mineshaft Escape
    62: "H",  # Planetarium           <- user-fixed
    63: "H",  # Secret Room Alt
    64: "H",  # Secret Room Alt Alt
    65: "L",  # Boss Rush
    67: "M",  # Boss Room (empty, twisted)
    70: "M",  # Echoes Reverse = Dark Home
    71: "M",  # Boss (alternate alternate)
    72: "P",  # Boss (Mother)         <- user-fixed
    74: "P",  # Boss (Dogma)          <- user-fixed
    75: "O",  # Boss (Beast)
    80: "C",  # Downpour (reversed)
    81: "C",  # Dross (reversed)
    82: "K",  # Genesis (reversed) = Ascent
    84: "E",  # Game Over
    85: "P",  # Boss (Hush Phase 1)
}


# --------------------------------------------------------------------------------------
# Jingle slots: one-shot clips cut from a master
# --------------------------------------------------------------------------------------
# master  : which master to cut from
# length  : clip length in seconds
# start   : cut offset in seconds. None means "pick automatically" (highest short-term
#           RMS window, distinct per jingle sharing a master). A number pins it.
# search  : optional (from, to) window in seconds to restrict the automatic search to.
# trigger : what fires it in game, shown on the audition page.
# zh      : the same, for the audition page's Chinese column.
#
# Offsets below are pinned to the values reviewed on the audition page. Pinning all of
# them matters: an automatic pick claims its window and blocks the others, so changing
# one unpinned jingle silently moves every other jingle that shares its master.

JINGLES = {
    19: dict(master="E", length=4.0, start=15.52, search=None,
             trigger="Devil Room door appears after a boss",
             zh="打完 BOSS 后恶魔房门出现"),
    21: dict(master="K", length=4.0, start=40.34, search=None,
             trigger="Angel Room door appears after a boss",
             zh="打完 BOSS 后天使房门出现"),
    # Reviewed: moved later, 34.00 -> 35.20 s. Slot 29 occupies 38.70-43.70 s of the
    # same master, so this can move at most 1.70 s later before the two overlap; this
    # takes 1.20 s of that and leaves a 0.50 s gap.
    25: dict(master="H", length=3.0, start=35.20, search=None,
             trigger="A secret room is revealed",
             zh="炸开密室时"),
    27: dict(master="H", length=5.0, start=21.12, search=None,
             trigger="Entering the Treasure Room (variant 1 of 4)",
             zh="进入宝箱房，4 个变体之一"),
    28: dict(master="H", length=5.0, start=13.74, search=None,
             trigger="Entering the Treasure Room (variant 2 of 4)",
             zh="进入宝箱房，4 个变体之一"),
    29: dict(master="H", length=5.0, start=38.70, search=None,
             trigger="Entering the Treasure Room (variant 3 of 4)",
             zh="进入宝箱房，4 个变体之一"),
    30: dict(master="H", length=5.0, start=27.16, search=None,
             trigger="Entering the Treasure Room (variant 4 of 4)",
             zh="进入宝箱房，4 个变体之一"),
    # Reviewed twice. The RMS heuristic kept landing mid-vocal, which is what it is
    # built to do -- the loudest window of this master *is* the middle of a sung
    # phrase. Chosen instead from phrase_windows(), then trimmed at 22.90 s, the last
    # energy seam before the vocal that runs 23.4-24.6 s.
    32: dict(master="L", length=3.6, start=19.30, search=None,
             trigger="Challenge Room starts",
             zh="挑战房开始"),
    # Reviewed: moved off `arcade` onto the boss track, ending on the full decay at
    # 69.80 s just before the next phrase begins -- a hit and its ring-out. Puts the
    # challenge room's entry, fight and outro all on the same music.
    34: dict(master="L", length=6.0, start=63.80, search=None,
             trigger="Challenge Room cleared",
             zh="挑战房通关"),
    # Pinned at the value reviewed earlier. It has to be pinned now that 32 and 34 are
    # fixed on this master: an automatic pick would be pushed elsewhere by their claims.
    35: dict(master="L", length=3.0, start=44.98, search=None,
             trigger="Boss fight intro, right before the boss music",
             zh="BOSS 战开场，接在 BOSS 曲之前"),
    47: dict(master="G", length=3.0, start=54.60, search=None,
             trigger="A boss dies",
             zh="BOSS 死亡"),
    # Reviewed: extended tail. Capped at 4.7 s -- the master ends at 68.34 s, so this
    # start has only 5.04 s of source left, not the 2 s of extension the others got.
    48: dict(master="F", length=4.7, start=63.30, search=None,
             trigger="A boss dies (alternate)",
             zh="BOSS 死亡，变体"),
    # Reviewed: extended tail, 4.0 -> 6.0 s.
    49: dict(master="P", length=6.0, start=32.22, search=None,
             trigger="Hush dies",
             zh="缄默死亡"),
    66: dict(master="G", length=4.0, start=65.86, search=None,
             trigger="Boss Rush cleared",
             zh="BOSS RUSH 通关"),
    68: dict(master="M", length=4.0, start=30.58, search=None,
             trigger="Mom's Shadow appears in the Mineshaft chase",
             zh="废弃矿井逃脱，妈妈的影子出现"),
    # Reviewed: trimmed the end slightly, 4.0 -> 3.4 s.
    69: dict(master="H", length=3.4, start=3.14, search=None,
             trigger="The Strange Door opens",
             zh="奇怪的门打开"),
    # Reviewed: start moved 1.36 s earlier, end 1.16 s earlier.
    73: dict(master="P", length=4.2, start=0.60, search=None,
             trigger="Dogma's intro cutscene",
             zh="教条登场演出"),
    # Reviewed: extended tail, 3.0 -> 5.0 s.
    76: dict(master="A", length=5.0, start=12.56, search=None,
             trigger="A boss dies (second alternate)",
             zh="BOSS 死亡，第二变体"),
    77: dict(master="P", length=4.0, start=27.08, search=None,
             trigger="Mother dies",
             zh="母亲死亡"),
    78: dict(master="P", length=4.0, start=8.74, search=None,
             trigger="Dogma dies",
             zh="教条死亡"),
    # Reviewed: start moved 2.10 s earlier, end 1.10 s earlier.
    79: dict(master="O", length=7.0, start=87.60, search=None,
             trigger="The Beast dies",
             zh="祸兽死亡"),
    # Reviewed: trimmed the end slightly, 3.0 -> 2.5 s.
    83: dict(master="E", length=2.5, start=0.98, search=None,
             trigger="Game over, just before the death screen music",
             zh="死亡瞬间，接在 Game Over 循环曲之前"),
}


def jingle_slug(n):
    return f"jingle_{slot_slug(n)}"


_SLUG_OVERRIDES = {
    19: "devil_appear",
    21: "angel_appear",
    25: "secret_find",
    27: "treasure_1",
    28: "treasure_2",
    29: "treasure_3",
    30: "treasure_4",
    32: "challenge_start",
    34: "challenge_end",
    35: "boss_intro",
    47: "boss_death",
    48: "boss_death_alt",
    49: "hush_death",
    66: "boss_rush_end",
    68: "shadow_intro",
    69: "strange_door",
    73: "dogma_intro",
    76: "boss_death_alt2",
    77: "mother_death",
    78: "dogma_death",
    79: "beast_death",
    83: "game_over",
}


def slot_slug(n):
    return _SLUG_OVERRIDES[n]


def ogg_name(n):
    """Output ogg filename for a slot."""
    if n in LOOPS:
        return f"{master_slug(LOOPS[n])}.ogg"
    return f"{jingle_slug(n)}.ogg"


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------

# (floor slot, boss slot) for every boss fought on a floor the player walks around on.
# Assigning both the same master makes the floor's ordinary rooms play boss music --
# the Void shipped that way once, so it is now a build error rather than a thing to
# remember.
FLOOR_BOSS_PAIRS = [
    (1, 36),    # Basement          / Boss
    (7, 38),    # Depths            / Mom
    (10, 39),   # Womb              / Mom's Heart
    (12, 44),   # Blue Womb         / Hush
    (13, 41),   # Sheol             / Satan
    (14, 40),   # Cathedral         / Isaac
    (15, 42),   # Dark Room         / The Lamb
    (16, 43),   # Chest             / ???
    (17, 46),   # Void              / Delirium
    (24, 45),   # Arcade            / Ultra Greed
    (58, 72),   # Corpse            / Mother
    (59, 75),   # Home              / The Beast
    (60, 61),   # Abandoned Mineshaft / Mineshaft Escape
]


def validate():
    """Raise AssertionError on any inconsistency. Called by every build script."""
    assert len(SLOT_NAMES) == TOTAL_SLOTS, (
        f"SLOT_NAMES has {len(SLOT_NAMES)} entries, expected {TOTAL_SLOTS}"
    )
    assert len(set(SLOT_NAMES)) == TOTAL_SLOTS, "duplicate slot name in SLOT_NAMES"

    overlap = set(LOOPS) & set(JINGLES)
    assert not overlap, f"slots defined as both loop and jingle: {sorted(overlap)}"

    covered = set(LOOPS) | set(JINGLES)
    missing = set(range(1, TOTAL_SLOTS + 1)) - covered
    assert not missing, (
        "unmapped slots (they would silently fall back to vanilla Rebirth music): "
        + ", ".join(f"{n} {slot_name(n)!r}" for n in sorted(missing))
    )
    extra = covered - set(range(1, TOTAL_SLOTS + 1))
    assert not extra, f"slot numbers out of range: {sorted(extra)}"

    for n, key in LOOPS.items():
        assert key in MASTERS, f"slot {n} references unknown master {key!r}"
    for n, spec in JINGLES.items():
        assert spec["master"] in MASTERS, (
            f"jingle {n} references unknown master {spec['master']!r}"
        )
        assert spec["length"] > 0, f"jingle {n} has non-positive length"
        assert n in _SLUG_OVERRIDES, f"jingle {n} has no output slug"

    slugs = {slot_slug(n) for n in JINGLES}
    assert len(slugs) == len(JINGLES), "duplicate jingle slug"

    collisions = [
        f"{slot_name(f)!r} ({f}) and {slot_name(b)!r} ({b}) both use {LOOPS[f]}"
        for f, b in FLOOR_BOSS_PAIRS
        if f in LOOPS and b in LOOPS and LOOPS[f] == LOOPS[b]
    ]
    assert not collisions, (
        "a floor shares a master with the boss fought on it, so its ordinary rooms "
        "would play boss music:\n  " + "\n  ".join(collisions)
    )

    return True


def used_masters():
    return sorted(set(LOOPS.values()) | {s["master"] for s in JINGLES.values()})


def jingles_by_master():
    """master key -> [slot numbers], ascending. Used to allocate distinct cut windows."""
    out = {}
    for n in sorted(JINGLES):
        out.setdefault(JINGLES[n]["master"], []).append(n)
    return out


if __name__ == "__main__":
    validate()
    print(f"OK: {TOTAL_SLOTS} slots, {len(LOOPS)} loops, {len(JINGLES)} jingles, "
          f"{len(used_masters())}/{len(MASTERS)} masters used")
