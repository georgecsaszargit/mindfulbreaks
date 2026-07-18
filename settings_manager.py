# File: settings_manager.py
import sys
import os
import json

class SettingsManager:
    """
    Manages application settings using a JSON file in the user's config directory.
    """
    # Define keys to ensure consistency
    KEY_BREAK_INTERVAL = 'break-interval-minutes'
    # --- Added for Overlay Geometry ---
    KEY_OVERLAY_WIDTH = 'overlay-width'
    KEY_OVERLAY_HEIGHT = 'overlay-height'
    KEY_OVERLAY_TOP_MARGIN = 'overlay-top-margin'
    KEY_OVERLAY_HORIZONTAL_CENTERED = 'overlay-horizontal-centered'

    # --- Added for Schedule ---
    KEY_SCHEDULE_ENABLED = 'schedule-enabled'
    KEY_SCHEDULE = 'schedule'  # dict: day index (0=Mon..6=Sun) -> {"from": int, "until": int}

    def __init__(self):
        """
        Initializes the SettingsManager.

        Loads settings from the JSON file or creates a default one.
        """
        # Determine config path
        config_dir = os.path.join(os.path.expanduser("~"), ".config", "mindfulbreaks")
        self.config_path = os.path.join(config_dir, "settings.json")
        self._settings = {} # In-memory cache for settings

        try:
            # Ensure directory exists
            os.makedirs(config_dir, exist_ok=True)
        except OSError as e:
            raise RuntimeError(f"Fatal: Could not create config directory at '{config_dir}'. Error: {e}")

        self._load_settings()

    def _get_default_schedule(self) -> dict:
        """
        Returns the default schedule dict (0=Mon .. 6=Sun).
        Mon-Fri (0-4): enabled, 8 to 18.
        Sat-Sun (5-6): disabled.
        """
        schedule = {}
        for d in range(7):
            if d < 5:  # Monday-Friday
                schedule[str(d)] = {"enabled": True, "from": 8, "until": 18}
            else:  # Saturday-Sunday
                schedule[str(d)] = {"enabled": False, "from": 9, "until": 17}
        return schedule

    def _get_default_settings(self) -> dict:
        """Returns a dictionary with the default application settings."""
        return {
            self.KEY_BREAK_INTERVAL: 60,
            # --- Added for Overlay Geometry ---
            self.KEY_OVERLAY_WIDTH: 1000,
            self.KEY_OVERLAY_HEIGHT: 600,
            self.KEY_OVERLAY_TOP_MARGIN: 0,
            self.KEY_OVERLAY_HORIZONTAL_CENTERED: True,
            # --- Added for Schedule ---
            self.KEY_SCHEDULE_ENABLED: True,
            self.KEY_SCHEDULE: self._get_default_schedule(),
        }

    def _load_settings(self):
        """Loads settings from the JSON file into the in-memory cache."""
        defaults = self._get_default_settings()
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    loaded_settings = json.load(f)
                # Merge loaded settings with defaults to ensure all keys exist
                self._settings = {**defaults, **loaded_settings}
                print(f"Settings loaded from {self.config_path}")
            else:
                # If file doesn't exist, create it with defaults
                print(f"Settings file not found. Creating default at {self.config_path}")
                self._settings = defaults
                self._save_settings()
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not read or parse settings file. Using defaults. Error: {e}", file=sys.stderr)
            self._settings = defaults

    def _save_settings(self):
        """Saves the current in-memory settings to the JSON file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._settings, f, indent=4)
            print(f"Settings saved to {self.config_path}")
        except IOError as e:
            print(f"Error: Could not write settings to '{self.config_path}'. Error: {e}", file=sys.stderr)

    # --- Public Getter Methods ---

    def get_break_interval(self) -> int:
        """Retrieves the currently configured break interval in minutes."""
        return self._settings.get(self.KEY_BREAK_INTERVAL, self._get_default_settings()[self.KEY_BREAK_INTERVAL])

    # --- Added for Overlay Geometry ---

    def get_overlay_width(self) -> int:
        """Retrieves the overlay width in pixels."""
        return self._settings.get(self.KEY_OVERLAY_WIDTH, self._get_default_settings()[self.KEY_OVERLAY_WIDTH])

    def get_overlay_height(self) -> int:
        """Retrieves the overlay height in pixels."""
        return self._settings.get(self.KEY_OVERLAY_HEIGHT, self._get_default_settings()[self.KEY_OVERLAY_HEIGHT])

    def get_overlay_top_margin(self) -> int:
        """Retrieves the overlay top margin in pixels."""
        return self._settings.get(self.KEY_OVERLAY_TOP_MARGIN, self._get_default_settings()[self.KEY_OVERLAY_TOP_MARGIN])

    def get_overlay_horizontal_centered(self) -> bool:
        """Retrieves whether the overlay should be horizontally centered."""
        return self._settings.get(self.KEY_OVERLAY_HORIZONTAL_CENTERED, self._get_default_settings()[self.KEY_OVERLAY_HORIZONTAL_CENTERED])

    # --- Added for Schedule ---

    def get_schedule_enabled(self) -> bool:
        """Retrieves whether the break schedule is enabled."""
        return self._settings.get(self.KEY_SCHEDULE_ENABLED, self._get_default_settings()[self.KEY_SCHEDULE_ENABLED])

    def get_schedule(self) -> dict:
        """Retrieves the full schedule dict (0=Mon .. 6=Sun)."""
        defaults = self._get_default_settings()
        schedule = self._settings.get(self.KEY_SCHEDULE, defaults[self.KEY_SCHEDULE])
        # Ensure all 7 days exist; fill missing with defaults
        default_schedule = defaults[self.KEY_SCHEDULE]
        result = {}
        for d in range(7):
            day_key = str(d)
            day = schedule.get(day_key, default_schedule[day_key])
            # Validate structure
            if not isinstance(day, dict) or "from" not in day or "until" not in day:
                day = default_schedule[day_key]
            result[day_key] = {
                "enabled": bool(day.get("enabled", default_schedule[day_key]["enabled"])),
                "from": self._validate_hour(day.get("from", default_schedule[day_key]["from"])),
                "until": self._validate_hour(day.get("until", default_schedule[day_key]["until"])),
            }
        return result

    def get_schedule_for_day(self, day_index: int) -> dict:
        """Retrieves the schedule for a specific day (0=Mon .. 6=Sun)."""
        if not 0 <= day_index <= 6:
            raise ValueError(f"day_index must be 0-6, got {day_index}")
        return self.get_schedule()[str(day_index)]

    @staticmethod
    def _validate_hour(value) -> int:
        """Clamps an hour value to the valid 0-23 range."""
        try:
            v = int(value)
        except (ValueError, TypeError):
            return 9
        return max(0, min(23, v))

    def is_break_allowed_now(self) -> bool:
        """
        Checks whether a break is allowed at the current time based on the schedule.

        Returns True if the schedule is disabled (breaks always allowed),
        or if today is enabled and the current hour is within today's
        configured from-until window.
        """
        if not self.get_schedule_enabled():
            return True
        import datetime
        now = datetime.datetime.now()
        day_index = now.weekday()  # Monday=0 .. Sunday=6
        hour = now.hour
        day_schedule = self.get_schedule_for_day(day_index)
        # If today is disabled, no breaks allowed
        if not day_schedule.get("enabled", True):
            return False
        from_hour = day_schedule["from"]
        until_hour = day_schedule["until"]
        # If from == until, treat as "all day off" (no breaks allowed)
        if from_hour == until_hour:
            return False
        # Normal case: from < until (same-day window)
        if from_hour < until_hour:
            return from_hour <= hour < until_hour
        # Wrap-around window: from > until (e.g., 22 to 6, overnight)
        return hour >= from_hour or hour < until_hour

    # --- Public Setter Methods ---

    def set_break_interval(self, minutes: int):
        """
        Sets the break interval in minutes and saves to file.
        Args:
            minutes: The desired break interval in minutes (integer >= 1).
        """
        try:
            validated_minutes = max(1, int(minutes))
        except (ValueError, TypeError):
            print(f"Warning: Invalid type/value for minutes ('{minutes}'). Using default.", file=sys.stderr)
            validated_minutes = self._get_default_settings()[self.KEY_BREAK_INTERVAL]

        self._settings[self.KEY_BREAK_INTERVAL] = validated_minutes
        self._save_settings()

    # --- Added for Schedule ---

    def set_schedule_enabled(self, enabled: bool):
        """Sets whether the break schedule is enabled and saves to file."""
        self._settings[self.KEY_SCHEDULE_ENABLED] = bool(enabled)
        self._save_settings()

    def set_schedule(self, schedule: dict):
        """
        Sets the full schedule dict and saves to file.

        Args:
            schedule: dict keyed by day index string ("0".."6"), each with
                      {"enabled": bool, "from": int, "until": int} in 0-23 range.
        """
        default_schedule = self._get_default_schedule()
        result = {}
        for d in range(7):
            day_key = str(d)
            day = schedule.get(day_key, default_schedule[day_key]) if isinstance(schedule, dict) else default_schedule[day_key]
            if not isinstance(day, dict) or "from" not in day or "until" not in day:
                day = default_schedule[day_key]
            result[day_key] = {
                "enabled": bool(day.get("enabled", default_schedule[day_key]["enabled"])),
                "from": self._validate_hour(day.get("from", default_schedule[day_key]["from"])),
                "until": self._validate_hour(day.get("until", default_schedule[day_key]["until"])),
            }
        self._settings[self.KEY_SCHEDULE] = result
        self._save_settings()

# --- Test Code Block ---
if __name__ == '__main__':
    print("Running basic SettingsManager test...")
    try:
        manager = SettingsManager()

        # Test Interval
        initial_interval = manager.get_break_interval()
        print(f"Initial break interval: {initial_interval}")
        manager.set_break_interval(15)
        print(f"Set to 15, retrieved: {manager.get_break_interval()}")
        manager.set_break_interval(initial_interval)
        print(f"Reset to {initial_interval}, retrieved: {manager.get_break_interval()}")

        # Test Schedule
        print("\n--- Testing Schedule ---")
        initial_sched_enabled = manager.get_schedule_enabled()
        print(f"Initial schedule enabled: {initial_sched_enabled}")
        manager.set_schedule_enabled(True)
        print(f"Set to True, retrieved: {manager.get_schedule_enabled()}")
        manager.set_schedule_enabled(initial_sched_enabled)
        print(f"Reset to {initial_sched_enabled}, retrieved: {manager.get_schedule_enabled()}")

        initial_schedule = manager.get_schedule()
        print(f"Initial schedule: {initial_schedule}")
        new_schedule = {str(d): {"enabled": True, "from": 10, "until": 18} for d in range(7)}
        manager.set_schedule(new_schedule)
        print(f"Set 10-18, retrieved: {manager.get_schedule()}")
        manager.set_schedule(initial_schedule)
        print(f"Reset, retrieved: {manager.get_schedule()}")

        print(f"is_break_allowed_now (schedule disabled): {manager.is_break_allowed_now()}")
        manager.set_schedule_enabled(True)
        print(f"is_break_allowed_now (schedule enabled): {manager.is_break_allowed_now()}")
        manager.set_schedule_enabled(initial_sched_enabled)

        print("\nAll tests passed if retrieved values match set/reset values (and minimums enforced).")
        print(f"\nVerify by checking the contents of the file: {manager.config_path}")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
