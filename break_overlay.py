# File: break_overlay.py (GTK3 Version - Corrected Signal Emission & Dismiss Delay)
import sys
import gi
import time # Only for test delay

try:
    gi.require_version('Gtk', '3.0')
    gi.require_version('GLib', '2.0')
    gi.require_version('GObject', '2.0')
    gi.require_version('Gdk', '3.0') # Needed for Screen, Button constants
except ValueError as e:
    print(f"Error: Could not satisfy Gtk/GLib/GObject/Gdk version requirements. {e}", file=sys.stderr)
    sys.exit(1)

from gi.repository import Gtk, GLib, GObject, Gdk

class BreakOverlayWindow(Gtk.Window): # Inherit from Gtk.Window
    """
    A fullscreen, semi-transparent overlay window displayed during break time (GTK3).
    Shows elapsed break time and offers postpone options.
    Includes a 3-second delay before background clicks dismiss the window.
    """

    __gsignals__ = {
        'postponed': (GObject.SignalFlags.RUN_FIRST, None, (int,)), # Emits postpone minutes
    }

    # Delay before buttons are enabled (in seconds)
    BUTTON_ENABLE_DELAY_SECONDS = 3

    def __init__(self, width: int = 1000, height: int = 600, top_margin: int = 0, is_centered: bool = True, **kwargs):
        """Initializes the BreakOverlayWindow."""
        super().__init__(**kwargs)

        self._elapsed_seconds = 0
        self._elapsed_timer_id = None

        self.set_title("MindfulBreak - Take a Break!")
        self.set_decorated(False)
        self.set_keep_above(True)
        # Set window type hint to SPLASHSCREEN to prevent tiling window managers
        # from automatically managing this window.
        self.set_type_hint(Gdk.WindowTypeHint.SPLASHSCREEN)        
        self.set_default_size(width, height)

        # --- Position the window ---
        screen = Gdk.Screen.get_default()
        # Get geometry of the primary monitor
        monitor_num = screen.get_primary_monitor()
        monitor_geometry = screen.get_monitor_geometry(monitor_num)

        # Calculate position relative to the primary monitor,
        # accounting for multi-monitor setups where the primary
        # monitor might not start at (0, 0).
        pos_y = top_margin + monitor_geometry.y
        pos_x = monitor_geometry.x # Default to left edge of primary monitor

        if is_centered:
            pos_x = monitor_geometry.x + (monitor_geometry.width - width) // 2

        # Ensure position is within screen bounds as a fallback
        pos_x = max(monitor_geometry.x, pos_x)
        pos_y = max(monitor_geometry.y, pos_y)

        self.move(pos_x, pos_y)

        # Set opacity (Ignoring deprecation warning)
        try:
            self.set_opacity(0.75)
        except AttributeError:
             print("Warning: set_opacity not available.", file=sys.stderr)

        # --- EventBox for background click detection ---
        self.event_box = Gtk.EventBox()
        self.add(self.event_box)

        # --- Main Layout Box (Inside the EventBox) ---
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_vexpand(True)
        main_box.set_hexpand(True)
        main_box.set_valign(Gtk.Align.CENTER)
        main_box.set_halign(Gtk.Align.CENTER)
        self.event_box.add(main_box)

        # --- Content Box (to group labels and buttons) ---
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        content_box.set_valign(Gtk.Align.CENTER)
        content_box.set_halign(Gtk.Align.CENTER)
        main_box.pack_start(content_box, False, False, 0)

        # --- Main Label ---
        lbl_title = Gtk.Label()
        lbl_title.set_markup("<span size='xx-large' weight='bold'>Time for a break!</span>")
        lbl_title.get_style_context().add_class("overlay-title")
        content_box.pack_start(lbl_title, False, False, 0)

        # --- Elapsed Time Label ---
        self.lbl_elapsed_time = Gtk.Label(label="Break started: 00:00")
        self.lbl_elapsed_time.get_style_context().add_class("overlay-elapsed")
        content_box.pack_start(self.lbl_elapsed_time, False, False, 0)

        # --- Button Box ---
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=15)
        button_box.set_halign(Gtk.Align.CENTER)
        content_box.pack_start(button_box, False, False, 15)
        self.action_buttons = []  # Store buttons to enable them later

        # --- Postpone Buttons ---
        # Create buttons in a loop to ensure consistent styling and state
        for minutes in [5, 10, 20, 30]:
            btn = Gtk.Button(label=f"Postpone {minutes} min")
            btn.connect('clicked', self._on_postpone_clicked, minutes)
            # Apply style and initial state consistently
            btn.get_style_context().add_class("overlay-button")
            btn.set_sensitive(False)
            # Add to layout and list for later enabling
            button_box.pack_start(btn, False, False, 0)
            self.action_buttons.append(btn)

        # --- Apply CSS ---
        self._apply_css()

        print("BreakOverlayWindow (GTK3): Initialized.")


    def _apply_css(self):
        """Applies custom CSS for styling the overlay."""
        provider = Gtk.CssProvider()
        # Use a generic selector for the window now
        css = """        
        window {
            background-color: rgba(30, 30, 30, 0.85);
        }
        label {
            color: white;
            text-shadow: 1px 1px 2px black;
            background-color: transparent;
        }
        label.overlay-title { font-size: 24pt; }
        label.overlay-elapsed { font-size: 16pt; }
        button.overlay-button {
            font-size: 12pt; padding: 8px 16px; margin: 15px;
            border-radius: 5px; background-image: none; background-color: #555;
            color: white; border: 1px solid #777;
            box-shadow: 1px 1px 3px rgba(0,0,0,0.4);
        }
        button.overlay-button:hover { background-color: #666; }
        button.overlay-button:active { background-color: #444; }
        """
        try:
            provider.load_from_data(css.encode('utf-8'))
        except GLib.Error as e:
            print(f"CSS Loading Error: {e}", file=sys.stderr)
            return
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def show_and_start_elapsed_timer(self):
        """Makes the window visible, starts elapsed timer, and starts dismiss delay timer."""
        print("BreakOverlayWindow: Showing and starting timers.")
        self._elapsed_seconds = 0
        self._update_elapsed_label()

        # --- Start timer to enable buttons ---
        print(f"BreakOverlayWindow: Starting {self.BUTTON_ENABLE_DELAY_SECONDS}s button enable timer.")
        GLib.timeout_add_seconds(
            self.BUTTON_ENABLE_DELAY_SECONDS,
            self._enable_buttons
        )

        # Ensure previous elapsed timer is stopped if any
        if self._elapsed_timer_id:
            GLib.source_remove(self._elapsed_timer_id)
        # Start elapsed timer
        self._elapsed_timer_id = GLib.timeout_add_seconds(1, self._update_elapsed_timer)

        self.show_all()

    def _enable_buttons(self):
        """Callback for the button delay timer. Enables all action buttons."""
        print("BreakOverlayWindow: Delay ended. Enabling postpone buttons.")
        for btn in self.action_buttons:
            btn.set_sensitive(True)
        return GLib.SOURCE_REMOVE # Stop this timer

    def hide_and_stop_elapsed_timer(self):
        """Hides the window and stops the timers."""
        print("BreakOverlayWindow: Hiding and stopping timers.")
        if self._elapsed_timer_id:
            GLib.source_remove(self._elapsed_timer_id)
            self._elapsed_timer_id = None

        # Check if not already destroyed before calling destroy
        if hasattr(self, 'is_destroyed') and not self.is_destroyed():
             print("BreakOverlayWindow: Calling self.destroy()")
             self.destroy()
        elif hasattr(self, 'props') and self.props.visible:
             print("BreakOverlayWindow: Calling self.hide()")
             self.hide()
        else:
             print("BreakOverlayWindow: Already destroyed or being destroyed/hidden.")


    def _update_elapsed_timer(self) -> bool:
        """Internal callback to update the elapsed time label."""
        self._elapsed_seconds += 1
        self._update_elapsed_label()
        return True # Keep timer running

    def _update_elapsed_label(self):
        """Formats seconds into MM:SS and updates the label."""
        minutes = self._elapsed_seconds // 60
        seconds = self._elapsed_seconds % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        self.lbl_elapsed_time.set_label(f"Break started: {time_str}")

    def _on_postpone_clicked(self, button, minutes: int):
        """
        Handles clicks on the postpone buttons. Works immediately.
        """
        print(f"BreakOverlayWindow: Postpone {minutes} min clicked.")
        self.emit('postponed', minutes) # Emit signal BEFORE destroy
        self.hide_and_stop_elapsed_timer()


# --- Test Code (GTK3 - Modified for delay test) ---
if __name__ == '__main__':
    print("Running BreakOverlayWindow Test (GTK3 Version with Dismiss Delay)...")

    main_loop = GLib.MainLoop()
    overlay_win = None
    
    def on_postponed(emitter, minutes):
        print(f"[Signal Handler] ****** POSTPONED: {minutes} minutes ******")
        if main_loop.is_running(): main_loop.quit()

    # --- Test Setup ---
    try:
        try: Gtk.init_check()
        except Exception: Gtk.init(None)

        overlay_win = BreakOverlayWindow()

        overlay_win.connect('postponed', on_postponed)
        overlay_win.connect('destroy', lambda w: print("[Debug] Overlay Destroy signal received.") or (main_loop.quit() if main_loop.is_running() else None))

        def show_overlay():
            print("Showing overlay...")
            if overlay_win and hasattr(overlay_win, 'is_destroyed') and not overlay_win.is_destroyed():
                overlay_win.show_and_start_elapsed_timer()
                print(f"--- Buttons will be disabled for {BreakOverlayWindow.BUTTON_ENABLE_DELAY_SECONDS} seconds. Clicking background will do nothing. ---")
            else:
                print("Error: Overlay window was destroyed before it could be shown.")
                if main_loop.is_running(): main_loop.quit()
            return False

        GLib.timeout_add_seconds(1, show_overlay)

        print("\nStarting Gtk MainLoop...")
        main_loop.run()

    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", file=sys.stderr)
        if main_loop.is_running():
             main_loop.quit()
    finally:
        print("\nTest finished.")
