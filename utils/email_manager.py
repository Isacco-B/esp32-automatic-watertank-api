import json

RECIPIENTS_FILE = "/email_recipients.json"


class EmailManager:
    """
    Manages email recipients list (persistent storage).
    Email sending is delegated to the mqtt-email-relay server.
    """

    def __init__(self):
        self.recipients = []
        self.load_recipients()

    def load_recipients(self) -> None:
        try:
            with open(RECIPIENTS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    self.recipients = data
            print(f"Loaded {len(self.recipients)} email recipients")
        except (OSError, ValueError):
            print("No existing recipients, starting fresh")

    def save_recipients(self) -> None:
        try:
            with open(RECIPIENTS_FILE, "w") as f:
                json.dump(self.recipients, f)
        except Exception as e:
            print(f"Error saving recipients: {e}")

    def add_recipient(self, email: str) -> bool:
        if email in self.recipients:
            return False
        self.recipients.append(email)
        self.save_recipients()
        print(f"Email recipient added: {email}")
        return True

    def remove_recipient(self, email: str) -> bool:
        if email not in self.recipients:
            return False
        self.recipients.remove(email)
        self.save_recipients()
        print(f"Email recipient removed: {email}")
        return True

    def get_recipients(self) -> list:
        return self.recipients.copy()


email_manager = EmailManager()
