"""
EmailSender: the abstraction boundary between our application and any email
delivery vendor (SMTP, a transactional-email API, ...).

Same shape as AnimeProvider/VideoProvider: callers depend on this interface,
never on a concrete sender. No real vendor is wired in yet - adding one means
a new EmailSender subclass plus a branch in factory.py, nothing else.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class EmailMessage:
    """A plain-text email. `body` may contain secrets (e.g. a reset link) - never log it."""

    to: str
    subject: str
    body: str


class EmailSender(ABC):
    """Interface every email-delivery integration must implement."""

    @abstractmethod
    def send(self, message: EmailMessage) -> None:
        """
        Deliver `message`. Implementations may raise on delivery failure; callers
        that must not leak whether an address exists (see PasswordResetService)
        are responsible for containing that.
        """
