# File: pause_duration_dialog.py
import sys
import gi
try:
    gi.require_version('Gtk', '3.0')
except ValueError as e:
    print(f"Error: Could not satisfy Gtk version requirement (3.0). {e}", file=sys.stderr)
    # This might be non-fatal if dialog isn't used, but better to know.
    # sys.exit(1) # Or just let it fail later

from gi.repository import Gtk

class PauseDurationDialog(Gtk.Dialog):
    """
    A simple dialog to get a pause duration (in minutes) from the user.
    """
    def __init__(self, parent_window=None, title="Pause Timer"): # Make parent and title optional
        super().__init__(title=title, transient_for=parent_window, flags=0)
        self.add_buttons(
            # Use standard GTK stock IDs
            Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
            Gtk.STOCK_OK, Gtk.ResponseType.OK
        )

        self.set_modal(True)
        self.set_default_size(300, 100)
        self.set_border_width(10)
        self.set_position(Gtk.WindowPosition.CENTER) # Center it

        content_area = self.get_content_area() # Box GtkDialog uses

        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        # Set margins for the hbox within the content area
        hbox.set_margin_top(10)
        hbox.set_margin_bottom(10)
        hbox.set_margin_start(5)
        hbox.set_margin_end(5)
        content_area.pack_start(hbox, True, True, 0) # Fill horizontally

        # --- Label Changed ---
        label = Gtk.Label(label="Pause duration (minutes):")
        label.set_xalign(0) # Align left
        hbox.pack_start(label, False, False, 0) # Don't expand label

        self.spin_duration = Gtk.SpinButton()
        # --- Adjustment Changed for Minutes ---
        adjustment = Gtk.Adjustment(
            value=5,     # Default 5 minutes
            lower=1,     # Min 1 minute
            upper=1440,    # Max 24 hours (in minutes)
            step_increment=1, # Step by 1 min
            page_increment=5, # Page up/down by 5 mins
            page_size=0
        )
        self.spin_duration.set_adjustment(adjustment)
        self.spin_duration.set_digits(0) # No decimal places for minutes
        self.spin_duration.set_numeric(True)
        hbox.pack_start(self.spin_duration, True, True, 0) # Expand spin button

        # Set OK button as default response on Enter
        ok_button = self.get_widget_for_response(Gtk.ResponseType.OK)
        if ok_button:
            ok_button.set_can_default(True)
            ok_button.grab_default()

        self.spin_duration.grab_focus() # Focus input field
        self.show_all()

    def get_duration_seconds(self):
        """Returns the selected duration converted to seconds."""
        # --- Conversion Added ---
        try:
            minutes = self.spin_duration.get_value_as_int()
        except Exception: # Catch potential errors if value is weird somehow
             minutes = 0
        # Ensure minimum of 1 minute? No, allow <1 min if user types it, converted below.
        # The adjustment lower bound handles the spin button itself.
        return max(1, minutes * 60) # Return seconds, minimum 1 sec

# --- Test Code ---
if __name__ == '__main__':
    print("Running PauseDurationDialog Test (Minutes Input)...")
    try: Gtk.init_check()
    except Exception: Gtk.init(None)

    dialog = PauseDurationDialog()
    response = dialog.run() # Blocks until dialog responds

    if response == Gtk.ResponseType.OK:
        # Get minutes from spin button directly for display
        minutes_entered = dialog.spin_duration.get_value_as_int()
        # Get calculated seconds using the method
        duration_seconds = dialog.get_duration_seconds()
        print(f"Dialog OK, duration selected: {minutes_entered} minutes ({duration_seconds} seconds)")
    elif response == Gtk.ResponseType.CANCEL or response == Gtk.ResponseType.DELETE_EVENT:
         print("Dialog Cancelled or Closed.")
    else:
         print(f"Dialog returned unexpected response: {response}")

    dialog.destroy()
    print("Test finished.")
