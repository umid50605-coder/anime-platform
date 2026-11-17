"""
SmtpEmailSender: delivers plain-text mail through an SMTP server (stdlib only).

Configuration comes from settings/environment - nothing is hardcoded. send()
raises on ANY failure (connect, TLS, auth, timeout, rejected recipient) so
callers never report delivery that did not happen. Exceptions are not
swallowed or reworded here; callers log only the exception type.
"""

import smtplib
import ssl
from email.message import EmailMessage as MimeMessage
from email.utils import formataddr

from app.integrations.email.sender import EmailMessage, EmailSender


class SmtpEmailSender(EmailSender):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        from_name: str,
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not host or not from_address:
            raise ValueError("smtp_host and email_from_address are required for SMTP delivery")
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._from_name = from_name
        self._use_tls = use_tls
        self._use_ssl = use_ssl
        self._timeout = timeout_seconds

    def send(self, message: EmailMessage) -> None:
        mime = MimeMessage()
        mime["From"] = formataddr((self._from_name, self._from_address))
        mime["To"] = message.to
        mime["Subject"] = message.subject
        mime.set_content(message.body)

        # Explicit default context: verifies the server certificate and hostname.
        context = ssl.create_default_context()
        if self._use_ssl:
            smtp_cm = smtplib.SMTP_SSL(
                self._host, self._port, timeout=self._timeout, context=context
            )
        else:
            smtp_cm = smtplib.SMTP(self._host, self._port, timeout=self._timeout)
        with smtp_cm as smtp:
            if self._use_tls and not self._use_ssl:
                smtp.starttls(context=context)
            if self._username:
                smtp.login(self._username, self._password)
            refused = smtp.send_message(mime)
        if refused:
            # send_message returns refused recipients instead of raising when
            # only SOME were refused; with one recipient any entry is a failure.
            raise smtplib.SMTPRecipientsRefused(refused)
