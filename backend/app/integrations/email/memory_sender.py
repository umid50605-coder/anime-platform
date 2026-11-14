"""
InMemoryEmailSender: the only EmailSender implemented so far.

It delivers nothing - messages are appended to a bounded in-process outbox.
That is what the test suite reads reset links from, and it is a deliberate
stand-in until a real vendor is chosen (same role MockAnimeProvider plays).
"""

from collections import deque

from app.integrations.email.sender import EmailMessage, EmailSender

# Bounded so a long-running process using this sender can't grow without limit.
_OUTBOX_MAX_MESSAGES = 100


class InMemoryEmailSender(EmailSender):
    def __init__(self) -> None:
        self.outbox: deque[EmailMessage] = deque(maxlen=_OUTBOX_MAX_MESSAGES)

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)

    def clear(self) -> None:
        self.outbox.clear()
