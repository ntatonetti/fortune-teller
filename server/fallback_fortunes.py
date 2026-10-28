"""Canned lines for when Claude is unreachable (party Wi-Fi dies, no API key yet)."""

import random

from .models import Fortune, Greeting

ADULT = [
    (
        "The Omen of the Second Glass",
        "Before the moon sets, you will be offered a second drink... and a secret. Accept only one.",
        "Find someone wearing black and ask them what they are hiding.",
    ),
    (
        "The Clock That Runs Backward",
        "A clock somewhere in this house is running backward. When you hear it... someone will owe you a favor.",
        "Make a stranger laugh before the next song ends.",
    ),
    (
        "The Visitor at the Gate",
        "Someone at this party has been waiting all night to talk to you. They are closer than you think.",
        "Compliment the costume you envy most, out loud.",
    ),
    (
        "The Unlit Candle",
        "You carry a small flame that others cannot see. Guard it from the wind... and from the punch bowl.",
        "Teach someone a dance move they did not ask to learn.",
    ),
    (
        "The Key Without a Lock",
        "You will find a key tonight that opens nothing... yet. Keep it. The lock is coming.",
        "Ask three guests what they fear most and remember the strangest answer.",
    ),
]

CHILD = [
    (
        "The Brave Little Lantern",
        "You have the courage of a lantern in the dark. Tonight, your bravery will light the way for a friend!",
        "Do your very best monster roar for a grown-up.",
    ),
    (
        "The Secret Candy Map",
        "A secret map of sweets is hidden in your future. Follow your nose and your heart... treasure awaits!",
        "Find someone in orange and give them a high five.",
    ),
    (
        "The Friendly Ghost",
        "A friendly ghost has chosen you as their favorite person. They will follow you, giggling, all night long.",
        "Teach a grown-up your silliest dance.",
    ),
    (
        "The Star Catcher",
        "I see a star with your name on it. One day you will do something so amazing, the moon will clap!",
        "Make up a magic spell and cast it on the snack table.",
    ),
]

GREETINGS_ADULT = [
    "Ahh... a visitor. The gears have been waiting for you. Come closer...",
    "Who disturbs the mechanism? Step forward... I have seen you before... in a dream.",
]
GREETINGS_CHILD = [
    "Oh! Hello there, little traveler! Come closer, I have a special fortune just for you.",
    "Well, well... what a magnificent costume! Come closer, brave one.",
]


def greeting() -> Greeting:
    # Without eyes we can't tell who is there, so stay gentle.
    return Greeting(
        audience="child", group_size=1, costume="", greeting=random.choice(GREETINGS_CHILD), source="fallback"
    )


def fortune(audience: str, costume: str) -> Fortune:
    child = audience in ("child", "mixed")
    title, text, task = random.choice(CHILD if child else ADULT)
    number = random.randint(1, 99)
    opener = "Oh, how wonderful..." if child else "The gears turn... and I see..."
    spoken = f"{opener} {text} Your lucky number is {number}. And before you go... {task}"
    return Fortune(
        audience=audience,
        group_size=1,
        costume=costume,
        spoken=spoken,
        card_title=title,
        card_text=text,
        lucky_number=number,
        task=task,
        gist=title,
        source="fallback",
    )
