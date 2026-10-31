# Madame Mechanika, the Clockwork Oracle

An AI fortune-teller booth for a Halloween party. A projected 1920s carnival automaton sleeps behind the glass until someone walks up. Then she creaks awake, notices their costume, takes payment (a pirate's gold coin, or a whispered secret), listens to the question they bring to the fates, asks them one back, has them draw three tarot cards in her crystal ball, and reads the cards as a fortune about *them*. At the end a receipt printer spits out a fortune ticket.

She is a photograph of a grandmother at her table: crystal ball, cards, candles, marionette seams down her chin. The face is deliberately mechanical: her eyes and mouth change between still frames on a choppy 12 fps "servo" tick, the mouth opening wider the louder her voice, and her head never moves (she can be projected onto a mannequin's head): asleep, her light is just turned down. The words are not mechanical at all, because Claude is looking at the guest through the camera. That mismatch is the uncanny part.

- **Adults** get spooky, wry, PG-13 readings, sometimes with a mid-sentence mechanical seizure. She remembers earlier guests by costume and weaves them in ("Beware the pirate...").
- **Kids**: if Claude sees a child (or isn't sure), she becomes a twinkly grandmother: whimsical, warm, nothing scary. Once a child is seen at the greeting, the whole reading stays in kid mode.
- She only ever remarks on costumes, props, colors and vibe. She never comments on bodies, age, looks or ethnicity.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env               # then fill in the Claude and ElevenLabs keys
.venv/bin/python -m server
```

Open **http://localhost:8000** in Chrome. Pick the camera, click **Awaken the Oracle**, and press **H** for the key list.

She needs the internet: Claude for every word she says about a guest, ElevenLabs for her voice, Chrome's speech recognition for her ears, and the face-detection runtime, which loads from a CDN. The server won't start without the keys. If a call fails mid-party she skips the greeting, or says "the spirits are silent" instead of a fortune.

### How a reading goes

1. **Asleep:** her face dims like a turned-down gas lamp, with a music box playing; she stays upright with her eyes open. While no one is about she talks in her sleep about a fifth of the time (`SLEEP_TALK`): half-sense nonsense ("Who left the moon in the ticket slot...") or, half the time (`SLEEP_MUMBLE`), a muffled murmur with no words in it. She hushes the moment anyone appears. If someone lingers at a distance, her eyes follow them, and now and then she calls "Is someone there? Come closer..."
2. **Wake:** when a face comes close enough for about a second, her gears grind, she sits up, and she greets them by their costume. She also works out whether a child is present, unless `AUDIENCE` on the setup screen says so outright: `child` gives every guest a child's reading, `adult` every guest a grown-up's (**A** at the booth cycles auto, adults only, kids only).
3. **Payment:** "A pirate's gold coin, if you have one... hold it up to the glass, so I can see it shine. If your pockets are empty... whisper me a secret instead."
   - A coin shown to the camera, or dropped in the cup, pays. While she waits, a small Claude model (`COIN_MODEL`, Haiku) looks at the camera every 1.5 s (`COIN_LOOK_EVERY_S`). When it sees a coin in someone's hand, or someone reaching forward as if to drop one in (it errs on the generous side), she says "Ahh... real pirate gold. Into the cup it goes." She gives it 2.5 s (`COIN_CUP_S`) to land, then a clink plays. No coin hardware is needed: the cup is only a prop.
   - A button press (or Space) still counts as a coin, for when the camera misses it.
   - Grown-ups only: two or more spoken words count as a secret. Kids pay with a coin. The secret is never saved or sent anywhere, only the fact that one was told, and the screen shows it only as dots.
4. **Question:** "Now... ask the fates your question." A bell rings, and she listens patiently, because kids especially stop mid-sentence, say "um", or turn to ask a parent what to ask. A pause only counts once it's long enough: about 2 seconds for adults and 3 for kids, plus 2.5 more if they've said fewer than three words or stopped on a word like "and", "um" or "will". While the camera sees them turned away, or can't see their face at all, the clock stops. At each pause a quick Claude check (Haiku) decides whether they've actually finished asking. If not, she waits up to 6 more seconds for the rest. She gives up after 30 seconds in all. Pressing the button means "that's my question." If they stay silent, she answers "the question you hold in your heart."
5. **A conversation or the cards** (adults only): kids go straight to their fortune. Each adult reading is, at random, one of these (whichever are on):
   - **Her question back** (`FOLLOW_UP`): she asks them one question to draw them out ("Is this a matter of the heart... or of coin?"). Claude (`CHAT_MODEL`, Haiku by default) writes it from their question and costume while she reacts to the question, so there's hardly a pause. She listens to the answer as patiently as to the question (the same pauses, and a Claude check that they've finished answering), and the button means "that's my answer".
   - **The cards** (`TAROT`): "Now... the cards. Your past, your present, your future..." Tarot cards shuffle through her crystal ball (the 1909 Rider-Waite-Smith deck, public domain, in `static/img/tarot/`), and the card showing when they say "stop" (or "this one", "now", "that's it") is theirs. Other words don't count, so friends chatting nearby don't stop the cards. They stop `CARDS` cards (3 by default, at most 5) in quick succession: each one shows a moment with its place ("past: The Tower", `CARD_HOLD_S`), then the deck shuffles again for the next. Without a working mic each card picks itself after a moment, and nobody choosing within `DRAW_WAIT_S` makes the card showing theirs.
6. **Consult:** the gears spin and the ball swirls. Adults see her eyes roll back; kids see her peer into the ball. Meanwhile, for adults, the guest's own face, caught by the camera and toned like an old spirit photograph, flickers up three times (`FACE_FLICKERS` in `.env`), solid at `FLICKER_OPACITY=1` or half mist at 0.5. `FLICKER_WHERE` (a dropdown on the setup screen) puts it in her crystal ball (`ball`, the default) or over her own face (`face`, warped so their eyes, nose and mouth land on hers). Kids see it too with `KID_FLICKER=true`. If she has a mechanical seizure later, their face stutters again.
7. **Fortune:** with the cards, once all are drawn she reads them one at a time (past, present, future, each with a playful reveal), each card back in her ball as she speaks of it, then draws them together to answer their question, with what they told her, their costume, a lucky number and a task for the party. Without them, she reads one fortune from a random omen. The card prints with "You asked: ..." and the three cards on it. Then her light dims again. That guest won't wake her again until they've stepped away, but the next person does at once, even while the last one is still standing there: she follows the last guest by where they stand and their costume's colours (`SAME_GUEST`; **D** shows how alike the face in front of her is).

**Waking with a start:** about a third of the time (`WAKE_STARTLE`) she snorts awake, looks about dazed for a moment (`WAKE_DAZED_S`), and mutters ("Wh... where... what year is it?") before she finds the guest.

**Settings:** everything that changes how she behaves (her name, the Claude model and effort, her voice, her memory, the face flicker, her looks, and every pause, wait and transition above, in seconds) is listed on the setup screen with its value and what it does, and can be edited there. Models, efforts and the voice model are dropdowns. Numbers have a slider over their usual span and a box to type the number in, which can go past the slider. **Awaken the Oracle** saves the edits into `.env` and reloads every setting, including edits made to `.env` by hand, so no restart is needed. `.env.example` lists them too.

**Voices:** the setup screen lists her voices; press **Hear** to listen to one and **Use this voice** to give it to her; the one she uses is marked **In use**. Add a voice with a name and its ElevenLabs voice ID, or remove one; they're kept in `.env` as `VOICES`. The voice she has is always in the list; remove it and she takes the first one left. When you awaken her in a new voice, it's tried first (she won't start in a voice ElevenLabs refuses) and all her stock lines are voiced again in it, which takes a few seconds the first time.

**Her looks:** her photographed eyes follow what she's doing. She looks left, right, up or down when her gaze goes past `LOOK_SIDE`, and glances away now and then while awake (`GLANCE_MIN_S` to `GLANCE_MAX_S`, held for `GLANCE_S`). Her brows go up when she wakes and greets them, her eyes roll back in a trance while she consults an adult (kids see her look down into the ball), and her lids hang half shut when she's startled awake. Her mouth opens no wider than `MOUTH_OPEN` (default 2, the drop to her teeth); the full drop runs off the foam head.

**Walking away:** if every face disappears from the camera for 8 seconds at any point in a reading, she stops mid-sentence, grumbles ("Hmph. Gone without a word..."), and goes back to sleep. If they leave during the fortune, no ticket prints. This only applies once the camera has actually seen the guest, so a dark booth where face detection struggles never cuts a real reading short. Pressing the button or speaking also counts as "still here". **J / K** adjust the 8 seconds, and **D** shows the countdown.

**Listening** uses Chrome's built-in speech recognition, which needs internet but no extra keys. She only listens while she's silent, so she never hears herself. macOS uses the system microphone, so set the input to your webcam's mic, or better, a small USB mic near the glass, in System Settings → Sound → Input. If the party is too loud, the operator can press **/** and type what the guest said. **L** turns listening off, and then she just takes coins and skips the question.

**Keeping her fresh:** every stock line has two or three wordings and never repeats back to back. Each fortune gets a lucky number she hasn't used recently and a random sign to read from (a tarot card, tea leaves, a raven, a cracked mirror and so on), with gentler options for kids. She's also told her recent greetings and fortunes, so she avoids reusing their openings, omens and tasks.

**Her signature lines:** `server/phrases.py` holds wording we wrote for her ("Hold still... the gears are turning for you.", "Go now... before the clockwork changes its mind."). Each greeting is offered three greeting lines and uses one if it fits. Each fortune is offered a few lines for two of its three places (opening, middle, close) and works in two, writing the rest itself. Kids only get the kid lines. Every line has odds in front of it, e.g. `(3, "Mark me well...")`: a 3 is offered three times as often as a 1, and 0 turns a line off. Our classic lines start at 3 and the crazier ones at 1. To change how she talks, edit the lines or their odds and restart the server.

### Try it without any hardware

- Walk up to the laptop camera. She wakes when your face is close enough, and **[** / **]** adjust how close that is. **D** shows what the camera sees, with face boxes: yellow means seen, green means close enough to wake her. It also shows how far the nearest head is turned; past 0.3 it reads AWAY, and while she's waiting for a question that stops her pause clock.
- **Space** is the gold coin. **W** wakes her manually. Talk when she asks for a secret or a question; Chrome asks for mic permission once, when you click Awaken.
- **A** cycles `AUDIENCE`: auto, adults only, kids only (saved to `.env`). **G** makes the next adult reading glitch.
- To test the guest's side without sitting through her full readings, open **http://localhost:8000/?brief**. Her greeting and fortune are then capped at 20 words (`?brief=30` for 30). Her fixed lines and all the timings stay the same. The setting is never saved, so a plain page load is always the full reading.
- Printed tickets show up in the server terminal until a real printer is connected.

## Keys and voices

**Claude:** create an API key at console.anthropic.com and set `ANTHROPIC_API_KEY`. The default model is `claude-opus-5-5` at low effort. If greetings feel slow, try `CLAUDE_MODEL=claude-haiku-5-5`. A reading is two calls (greeting and fortune), each with one camera frame, which comes to a few cents per guest on Opus, plus tiny Haiku calls (no image): one at each pause while they ask or answer, and one for each question she asks them back.

**ElevenLabs:**
1. Sign up at elevenlabs.io. Under Developers → API Keys, create a key and set it as `ELEVENLABS_API_KEY`.
2. Open the Voice Library and search for things like *old witch*, *fortune teller*, *grandmother storyteller*, *raspy*, or *Transylvanian*. Add one you like to your voices.
3. Open the voice, choose "..." → **Copy voice ID**, and set `ELEVENLABS_VOICE_ID`. Add more voices on the setup screen to switch between them.

Each reading is about 500–700 characters of speech. Check that your plan's monthly character quota covers your guest count. The fixed lines are rendered once and cached in `data/tts_cache/`.

Her machine sounds (the creaks, grinding gears, the whir while she consults, the coin drop, the ticket ratchet, and the crystal ball's sparkly hum, which follows its glow while she's awake) are real ElevenLabs sound effects, committed in `static/sfx/`, so the booth never generates them at party time. To remake them, edit the prompts in `server/sfx.py` (or delete a file) and run `.venv/bin/python scripts/make_sfx.py`. That script only requests missing clips and removes clips from old prompts. Then commit `static/sfx/`. The key needs the **Sound Effects** permission as well as Text to Speech (Developers → API Keys → edit the key). Any sound without a clip uses the built-in synthesized version.

The voice is pushed through a phonograph filter in the browser (band-limited, slightly overdriven, wobbly, crackly), so a clean voice ends up sounding like a worn record.

## The booth

- **Projector:** rear-project onto a sheet or frosted shower curtain stretched inside a cardboard cabinet front. Use the projector's "rear" mode, or press **M** to mirror the image. Everything around her is near-black, so only she glows. Keep the area dim. To show only her face and crystal ball, floating in the dark, set `BACKGROUND` to false on the setup screen.
- **Camera:** a USB webcam at about eye height near the "glass," aimed at where guests stand. Put a small warm light on the guest's face. That matters more than the webcam model in a dark backyard. If her eyes follow people the wrong way, press **I**.
- **Speaker:** wired (3.5 mm). Bluetooth delay makes the jaw flap ahead of the voice.
- **Button:** a big arcade button on a "zero delay" USB encoder shows up as a gamepad, and any button on any gamepad counts as a coin. No driver needed. She sees coins held up to the camera, so the button is only a backup. Put a cup or treasure chest by the glass for the coins. Press **B** if you'd rather she start automatically after the invite.
- **Printer** (USB ESC/POS thermal):
  ```bash
  brew install libusb
  system_profiler SPUSBHostDataType   # note the printer's Vendor ID and Product ID (SPUSBDataType on older macOS)
  ```
  Then in `.env` set `PRINTER=usb`, `PRINTER_USB_VENDOR=0x....`, `PRINTER_USB_PRODUCT=0x....`, and `PRINTER_WIDTH_CHARS` (32 for 58 mm paper, 48 for 80 mm). The NetumScan NS8360 shows up as "POS80 Printer USB" with `0x0416` / `0x5011` and takes 48. If the printer doesn't appear, check it's switched on. Curly quotes, dashes and "…" print as plain ASCII, since thermal codepages don't have them. If the printer jams or is unplugged, the show carries on without the card.

## Head mode: projecting onto a foam head

This is the Haunted Mansion "Madame Leota" trick. Instead of a picture on a sheet, only her face is projected onto a blank foam head, and the crystal-ball mist onto a frosted glass globe below it. The real 3D shape (nose, eye sockets, cheeks) makes it read as a solid porcelain head with a living face. Switch modes with **V**, or pick "Foam head" on the setup screen. The screen mode stays available as a fallback.

**Build it**
1. Paint the foam head with water-based gesso: 2–3 thin coats with a foam brush, letting each dry. **Spray paint melts styrofoam.**
2. Push a dowel up through the neck into a weighted base, so the face is at about a seated person's eye level. Put a turban or scarf over the top of the head and a shawl over a box below it for shoulders. Hang black fabric about a foot or more behind.
3. Set the frosted globe opening-down on a candle holder just below the head, with dark cloth around the base.
4. Keep the area as dark as possible. Any nearby light washes the face out.

**Nebula Mars 3 Air settings** (1080p, 400 ANSI lumens, throw ratio 1.2:1)
- **Distance:** about 1.2 m from the head gives a 1.0 m × 0.56 m image. That fits the head with the globe below it, at roughly 290 px across the face. Closer is sharper, but at 1.0 m the image is only 47 cm tall.
- **Placement:** aim as straight at the face as you can, within about 15–20°. Above the guests' heads, angled down, avoids shadows.
- **Turn off automatic adjustments** under *Settings → Projector*: auto keystone (startup and after movement), "Auto Focus After Movement", and obstacle avoidance or screen fit. Otherwise someone bumping the table, or walking in front, re-warps the image and ruins the alignment. Focus once by hand. Leave the projector's own keystone at zero and do all warping in the alignment tool, so you keep full resolution.
- **Projector mode:** *Front* for the head, *Rear* for the sheet. The projector's Rear mode makes the **M** key unnecessary.
- **Power:** plug it in. On battery, Auto mode drops to Eco, which is dimmer.
- **Connection:** HDMI in. Use a USB-C to HDMI adapter if your Mac has no HDMI port. Mirroring the displays is easiest, so you can drag the alignment dots on the laptop and watch them move on the head.

**Align it** by pressing **C** in head mode, with her held awake and her mouth opening and closing.
1. Drag the dashed center dot of the FACE surface onto the head, and use **+ / −** to size it.
2. Drag the four corner dots to warp the face until it sits on the foam. This corrects the projector's angle.
3. Press **P** for crosshairs, then line up the features: **J/K** eye spacing, **U/N** eye height, **T/Y** eye size, **I/M** mouth height. Put the irises in the sculpted eyes and the lips on the lips.
4. Press **Tab** to switch to the BALL surface, and fit its circle to the globe.
5. **Tab** on to the BACKGROUND surface, the big frame behind the other two. It shows her room (the rest of her photograph: table, cards, candles) on the backdrop behind the head. Move, size and warp it like the others. **[ / ]** make it darker or brighter. Press **B** to turn it off, so only her face and the globe are lit (saved as `BACKGROUND`, the same setting as on the setup screen).
6. Press **C** or **Esc** when done. The alignment is saved in the browser automatically.

In head mode the marquee and subtitles are off, because the projector should only light her. **S** turns subtitles back on if you put a white card under her for them. Asleep, her face dims like a turned-down gas lamp, and it sputters up to full brightness when she wakes.

### Shopping list (checked on Amazon, Oct 27)

| Item | Pick | ~Price |
|---|---|---|
| Webcam | Logitech C270 (B004FHO5Y6), or C920x (B085TFF7M1) for better low light | $21 / $70 |
| Button | EG STARTS 100 mm dome (B071FSKY6Q). Its LED needs 12 V, but the switch works on the encoder | $13 |
| Encoder | Reyann Zero Delay USB encoder (B00UUROWWK). It has 4.8 mm terminals, which match the button | $13 |
| Speaker | Anker Soundcore 2 with AUX in (B01MTB55WH) | $30 |
| Printer | symcode 58 mm USB ESC/POS (B06XW8MK6W), or NetumScan 80 mm with cutter (B0D2Q1PHP4) | $46 / $59 |
| Paper | MUNBYN 58 mm 50-pack (B08RRZT2JL) | $20 |
| USB-C hub | Anker 4-port USB-A (B0CCDZWH5H) | $10 |
| Face light | USB dimmable mini spotlight (B0DF74Z9SN) | $10 |
| Foam head | SHANY styrofoam mannequin head (B0CL5LZ22X) | $15 |
| Head paint | Liquitex Basics acrylic gesso, 16 oz (B000KNDMLG); water-based, so foam-safe | $14 |
| Brushes | Foam brush set, 24 pcs (B09YRGFBXD) | $7 |
| Crystal ball | BOKT frosted matte opal glass globe, 5.9" (B08SVVG2L4) | $24 |

## Privacy

Camera frames go to Claude for the reading and are never saved. Guests' questions, and their answers to hers, go to Claude so she can answer them, and the question is printed on their card. They're kept only in her history on this machine (`data/history/`, one file per day, browsable at /history.html), with every other Claude call and never a camera frame; delete those files to wipe it. Whispered secrets never leave the browser at all, and neither does the picture of the guest's face that flickers in her ball or over her face; it's forgotten when she goes back to sleep. The only thing kept is a one-line costume description per guest in `data/guests.json` (for example "a witch with a crooked broom"), so she can reference earlier guests. To wipe it, press **Esc** for the setup screen and click **Forget everyone**; do this right before the party. You can also run `curl -X DELETE localhost:8000/api/guests` or delete the file. Entries older than 12 hours are forgotten automatically, which you can change with `MEMORY_MAX_AGE_H` in `.env`, so test runs from earlier in the week won't show up. A sign that says "THE ORACLE SEES YOU" is both fun and fair warning.

## Development

```bash
.venv/bin/python -m pytest -q        # server tests (no network, no keys needed)
node --test tests/js/*.test.mjs      # projection-mapping math, sounds, and patient listening
PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/bin/playwright install chromium   # once
.venv/bin/python scripts/smoke.py    # drives a full reading in headless Chrome, saves screenshots
HEAD=1 .venv/bin/python scripts/smoke.py   # same in head mode, plus the alignment screen
WALKAWAY=1 .venv/bin/python scripts/smoke.py   # guest leaves mid-reading (WALKAWAY=speak: mid-fortune)
```

Layout:
- `server/oracle.py`: persona, safety rules, and Claude calls
- `server/phrases.py`: her signature lines, for Claude to choose from
- `server/voice.py`: ElevenLabs, plus the cache
- `server/printer.py`: fortune cards
- `static/js/puppet.js`: the automaton drawing, in screen and head modes
- `static/js/portrait.js` and `static/img/mechanika/`: her photograph. Every frame is an edit of `base.png` that changes only her face, so its eyes, brows or mouth can be laid over the base: `blink`, `eyes-half`, `look-left`, `look-right`, `look-up`, `look-down` and `trance` for her eyes, `brows-up`, and `mouth-1` to `mouth-3`. (`asleep` and `asleep-peek` aren't used: asleep, she is only dimmed.) Without these files she falls back to the drawn porcelain doll. `forehead.png` is laid over every frame: forehead skin painted over her pendant and the hair above her temples, so only her face lands on the foam head. Rerun `.venv/bin/python scripts/clean_forehead.py` if `base.png` changes, or pass it a copy of `base.png` cleaned up by an image model to use that instead. `static/js/mechanika-mesh.js` holds her face-mesh points (from `scripts/measure_face.py`), for warping a guest's face onto hers with `FLICKER_WHERE=face`.
- `static/js/headmap.js`, `static/js/homography.js`: head-mode surfaces, corner-pin warp and alignment
- `static/js/sound.js`: synthesized sound effects and the phonograph chain
- `static/js/watcher.js`: camera and face detection
- `static/js/main.js`: the state machine that runs each reading
