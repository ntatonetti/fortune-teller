# Madame Mechanika, the Clockwork Oracle

An AI fortune-teller booth for a Halloween party. A projected 1920s carnival automaton sleeps behind the glass until someone walks up. Then she creaks awake, notices their costume, takes payment (a pirate's gold coin, or a whispered secret), listens to the question they bring to the fates, and answers it with a fortune about *them*. At the end a receipt printer spits out a fortune ticket.

The body is deliberately mechanical: the head, eyes, and lids move on a choppy 12 fps "servo" tick, and the jaw is a ventriloquist-dummy hinge driven by the loudness of her voice. The words are not mechanical at all, because Claude is looking at the guest through the camera. That mismatch is the uncanny part.

- **Adults** get spooky, wry, PG-13 readings, sometimes with a mid-sentence mechanical seizure. She remembers earlier guests by costume and weaves them in ("Beware the pirate...").
- **Kids**: if Claude sees a child (or isn't sure), she becomes a twinkly grandmother: whimsical, warm, nothing scary. Once a child is seen at the greeting, the whole reading stays in kid mode.
- She only ever remarks on costumes, props, colors and vibe. She never comments on bodies, age, looks or ethnicity.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./scripts/fetch_vendor.sh          # face-detection runtime, so the booth works offline
cp .env.example .env               # then fill in keys (all optional)
.venv/bin/python -m server
```

Open **http://localhost:8000** in Chrome. Pick the camera, click **Awaken the Oracle**, and press **H** for the key list.

With no keys at all she still runs, using canned fortunes and the built-in macOS "Grandma" voice. That's handy for testing and is also the automatic fallback if the party Wi-Fi drops.

### How a reading goes

1. **Asleep:** she's slumped over with a music box playing. If someone lingers at a distance, one eye cracks open and follows them, and now and then she calls "Is someone there? Come closer..."
2. **Wake:** when a face comes close enough for about a second, her gears grind, she sits up, and she greets them by their costume. She also works out whether a child is present.
3. **Payment:** "A pirate's gold coin, if you have one... drop it in and press the button. If your pockets are empty... whisper me a secret instead."
   - A button press counts as a coin.
   - Two or more spoken words count as a secret. The secret is never saved or sent anywhere, only the fact that one was told, and the screen shows it only as dots.
4. **Question:** "Now... ask the fates your question." A bell rings, and she listens until they pause, up to 14 seconds. Pressing the button means "that's my question." If they stay silent, she answers "the question you hold in your heart."
5. **Consult:** the gears spin and the ball swirls. Adults see her eyes roll back; kids see her peer into the ball.
6. **Fortune:** she answers their question, weaving in their costume, an omen, a lucky number, and a task for the party. The card prints with "You asked: ..." on it. Then she slumps back to sleep, and won't wake again until that person steps away.

**Walking away:** if every face disappears from the camera for 8 seconds at any point in a reading, she stops mid-sentence, grumbles ("Hmph. Gone without a word..."), and goes back to sleep. If they leave during the fortune, no ticket prints. This only applies once the camera has actually seen the guest, so a dark booth where face detection struggles never cuts a real reading short. Pressing the button or speaking also counts as "still here". **J / K** adjust the 8 seconds, and **D** shows the countdown.

**Listening** uses Chrome's built-in speech recognition, which needs internet but no extra keys. She only listens while she's silent, so she never hears herself. macOS uses the system microphone, so set the input to your webcam's mic, or better, a small USB mic near the glass, in System Settings → Sound → Input. If the party is too loud, the operator can press **/** and type what the guest said. **L** turns listening off, and then she just takes coins and skips the question.

**Keeping her fresh:** every stock line has two or three wordings and never repeats back to back. Each fortune gets a lucky number she hasn't used recently and a random sign to read from (a tarot card, tea leaves, a raven, a cracked mirror and so on), with gentler options for kids. She's also told her recent greetings and fortunes, so she avoids reusing their openings, omens and tasks.

**Steering her:** open **http://localhost:8000/steer.html** in another tab, or on your phone, to whisper her stage directions the guests can't hear. **Next guest** is used for one reading and then cleared, and the page shows which costume it went to: "This is Sam, it's her birthday," or "Tell him to ask Priya to dance." **All night** stays until you change it: "The costume contest is at 9, nudge people to enter." She weaves them into her greeting and fortune, and her safety rules and kid mode still come first. Notes live in memory only and are gone when the server restarts. They need Claude; the canned fortunes ignore them. To reach the page from a phone, start the server with `HOST=0.0.0.0` and open `http://<laptop's IP>:8000/steer.html` on the same Wi-Fi. Anyone on that Wi-Fi can open it, so keep the address to yourself.

### Try it without any hardware

- Walk up to the laptop camera. She wakes when your face is close enough, and **[** / **]** adjust how close that is. **D** shows what the camera sees, with face boxes: yellow means seen, green means close enough to wake her.
- **Space** is the gold coin. **W** wakes her manually. Talk when she asks for a secret or a question; Chrome asks for mic permission once, when you click Awaken.
- **A** forces adult or child mode, and **G** makes the next adult reading glitch.
- Printed tickets show up in the server terminal until a real printer is connected.

## Keys and voices

**Claude:** create an API key at console.anthropic.com and set `ANTHROPIC_API_KEY`. The default model is `claude-opus-5-5` at low effort. If greetings feel slow, try `CLAUDE_MODEL=claude-haiku-5-5`. A reading is two calls (greeting and fortune), each with one camera frame, which comes to a few cents per guest on Opus.

**ElevenLabs:**
1. Sign up at elevenlabs.io. Under Developers → API Keys, create a key and set it as `ELEVENLABS_API_KEY`.
2. Open the Voice Library and search for things like *old witch*, *fortune teller*, *grandmother storyteller*, *raspy*, or *Transylvanian*. Add one you like to your voices.
3. Open the voice, choose "..." → **Copy voice ID**, and set `ELEVENLABS_VOICE_ID`.

Each reading is about 500–700 characters of speech. Check that your plan's monthly character quota covers your guest count. The fixed lines are rendered once and cached in `data/tts_cache/`.

Her machine sounds (the creaks, grinding gears, the whir while she consults, the coin drop, the ticket ratchet, and the crystal ball's sparkly hum, which follows its glow while she's awake) are real ElevenLabs sound effects, committed in `static/sfx/`, so the booth never generates them at party time. To remake them, edit the prompts in `server/sfx.py` (or delete a file) and run `.venv/bin/python scripts/make_sfx.py`. That script only requests missing clips and removes clips from old prompts. Then commit `static/sfx/`. The key needs the **Sound Effects** permission as well as Text to Speech (Developers → API Keys → edit the key). Any sound without a clip uses the built-in synthesized version.

The voice is pushed through a phonograph filter in the browser (band-limited, slightly overdriven, wobbly, crackly), so a clean voice ends up sounding like a worn record.

## The booth

- **Projector:** rear-project onto a sheet or frosted shower curtain stretched inside a cardboard cabinet front. Use the projector's "rear" mode, or press **M** to mirror the image. Everything around her is near-black, so only she glows. Keep the area dim.
- **Camera:** a USB webcam at about eye height near the "glass," aimed at where guests stand. Put a small warm light on the guest's face. That matters more than the webcam model in a dark backyard. If her eyes follow people the wrong way, press **I**.
- **Speaker:** wired (3.5 mm). Bluetooth delay makes the jaw flap ahead of the voice.
- **Button:** a big arcade button on a "zero delay" USB encoder shows up as a gamepad, and any button on any gamepad counts as a coin. No driver needed. Put a treasure chest or slot box next to it for the gold coins. For a real coin drop, mount a microswitch with a lever inside the slot so a falling coin trips it, and wire it to a second input on the same encoder. Press **B** if you'd rather she start automatically after the invite.
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
5. Press **C** or **Esc** when done. The alignment is saved in the browser automatically.

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

Camera frames go to Claude for the reading and are never saved. Guests' questions go to Claude so she can answer them, and are printed on their card, but they're not stored. Whispered secrets never leave the browser at all. The only thing kept is a one-line costume description per guest in `data/guests.json` (for example "a witch with a crooked broom"), so she can reference earlier guests. To wipe it, press **Esc** for the setup screen and click **Forget everyone**; do this right before the party. You can also run `curl -X DELETE localhost:8000/api/guests` or delete the file. Entries older than 12 hours are forgotten automatically, which you can change with `MEMORY_MAX_AGE_H` in `.env`, so test runs from earlier in the week won't show up. A sign that says "THE ORACLE SEES YOU" is both fun and fair warning.

## Development

```bash
.venv/bin/python -m pytest -q        # server tests (no network, no keys needed)
node --test tests/js/*.test.mjs      # projection-mapping math
PLAYWRIGHT_BROWSERS_PATH=.venv/ms-playwright .venv/bin/playwright install chromium   # once
.venv/bin/python scripts/smoke.py    # drives a full reading in headless Chrome, saves screenshots
HEAD=1 .venv/bin/python scripts/smoke.py   # same in head mode, plus the alignment screen
WALKAWAY=1 .venv/bin/python scripts/smoke.py   # guest leaves mid-reading (WALKAWAY=speak: mid-fortune)
```

Layout:
- `server/oracle.py`: persona, safety rules, and Claude calls
- `server/steer.py`, `static/steer.html`: the keeper's whispered stage directions
- `server/voice.py`: ElevenLabs or `say`, plus the cache
- `server/printer.py`: fortune cards
- `static/js/puppet.js`: the automaton drawing, in screen and head modes
- `static/js/headmap.js`, `static/js/homography.js`: head-mode surfaces, corner-pin warp and alignment
- `static/js/sound.js`: synthesized sound effects and the phonograph chain
- `static/js/watcher.js`: camera and face detection
- `static/js/main.js`: the state machine that runs each reading
