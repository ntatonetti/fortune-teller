"""Keeping her from repeating herself over a long night.

Claude left alone drifts toward the same moves ("Ahh...", lucky number 13, "find a
stranger"). So each reading gets a lucky number she hasn't used lately, a random
sign to read from, and a list of what she already said, to steer away from.
"""

import random
from collections import deque

# Recent greetings live in memory only; fortunes are remembered in the guest log.
recent_greetings: deque[str] = deque(maxlen=8)

TAROT = [
    "The Fool", "The Magician", "The High Priestess", "The Empress", "The Emperor", "The Hierophant",
    "The Lovers", "The Chariot", "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil", "The Tower", "The Star", "The Moon",
    "The Sun", "Judgement", "The World",
]
TAROT_FOR_KIDS = ["The Fool", "The Magician", "The Empress", "The Chariot", "Strength", "Wheel of Fortune", "The Star", "The Moon", "The Sun", "The World"]
# Where the guest draws from (TAROT in .env), and where each card's picture is:
# the 1909 Rider-Waite-Smith scans, public domain, in static/img/tarot/.
# Each card drawn, in order: as many as CARDS lets them (they can say "enough" sooner).
SPREAD = ["past", "present", "future", "obstacle", "outcome"]


def card_image(name: str) -> str:
    return f"/img/tarot/{name.lower().replace(' ', '-')}.jpg"

SIGNS = [
    "tea leaves left in a chipped cup", "a raven tapping at the glass", "a crack spreading across a mirror",
    "candle smoke curling the wrong way", "a moth circling the lamp", "a playing card that slips from her sleeve",
    "the hands of a pocket watch spinning backward", "a key that appears in the crystal ball",
    "the lines of the guest's palm, seen through the glass", "a ship in a bottle rocking on a calm shelf",
    "a music box that starts playing by itself", "a single black feather drifting down", "the phase of tonight's moon",
    "a coin that lands on its edge", "a spider weaving one letter into its web", "frost forming in the shape of a door",
]
SIGNS_FOR_KIDS = [
    "a friendly bat waving from the ceiling", "a pumpkin that winks", "a star falling into the crystal ball",
    "a playing card that slips from her sleeve", "a music box that starts playing by itself", "a key that appears in the crystal ball",
    "a moth with glittering wings", "the phase of tonight's moon", "a coin that lands on its edge",
    "a tiny ghost doing somersaults in the mist",
]


def pick_lucky(recent: list[int]) -> int:
    used = set(recent)
    choices = [n for n in range(1, 100) if n not in used and n != 13] or list(range(1, 100))
    # 13 is too tempting for her; allow it now and then, not by default.
    if random.random() < 0.04 and 13 not in used:
        return 13
    return random.choice(choices)


def pick_sign(kid: bool) -> str:
    if kid:
        return random.choice([f"the tarot card {random.choice(TAROT_FOR_KIDS)}", random.choice(SIGNS_FOR_KIDS)])
    return random.choice([f"the tarot card {random.choice(TAROT)}", random.choice(SIGNS)])


def opener(spoken: str, words: int = 8) -> str:
    return " ".join(spoken.split()[:words])
