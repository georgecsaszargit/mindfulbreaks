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
    including break interval and the break schedule.
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

        # --- Schedule Section ---
        vbox.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 10)

        # Schedule enable row
        hbox_sched_enable = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vbox.pack_start(hbox_sched_enable, False, False, 5)

        label_sched_enable = Gtk.Label(label="Enable Break Schedule:")
        label_sched_enable.set_xalign(0)
        hbox_sched_enable.pack_start(label_sched_enable, True, True, 0)

        self.switch_schedule_enable = Gtk.Switch()
        self.switch_schedule_enable.set_valign(Gtk.Align.CENTER)
        self.switch_schedule_enable.set_active(self._settings_manager.get_schedule_enabled())
        hbox_sched_enable.pack_end(self.switch_schedule_enable, False, False, 0)

        # Schedule grid (7 days x from/until)
        self._day_names = ["Monday", "Tuesday", "Wednesday", "Thursday",
                           "Friday", "Saturday", "Sunday"]
        self._schedule_spin_from = []  # list of SpinButton, index 0=Mon..6=Sun
        self._schedule_spin_until = []
        self._schedule_rows = []  # list of Gtk.Box rows for sensitivity toggling

        schedule_grid = Gtk.Grid()
        schedule_grid.set_column_spacing(10)
        schedule_grid.set_row_spacing(5)
        vbox.pack_start(schedule_grid, False, False, 5)

        # Per-day enable checkboxes
        self._schedule_day_checks = []  # list of Gtk.CheckButton, index 0=Mon..6=Sun

        # Header row
        lbl_blank = Gtk.Label(label="")
        lbl_day = Gtk.Label(label="Day")
        lbl_day.set_xalign(0)
        lbl_from = Gtk.Label(label="From (hour)")
        lbl_until = Gtk.Label(label="Until (hour)")
        schedule_grid.attach(lbl_blank, 0, 0, 1, 1)
        schedule_grid.attach(lbl_day, 1, 0, 1, 1)
        schedule_grid.attach(lbl_from, 2, 0, 1, 1)
        schedule_grid.attach(lbl_until, 3, 0, 1, 1)

        current_schedule = self._settings_manager.get_schedule()
        for day_idx in range(7):
            day_key = str(day_idx)
            day_schedule = current_schedule.get(day_key, {"enabled": True, "from": 9, "until": 17})

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            schedule_grid.attach(row_box, 0, day_idx + 1, 4, 1)
            self._schedule_rows.append(row_box)

            # Per-day enable checkbox
            check_day = Gtk.CheckButton()
            check_day.set_active(day_schedule.get("enabled", True))
            row_box.pack_start(check_day, False, False, 0)
            self._schedule_day_checks.append(check_day)

            label_day = Gtk.Label(label=self._day_names[day_idx])
            label_day.set_xalign(0)
            label_day.set_size_request(110, -1)
            row_box.pack_start(label_day, False, False, 0)

            spin_from = Gtk.SpinButton()
            adj_from = Gtk.Adjustment(
                value=day_schedule["from"], lower=0.0, upper=23.0,
                step_increment=1.0, page_increment=1.0, page_size=0.0
            )
            spin_from.set_adjustment(adj_from)
            spin_from.set_digits(0)
            spin_from.set_numeric(True)
            spin_from.set_range(0, 23)
            row_box.pack_start(spin_from, False, False, 0)
            self._schedule_spin_from.append(spin_from)

            spin_until = Gtk.SpinButton()
            adj_until = Gtk.Adjustment(
                value=day_schedule["until"], lower=0.0, upper=23.0,
                step_increment=1.0, page_increment=1.0, page_size=0.0
            )
            spin_until.set_adjustment(adj_until)
            spin_until.set_digits(0)
            spin_until.set_numeric(True)
            spin_until.set_range(0, 23)
            row_box.pack_start(spin_until, False, False, 0)
            self._schedule_spin_until.append(spin_until)

        # Connect the enable switch to toggle sensitivity of schedule rows
        self.switch_schedule_enable.connect("notify::active", self._on_schedule_enable_toggled)
        self._on_schedule_enable_toggled(self.switch_schedule_enable, None)

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
        self._initial_schedule_enabled = self.switch_schedule_enable.get_active()
        self._initial_schedule = self._collect_schedule_from_ui()

        btn_save.connect("clicked", self._on_save_clicked)
        btn_cancel.connect("clicked", self._on_cancel_clicked)
        self.connect("delete-event", self._on_delete_event) # Handle window 'X' button

        print("SettingsWindow (GTK3): Initialized.")
        self.show_all() # Make window and widgets visible


    def _on_schedule_enable_toggled(self, switch, gparam):
        """Toggles sensitivity of the schedule day rows based on the enable switch."""
        enabled = self.switch_schedule_enable.get_active()
        for row in self._schedule_rows:
            row.set_sensitive(enabled)

    def _collect_schedule_from_ui(self) -> dict:
        """Reads the current schedule values (including per-day enabled) from the UI into a dict."""
        schedule = {}
        for day_idx in range(7):
            day_key = str(day_idx)
            schedule[day_key] = {
                "enabled": self._schedule_day_checks[day_idx].get_active(),
                "from": self._schedule_spin_from[day_idx].get_value_as_int(),
                "until": self._schedule_spin_until[day_idx].get_value_as_int(),
            }
        return schedule


    def _on_save_clicked(self, widget):
        """Saves all settings if changed and closes the window."""
        print("SettingsWindow: Save clicked.")

        # Get current values
        current_interval = self.spin_break_interval.get_value_as_int()
        current_schedule_enabled = self.switch_schedule_enable.get_active()
        current_schedule = self._collect_schedule_from_ui()

        # Check if anything changed
        interval_changed = current_interval != self._initial_interval
        schedule_enabled_changed = current_schedule_enabled != self._initial_schedule_enabled
        schedule_changed = current_schedule != self._initial_schedule

        if not (interval_changed or schedule_enabled_changed or schedule_changed):
            print("SettingsWindow: No changes detected.")
            self.destroy() # Close without saving if nothing changed
            return

        print("SettingsWindow: Changes detected, saving...")
        try:
            # Save all changed values (SettingsManager handles sync internally)
            if interval_changed:
                self._settings_manager.set_break_interval(current_interval)
            if schedule_enabled_changed:
                 self._settings_manager.set_schedule_enabled(current_schedule_enabled)
            if schedule_changed:
                 self._settings_manager.set_schedule(current_schedule)

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
            if saved_interval is not None and saved_interval != new_interval:
                 print(f"[Verification] ERROR: Interval mismatch. Expected {new_interval}, got {saved_interval}")
                 settings_ok = False
            else:
                 print(f"[Verification] Interval OK ({saved_interval}).")

            # Print other saved values
            print(f"[Verification] Schedule enabled saved as: {saved_settings.get(SettingsManager.KEY_SCHEDULE_ENABLED)}")
            print(f"[Verification] Schedule saved as: {saved_settings.get(SettingsManager.KEY_SCHEDULE)}")

            if settings_ok: print("[Verification] All checks passed.")
        except Exception as e:
             print(f"[Verification] Could not read or parse config file: {e}")

        print("Quitting main loop after save.")
        if main_loop.is_running():
            main_loop.quit()

    try:
        settings_mgr = SettingsManager()
        print(f"Initial interval: {settings_mgr.get_break_interval()}")
        print(f"Initial schedule enabled: {settings_mgr.get_schedule_enabled()}")
        print(f"Initial schedule: {settings_mgr.get_schedule()}")

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
