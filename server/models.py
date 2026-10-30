from pydantic import BaseModel


class Greeting(BaseModel):
    audience: str
    group_size: int
    costume: str
    greeting: str


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
