# Real sound effects instead of spoken "creak and whirr"

## Problem

Claude sometimes wrote sound effects into Madame Mechanika's lines ("*creak*... whirrr... ah, a visitor"), and ElevenLabs read them aloud. Nothing in the stock lines did this. It came from the persona ("made of brass gears") and the greeting prompt ("you are creaking awake"). Meanwhile the browser already plays synthesized machine sounds at the right moments (`static/js/sound.js`), and they're thin.

## Goal

- She doesn't say sound effects. The machine makes them.
- The machine sounds (`creak`, `grind`, `whir`, `coin`, `ratchet`) are real clips made with the ElevenLabs Sound Effects API.
- The crystal ball has its own ambient shimmer (`ball`) while she's awake, its volume following the ball's glow.
- The booth needs no network or key for them at party time. Without clips, it falls back to the current synth sounds.

Non-goals: letting Claude cue effects mid-sentence; replacing the music box, bells, shimmer, or clock tick; post-processing Claude's text.

## Design

### 1. Clean speech (prompt only)

In `server/oracle.py`:
- `PERSONA` gains: "Your words are spoken aloud by your voice box. Never write sound effects, noises, or stage directions (no creak, whirr, clank, no asterisks or brackets). Your machinery makes its own sounds."
- The greeting prompt's "you are creaking awake" becomes "you are stirring awake".

A regex scrubber was tried and dropped. Telling noises apart from prose ("Ding, dong, the witch is dead") made it the hardest code in the change, for a case the prompt already covers.

### 2. Clip library (generated once, committed)

`server/sfx.py`:
- `EFFECTS` maps each effect to two or three `(prompt, duration_seconds)` variants, 13 clips in all. `LOOPED = {"whir", "ball"}`, because those play for as long as a phase lasts (the consult alone can be anywhere from 3.5 to about 20 seconds).
- `generate()` requests each missing clip, one at a time, from `POST https://api.elevenlabs.io/v1/sound-generation` with `model_id: eleven_text_to_sound_v2`, `prompt_influence: 0.5`, and `loop: true` for the looped effects. A failed clip is logged and skipped. A 401/403 exits with a message naming the Sound Effects key permission.
- Files are named `<effect>-<i>-<hash>.mp3`, where the hash covers the prompt, duration and loop flag. Editing a prompt therefore produces a new file. `available()` lists only the files that match the current prompts, and `prune()` deletes the rest.

`scripts/make_sfx.py` runs `generate()` and `prune()`, then prints a count per effect. Clips live in `static/sfx/` (`config.SFX_DIR`), are committed to the repo, and are served by the existing static file mount. `/api/config` lists them as `"sfx": {effect: ["/sfx/<file>", ...]}`.

### 3. Playback (browser)

In `static/js/sound.js`:
- `loadEffects(map)` decodes every clip. A clip that fails to load is dropped, and the method never rejects.
- `creak`, `grind`, `whir`, `coin` and `ratchet` each play a random variant, never the same one twice in a row (`pickVariant`). Without a clip, they run the existing synth code. Signatures are unchanged.
- `whir(on)` loops its clip with a fade in and out, and always stops any running whir first, so loops never stack.
- `ball(level)` loops the ball clip at `level` × its base gain, easing between levels. `main.js` calls it wherever it sets the ball's glow: 0.45 on waking, 1 while consulting, 0.55 afterwards, and 0 (a fade out) when she goes to sleep, so the music box plays alone. Without a clip the ball stays silent.
- `begin()` waits for the clips to decode before she first settles to sleep, so even the first creak is a clip.
- Clips go through the existing `sfx` bus, which bypasses the phonograph filter and the jaw analyser.

## Testing

- Python: every variant is requested, with the loop flag only for the whir and the ball. A rerun requests only missing clips. A permission error stops after one request. Stale clips are ignored and pruned. The committed clips are advertised and served.
- JS: `pickVariant` never repeats back to back.
- Manual: wake (creak + grind), coin, consult (whir loop; ball swells), glitch (grind), end of reading (ratchet), sleep (ball fades out).
