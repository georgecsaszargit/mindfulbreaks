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
    KEY_IDLE_ENABLED = 'idle-monitor-enabled'
    KEY_IDLE_THRESHOLD = 'idle-threshold-seconds'
    # --- Added for Overlay Geometry ---
    KEY_OVERLAY_WIDTH = 'overlay-width'
    KEY_OVERLAY_HEIGHT = 'overlay-height'
    KEY_OVERLAY_TOP_MARGIN = 'overlay-top-margin'
    KEY_OVERLAY_HORIZONTAL_CENTERED = 'overlay-horizontal-centered'    

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

    def _get_default_settings(self) -> dict:
        """Returns a dictionary with the default application settings."""
        return {
            self.KEY_BREAK_INTERVAL: 60,
            self.KEY_IDLE_ENABLED: True,
            self.KEY_IDLE_THRESHOLD: 3600,
            # --- Added for Overlay Geometry ---
            self.KEY_OVERLAY_WIDTH: 1000,
            self.KEY_OVERLAY_HEIGHT: 600,
            self.KEY_OVERLAY_TOP_MARGIN: 0,
            self.KEY_OVERLAY_HORIZONTAL_CENTERED: True            
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

    def get_idle_monitor_enabled(self) -> bool:
        """Retrieves whether the idle monitor is enabled."""
        return self._settings.get(self.KEY_IDLE_ENABLED, self._get_default_settings()[self.KEY_IDLE_ENABLED])

    def get_idle_threshold_seconds(self) -> int:
        """Retrieves the idle threshold in seconds."""
        # Ensure value is reasonable on read, min 10s
        value = self._settings.get(self.KEY_IDLE_THRESHOLD, self._get_default_settings()[self.KEY_IDLE_THRESHOLD])
        return max(10, value)

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

    def set_idle_monitor_enabled(self, enabled: bool):
        """Sets whether the idle monitor is enabled and saves to file."""
        self._settings[self.KEY_IDLE_ENABLED] = bool(enabled)
        self._save_settings()

    def set_idle_threshold_seconds(self, seconds: int):
        """Sets the idle threshold in seconds and saves to file."""
        try:
            validated_seconds = max(10, int(seconds))
        except (ValueError, TypeError):
            print(f"Warning: Invalid value '{seconds}' for idle threshold, using 10.", file=sys.stderr)
            validated_seconds = 10

        self._settings[self.KEY_IDLE_THRESHOLD] = validated_seconds
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

        # Test Idle Enabled
        initial_idle_enabled = manager.get_idle_monitor_enabled()
        print(f"\nInitial idle enabled: {initial_idle_enabled}")
        manager.set_idle_monitor_enabled(not initial_idle_enabled)
        print(f"Set to {not initial_idle_enabled}, retrieved: {manager.get_idle_monitor_enabled()}")
        manager.set_idle_monitor_enabled(initial_idle_enabled)
        print(f"Reset to {initial_idle_enabled}, retrieved: {manager.get_idle_monitor_enabled()}")

        # Test Idle Threshold
        initial_idle_threshold = manager.get_idle_threshold_seconds()
        print(f"\nInitial idle threshold: {initial_idle_threshold}")
        manager.set_idle_threshold_seconds(30)
        print(f"Set to 30, retrieved: {manager.get_idle_threshold_seconds()}")
        manager.set_idle_threshold_seconds(5) # Test minimum enforcement
        print(f"Set to 5, retrieved: {manager.get_idle_threshold_seconds()} (should be >= 10)")
        manager.set_idle_threshold_seconds(initial_idle_threshold)
        print(f"Reset to {initial_idle_threshold}, retrieved: {manager.get_idle_threshold_seconds()}")

        print("\nAll tests passed if retrieved values match set/reset values (and minimums enforced).")
        print(f"\nVerify by checking the contents of the file: {manager.config_path}")

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
