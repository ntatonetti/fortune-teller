from pydantic import BaseModel


class Greeting(BaseModel):
    audience: str
    group_size: int
    costume: str
    greeting: str
    seated: bool = False  # the guest nearest the glass is sitting down


class Fortune(BaseModel):
    audience: str
    group_size: int
    costume: str
    spoken: str
    card_title: str
    card_text: str
    lucky_number: int
    task: str
    gist: str
    question: str = ""  # what the guest asked, for the printed card
    cards: list[str] = []  # the tarot spread they drew (past, present, future), if any
    readings: list[str] = []  # what she says over each of those cards
