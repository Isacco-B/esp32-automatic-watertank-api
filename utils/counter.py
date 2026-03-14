import json
import time

from utils.timezone import now_unix

COUNTER_FILE = "/counters.json"
COUNTER_24H_FILE = "/counters_24h.json"

RESET_HOUR = 23
RESET_MINUTE = 59


class CommandCounter:

    def __init__(self):
        self.total_counters = {
            "siren": 0,
            "pump": 0,
            "alarm": 0,
        }

        self.counters_24h = {
            "siren": 0,
            "pump": 0,
            "alarm": 0,
        }

        self.last_reset_date = None  # "YYYY-MM-DD"

        self.load_counters()

    def _today_str(self) -> str:
        t = time.localtime(now_unix())
        return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"

    def _should_reset(self) -> bool:
        """Return True if it's past 23:59 of a new day since last reset."""
        t = time.localtime(now_unix())
        today = self._today_str()

        past_reset_time = t[3] > RESET_HOUR or (
            t[3] == RESET_HOUR and t[4] >= RESET_MINUTE
        )

        return past_reset_time and today != self.last_reset_date

    def _reset_24h_if_needed(self) -> None:
        if self._should_reset():
            for command in self.counters_24h:
                self.counters_24h[command] = 0
            self.last_reset_date = self._today_str()
            self.save_counters()
            print(f"Daily counters reset at {self.last_reset_date}")

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
                    self.counters_24h = data.get("counts", self.counters_24h)
                    self.last_reset_date = data.get("last_reset_date", None)
        except (OSError, ValueError):
            print("No existing 24h counters")

        self._reset_24h_if_needed()

    def save_counters(self) -> None:
        """Save counters to persistent storage."""
        try:
            with open(COUNTER_FILE, "w") as f:
                json.dump(self.total_counters, f)

            with open(COUNTER_24H_FILE, "w") as f:
                json.dump(
                    {
                        "counts": self.counters_24h,
                        "last_reset_date": self.last_reset_date,
                    },
                    f,
                )
        except Exception as e:
            print(f"Error saving counters: {e}")

    def increment(self, command: str) -> None:
        """Increment counter for a command."""
        if command not in self.total_counters:
            print(f"Unknown command: {command}")
            return

        self._reset_24h_if_needed()

        self.total_counters[command] += 1
        self.counters_24h[command] = self.counters_24h.get(command, 0) + 1
        self.save_counters()

    def get_statistics(self) -> dict:
        """Get formatted statistics."""
        self._reset_24h_if_needed()

        return {
            "last_24_hours": {
                "sirena": self.counters_24h.get("siren", 0),
                "pompa": self.counters_24h.get("pump", 0),
                "allarmi": self.counters_24h.get("alarm", 0),
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
                self.counters_24h[command] = 0
            self.last_reset_date = self._today_str()

        if counter_type in ["all", "total"]:
            for command in self.total_counters:
                self.total_counters[command] = 0

        self.save_counters()
        print(f"Counters reset: {counter_type}")


counter = CommandCounter()
