# File: settings_window.py (GTK3 Fallback Version - Updated)
import sys
import gi

try:
    # Use Gtk 3 for compatibility
    gi.require_version('Gtk', '3.0')
    gi.require_version('GLib', '2.0')
    gi.require_version('GObject', '2.0')
except ValueError as e:
    print(f"Error: Could not satisfy Gtk/GLib/GObject version requirement. {e}", file=sys.stderr)
    sys.exit(1)

from gi.repository import Gtk, GObject, Gio, GLib # Import GLib

# Import the settings manager from Ticket 1
try:
    from settings_manager import SettingsManager
except ImportError as e:
     print(f"Error: Could not import SettingsManager. Make sure settings_manager.py is in the same directory or Python path. {e}", file=sys.stderr)
     sys.exit(1)


class SettingsWindow(Gtk.Window): # Inherit from Gtk.Window
    """
    A preferences window for configuring MindfulBreak settings (GTK3 Version),
    including break interval and idle detection.
    """

    # Signal emitted when settings are applied/saved
    __gsignals__ = {
        # Keep original signature, main app re-reads all settings on save
        'settings_saved': (GObject.SignalFlags.RUN_FIRST, None, (int,)), # Emits new interval
    }

    def __init__(self, settings_manager: SettingsManager, **kwargs):
        """
        Initializes the SettingsWindow.

        Args:
            settings_manager: An instance of the SettingsManager to load/save values.
            **kwargs: Additional keyword arguments for the Gtk.Window.
        """
        super().__init__(title="MindfulBreak Settings", **kwargs)
        self._settings_manager = settings_manager

        self.set_modal(True)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(12) # Add some padding
        self.set_resizable(False)

        # --- Main Box ---
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)

        # --- Break Interval Row ---
        hbox_interval = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(hbox_interval, True, True, 0)

        label_interval = Gtk.Label(label="Interval Between Breaks (minutes):")
        label_interval.set_xalign(0)
        hbox_interval.pack_start(label_interval, False, False, 0)

        self.spin_break_interval = Gtk.SpinButton()
        adjustment_interval = Gtk.Adjustment(
            value=self._settings_manager.get_break_interval(),
            lower=1.0, upper=180.0, step_increment=1.0, page_increment=5.0, page_size=0.0
        )
        self.spin_break_interval.set_adjustment(adjustment_interval)
        self.spin_break_interval.set_digits(0)
        self.spin_break_interval.set_numeric(True)
        hbox_interval.pack_start(self.spin_break_interval, True, True, 0)

        # --- Enable Idle Detection Row ---
        hbox_idle_enable = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(hbox_idle_enable, False, False, 5) # Less vertical space

        label_idle_enable = Gtk.Label(label="Enable Idle Detection:")
        label_idle_enable.set_xalign(0)
        hbox_idle_enable.pack_start(label_idle_enable, True, True, 0) # Allow label to expand

        self.switch_idle_enable = Gtk.Switch()
        self.switch_idle_enable.set_valign(Gtk.Align.CENTER)
        self.switch_idle_enable.set_active(self._settings_manager.get_idle_monitor_enabled())
        hbox_idle_enable.pack_end(self.switch_idle_enable, False, False, 0) # Pack switch at end

        # --- Idle Threshold Row ---
        hbox_idle_threshold = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(hbox_idle_threshold, False, False, 5)

        label_idle_threshold = Gtk.Label(label="Idle Threshold (seconds):")
        label_idle_threshold.set_xalign(0)
        hbox_idle_threshold.pack_start(label_idle_threshold, False, False, 0)

        self.spin_idle_threshold = Gtk.SpinButton()
        adjustment_threshold = Gtk.Adjustment(
            value=self._settings_manager.get_idle_threshold_seconds(),
            lower=10.0, upper=7200.0, step_increment=5.0, page_increment=30.0, page_size=0.0
        )
        self.spin_idle_threshold.set_adjustment(adjustment_threshold)
        self.spin_idle_threshold.set_digits(0)
        self.spin_idle_threshold.set_numeric(True)
        hbox_idle_threshold.pack_start(self.spin_idle_threshold, True, True, 0)

        # --- Separator and Buttons ---
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 15) # More space before buttons

        action_area = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        action_area.set_halign(Gtk.Align.END) # Align buttons to the right
        vbox.pack_start(action_area, False, False, 0)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_save = Gtk.Button(label="Save")
        btn_save.get_style_context().add_class(Gtk.STYLE_CLASS_SUGGESTED_ACTION)

        action_area.pack_end(btn_save, False, False, 0)
        action_area.pack_end(btn_cancel, False, False, 0)

        # --- Connect Signals ---
        # Store initial values for *all* settings to detect changes
        self._initial_interval = self.spin_break_interval.get_value_as_int()
        self._initial_idle_enabled = self.switch_idle_enable.get_active()
        self._initial_idle_threshold = self.spin_idle_threshold.get_value_as_int()

        btn_save.connect("clicked", self._on_save_clicked)
        btn_cancel.connect("clicked", self._on_cancel_clicked)
        self.connect("delete-event", self._on_delete_event) # Handle window 'X' button

        print("SettingsWindow (GTK3): Initialized.")
        self.show_all() # Make window and widgets visible


    def _on_save_clicked(self, widget):
        """Saves all settings if changed and closes the window."""
        print("SettingsWindow: Save clicked.")

        # Get current values
        current_interval = self.spin_break_interval.get_value_as_int()
        current_idle_enabled = self.switch_idle_enable.get_active()
        current_idle_threshold = self.spin_idle_threshold.get_value_as_int()

        # Check if anything changed
        interval_changed = current_interval != self._initial_interval
        idle_enabled_changed = current_idle_enabled != self._initial_idle_enabled
        idle_threshold_changed = current_idle_threshold != self._initial_idle_threshold

        if not (interval_changed or idle_enabled_changed or idle_threshold_changed):
            print("SettingsWindow: No changes detected.")
            self.destroy() # Close without saving if nothing changed
            return

        print("SettingsWindow: Changes detected, saving...")
        try:
            # Save all changed values (SettingsManager handles sync internally)
            if interval_changed:
                self._settings_manager.set_break_interval(current_interval)
            if idle_enabled_changed:
                 self._settings_manager.set_idle_monitor_enabled(current_idle_enabled)
            if idle_threshold_changed:
                 self._settings_manager.set_idle_threshold_seconds(current_idle_threshold)

            # Emit signal AFTER successfully saving
            self.emit('settings_saved', current_interval) # Keep original signature
            self.destroy() # Close the window

        except Exception as e:
             # saved_successfully = False # Not needed if we always destroy
             print(f"Error saving settings: {e}", file=sys.stderr)
             # Show error dialog
             dialog = Gtk.MessageDialog(
                 transient_for=self, flags=0, message_type=Gtk.MessageType.ERROR,
                 buttons=Gtk.ButtonsType.CANCEL, text="Error Saving Settings",
             )
             dialog.format_secondary_text(str(e))
             dialog.run()
             dialog.destroy()
             # Still destroy the settings window even if save failed? Yes, probably less confusing.
             self.destroy()


    def _on_cancel_clicked(self, widget):
        """Closes the window without saving."""
        print("SettingsWindow: Cancel clicked.")
        self.destroy()

    def _on_delete_event(self, widget, event):
        """Handles the window close ('X') button like Cancel."""
        print("SettingsWindow: Delete event (closed).")
        # Return False to allow the window to close, True would prevent it
        return False


# --- Test Code (GTK3 Version - Update to show new widgets) ---
if __name__ == '__main__':
    print("Running SettingsWindow Test (GTK3 Version)...")

    main_loop = GLib.MainLoop()
    settings_win = None

    def on_settings_saved(emitter, new_interval):
        print(f"[Signal Handler] ****** settings_saved: New interval = {new_interval} ******")
        # Add verification for new settings
        import json
        import os
        try:
            config_path = os.path.join(os.path.expanduser("~"), ".config", "mindfulbreaks", "settings.json")
            print(f"Verifying saved settings by reading '{config_path}'...")
            settings_ok = True
            if not os.path.exists(config_path):
                print("[Verification] ERROR: Config file does not exist.")
                return

            with open(config_path, 'r') as f:
                saved_settings = json.load(f)

            # Verify Interval (assuming the saved value is what was just set in the UI)
            saved_interval = saved_settings.get(SettingsManager.KEY_BREAK_INTERVAL)
            # Note: We don't have the *new* value for idle/threshold easily in the test handler,
            # but we can check the interval. The main test is that the file is written.
            if saved_interval is not None and saved_interval != new_interval:
                 print(f"[Verification] ERROR: Interval mismatch. Expected {new_interval}, got {saved_interval}")
                 settings_ok = False
            else:
                 print(f"[Verification] Interval OK ({saved_interval}).")

            # Print other saved values
            print(f"[Verification] Idle Enabled saved as: {saved_settings.get(SettingsManager.KEY_IDLE_ENABLED)}")
            print(f"[Verification] Idle Threshold saved as: {saved_settings.get(SettingsManager.KEY_IDLE_THRESHOLD)}")

            if settings_ok: print("[Verification] All checks passed.")
        except Exception as e:
             print(f"[Verification] Could not read or parse config file: {e}")

        print("Quitting main loop after save.")
        if main_loop.is_running():
            main_loop.quit()

    try:
        settings_mgr = SettingsManager()
        print(f"Initial interval: {settings_mgr.get_break_interval()}")
        print(f"Initial idle enabled: {settings_mgr.get_idle_monitor_enabled()}")
        print(f"Initial idle threshold: {settings_mgr.get_idle_threshold_seconds()}")

        try: Gtk.init_check()
        except Exception: Gtk.init(None)

        settings_win = SettingsWindow(settings_manager=settings_mgr)
        settings_win.connect('settings_saved', on_settings_saved)
        settings_win.connect('destroy', lambda w: main_loop.quit() if main_loop.is_running() else None)

        print("Settings window presented. Use Save/Cancel or close the window.")
        print("\nStarting Gtk MainLoop...")
        main_loop.run()

    except Exception as e:
         print(f"Unexpected error during setup: {e}", file=sys.stderr)
         if main_loop.is_running(): main_loop.quit()

    print("\nTest finished.")
