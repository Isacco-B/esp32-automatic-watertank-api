import json

from lib.umail import SMTP
from secrets import EMAIL_ADDRESS, EMAIL_HOST, EMAIL_PASSWORD, EMAIL_PORT

RECIPIENTS_FILE = "/email_recipients.json"


class EmailManager:
    """
    Manages email recipients and sends alarm notifications.
    """

    def __init__(self):
        self.recipients = []
        self.load_recipients()

    def load_recipients(self) -> None:
        """Load recipients from persistent storage."""
        try:
            with open(RECIPIENTS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.recipients = data
            print(f"Loaded {len(self.recipients)} email recipients")
        except (OSError, ValueError):
            print("No existing recipients, starting fresh")

    def save_recipients(self) -> None:
        """Save recipients to persistent storage."""
        try:
            with open(RECIPIENTS_FILE, "w") as f:
                json.dump(self.recipients, f)
        except Exception as e:
            print(f"Error saving recipients: {e}")

    def add_recipient(self, email: str) -> bool:
        """Add an email recipient. Returns False if already present."""
        if email in self.recipients:
            return False
        self.recipients.append(email)
        self.save_recipients()
        print(f"Email recipient added: {email}")
        return True

    def remove_recipient(self, email: str) -> bool:
        """Remove an email recipient. Returns False if not found."""
        if email not in self.recipients:
            return False
        self.recipients.remove(email)
        self.save_recipients()
        print(f"Email recipient removed: {email}")
        return True

    def get_recipients(self) -> list:
        """Return a copy of the recipients list."""
        return self.recipients.copy()

    def send_alarm_email(self, subject: str, body: str) -> bool:
        """
        Send an alarm email to all recipients in a single SMTP connection.
        Returns True if the email was sent successfully.
        """
        if not self.recipients:
            print("No email recipients configured, skipping email notification")
            return False

        try:
            smtp = SMTP(EMAIL_HOST, EMAIL_PORT, ssl=True)
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.to(self.recipients)
            smtp.write(f"From: {EMAIL_ADDRESS}\r\n")
            smtp.write(f"To: {', '.join(self.recipients)}\r\n")
            smtp.write(f"Subject: {subject}\r\n\r\n")
            smtp.write(body)
            code, msg = smtp.send()
            smtp.quit()

            if code == 250:
                print(f"Alarm email sent to {len(self.recipients)} recipient(s)")
                return True
            else:
                print(f"Email send failed: {code} {msg}")
                return False

        except Exception as e:
            print(f"Error sending alarm email: {e}")
            return False


email_manager = EmailManager()
