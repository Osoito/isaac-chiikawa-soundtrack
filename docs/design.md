# Chiikawa Soundtrack — Design Spec

**Date:** 2026-08-21
**Target:** *The Binding of Isaac: Repentance+*, a Soundtrack Menu compatible music mod.

---

## 1. Goal

Ship a music mod that registers a soundtrack named **`Chiikawa`** with the
[Soundtrack Menu](https://steamcommunity.com/sharedfiles/filedetails/?id=1933285222) mod
(`musicpicker_1933285222`), so the player can select it — or mix it per-track — from
Mod Config Menu. Every controllable music slot in the game must play Chiikawa audio;
none may fall back to the vanilla Rebirth soundtrack.

## 2. Environment (verified)

| Item | Value |
|---|---|
| Game install | `D:\softwares\Steam\steamapps\common\The Binding of Isaac Rebirth` |
| Mods dir | `<install>\mods\` |
| User data / log | `%USERPROFILE%\Documents\My Games\Binding of Isaac Repentance+\` |
| Soundtrack Menu | installed, v2.97, `musicpicker_1933285222` |
| Music Mod Callback (Rep) | installed, v1.32, `music mod callback rep_2491006386` |
| REPENTOGON | **not installed** |
| ffmpeg / ffprobe | `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_...\bin\` |
| Python | `%LOCALAPPDATA%\Programs\Python\Python313\python.exe` |

Because REPENTOGON is absent, Soundtrack Menu runs on the **Music Mod Callback** path
(`soundtrackmenu.lua`, not `soundtrackmenu-rgon.lua`). That path exposes **85 track
slots**. Title-screen music, run-start jingles and the pre-floor nightmare jingle are
**not** controllable and are out of scope.

## 3. Source audio

16 unique tracks, extracted from user-supplied 720p MP4s (AAC 48 kHz stereo,
~190 kbps audio) into lossless FLAC masters in `audio_master/`.

| Key | Master file | Duration | Character |
|---|---|---|---|
| A | `地下室层.flac` | 72.5 s | bright, everyday |
| B | `燃烧层.flac` | 38.5 s | short, agitated |
| C | `水下层.flac` | 88.0 s | aquatic |
| D | `子宫.flac` | 62.5 s | organic |
| E | `阴间.flac` | 33.6 s | short, dark |
| F | `商店.flac` | 72.5 s | light, cheerful |
| G | `游戏房.flac` | 75.2 s | upbeat |
| H | `宝藏房.flac` | 47.6 s | mysterious |
| I | `矿井层.flac` | 55.0 s | subterranean |
| J | `陵墓层.flac` | 40.6 s | somber |
| K | `家层和卧室.flac` | 79.5 s | warm, home |
| L | `塞壬boss曲.flac` | 82.0 s | combat |
| M | `精神错乱.flac` | 46.0 s | chaotic |
| N | `超级撒旦.flac` | 78.2 s | heavy combat |
| O | `祸兽.flac` | 154.5 s | final battle |
| P | `见证者.flac` | 51.7 s | combat |

**Removed:** the file originally named `尸宫层.mp4` was byte-identical to
`家层和卧室.mp4` (md5 `1c1ca2f2496c1d23424a3716a021d3b7`). Its duplicate FLAC was
deleted; the Corpse slot is covered by reuse (§5). Originals are archived under
`_source_mp4/` and are not deleted.

## 4. Architecture

```
IssacChiikawaMusicMod/
├── audio_master/              # 16 lossless FLAC masters (hand-managed, source of truth)
├── _source_mp4/               # archived original MP4s
├── build/
│   ├── tracks.py              # single source of truth: slot -> master + clip definitions
│   ├── ffio.py                # ffmpeg discovery, loudness measurement, envelope analysis
│   ├── build_audio.py         # FLAC -> ogg (loops) + jingle clips
│   ├── build_xml.py           # generate content/music.xml and mod/dev_slots.lua
│   ├── verify.py              # Layer 1 signal checks (§7)
│   ├── audition.py            # Layer 2 HTML audition page (§7)
│   ├── deploy.py              # copy mod/ into the game's mods dir
│   ├── cut_points.json        # GENERATED: chosen jingle offsets + loudness targets
│   └── verify_report.json     # GENERATED: machine-readable Layer 1 results
├── mod/                       # the shippable mod
│   ├── metadata.xml           # hand-written
│   ├── main.lua               # hand-written
│   ├── dev_jingle_test.lua    # hand-written, DEV ONLY — excluded by deploy.py --release
│   ├── dev_slots.lua          # GENERATED, DEV ONLY — slot table for the harness
│   ├── content/music.xml      # GENERATED
│   └── resources/music/Chiikawa/*.ogg   # GENERATED
└── docs/
```

Three independent units, each testable on its own:

- **`tracks.py`** — pure data. Maps each of the 85 slot names to either a master key
  (loop) or a clip spec (jingle: master key + start offset + length). No I/O.
- **`build_audio.py`** — consumes `tracks.py`, invokes ffmpeg, writes `.ogg` files.
  Depends on ffmpeg only.
- **`build_xml.py`** — consumes `tracks.py`, writes `music.xml`. Pure text, no audio.

`ffio.py` is the only place that knows where ffmpeg lives or how to read a loudness
measurement out of it; everything else calls it. `verify.py` and `audition.py` are
read-only consumers of `tracks.py` plus the built `.ogg` files; neither can change the
build.

Splitting XML generation from audio encoding means the slot mapping can be iterated on
(cheap, seconds) without re-encoding audio (expensive). Likewise, adjusting a jingle cut
point re-encodes one clip, not all 38 files.

### Mod identity

- Soundtrack name registered with the menu: **`Chiikawa`** (ASCII — Isaac's font cannot
  render CJK, and the track-name lookup is a plain string concat).
- Mod folder / `<directory>`: `chiikawa soundtrack`.
- Every music track is named `Chiikawa <SlotName>` where `<SlotName>` is verbatim from
  Soundtrack Menu's `tracktypes` table (e.g. `Chiikawa Womb/Utero`, `Chiikawa Boss (Beast)`).
  Soundtrack Menu resolves these via `Isaac.GetMusicIdByName(soundtrack .. " " .. tracktype)`
  (`soundtrackmenu.lua:793`).
- Output `.ogg` filenames are ASCII slugs to avoid any XML/filesystem encoding risk.

### `main.lua`

```lua
local mod = RegisterMod("Chiikawa Soundtrack", 1)

function mod:onGameStart()
    if SoundtrackSongList then
        AddSoundtrackToMenu("Chiikawa")
    else
        Isaac.ConsoleOutput("The Soundtrack Menu mod is required for the Chiikawa Soundtrack\n")
    end
end

mod:AddCallback(ModCallbacks.MC_POST_GAME_STARTED, mod.onGameStart)
```

This mirrors the shipped reference mod `sayonara zetsubou sensei soundtrack_2817873319`.
Jukebox (`AddTitlesToJukebox`) support is deliberately omitted — YAGNI; it requires a
separate mod the user does not have.

## 5. Slot mapping (all 85 slots)

Rationale: keep each Isaac *chapter* internally consistent, avoid two adjacent floors
sharing a track where a distinct one is available, and reserve the four combat masters
(L/N/P/O) for an escalating boss ladder — L for ordinary bosses, N for the
Mom/Satan line, P for the Hush/Mother/Dogma line, O for the two endgame bosses.

One rule sits above the rest, learned the hard way: **a floor must never share a master
with the boss fought on it**, or the floor's ordinary rooms play boss music.

In the two tables below, text after an em-dash or in a trailing parenthesis is an
explanatory gloss for the reader, **not** part of the slot name — e.g. slot 46 is
`Boss (Void)`, slot 70 is `Echoes Reverse`, slot 82 is `Genesis (reversed)`. The
authoritative, verbatim list of the 85 slot names lives in `build/tracks.py`, copied
from `soundtrackmenu.lua`, and is what the generator and its assertions use.

### Loop slots (63)

| # | Slot name | Master |
|---|---|---|
| 1 | Basement | A |
| 2 | Cellar | A |
| 3 | Burning Basement | B |
| 4 | Caves | I |
| 5 | Catacombs | I |
| 6 | Flooded Caves | C |
| 7 | Depths | J |
| 8 | Necropolis | J |
| 9 | Dank Depths | J |
| 10 | Womb/Utero | D |
| 11 | Scarred Womb | D |
| 12 | Blue Womb | E |
| 13 | Sheol | E |
| 14 | Cathedral | K |
| 15 | Dark Room | E |
| 16 | Chest | K |
| 17 | Void | O |
| 18 | Library Room | H |
| 20 | Devil Room | E |
| 22 | Angel Room | K |
| 23 | Shop Room | F |
| 24 | Arcade Room | G |
| 26 | Secret Room | H |
| 31 | Boss Room (empty) | K |
| 33 | Challenge Room (fight) | L |
| 36 | Boss | L |
| 37 | Boss (alternate) | P |
| 38 | Boss (Depths - Mom) | N |
| 39 | Boss (Womb - Mom's Heart) | N |
| 40 | Boss (Cathedral - Isaac) | P |
| 41 | Boss (Sheol - Satan) | N |
| 42 | Boss (Dark Room) | N |
| 43 | Boss (Chest - ???) | P |
| 44 | Boss (Blue Womb - Hush) | P |
| 45 | Boss (Ultra Greed) | M |
| 46 | Boss (Void) — Delirium | M |
| 50 | Boss (Mega Satan) | N |
| 51 | Utero | D |
| 52 | Downpour | C |
| 53 | Dross | C |
| 54 | Mines | I |
| 55 | Ashpit | I |
| 56 | Mausoleum | J |
| 57 | Gehenna | J |
| 58 | Corpse | C |
| 59 | Home | K |
| 60 | Abandoned Mineshaft | H |
| 61 | Mineshaft Escape | M |
| 62 | Planetarium | H |
| 63 | Secret Room Alt | H |
| 64 | Secret Room Alt Alt | H |
| 65 | Boss Rush | L |
| 67 | Boss Room (empty, twisted) | M |
| 70 | Echoes Reverse (Dark Home) | M |
| 71 | Boss (alternate alternate) | M |
| 72 | Boss (Mother) | P |
| 74 | Boss (Dogma) | P |
| 75 | Boss (Beast) | O |
| 80 | Downpour (reversed) | C |
| 81 | Dross (reversed) | C |
| 82 | Genesis (reversed) — Ascent | K |
| 84 | Game Over | E |
| 85 | Boss (Hush Phase 1) | P |

User-fixed assignments honoured: 塞壬boss曲 → slot 36 (Boss); 见证者 → slots 44/72/74
(Hush / Mother / Dogma); 宝藏房 → slots 18 + 62 (Library + Planetarium).

**Revised after in-game testing.** Slot 17 (the Void floor) and slot 46 (the Delirium
fight that happens on it) were both assigned M, so the floor's ordinary rooms played
boss music. An audit of all thirteen floor/boss pairs found this was the only collision;
the other twelve were already distinct. `validate()` now enforces the rule against
`FLOOR_BOSS_PAIRS` so it cannot regress.

The fix also corrected an allocation mistake. `beast` is the longest master by a wide
margin -- 154.5 s against 88 s for the next -- and length is exactly what a floor loop
needs, since the player walks a whole floor while it repeats. It was carrying one boss
slot instead.

- 17 Void: M → **O** `beast`. Shares with slot 75 (the Beast), but those sit on
  different run paths and are not heard in one playthrough.
- 46 Delirium keeps **M** `delirium`. Once the floor moved off M the clash was gone,
  and M is the master recorded for this fight in the first place.

### Jingle slots (22)

Jingles are one-shot (`loop="false"`). None of the 16 masters is a jingle, so each is
cut from a master. Cut points are chosen by an automated heuristic — see §6 stage 4 — and are
expected to need one round of manual adjustment after listening.

| # | Slot name | Cut from | Window | Length |
|---|---|---|---|---|
| 19 | Devil Room appear (jingle) | E `sheol` | 15.52–19.52 s | 4 s |
| 21 | Holy Room Find (jingle) | K `home` | 40.34–44.34 s | 4 s |
| 25 | Secret Room Find (jingle) | H `treasure` | 35.20–38.20 s | 3 s |
| 27 | Treasure Room Entry (jingle) 1 | H `treasure` | 21.12–26.12 s | 5 s |
| 28 | Treasure Room Entry (jingle) 2 | H `treasure` | 13.74–18.74 s | 5 s |
| 29 | Treasure Room Entry (jingle) 3 | H `treasure` | 38.70–43.70 s | 5 s |
| 30 | Treasure Room Entry (jingle) 4 | H `treasure` | 27.16–32.16 s | 5 s |
| 32 | Challenge Room Entry (jingle) | L `boss_siren` | 19.30–22.90 s | 3.6 s |
| 34 | Challenge Room Outro (jingle) | L `boss_siren` | 63.80–69.80 s | 6 s |
| 35 | Boss (jingle) | L `boss_siren` | 44.98–47.98 s | 3 s |
| 47 | Boss Death (jingle) | G `arcade` | 54.60–57.60 s | 3 s |
| 48 | Boss Death Alternate (jingle) | F `shop` | 63.30–68.00 s | 4.7 s |
| 49 | Boss Hush Death (jingle) | P `witness` | 32.22–38.22 s | 6 s |
| 66 | Boss Rush (jingle) | G `arcade` | 65.86–69.86 s | 4 s |
| 68 | Mom's Shadow Intro | M `delirium` | 30.58–34.58 s | 4 s |
| 69 | Strange Door (jingle) | H `treasure` | 3.14–6.54 s | 3.4 s |
| 73 | Dogma Intro | P `witness` | 0.60–4.80 s | 4.2 s |
| 76 | Boss Death Alternate Alternate (jingle) | A `basement` | 12.56–17.56 s | 5 s |
| 77 | Boss Mother Death (jingle) | P `witness` | 27.08–31.08 s | 4 s |
| 78 | Boss Dogma Death (jingle) | P `witness` | 8.74–12.74 s | 4 s |
| 79 | Boss Beast Death (jingle) | O `beast` | 87.60–94.60 s | 7 s |
| 83 | Game Over (jingle) | E `sheol` | 0.98–3.48 s | 2.5 s |

Slots 27–30 take four *different* 5 s windows of H so treasure-room entries vary.

Every offset above is now pinned in `tracks.py`. That matters mechanically, not just as
a record: an automatic pick claims its window and blocks the others, so leaving one
jingle unpinned means editing it silently relocates every other jingle sharing its
master. The values were settled over two review rounds on the audition page.

Two of them did not come from the RMS heuristic at all. Slot 32 kept landing mid-vocal
through two attempts, which is what maximising RMS is *built* to do — the loudest window
of a track is the middle of its loudest phrase. `build_audio.phrase_windows()` was added
to search the opposite way: find energy dips, treat the rise out of one as a phrase
start, and end at the next dip. Slots 32 and 34 were chosen from its output, and 34 moved
off `arcade` onto `boss_siren` in the process, which also puts the challenge room's
entry, fight and outro on the same music.

## 6. Audio pipeline

Encoding throughout is Ogg Vorbis, `-c:a libvorbis -q:a 5` (~160 kbps, 48 kHz stereo).
The source is ~190 kbps AAC, so q5 is transparent enough at game volume without
inflating the mod's size.

### Stage 1 — trimmed masters

`silenceremove` strips leading and trailing digital silence from each FLAC into
`build/.cache/<slug>.wav`. Everything downstream — the looping ogg, the cut-point
analysis, the jingle clips, the audition page — derives from that wav, so an offset
means the same thing everywhere it is reported.

### Stage 2 — loudness normalisation

**This step was not in the original design and was added after measurement.** As built
from raw cuts, the 16 masters spanned **15.4 LU** (`underwater` −27.9 LUFS against
`treasure` −12.5 LUFS). That is the single most audible defect the mod could ship with:
the volume would change every time the player walks onto a new floor.

The target is anchored on the game's own soundtrack, measured over the vanilla Rebirth
oggs that Soundtrack Menu bundles:

| | vanilla Rebirth | Chiikawa, raw | Chiikawa, normalised |
|---|---|---|---|
| loop mean | −11.6 LUFS | −18.9 LUFS | −19.1 LUFS |
| loop spread | 9.6 LU | 15.4 LU | **0.2 LU** |
| jingle mean | −14.5 LUFS | −13.7 LUFS | −22.1 LUFS |
| jingle vs loop | −2.9 LU | +5.2 LU | **−2.9 LU** |

Two decisions follow from those numbers:

- **Jingles sit 2.9 LU below the loops**, reproducing vanilla's own relationship. Left
  alone they were 5.2 LU *above*, because each is cut from the loudest phrase of its
  master — the opposite of how the game balances its own stings.
- **The absolute target is derived from the material, not from vanilla.** Reaching
  −11.6 LUFS needs ~10 dB of limiting on the peakiest masters, which audibly squashes
  them; these are dynamic anime BGM sitting near −22 LUFS, not a loudness-war master.
  So `build_audio.py` computes the loudest level *every* master can reach while the
  limiter does no more than `LIMIT_BUDGET_DB` (3 dB) of work, capped at vanilla's level.
  That currently yields −19.1 LUFS, set by `sheol`.

The consequence is that the mod plays **7.5 LU quieter than the vanilla soundtrack**, so
switching between them in Soundtrack Menu changes the volume. `verify.py` reports this
as a standing WARN rather than hiding it. Raising `LIMIT_BUDGET_DB` trades dynamics for
loudness; `LOUDNESS_OVERRIDE` pins a single master that the derived target suits badly.

Implementation is a measured gain followed by `alimiter` at the true-peak ceiling
(−1.0 dBTP). Vanilla routinely exceeds 0 dBTP; we do not copy that.

### Stage 3 — loops

Encoded straight from the normalised master, referenced by `loop="true"`.

Loop points are **not** hand-authored in v1. The `intro=` attribute of `music.xml` is
left unused. Isaac hard-loops the file end-to-start; a small seam is accepted for the
first playable build and refined per-track afterwards if it is audible.

### Stage 4 — jingles

1. Cut `[start, start+len]` from the trimmed master. Where `start` is `null`, the
   heuristic picks the highest short-term RMS window, so the clip lands on a musical
   phrase rather than a fade-in. Jingles sharing a master claim distinct, non-overlapping
   windows (a 1 s guard between them), which is what gives Treasure Room entries 1–4
   four different stings. The search covers the whole master minus a 0.5 s guard at each
   end; the original "first 30 s" rule was dropped as arbitrary, and a per-jingle
   `search` window replaces it for cases that need pinning.
2. Apply a 100 ms fade-in and a 400 ms fade-out so the one-shot ends cleanly.
3. Normalise to the jingle target, never exceeding what the clip's own headroom allows,
   so a short clip cannot end up squashed harder than the loops beside it.

Chosen offsets are written to `build/cut_points.json` so the audition page can display
them and so an automatic pick can be read, pinned, and adjusted.

Total output: 16 loops + 22 jingles = **38 ogg files, 19.3 MB**.

## 7. Testing / verification

Verification is layered cheapest-first. Jingles are the risky part — their cut points
are machine-chosen and each needs a human ear — so the design deliberately makes the
jingle iteration loop runnable **without launching the game**.

### Layer 1 — automated, no game, no ears

Run as part of the build; failures block deploy.

1. `build_xml.py` asserts all 85 slot names are present exactly once, and that every
   name matches Soundtrack Menu's `tracktypes` strings verbatim (the list is checked
   into `build/tracks.py` as a literal copied from `soundtrackmenu.lua`).
2. `build_audio.py` asserts every referenced `.ogg` exists after the run and is non-empty.
3. `ffprobe` every produced `.ogg`: decodable, codec is `vorbis`, duration within
   ±50 ms of the value declared in `tracks.py`.

4. `metadata.xml` parses, and its `<directory>` matches the folder the mod installs to.
   A mismatch there is a silent misbehaviour, not an error the game reports.

Signal checks, via `ffmpeg -af ebur128` and RMS analysis of the decoded audio:

5. **No clipping** — true peak at or below the −1 dBTP ceiling, loops and jingles alike.
6. **Onset carries signal** — RMS of the 200 ms just after the fade-in is above the noise
   floor. Guards against a cut window landing in a musical gap, which would make the
   jingle read as "nothing played".
7. **Tail ends quiet** — the last 100 ms sits at least 10 dB below the clip's own level,
   confirming the fade-out shaped the ending and there is no hard-cut click. *An earlier
   draft tested for a monotonic decay across the whole 400 ms fade window; that is the
   wrong metric, because a musical swell inside the window can net-rise early while the
   fade is working correctly. Where the tail ends up is what matters.*
8. **Cut is not into a quiet passage** — clip RMS against its own built loop. Both sides
   must be measured after loudness normalisation; comparing a normalised clip to a raw
   master measures the normalisation gain and nothing else.
9. **Mutual loudness consistency** — integrated LUFS within ±1.5 LU across the 16 loops,
   and again across the 22 jingles. The loop half is the important one: it is what keeps
   the volume steady from floor to floor.
10. **Level against vanilla** — loop mean against the measured vanilla Rebirth mean, and
    the jingle-to-loop offset against vanilla's own −2.9 LU. See §6; the absolute gap is
    an accepted, reported trade-off.
11. **Cross-channel balance** — the jingle-to-loop offset scaled by the player's
    `SFXVolume`/`MusicVolume` ratio from `options.ini`, since on Repentance+ the two play
    on different channels. A muted music slider is reported as a FAIL, because no
    listening test below is meaningful until it is raised.

### Layer 2 — human ear, still no game

`build/audition.py` emits a self-contained HTML audition page (published as an Artifact)
listing all 22 jingles: slot name, the in-game event that triggers it, the source master,
the cut window as `mm:ss.s–mm:ss.s`, an inline player, and the full source master
alongside for comparison. ~2.5 MB with the audio embedded as data URIs.

This is the main iteration loop: listen → adjust a start offset or length in
`tracks.py` → rebuild → refresh. A round trip is seconds, versus minutes for a
game restart. Expect several passes here.

### Layer 3 — in game, deterministically triggered

Most jingles are situational (devil room appearing, secret room found, a specific boss
dying). Farming those rooms to audition a 4-second clip is not viable, so the mod
carries a **dev-only** Lua file registering a console command:

```
chiikawa_jingle 27     -- play Treasure Room Entry 1, print the slot name on screen
chiikawa_jingle all    -- walk all 22 in order, 3 s apart
```

implemented as `MusicManager():PlayJingle(Isaac.GetMusicIdByName("Chiikawa " .. slot))`.
Soundtrack Menu uses the same call (`soundtrackmenu.lua:2046`), so this exercises the
real path.

This layer catches the three failure modes Layer 2 cannot see:

- a typo'd track name (which otherwise fails *silently* — see §8),
- a jingle that loops because `loop="false"` was missed, since `PlayJingle` should return
  to floor music on its own,
- loudness that is wrong **in the game's actual mix** rather than in isolation.

`deploy.py` excludes this file from a release build.

### Channel note (Repentance+ specific)

On Repentance+, jingles play on the **SFX volume** channel while music plays on the
**music volume** channel — Soundtrack Menu's author documents this, and the split does
not exist in plain Repentance. The user's current `options.ini` reads
`MusicVolume=0.0000`, `SFXVolume=0.9000`, so with today's settings floor music would be
inaudible while jingles play at 90%. Before any listening test, music volume must be
raised, and Layer 1 item 11 must use the settings actually in effect during the test.

### Layer 0 — smoke test, run once before the above

1. Launch the game; the debug console shows no error from `Chiikawa Soundtrack`.
2. Mod Config Menu → *Set Soundtrack* → `Chiikawa` appears and can be selected.
3. Start a run; Basement plays master A. Sample other chapters via the debug console
   (`stage 4`, `stage 6`, `stage 8`, `stage 11`).

**Pass criterion for "complete":** Layer 0 items 1–3, Layer 1 fully green, and Layer 3
`chiikawa_jingle all` heard end to end with no dead, clipped, or looping clip.

## 8. Error handling

- **Soundtrack Menu absent** — `main.lua` guards on `SoundtrackSongList` and prints a
  console message instead of erroring. Matches the reference mod's behaviour.
- **A track name typo** — Soundtrack Menu silently falls back to Rebirth
  (`soundtrackmenu.lua:481-489`), which is a *silent* failure. This is why §7 item 1
  validates names against a checked-in copy of the canonical list rather than trusting
  hand-typed XML.
- **Missing ogg at runtime** — Isaac logs a resource error and plays nothing. Caught by
  §7 item 2 before shipping.
- **Deploy overwriting an existing folder** — `deploy.py` refuses to write into the game
  mods dir if the target exists and was not produced by this project (checked by a
  marker file), unless `--force` is passed.

## 9. Out of scope (YAGNI)

- Jukebox / `AddTitlesToJukebox` support.
- REPENTOGON-only slots and Continuous Floor Music.
- Title screen, run-start and nightmare jingles (not controllable without REPENTOGON).
- Hand-authored `intro=` loop points.

## 10. Publishing

Release builds are produced by `deploy.py --release`, which drops the dev harness
(`dev_jingle_test.lua`, `dev_slots.lua`) and the build marker, leaving `metadata.xml`,
`previewpic.png`, `main.lua`, `content/music.xml` and the 38 oggs. Upload with the
game's own tool, `tools/ModUploader/ModUploader.exe`.

The Workshop item id is the one piece of state the uploader creates: on first publish it
writes `<id>` into the *installed* `metadata.xml`. A later deploy would overwrite that
file and drop the id, and the next upload would then create a second, unrelated Workshop
item. `deploy.py` therefore reads any `<id>` out of the installed copy and writes it back
into `mod/metadata.xml` before overwriting, so the link survives without anyone having
to remember it.

`previewpic.png` is generated by `build/make_preview.py` from the RMS envelope of a
built track. Replacing it by hand is fine; nothing depends on that script.

## 11. Legal note

The source audio is copyrighted material from the *Chiikawa* franchise. This mod is
built for local personal use. Distribution — including Steam Workshop upload — is the
user's decision and carries the usual risk that applies to every anime soundtrack mod on
the Workshop.
