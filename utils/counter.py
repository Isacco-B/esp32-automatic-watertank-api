import json

from utils.timezone import now_unix

COUNTER_FILE = "/counters.json"
COUNTER_24H_FILE = "/counters_24h.json"


class CommandCounter:

    def __init__(self):
        self.total_counters = {
            "siren": 0,
            "pump": 0,
            "alarm": 0,
        }

        self.counters_24h = {
            "siren": [],
            "pump": [],
            "alarm": [],
        }

        self.load_counters()

    def load_counters(self) -> None:
        """Load counters from persistent storage."""
        try:
            with open(COUNTER_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.total_counters.update(data)
                print(f"Loaded counters: {self.total_counters}")
        except (OSError, ValueError):
            print("No existing counters, starting fresh")

        try:
            with open(COUNTER_24H_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.counters_24h = data
                self.cleanup_24h_counters()
        except (OSError, ValueError):
            print("No existing 24h counters")

    def save_counters(self) -> None:
        """Save counters to persistent storage."""
        try:
            with open(COUNTER_FILE, "w") as f:
                json.dump(self.total_counters, f)

            with open(COUNTER_24H_FILE, "w") as f:
                json.dump(self.counters_24h, f)
        except Exception as e:
            print(f"Error saving counters: {e}")

    def increment(self, command: str) -> None:
        """Increment counter for a command."""
        if command not in self.total_counters:
            print(f"Unknown command: {command}")
            return

        self.total_counters[command] += 1

        current_time = now_unix()
        if command not in self.counters_24h:
            self.counters_24h[command] = []
        self.counters_24h[command].append(current_time)

        self.cleanup_24h_counters()
        self.save_counters()

    def cleanup_24h_counters(self) -> None:
        """Remove timestamps older than 24 hours."""
        current_time = now_unix()
        cutoff_time = current_time - (24 * 3600)

        for command in self.counters_24h:
            self.counters_24h[command] = [
                ts for ts in self.counters_24h[command] if ts > cutoff_time
            ]

    def get_24h_counts(self) -> dict:
        """Get command counts for last 24 hours."""
        self.cleanup_24h_counters()
        return {command: len(timestamps) for command, timestamps in self.counters_24h.items()}

    def get_statistics(self) -> dict:
        """Get formatted statistics."""
        counts_24h = self.get_24h_counts()

        return {
            "last_24_hours": {
                "sirena": counts_24h.get("siren", 0),
                "pompa": counts_24h.get("pump", 0),
                "allarmi": counts_24h.get("alarm", 0),
            },
            "totale": {
                "sirena": self.total_counters.get("siren", 0),
                "pompa": self.total_counters.get("pump", 0),
                "allarmi": self.total_counters.get("alarm", 0),
            },
        }

    def reset_counters(self, counter_type: str = "all") -> None:
        """Reset counters by type: '24h', 'total', or 'all'."""
        if counter_type in ["all", "24h"]:
            for command in self.counters_24h:
                self.counters_24h[command] = []

        if counter_type in ["all", "total"]:
            for command in self.total_counters:
                self.total_counters[command] = 0

        self.save_counters()
        print(f"Counters reset: {counter_type}")


counter = CommandCounter()
