import logging

from app.config import get_settings

logger = logging.getLogger("casio.email")


def send_password_reset(to_email: str, link: str) -> None:
    """No email service is configured yet. In "console" mode the email is
    printed to the backend terminal so the reset flow can still be used.
    To send real email later, add an email provider here (e.g. SMTP, Resend)."""
    if get_settings().email_mode == "console":
        print(
            "\n=== CASIO password reset email (console mode) ===\n"
            f"To: {to_email}\nReset your password: {link}\n"
            "=================================================\n",
            flush=True,
        )
    else:
        logger.warning("EMAIL_MODE=%s is not supported yet; reset email not sent", get_settings().email_mode)
