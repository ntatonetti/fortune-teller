"""Her signature wording: lines we wrote, for Claude to choose from.

Each reading Claude is shown a few of these at random and works one or two in,
word for word or close to it, writing everything else itself. Edit freely: add
a line, cut one that has gone stale. Greetings come before she knows who is
there, so they stay all-ages; children only ever get the KIDS lists.
"""

import random

GREETING = [
    "Who winds my springs at this hour?",
    "Step closer... the glass is thin tonight.",
    "My clockwork heart ticks faster... it must be you.",
    "The crystal said you would come... it is rarely wrong.",
    "A hundred years I have waited... and here you are, right on time.",
    "Oh! A visitor... my gears were hoping.",
    "Do not be shy... the brass does not bite.",
]

# Grouped by where they sit in a fortune, so she opens with an opener and so on.
ADULT = {
    "to open with": [
        "Hold still... the gears are turning for you.",
        "Let me look deeper... past the costume, to the soul wearing it.",
        "The mist parts... and I see...",
        "Your coin is still warm... it remembers where it has been.",
    ],
    "for the middle": [
        "Mark me well...",
        "The brass remembers what flesh forgets.",
        "The cards do not lie... though they do exaggerate.",
        "Something follows you tonight... it is mostly harmless.",
        "The spirits are giggling... that is rarely a good sign.",
        "I have seen this once before, in 1926... it ended in a waltz.",
    ],
    "to close with": [
        "The fates have spoken... and they never repeat themselves.",
        "Go now... before the clockwork changes its mind.",
        "Take your ticket... and tell no one what it says. Or everyone.",
        "My springs wind down... the reading is done.",
        "Remember this night... I certainly will.",
    ],
}

KIDS = {
    "to open with": [
        "Oh my, oh my... a brave one!",
        "Let me polish my crystal ball... there we are.",
        "The stars are twinkling just for you tonight.",
    ],
    "for the middle": [
        "The magic is very sure about this.",
        "Even the bats are cheering for you.",
        "My gears are humming a happy tune.",
        "That is the bravest thing I have seen all night.",
    ],
    "to close with": [
        "Off you go, little adventurer... the night is full of treats.",
        "Take your ticket... it is a little piece of magic.",
        "My gears are sleepy now... goodnight, brave one.",
    ],
}

_RULE = (
    "Weave them in so they sound like your own; keep each one recognizable, though you may adjust a word"
    " or two to fit. These are your signature lines, so it is fine if a guest earlier tonight heard one."
)


def for_greeting(rng=random) -> str:
    lines = "\n".join(f"- {l}" for l in rng.sample(GREETING, 3))
    return f"\n\nSome of your signature lines. Use one of these if it fits, otherwise none:\n{lines}\n{_RULE}"


def for_fortune(kid: bool, rng=random) -> str:
    # Only two of the three places each time, so readings don't all open, turn and close the same way.
    places = rng.sample(list((KIDS if kid else ADULT).items()), 2)
    groups = "\n".join(f"{where}: " + " / ".join(f'"{l}"' for l in rng.sample(lines, 2)) for where, lines in places)
    return f"\n\nSome of your signature lines. Use one from each place, at most two in all:\n{groups}\n{_RULE}"
