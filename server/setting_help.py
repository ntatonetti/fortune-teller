"""The longer story of each setting, for the start screen: what it changes,
when to touch it, and an example. Keyed by env name; every setting has one."""

HELP: dict[str, tuple[str, str]] = {
    # Her
    "ORACLE_NAME": (
        "The name she gives herself. It heads the screen, the top of every printed ticket, and Claude is told it's her name, so she may say it.",
        "Madame Mechanika, or Zoltara for a different booth",
    ),
    # Her mind
    "CLAUDE_MODEL": (
        "The Claude model that looks through the camera and writes everything she says about a guest: the greeting and the fortune. Bigger models notice more and write better; smaller ones answer faster.",
        "claude-opus-5-5 for the best readings; claude-haiku-5-5 if guests wait too long for her to speak",
    ),
    "GREET_EFFORT": (
        "How long Claude may think before greeting someone. More effort means a sharper first line but a longer silence after she wakes, so keep it low: the greeting should come quickly.",
        "low: she greets about a second after waking",
    ),
    "FORTUNE_EFFORT": (
        "How long Claude may think over the fortune. The fortune is the main event and she is already consulting her ball, so a pause is part of the show. More effort gives more specific, better-built fortunes.",
        "high: richer fortunes, a few more seconds of consulting",
    ),
    "GREET_TIMEOUT_S": (
        "If Claude hasn't sent the greeting back by then, she skips it and goes straight on to asking for payment, so a slow network never leaves a guest staring at a silent face.",
        "8: on a slow connection, raise it to 12",
    ),
    "FORTUNE_TIMEOUT_S": (
        "If the fortune hasn't come back by then, she gives up and says the spirits are silent, and the guest can press again. Set it longer than a typical fortune at your FORTUNE_EFFORT.",
        "20; if \"the spirits are silent\" comes up often, raise it to 30",
    ),
    "ASKED_MODEL": (
        "A small, fast Claude model that listens while a guest asks their question and decides whether they've finished or are only pausing. If they aren't done, she keeps listening for QUESTION_MORE_S longer. It runs every time they pause, so it should be quick.",
        "claude-haiku-5-5",
    ),
    "ASKED_TIMEOUT_S": (
        "How long she waits for that finished-or-not judgement. Past this she assumes they're done and moves on.",
        "4: she never waits more than 4 s on it",
    ),
    # Her voice
    "ELEVENLABS_VOICE_ID": (
        "The ElevenLabs voice she speaks in. Choose it from the list below with Use this voice. Switching voices re-records all her stock lines when you awaken her, which takes a few seconds and uses ElevenLabs credits.",
        "pick \"Original\" in the list below",
    ),
    "VOICES": (
        "Your shortlist of voices to choose between, as name and ElevenLabs voice ID. Find voices in the ElevenLabs Voice Library, open one, choose \"...\" and Copy voice ID. Hear plays a sample line in that voice.",
        "Witch=AbC123xyz456DEF789gh",
    ),
    "ELEVENLABS_MODEL": (
        "How ElevenLabs turns her words into speech. flash and turbo are fast and a little synthetic, which is what makes her sound eerie through the phonograph filter. v3 and v4 sound like a real actor: smoother, more natural, less creepy, and slower. Changing it re-records her stock lines.",
        "eleven_flash_v2_5 for the uncanny automaton; eleven_v4 for a natural voice",
    ),
    # Her memory
    "MEMORY_RECALL": (
        "How many of tonight's earlier guests (text descriptions of their costumes, never pictures) Claude is shown with each reading, so she can mention them: \"another pirate came by earlier...\". More means more callbacks but a longer, slower request. 0 turns her memory off.",
        "15: she can refer back to the last 15 guests",
    ),
    "MEMORY_MAX_AGE_H": (
        "Guests older than this are forgotten, so last night's party doesn't leak into tonight's. Forget everyone, on this screen, clears them all at once.",
        "12: a party that starts at 7 pm is forgotten by 7 am",
    ),
    # The guest's face in hers
    "FLICKER_WHERE": (
        "Where the guest's own face flashes up while she consults. ball: inside her crystal ball, like a vision. face: over her face, as if she becomes them for a moment.",
        "ball when projecting onto the foam head and globe",
    ),
    "FACE_FLICKERS": (
        "How many times their face flashes up during the consult. Each flash lasts GLIMPSE_MIN_S to GLIMPSE_MAX_S. 0 turns it off.",
        "3: three quick glimpses while she gazes into the ball",
    ),
    "FLICKER_OPACITY": (
        "How solid their face is when it flashes up. 1 is fully solid; lower values are see-through, like mist.",
        "0.5: a ghostly half-face",
    ),
    "KID_FLICKER": (
        "Whether children see their own face flicker up too. It's off by default because it can scare younger kids.",
        "off for a family party; on for an older crowd",
    ),
    # Sleep and waking
    "WAKE_HOLD_S": (
        "Someone must stand close enough (the wake distance, set with [ and ] at the booth) for this long before she wakes. Too short and passers-by wake her; too long and guests wonder whether she's on.",
        "0.7: a brief stop in front of her is enough",
    ),
    "WAKE_PAUSE_S": (
        "After waking, she looks at the guest for at least this long before greeting, which feels deliberate rather than instant. The greeting itself is being written meanwhile.",
        "1.9",
    ),
    "DIM_S": (
        "How long her light takes to fade as she falls asleep, or to come up as she wakes.",
        "0.9: a slow, theatrical fade",
    ),
    "FALL_ASLEEP_S": (
        "After her farewell, how long until she's fully asleep and can be woken again.",
        "1.6",
    ),
    "REWAKE_GONE_S": (
        "After a reading she ignores the guest who just had it, but a new face wakes her straight away. Once that last guest has been out of sight this long they're forgotten, so even they can wake her again.",
        "2.5: step away for a few seconds and come back for another reading",
    ),
    "REWAKE_ANYWAY_S": (
        "If the last guest just stands there after their reading, she greets them again after this long, as if they were new.",
        "30; lower it to 10 if lingering guests should get another go sooner",
    ),
    "SAME_GUEST": (
        "How she tells the guest who just left from someone new: by how alike the colours of their costume are (0 to 1). If she greets the person who just finished, lower it. If she ignores the next person in line, raise it. The debug view (D) shows the \"alike\" number live.",
        "0.6; two guests in similar black costumes may need 0.8",
    ),
    "PEEK_AFTER_S": (
        "Someone hanging around, too far away to wake her: after this long her eyes start following them while she stays asleep.",
        "2.5",
    ),
    "BECKON_AFTER_S": (
        "Someone still lingering out of range after this long: she calls them over (\"come into the light...\").",
        "7",
    ),
    "BECKON_EVERY_S": (
        "At most one call-over in this long, so a crowd nearby doesn't make her call out nonstop.",
        "60: at most one call-over a minute",
    ),
    "BLINK_MIN_S": (
        "While awake she blinks at random, never sooner than this after the last blink.",
        "2.5",
    ),
    "BLINK_MAX_S": (
        "And never later than this.",
        "7.5: between 2.5 and 7.5 s apart, like a person",
    ),
    "BLINK_S": (
        "How long her eyes stay shut in each blink.",
        "0.17 is a natural blink; 0.4 looks sleepy",
    ),
    "SLEEP_TALK": (
        "While she sleeps with no one around, the share of the time she mutters in her sleep (nonsense lines about moths, clocks and spoons). 0 means she sleeps silently.",
        "0.2: talking about a fifth of the time",
    ),
    "SLEEP_MUMBLE": (
        "Of that sleep talk, the share that's muffled into an unintelligible murmur rather than clear words.",
        "0.5: half murmurs, half words you can make out",
    ),
    "WAKE_STARTLE": (
        "The share of wakings where she snorts awake, startled and dazed, instead of waking calmly.",
        "0.35: about one waking in three",
    ),
    "WAKE_DAZED_S": (
        "After a startled waking, how long she looks around, dazed, before greeting.",
        "1.6",
    ),
    # Her looks
    "LOOK_SIDE": (
        "How far off-centre (0 to 1) a guest must stand before her eyes turn to look at them. Lower and her eyes follow small movements; higher and she only looks for someone well to the side.",
        "0.35",
    ),
    "MOUTH_OPEN": (
        "Her widest mouth while talking. 1: lips parted. 2: dropped to show her teeth. 3: the full marionette drop, which can run off the bottom of the foam head.",
        "2 for the foam head; 3 on a flat screen",
    ),
    "GLANCE_MIN_S": (
        "While awake she now and then glances away (left, right, up or down), never sooner than this after the last glance.",
        "5",
    ),
    "GLANCE_MAX_S": (
        "And never later than this.",
        "14: a glance every 5 to 14 s",
    ),
    "GLANCE_S": (
        "How long each glance away holds. 0 means she never glances away.",
        "0.9",
    ),
    # Paying
    "PAY_TIMEOUT_S": (
        "After asking for payment (a press of the button, or a whispered secret), how long she waits before giving up and going back to sleep.",
        "40",
    ),
    "SECRET_LISTEN_S": (
        "How long each stretch of listening for a whispered secret lasts. Anything the mic hears counts as a secret. The words never leave the browser.",
        "12",
    ),
    "COIN_PAUSE_S": (
        "After the button is pressed (the coin drops), a beat before she asks for their question.",
        "0.8",
    ),
    # Their question
    "QUESTION_MAX_S": (
        "The longest she listens to a question, however long they keep talking.",
        "30",
    ),
    "QUESTION_START_S": (
        "If an adult hasn't started speaking by then, she gives up waiting and reads their fortune without a question.",
        "10",
    ),
    "QUESTION_START_KID_S": (
        "The same for children, who often need longer to get started.",
        "12",
    ),
    "QUESTION_PAUSE_S": (
        "A silence this long ends an adult's question. Too short and she cuts people off mid-thought; too long and there's an awkward wait after they finish.",
        "2.2",
    ),
    "QUESTION_PAUSE_KID_S": (
        "The same for children.",
        "3",
    ),
    "QUESTION_TRAILING_S": (
        "Extra time added to that pause when they trail off mid-sentence (\"will I...\"), since they're probably still thinking.",
        "2.5",
    ),
    "QUESTION_MORE_S": (
        "Extra listening time when ASKED_MODEL judges the question unfinished.",
        "6",
    ),
    "HEARD_SHOW_S": (
        "Their question stays on screen this long before she answers, so they can see she heard it.",
        "0.6",
    ),
    # Consulting, the fortune, the ticket
    "CONSULT_MIN_S": (
        "The shortest she consults her ball, even if the fortune is already back, so the reveal never feels instant.",
        "3.5",
    ),
    "GLIMPSE_MIN_S": (
        "The shortest each flash of the guest's face lasts (see FACE_FLICKERS).",
        "0.33",
    ),
    "GLIMPSE_MAX_S": (
        "The longest each flash lasts.",
        "0.58",
    ),
    "GLIMPSE_GAP_MIN_S": (
        "The shortest gap between flashes.",
        "0.42",
    ),
    "GLIMPSE_GAP_MAX_S": (
        "The longest gap between flashes.",
        "0.83",
    ),
    "GLITCH_S": (
        "Some adult readings have a mechanical seizure mid-fortune: her voice cuts out, her head shakes, the guest's face stutters, then she carries on. This is how long it lasts. It strikes about one adult reading in five; G at the booth forces it on the next one.",
        "1.3",
    ),
    "GLITCH_AT_MIN": (
        "The earliest point in the fortune the seizure can strike, as a fraction of it.",
        "0.3: no sooner than 30% of the way in",
    ),
    "GLITCH_AT_MAX": (
        "The latest point it can strike.",
        "0.55: by just past halfway",
    ),
    "SHUTDOWN_GLITCH_S": (
        "The shudder she gives when a guest walks away mid-reading, before she shuts down.",
        "0.5",
    ),
    "TICKET_PAUSE_S": (
        "How long she waits while the ticket prints, before her farewell.",
        "1.3; raise it if the printer is slow and she says goodbye before the ticket is out",
    ),
    "SUBTITLE_LINGER_S": (
        "Subtitles stay up this long after she stops talking.",
        "0.7",
    ),
    "NO_VOICE_WORD_S": (
        "If a voice clip fails and only subtitles show, how long each word stays before the next.",
        "0.4",
    ),
}
