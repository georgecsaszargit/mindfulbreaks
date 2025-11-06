# File: tray_icon.py
import sys
import gi
import math # For formatting time

try:
    # Use AyatanaAppIndicator3 if available (standard on modern Ubuntu/Debian)
    gi.require_version('AyatanaAppIndicator3', '0.1')
    use_ayatana = True
except ValueError:
    # Fallback to AppIndicator3
    try:
        print("AyatanaAppIndicator3 not found, falling back to AppIndicator3.", file=sys.stderr)
        gi.require_version('AppIndicator3', '0.1')
        use_ayatana = False
    except ValueError:
        print("Error: Neither AyatanaAppIndicator3 nor AppIndicator3 found.", file=sys.stderr)
        print("Please install gir1.2-ayatanaappindicator3-0.1 (preferred) or gir1.2-appindicator3-0.1", file=sys.stderr)
        sys.exit(1)

# Import the correct module based on availability
if use_ayatana:
    from gi.repository import AyatanaAppIndicator3 as AppIndicator3
else:
    from gi.repository import AppIndicator3

# Require Gtk and GLib/GObject
try:
    gi.require_version('Gtk', '3.0') # AppIndicator usually works best with Gtk3 menus
    gi.require_version('GObject', '2.0')
    gi.require_version('GLib', '2.0')
except ValueError as e:
     print(f"Error: Could not satisfy Gtk/GObject/GLib version requirement. {e}", file=sys.stderr)
     sys.exit(1)

from gi.repository import Gtk, GObject, GLib

class TrayIcon(GObject.Object):
    """
    Manages the system tray icon using AppIndicator library,
    displaying timer status and providing a control menu.
    Removed direct Pause option, uses Pause For... dialog.
    """

    # Define internal state constants
    STATE_RUNNING = "RUNNING"
    STATE_PAUSED = "PAUSED"       # Represents Idle or general paused state
    STATE_IDLE = "IDLE"         # Specific state for display label if needed, but uses PAUSED icon/menu
    STATE_BREAK = "BREAK_ACTIVE"
    STATE_STOPPED = "STOPPED"
    STATE_MANUAL_PAUSE = "MANUAL_PAUSE"

    # Define standard icon names (or use custom ones)
    ICON_DEFAULT = "preferences-system-time-symbolic"
    ICON_RUNNING = "media-playback-start-symbolic"
    ICON_PAUSED = "media-playback-pause-symbolic"
    ICON_BREAK = "dialog-warning-symbolic" # Or 'user-idle-symbolic'

    # Removed 'pause_timer_requested' signal
    __gsignals__ = {
        'start_timer_requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        # 'pause_timer_requested': (GObject.SignalFlags.RUN_FIRST, None, ()), # REMOVED
        'resume_timer_requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'pause_for_requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'set_time_requested': (GObject.SignalFlags.RUN_FIRST, None, ()),        
        'settings_requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'quit_requested': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, indicator_id: str):
        """
        Initializes the TrayIcon.

        Args:
            indicator_id: A unique ID for the application indicator.
        """
        GObject.Object.__init__(self)

        self.indicator = AppIndicator3.Indicator.new(
            indicator_id,
            self.ICON_DEFAULT,
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS)

        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)

        # Build the menu
        self.menu = Gtk.Menu()

        # --- Dynamic Item (Start/Resume/Start New) ---
        # This item no longer shows "Pause Timer"
        self.item_start_resume = Gtk.MenuItem(label="Start Timer")
        self.item_start_resume.connect('activate', self._on_start_resume_activate)
        self.menu.append(self.item_start_resume)
        self._current_dynamic_action = 'start' # Tracks what this item does

        # --- Pause For... Item ---
        self.item_pause_for = Gtk.MenuItem(label="Pause for...")
        self.item_pause_for.connect('activate', self._on_pause_for_activate)
        self.menu.append(self.item_pause_for)

        # --- Set Time... Item ---
        self.item_set_time = Gtk.MenuItem(label="Set Time...")
        self.item_set_time.connect('activate', self._on_set_time_activate)
        self.menu.append(self.item_set_time)        

        # --- Separator ---
        self.menu.append(Gtk.SeparatorMenuItem())

        # --- Settings ---
        item_settings = Gtk.MenuItem(label="Settings")
        item_settings.connect('activate', self._on_settings_activate)
        self.menu.append(item_settings)

        # --- Quit ---
        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect('activate', self._on_quit_activate)
        self.menu.append(item_quit)

        self.menu.show_all()
        self.indicator.set_menu(self.menu)

        # Set initial visual state
        self.update_status(self.STATE_STOPPED)

        print(f"TrayIcon: Initialized with ID '{indicator_id}'")


    def update_status(self, state: str, remaining_seconds: int = 0):
        """
        Updates the indicator icon and label based on the provided state.
        Now always shows MM:SS when running.

        Args:
            state: The current state (use STATE_* constants).
            remaining_seconds: Time left, used when state is RUNNING or MANUAL_PAUSE.
        """
        label = "MindfulBreak" # Default label
        icon_name = self.ICON_DEFAULT
        dynamic_label = "Start Timer"
        dynamic_action = "start"
        dynamic_sensitive = True
        pause_for_sensitive = False # "Pause for..." only available when running
        set_time_sensitive = False # "Set Time..." only available when running        

        if state == self.STATE_RUNNING:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            # --- Change: Always format as MM:SS ---
            label = f"{minutes:02d}:{seconds:02d} left"
            # --- End Change ---
            icon_name = self.ICON_RUNNING
            # Option 2: Disable the dynamic item when running
            dynamic_label = "Running..." # Display only, not clickable
            dynamic_action = "none"      # Custom action type
            dynamic_sensitive = False    # Disable it
            pause_for_sensitive = True   # Enable "Pause for..." when running
            set_time_sensitive = True    # Enable "Set Time..." when running            

        elif state == self.STATE_PAUSED:
            label = "Paused"
            icon_name = self.ICON_PAUSED
            dynamic_label = "Resume Timer"
            dynamic_action = "resume"

        elif state == self.STATE_IDLE:
            label = "Paused (Idle)"
            icon_name = self.ICON_PAUSED
            dynamic_label = "Resume Timer"
            dynamic_action = "resume"

        elif state == self.STATE_BREAK:
            label = "Break Time!"
            icon_name = self.ICON_BREAK
            dynamic_label = "Start New Timer" # Start after break
            dynamic_action = "start"

        elif state == self.STATE_STOPPED:
            label = "Stopped"
            icon_name = self.ICON_DEFAULT
            dynamic_label = "Start Timer"
            dynamic_action = "start"

        elif state == self.STATE_MANUAL_PAUSE:
             minutes = remaining_seconds // 60
             seconds = remaining_seconds % 60
             # --- Change: Format manual pause as MM:SS too ---
             label = f"Paused for {minutes:02d}:{seconds:02d}"
             # --- End Change ---
             icon_name = self.ICON_PAUSED
             dynamic_label = "Resume Now" # Allow manual resume
             dynamic_action = "resume"

        else:
             print(f"Warning: Unknown state '{state}' in update_status.", file=sys.stderr)

        # Apply updates (remains same)
        self.indicator.set_label(label, "")
        self.indicator.set_icon_full(icon_name, label)

        self.item_start_resume.set_label(dynamic_label)
        self.item_start_resume.set_sensitive(dynamic_sensitive)
        self._current_dynamic_action = dynamic_action

        self.item_pause_for.set_sensitive(pause_for_sensitive)
        self.item_set_time.set_sensitive(set_time_sensitive)        

        # print(f"TrayIcon: Updated - State={state}, Label='{label}', Icon='{icon_name}', DynAction='{dynamic_action}'")

    # --- Signal Emitters for Menu Actions ---
    def _on_start_resume_activate(self, widget):
        """Callback for the dynamic start/resume menu item."""
        if self._current_dynamic_action == "start":
            print("TrayIcon: Start action requested.")
            self.emit('start_timer_requested')
        elif self._current_dynamic_action == "resume":
            print("TrayIcon: Resume action requested.")
            self.emit('resume_timer_requested')
        elif self._current_dynamic_action == "none":
             # Action when item is disabled (e.g., "Running...")
             pass
        else:
             print(f"TrayIcon: Unknown dynamic action '{self._current_dynamic_action}'")

    def _on_pause_for_activate(self, widget):
        print("TrayIcon: Pause for... action requested.")
        self.emit('pause_for_requested')

    def _on_set_time_activate(self, widget):
        print("TrayIcon: Set Time... action requested.")
        self.emit('set_time_requested')

    def _on_settings_activate(self, widget):
        print("TrayIcon: Settings action requested.")
        self.emit('settings_requested')

    def _on_quit_activate(self, widget):
        print("TrayIcon: Quit action requested.")
        self.emit('quit_requested')


# --- Test Code (Minimal - uncomment and adapt if needed) ---
if __name__ == '__main__':
    print("Running TrayIcon Test...")
    print("This test code is minimal. Run the main application for full testing.")
    # Example of how to test the new state manually:
    # try:
    #     Gtk.init(None)
    #     tray = TrayIcon('test.indicator')
    #     def test_manual_pause():
    #         print("TEST: Setting manual pause state for 15s")
    #         tray.update_status(tray.STATE_MANUAL_PAUSE, 15)
    #         return False
    #     def test_running():
    #          print("TEST: Setting running state")
    #          tray.update_status(tray.STATE_RUNNING, 120)
    #          return False
    #
    #     GLib.timeout_add_seconds(5, test_running)
    #     GLib.timeout_add_seconds(10, test_manual_pause)
    #     Gtk.main()
    # except Exception as e:
    #     print(f"Error: {e}")

    pass # Keep python interpreter running if run directly without main loop
