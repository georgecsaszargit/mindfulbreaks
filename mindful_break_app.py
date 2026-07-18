# File: mindful_break_app.py (Main Application - Updated)

import sys
import os
import gi

try:
    # Ensure GTK 3, GLib, GObject, Gdk are available
    gi.require_version('Gtk', '3.0')
    gi.require_version('GLib', '2.0')
    gi.require_version('GObject', '2.0')
    gi.require_version('Gdk', '3.0')
    # Check for AppIndicator/Ayatana
    try:
        gi.require_version('AyatanaAppIndicator3', '0.1')
    except ValueError:
        gi.require_version('AppIndicator3', '0.1')

except ValueError as e:
    print(f"Error: Could not satisfy Gtk/GLib/GObject/AppIndicator version requirements. {e}", file=sys.stderr)
    sys.exit(1)

from gi.repository import Gtk, GLib, GObject, Gio

# Import all the components
try:
    from settings_manager import SettingsManager
    from timer_manager import TimerManager
    from tray_icon import TrayIcon
    from settings_window import SettingsWindow # GTK3 version
    from break_overlay import BreakOverlayWindow # GTK3 version
    from sound_player import SoundPlayer # playsound version with block=True fix
    from pause_duration_dialog import PauseDurationDialog # Import dialog
except ImportError as e:
     print(f"Error: Failed to import one or more application components. {e}", file=sys.stderr)
     print("Ensure all .py files are present.")
     sys.exit(1)

# --- Constants ---
APP_ID = "org.example.mindfulbreak"
DEFAULT_SOUND_FILE = "notification.wav" # ** Update if needed **

class MindfulBreakApp(Gtk.Application):
    """
    Main application class integrating all components for the break reminder.
    """

    def __init__(self, **kwargs):
        super().__init__(application_id=APP_ID,
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
                         **kwargs)

        # Component Instances
        self.settings_manager = None
        self.timer_manager = None
        self.tray_icon = None
        self.sound_player = None
        self.settings_window = None
        self.break_overlay_window = None

        # State flags and variables
        self._manual_pause_timer_id = None
        self._manual_pause_remaining_seconds = 0

        self.connect("command-line", self.on_command_line)


    def on_command_line(self, command_line, *args):
        print("MindfulBreakApp: Command line signal received.")
        self.activate()
        return 0


    def do_startup(self):
        """Initialize components when the application first starts."""
        Gtk.Application.do_startup(self)
        print("MindfulBreakApp: Starting up...")

        try:
            self.settings_manager = SettingsManager()

            # --- Sound Player Setup ---
            sound_path = DEFAULT_SOUND_FILE
            if not os.path.isabs(sound_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                sound_path = os.path.join(script_dir, DEFAULT_SOUND_FILE)
            self.sound_player = SoundPlayer(sound_file_path=sound_path)

            # --- Timer Manager Setup ---
            self.timer_manager = TimerManager()
            initial_interval = self.settings_manager.get_break_interval()
            self.timer_manager.set_interval(initial_interval)

            # --- Tray Icon Setup ---
            self.tray_icon = TrayIcon(indicator_id=APP_ID + ".indicator")

            # Initialize schedule toggle state from settings
            self.tray_icon.set_schedule_enabled_state(self.settings_manager.get_schedule_enabled())

            # --- Connect signals ---
            self._connect_signals()

            print("MindfulBreakApp: Startup complete.")

        except Exception as e:
            print(f"FATAL ERROR during startup: {e}", file=sys.stderr)
            self.quit()


    def do_activate(self):
        """Called when the application is activated."""
        self.hold()
        print("MindfulBreakApp: Holding application active.")

        if self.tray_icon:
            self.tray_icon.update_status(self.tray_icon.STATE_STOPPED)
        print("MindfulBreakApp: Activated (running in background).")

        # --- Auto-start Timer ---
        print("MindfulBreakApp: Attempting auto-start...")
        if self.settings_manager and self.timer_manager:
            try:
                self.on_start_timer_requested(None)
                print("MindfulBreakApp: Auto-start initiated.")
            except Exception as e:
                 print(f"Error during auto-start: {e}", file=sys.stderr)
                 if self.tray_icon:
                      self.tray_icon.update_status(self.tray_icon.STATE_STOPPED)
        else:
             print("MindfulBreakApp: Cannot auto-start, components missing.")
             if self.tray_icon:
                  self.tray_icon.update_status(self.tray_icon.STATE_STOPPED)


    def do_shutdown(self):
        """Clean up resources when the application quits."""
        if hasattr(self, 'get_is_busy') and self.get_is_busy():
             print("MindfulBreakApp: Releasing hold during shutdown.")
             self.release()

        print("MindfulBreakApp: Shutting down...")
        self._cancel_manual_pause()

        if self.timer_manager:
            self.timer_manager.stop()

        if self.settings_window and hasattr(self.settings_window, 'is_destroyed') and not self.settings_window.is_destroyed():
             print("MindfulBreakApp: Destroying settings window on shutdown.")
             self.settings_window.destroy()
        if self.break_overlay_window and hasattr(self.break_overlay_window, 'is_destroyed') and not self.break_overlay_window.is_destroyed():
             print("MindfulBreakApp: Destroying overlay window on shutdown.")
             self.break_overlay_window.destroy()

        Gtk.Application.do_shutdown(self)
        print("MindfulBreakApp: Shutdown complete.")


    def _connect_signals(self):
        """Connect signals from components to application handlers."""
        if not self.timer_manager or not self.tray_icon:
            print("Error: Cannot connect signals, components not initialized.", file=sys.stderr)
            return

        # --- Timer Manager Signals ---
        self.timer_manager.connect('timer_tick', self.on_timer_tick)
        self.timer_manager.connect('break_started', self.on_break_started)
        self.timer_manager.connect('timer_paused', self.on_timer_paused)
        self.timer_manager.connect('timer_resumed', self.on_timer_resumed)
        self.timer_manager.connect('timer_stopped', self.on_timer_stopped)
        self.timer_manager.connect('timer_started', self.on_timer_started)

        # --- Tray Icon Signals ---
        self.tray_icon.connect('start_timer_requested', self.on_start_timer_requested)
        self.tray_icon.connect('resume_timer_requested', self.on_resume_timer_requested)
        self.tray_icon.connect('pause_for_requested', self.on_pause_for_requested)
        self.tray_icon.connect('set_time_requested', self.on_set_time_requested)
        self.tray_icon.connect('settings_requested', self.on_settings_requested)
        self.tray_icon.connect('schedule_toggled', self.on_schedule_toggled)
        self.tray_icon.connect('quit_requested', self.on_quit_requested)


    # --- Signal Handler Methods ---

    # --- Timer Handlers ---
    def on_timer_tick(self, timer_manager, remaining_seconds):
        if self.tray_icon and timer_manager.state == timer_manager.STATE_RUNNING:
            self.tray_icon.update_status(self.tray_icon.STATE_RUNNING, remaining_seconds)

    def on_break_started(self, timer_manager):
        print("App: Break started.")

        # --- Schedule check: suppress break overlay outside allowed hours ---
        if self.settings_manager and not self.settings_manager.is_break_allowed_now():
            print("App: Break suppressed by schedule (outside allowed hours). Restarting cycle silently.")
            # Skip sound + overlay; restart the timer cycle without showing the break UI
            interval = self.settings_manager.get_break_interval()
            self.timer_manager.set_interval(interval)
            self.timer_manager.start()
            if self.tray_icon:
                self.tray_icon.update_status(self.tray_icon.STATE_RUNNING, self.timer_manager.remaining_seconds)
            return

        if self.sound_player:
            self.sound_player.play_break_sound()
        if self.tray_icon:
            self.tray_icon.update_status(self.tray_icon.STATE_BREAK)

        if self.break_overlay_window and hasattr(self.break_overlay_window, 'is_destroyed') and not self.break_overlay_window.is_destroyed():
             print("App: Destroying previous overlay instance.")
             self.break_overlay_window.destroy()

        # --- Get Overlay Geometry from Settings ---
        overlay_width = self.settings_manager.get_overlay_width()
        overlay_height = self.settings_manager.get_overlay_height()
        overlay_top_margin = self.settings_manager.get_overlay_top_margin()
        overlay_centered = self.settings_manager.get_overlay_horizontal_centered()
        print(f"App: Creating BreakOverlayWindow ({overlay_width}x{overlay_height}, top: {overlay_top_margin}, centered: {overlay_centered})")

        self.break_overlay_window = BreakOverlayWindow(
            width=overlay_width,
            height=overlay_height,
            top_margin=overlay_top_margin,
            is_centered=overlay_centered
        )

        print("App: Connecting overlay signals...")
        self.break_overlay_window.connect('dismissed', self.on_overlay_dismissed)
        self.break_overlay_window.connect('postponed', self.on_overlay_postponed)
        self.break_overlay_window.connect('destroy', self.on_overlay_window_destroyed)
        print("App: Showing overlay...")
        self.break_overlay_window.show_and_start_elapsed_timer()

    def on_timer_paused(self, timer_manager):
        if self._manual_pause_timer_id:
             return
        if self.tray_icon:
            self.tray_icon.update_status(self.tray_icon.STATE_PAUSED)

    def on_timer_resumed(self, timer_manager):
        self._cancel_manual_pause()
        if self.tray_icon:
             self.tray_icon.update_status(self.tray_icon.STATE_RUNNING, timer_manager.remaining_seconds)

    def on_timer_stopped(self, timer_manager):
        self._cancel_manual_pause()
        if self.tray_icon:
            self.tray_icon.update_status(self.tray_icon.STATE_STOPPED)

    def on_timer_started(self, timer_manager):
         self._cancel_manual_pause() # Cancel manual pause on any start/restart/postpone
         print(f"App: Timer started/postponed. Initial seconds: {timer_manager.remaining_seconds}")
         if self.tray_icon:
             # This call is correct - it passes the initial seconds
             # The updated update_status method will now format it as MM:SS
             self.tray_icon.update_status(self.tray_icon.STATE_RUNNING, timer_manager.remaining_seconds)

    # --- Tray Menu Handlers ---
    def on_start_timer_requested(self, tray_icon):
        print("App: Start timer requested via tray.")
        if not self.settings_manager or not self.timer_manager: return
        interval = self.settings_manager.get_break_interval()
        self.timer_manager.set_interval(interval)
        self.timer_manager.start()

    def on_resume_timer_requested(self, tray_icon):
        print("App: Resume timer requested via tray.")
        if not self.timer_manager: return
        self._cancel_manual_pause()
        if self.timer_manager.state == self.timer_manager.STATE_PAUSED:
            self.timer_manager.resume()

    def on_pause_for_requested(self, tray_icon):
        print("App: Pause for duration requested.")
        if self.timer_manager is None: return
        if self._manual_pause_timer_id:
             print("App: Manual pause already active.")
             return
        # Sensitivity check in tray icon is primary guard
        # if self.timer_manager.state != self.timer_manager.STATE_RUNNING:
        #     print("App: Cannot 'Pause for...' when timer is not running.")
        #     return

        dialog = PauseDurationDialog(parent_window=None)
        dialog.connect("response", self.on_pause_dialog_response)

    def on_set_time_requested(self, tray_icon):
        print("App: Set Time requested.")
        if self.timer_manager is None: return

        # Re-use the dialog with a different title
        dialog = PauseDurationDialog(parent_window=None, title="Set Remaining Time")
        dialog.connect("response", self.on_set_time_dialog_response)

    # --- Dialog Handlers ---
    def on_set_time_dialog_response(self, dialog, response_id):
        duration_seconds = 0
        if response_id == Gtk.ResponseType.OK:
            duration_seconds = dialog.get_duration_seconds()
            print(f"App: Set time dialog OK, new duration: {duration_seconds}s")
            if duration_seconds <= 0:
                 print("App: Invalid duration, ignoring.")
                 dialog.destroy()
                 return
        else:
            print("App: Set time dialog cancelled.")
            dialog.destroy()
            return

        dialog.destroy() # Destroy dialog before changing the timer

        # Convert seconds to float minutes for the postpone method
        duration_minutes = duration_seconds / 60.0
        self.timer_manager.postpone(duration_minutes)

    def on_settings_requested(self, tray_icon):
        print("App: Settings requested.")
        if not self.settings_manager: return

        if self.settings_window and hasattr(self.settings_window, 'is_destroyed') and not self.settings_window.is_destroyed():
             print("App: Settings window already open, presenting.")
             self.settings_window.present()
             return

        print("App: Creating settings window.")
        self.settings_window = SettingsWindow(settings_manager=self.settings_manager)
        self.settings_window.connect('settings_saved', self.on_settings_saved)
        self.settings_window.connect('destroy', self.on_settings_window_destroyed)

    def on_schedule_toggled(self, tray_icon, enabled):
        """Handles the schedule enable/disable toggle from the tray icon."""
        print(f"App: Schedule toggle requested, enabled={enabled}.")
        if not self.settings_manager: return
        self.settings_manager.set_schedule_enabled(enabled)
        # Tray check item already updated by the user click; keep in sync defensively
        if self.tray_icon:
            self.tray_icon.set_schedule_enabled_state(enabled)

    def on_quit_requested(self, tray_icon):
        """Handles the quit request from the tray icon."""
        print("App: Quit requested via tray.")
        if hasattr(self, 'get_is_busy') and self.get_is_busy():
            self.release()
        self.quit()

    # --- Settings Window Handlers ---
    def on_settings_saved(self, settings_window, new_interval):
        print(f"App: Settings saved signal received. Main interval (for next cycle): {new_interval} minutes.")
        if self.timer_manager:
            self.timer_manager.set_interval(new_interval)
            if self.timer_manager.state == self.timer_manager.STATE_STOPPED:
                 if self.tray_icon:
                      self.tray_icon.update_status(self.tray_icon.STATE_STOPPED)
        # Sync the tray schedule toggle with the (possibly updated) saved setting
        if self.tray_icon and self.settings_manager:
            self.tray_icon.set_schedule_enabled_state(self.settings_manager.get_schedule_enabled())

    def on_settings_window_destroyed(self, widget):
         print("App: Settings window destroyed.")
         if self.settings_window == widget:
              self.settings_window = None

    # --- Overlay Window Handlers ---
    def on_overlay_dismissed(self, overlay_window):
        print("App: Handling overlay dismissal (Done) signal...")
        if not self.settings_manager or not self.timer_manager: return
        # This effectively ends the break and starts the next work cycle
        interval = self.settings_manager.get_break_interval()
        self.timer_manager.set_interval(interval)
        self.timer_manager.start()

    def on_overlay_postponed(self, overlay_window, minutes):
        print(f"App: Handling overlay postpone signal ({minutes} minutes)...")
        if not self.timer_manager: return
        # Convert minutes if necessary (postpone method expects float minutes)
        self.timer_manager.postpone(float(minutes))

    def on_overlay_window_destroyed(self, widget):
        print("App: Break overlay window destroyed.")
        if self.break_overlay_window == widget:
            self.break_overlay_window = None

    def on_pause_dialog_response(self, dialog, response_id):
        duration_seconds = 0 # Get SECONDS from dialog method
        if response_id == Gtk.ResponseType.OK:
            duration_seconds = dialog.get_duration_seconds()
            print(f"App: Pause dialog OK, duration: {duration_seconds}s")
            if duration_seconds <= 0:
                 print("App: Invalid duration, ignoring.")
                 dialog.destroy()
                 return
        else:
            print("App: Pause dialog cancelled.")
            dialog.destroy()
            return

        dialog.destroy() # Destroy dialog before starting pause logic

        if self.timer_manager.state == self.timer_manager.STATE_RUNNING:
             self.timer_manager.pause()

        self._manual_pause_remaining_seconds = duration_seconds
        self._manual_pause_timer_id = GLib.timeout_add_seconds(1, self._manual_pause_tick)

        if self.tray_icon:
             self.tray_icon.update_status(self.tray_icon.STATE_MANUAL_PAUSE, self._manual_pause_remaining_seconds)

    # --- Manual Pause Timer Logic ---
    def _cancel_manual_pause(self):
        """Stops the manual pause timer if it's active."""
        if self._manual_pause_timer_id:
            print("App: Cancelling manual pause timer.")
            GLib.source_remove(self._manual_pause_timer_id)
            self._manual_pause_timer_id = None
            self._manual_pause_remaining_seconds = 0
            if self.timer_manager and self.timer_manager.state == self.timer_manager.STATE_PAUSED:
                 if self.tray_icon:
                     self.on_timer_paused(self.timer_manager) # Restore visual state

    def _manual_pause_tick(self):
        """Callback for the temporary manual pause timer."""
        if self._manual_pause_remaining_seconds <= 0:
            print("Warning: Manual pause tick called with zero/negative time remaining.")
            self._cancel_manual_pause() # Ensure timer ID is cleared
            if self.timer_manager and self.timer_manager.state == self.timer_manager.STATE_PAUSED:
                 print("App: Resuming main timer after manual pause finished (from tick).")
                 self.timer_manager.resume()
            return False # Stop this timer

        self._manual_pause_remaining_seconds -= 1

        if self.tray_icon:
             self.tray_icon.update_status(self.tray_icon.STATE_MANUAL_PAUSE, self._manual_pause_remaining_seconds)

        if self._manual_pause_remaining_seconds <= 0:
            print("App: Manual pause duration finished.")
            self._manual_pause_timer_id = None # Mark timer as stopped before resuming
            if self.timer_manager and self.timer_manager.state == self.timer_manager.STATE_PAUSED:
                 print("App: Resuming main timer after manual pause finished.")
                 self.timer_manager.resume()
            return False # Stop this timer
        else:
            return True # Continue this timer


# --- Main Execution ---
if __name__ == '__main__':
    print("Starting Mindful Break Application...")
    app = MindfulBreakApp()
    exit_status = app.run(sys.argv)
    print("Application finished.")
    sys.exit(exit_status)
