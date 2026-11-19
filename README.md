# Chiikawa Soundtrack for The Binding of Isaac: Repentance+

A Soundtrack Menu compatible music mod. Registers a soundtrack named `Chiikawa` covering all 85 controllable music slots. Published on the Steam Workshop as item [3787641648](https://steamcommunity.com/sharedfiles/filedetails/?id=3787641648).

16 lossless masters have to fill 85 slots, and 22 of those are jingles that need a five second phrase cut out of a full track at a musically sensible point. So the work here is a build. One file holds the slot mapping and the cut points, everything else is generated from it, a checker refuses to produce a build that would fall back to vanilla audio, and a Lua harness verifies the result inside the running game.

[docs/design.md](docs/design.md) records the reasoning behind each decision.

The mod itself is a Workshop subscription. How it was built is not, and that is what this repository is for.

## What you can take from this

**A wrong resource path fails silently in Isaac.** The engine falls back to its own asset and says nothing, so no build-side check can catch it. That one fact is why this repository has a Lua harness ([`mod/dev_slots.lua`](mod/dev_slots.lua), [`mod/dev_jingle_test.lua`](mod/dev_jingle_test.lua)) that resolves all 85 track names from inside the running game and lists the ones that fell back. If you are modding anything where the engine swallows your mistakes, that is the pattern.

**One file holds the mapping, everything else is generated.** [`build/tracks.py`](build/tracks.py) is the only place a slot number, a master and a cut offset are written down. `music.xml` and the Lua slot table are generated from it, and `build/verify.py` checks the result. Editing generated files is then impossible to do by accident.

**Cutting a five second phrase out of a full track at a musically sensible point.** `build/build_audio.py` searches for the cut instead of taking a fixed offset, and records the offset it chose in `build/cut_points.json` so a human can pin any one of them by hand afterwards.

**Verified Repentance+ audio facts.** Repentance+ routes jingles through the SFX volume channel while loops use the music channel, so the on-file loudness relation between a jingle and a loop is not what the player hears. Plain Repentance uses the music slider for both. `docs/design.md` has the measurements.

## Requirements

- Soundtrack Menu (`1933285222`)
- Music Mod Callback, Repentance/Rep+ version (`2491006386`), or REPENTOGON
- Mod Config Menu, to select the soundtrack

## Commands

Rebuild everything and install a dev build into the game.

```powershell
python build/build_audio.py; python build/build_xml.py; python build/verify.py; python build/deploy.py
```

Individually:

| Command | Does |
|---|---|
| `python build/tracks.py` | Validate the slot mapping only. Instant. |
| `python build/build_audio.py` | FLAC to 38 ogg files, with loudness normalisation. |
| `python build/build_audio.py --jingles` | Rebuild only the 22 jingle clips. |
| `python build/build_xml.py` | Regenerate `music.xml` and `dev_slots.lua`. No audio. |
| `python build/verify.py` | Layer 1 machine checks. Non-zero exit on FAIL. |
| `python build/audition.py` | Build the jingle audition page. |
| `python build/deploy.py` | Install a dev build (includes the console harness). |
| `python build/deploy.py --release` | Install without the dev harness. |
| `python build/deploy.py --dry-run` | List what would be copied. |

On a fresh clone there is no audio, so most of these have nothing to work on. `python build/tracks.py` is the one that still does something useful. It validates the whole slot mapping and prints `OK: 85 slots, 63 loops, 22 jingles, 16/16 masters used`. Start there.

## Mechanics

##### Adjusting a jingle cut

Every jingle's cut offset lives in `build/tracks.py` under `JINGLES`. A `start` of `None` means the offset was chosen automatically, and the chosen value is recorded in `build/cut_points.json`. Pin one by giving it a start value.

```python
27: dict(master="H", length=5.0, start=21.1, search=None, ...)
```

Then `python build/build_audio.py --jingles` and `python build/audition.py`.

##### In-game verification

A file can be correct on disk and still never reach the player, because the game falls back to its own asset without saying so. A dev build registers three console commands to catch that.

| Command | Does |
|---|---|
| `chiikawa_check` | Resolve all 85 track names, list any that fall back to vanilla. |
| `chiikawa_jingle <n>` | Play one jingle by slot number. |
| `chiikawa_jingle all` | Walk all 22 jingles, 3 s apart. `stop` cancels. |
| `chiikawa_music <n>` | Play a looping track by slot number. |

On load the harness prints `Chiikawa dev harness ready`. If a dev build does not print that line, the harness failed to load.

## Publishing to the Steam Workshop

1. `python build/deploy.py --release`, installs without the dev harness or build marker.
2. Close the game, then run `tools\ModUploader\ModUploader.exe` from the game folder.
3. Pick **Chiikawa Soundtrack**, confirm the preview image, upload.
4. Leave `<visibility>` as `Private` for the first upload, check the item on the Workshop, then switch it to `Public` and upload again.

On first publish the uploader writes the Workshop item id into the *installed* `metadata.xml`. Run `python build/deploy.py --release` once afterwards. It reads that id back into `mod/metadata.xml`, so later uploads update the same item and do not create a second one. Do not delete the `<id>` element once it exists.

## Layout

| Path | What it is |
|---|---|
| `audio_master/` | 16 lossless FLAC masters. The source of truth for audio. Not committed. |
| `_source_mp4/` | Archived original MP4s the masters were extracted from. Not committed. |
| `build/tracks.py` | Slot mapping and cut points. **The file to edit.** |
| `cover.png` | Workshop cover art, hand-drawn. The source copy. |
| `mod/` | The mod itself. Generated files are marked in their headers. |

`mod/previewpic.png` is `cover.png` flattened to RGB, and that is the file the Workshop uses. To change the cover, replace `cover.png` and re-flatten it. Nothing regenerates it automatically, so a build cannot overwrite hand-drawn art.

## Notes

The masters are copyrighted material from the *Chiikawa* franchise and are not mine to redistribute, so `audio_master/`, `_source_mp4/` and the built `mod/resources/` are excluded. Drop your own masters into `audio_master/`, name them to match the `MASTERS` table in `build/tracks.py`, and the pipeline runs end to end.

`cover.png` and `mod/previewpic.png` are hand-drawn and are included.

Three more repositories from the same run of game-mod work, each written up the same way. [isaac-voice-sfx-pipeline](https://github.com/Osoito/isaac-voice-sfx-pipeline) is the sound effect mod this one's build was reused for, [yukkuri-toolbar-presets](https://github.com/Osoito/yukkuri-toolbar-presets) mods a closed HSP3 game by reading its process memory, and [asset-pipeline](https://github.com/Osoito/asset-pipeline) is the scaffold the two Isaac mods have in common.
