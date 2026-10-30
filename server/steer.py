"""Stage directions from the booth's keeper, typed on /steer.html.

Two notes, held in memory only (a restart forgets them):
  tonight    - stays until changed, e.g. "the costume contest is at 9, plug it"
  next_guest - used for the next reading only, e.g. "this is Sam, it's her birthday"
The next-guest note is cleared once a Claude fortune has used it.
"""

MAX_CHARS = 500

tonight = ""
next_guest = ""
used_for = ""  # costume of the guest who got the last next-guest note


def set_notes(new_tonight: str | None = None, new_next: str | None = None) -> None:
    global tonight, next_guest, used_for
    if new_tonight is not None:
        tonight = new_tonight.strip()[:MAX_CHARS]
    if new_next is not None:
        next_guest = new_next.strip()[:MAX_CHARS]
        used_for = ""


def consume(note: str, costume: str) -> None:
    """Clear the next-guest note after a reading used it, unless it was changed meanwhile."""
    global next_guest, used_for
    if note and note == next_guest:
        next_guest = ""
        used_for = costume or "the last guest"


def prompt(next_note: str) -> str:
    notes = [f"For the whole night: {tonight}" if tonight else "", f"For this guest: {next_note}" if next_note else ""]
    notes = "\n".join(n for n in notes if n)
    if not notes:
        return ""
    return (
        "\n\nThe keeper of your booth has whispered you some stage directions. The guest cannot hear them."
        " Follow them where they fit, weave them in naturally, and never mention the keeper or that you were told."
        " Your hard rules and the CHILD/ADULT mode still come first. If the keeper gives a guest's name, you may use it."
        f"\n<keeper>\n{notes}\n</keeper>"
    )
