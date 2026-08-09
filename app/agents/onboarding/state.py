from typing import TypedDict


class OnboardingState(TypedDict, total=False):
    user_id: str
    telegram_id: int
    incoming_text: str

    current_step: int
    skip_all: bool
    finished: bool

    # message to send back to the user for this turn
    reply: str
