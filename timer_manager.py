import sys
import gi
import time # Used only for test printing

try:
    gi.require_version('GLib', '2.0')
    gi.require_version('GObject', '2.0')
except ValueError as e:
    print(f"Error: Could not satisfy GLib/GObject version requirement. {e}", file=sys.stderr)
    sys.exit(1)

from gi.repository import GLib, GObject

class TimerManager(GObject.Object):
    """
    Manages the countdown timer logic, state machine, and notifications.
    Inherits from GObject.Object to support GSignals.
    """

    # --- Define states ---
    STATE_STOPPED = 0
    STATE_RUNNING = 1
    STATE_PAUSED = 2
    STATE_BREAK_ACTIVE = 3 # Timer reached zero, waiting for user interaction

    # --- Define signals ---
    # Signals must be defined within the class scope using GObject.Signal
    # Format: signal_name = GObject.Signal(name, flags, return_type, (param_types...))
    __gsignals__ = {
        'timer_started': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'timer_paused': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'timer_resumed': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'timer_stopped': (GObject.SignalFlags.RUN_FIRST, None, ()),
        # Emits remaining seconds as an integer parameter
        'timer_tick': (GObject.SignalFlags.RUN_FIRST, None, (int,)),
        'break_started': (GObject.SignalFlags.RUN_FIRST, None, ()),
        # Could add a dedicated postpone signal if needed, but started covers it
        # 'timer_postponed': (GObject.SignalFlags.RUN_FIRST, None, (int,)), # Postponed minutes
    }

    def __init__(self):
        """Initializes the TimerManager."""
        # Initialize the parent GObject class
        GObject.Object.__init__(self)

        self._state = self.STATE_STOPPED
        self._timer_source_id = None # Stores the ID returned by GLib.timeout_add
        self._remaining_seconds = 0
        self._configured_interval_seconds = 0 # Default interval set via set_interval

    # --- Public Methods ---

    def set_interval(self, minutes: float): # Allow float for testing fractions
        """
        Sets the default interval for the timer. Does not start the timer.

        Args:
            minutes: The interval duration in minutes (must result in >= 1 second).
        """
        interval_seconds = int(round(minutes * 60)) # Convert to seconds and round nicely
        if interval_seconds < 1:
            print(f"Warning: Calculated interval ({interval_seconds}s from {minutes}min) is less than 1 second. Setting to 1 second.", file=sys.stderr)
            interval_seconds = 1

        self._configured_interval_seconds = interval_seconds
        # If stopped, update remaining time to the new interval potentially
        # If running/paused, the current cycle continues with the old interval.
        # The new interval applies on the *next* full start/reset.
        # If we are stopped, we can prime remaining_seconds for the next start.
        if self._state == self.STATE_STOPPED:
            self._remaining_seconds = self._configured_interval_seconds
        print(f"Timer interval set to {minutes:.2f} minutes ({self._configured_interval_seconds} seconds)")


    def start(self):
        """
        Starts the timer from the configured interval.
        If already running, it effectively restarts the timer.
        If paused, it restarts from the configured interval.
        """
        print("TimerManager: Start requested.")
        self._stop_internal_timer() # Clear any existing timer source

        if self._configured_interval_seconds <= 0:
            print("Warning: Cannot start timer, interval not set or is zero.", file=sys.stderr)
            return

        self._state = self.STATE_RUNNING
        self._remaining_seconds = self._configured_interval_seconds
        # Start the periodic timer, calling _tick every second (1000ms)
        self._timer_source_id = GLib.timeout_add_seconds(1, self._tick)
        self.emit('timer_started')
        # Emit initial tick immediately
        self.emit('timer_tick', self._remaining_seconds)
        print(f"TimerManager: Started with {self._remaining_seconds} seconds.")


    def pause(self):
        """
        Pauses the timer if it is currently running.
        """
        print("TimerManager: Pause requested.")
        if self._state == self.STATE_RUNNING:
            self._state = self.STATE_PAUSED
            self._stop_internal_timer() # Stop the GLib timer
            self.emit('timer_paused')
            print(f"TimerManager: Paused at {self._remaining_seconds} seconds.")
        else:
            print(f"TimerManager: Cannot pause, not running (state={self._state})")


    def resume(self):
        """
        Resumes the timer if it is currently paused.
        """
        print("TimerManager: Resume requested.")
        if self._state == self.STATE_PAUSED:
            self._state = self.STATE_RUNNING
            # Ensure we don't resume a timer that already finished while paused
            if self._remaining_seconds > 0:
                 # Restart the GLib timer
                self._timer_source_id = GLib.timeout_add_seconds(1, self._tick)
                self.emit('timer_resumed')
                # Emit current time immediately on resume
                self.emit('timer_tick', self._remaining_seconds)
                print(f"TimerManager: Resumed with {self._remaining_seconds} seconds.")
            else:
                 # This case shouldn't normally happen if pause stops ticks, but safety first
                 print("TimerManager: Resume requested but remaining time is zero. Entering break state.")
                 self._enter_break_state()
        else:
            print(f"TimerManager: Cannot resume, not paused (state={self._state})")


    def stop(self):
            """
            Stops the timer completely, regardless of state.
            Resets remaining time based on configured interval for next start.
            Always emits 'timer_stopped' signal if the state changes to stopped.
            """
            print("TimerManager: Stop requested.")
            previous_state = self._state # Store previous state
            self._stop_internal_timer()
            self._state = self.STATE_STOPPED
            # Reset remaining time for the next potential start
            self._remaining_seconds = self._configured_interval_seconds
            # Emit stopped signal if the state actually changed to stopped by this call
            if previous_state != self.STATE_STOPPED: # <--- This is the key condition
                 self.emit('timer_stopped')
            print("TimerManager: Stopped.")

    def postpone(self, minutes: float): # Allow float for fractions
        """
        Starts a shorter timer interval immediately (used after a break overlay).

        Args:
            minutes: The postpone duration in minutes (e.g., 5/60 for 5s).
                     Must result in >= 1 second.
        """
        print(f"TimerManager: Postpone requested for {minutes:.2f} minutes.")
        self._stop_internal_timer() # Clear any existing timer source

        postpone_seconds = int(round(minutes * 60)) # Convert to seconds and round
        if postpone_seconds < 1:
            print(f"Warning: Invalid postpone duration ({postpone_seconds}s from {minutes}min), using 1 second.", file=sys.stderr)
            postpone_seconds = 1

        self._state = self.STATE_RUNNING
        self._remaining_seconds = postpone_seconds
        self._timer_source_id = GLib.timeout_add_seconds(1, self._tick)
        # We reuse 'timer_started' for simplicity, could have a dedicated signal
        self.emit('timer_started')
        # Emit initial tick immediately
        self.emit('timer_tick', self._remaining_seconds)
        print(f"TimerManager: Postponed. Starting {self._remaining_seconds} second countdown.")

    # --- Private Methods ---

    def _stop_internal_timer(self):
        """Safely removes the GLib timer source if it exists."""
        if self._timer_source_id:
            GLib.source_remove(self._timer_source_id)
            self._timer_source_id = None
            # print("TimerManager: Internal GLib timer source stopped.")


    def _tick(self) -> bool:
        """
        Internal callback executed every second by GLib.timeout_add_seconds.
        Decrements remaining time and checks for break condition.

        Returns:
            bool: True to keep the timer running, False to stop it.
        """
        if self._state != self.STATE_RUNNING:
            # Should not happen if timer is managed correctly, but safety check
            print("Warning: _tick called while not in RUNNING state.", file=sys.stderr)
            self._timer_source_id = None # Ensure it stops
            return False # Stop the timer

        self._remaining_seconds -= 1
        # print(f"TimerManager: Tick! Remaining: {self._remaining_seconds}s") # Debug print

        if self._remaining_seconds > 0:
            self.emit('timer_tick', self._remaining_seconds)
            return True # Continue timer
        else:
            print("TimerManager: Timer reached zero.")
            self._enter_break_state()
            return False # Stop the timer (GLib.source_remove is implicit when False is returned)

    def _enter_break_state(self):
        """Transitions the timer to the break state."""
        self._state = self.STATE_BREAK_ACTIVE
        self._remaining_seconds = 0 # Ensure it's exactly zero
        self._timer_source_id = None # Timer source is automatically removed on returning False
        self.emit('break_started')
        print("TimerManager: Entered BREAK_ACTIVE state.")


    # --- Public property accessors (optional but good practice) ---
    @property
    def state(self):
        return self._state

    @property
    def remaining_seconds(self):
        return self._remaining_seconds

    @property
    def configured_interval_seconds(self):
         return self._configured_interval_seconds


# --- Test Code ---
if __name__ == '__main__':
    print("Running TimerManager Test...")

    main_loop = GLib.MainLoop()
    timer = TimerManager()

    # --- Signal Handlers ---
    def on_started(emitter):
        print("[Signal Handler] Timer Started")

    def on_paused(emitter):
        print("[Signal Handler] Timer Paused")

    def on_resumed(emitter):
        print("[Signal Handler] Timer Resumed")

    # *** MODIFIED on_stopped handler ***
    def on_stopped(emitter):
        print("[Signal Handler] Timer Stopped")
        # Quit the main loop *after* the stopped signal is processed
        print("Quitting main loop from on_stopped handler.")
        if main_loop.is_running():
            main_loop.quit()

    def on_tick(emitter, seconds_left):
        print(f"[Signal Handler] Tick! {seconds_left} seconds remaining.")

    # --- Test Control Functions ---
    def test_stop_scheduled(): # Renamed function that actually stops
        print("\n--- Testing Stop ---")
        timer.stop()
        # *** REMOVED main_loop.quit() call from here ***
        # The on_stopped handler will now quit the loop.
        # Add a small timeout just in case stop somehow doesn't emit signal (failsafe)
        def failsafe_quit():
            if main_loop.is_running():
                print("Failsafe quit triggered (on_stopped didn't run?).")
                main_loop.quit()
            return False
        GLib.timeout_add_seconds(2, failsafe_quit) # Quit after 2s if not already quit
        return False # Important: idle_add runs repeatedly unless you return False

    def on_break_final(emitter): # Handler for the second break (after postpone)
        print("[Signal Handler] Final Break Started (will schedule stop).")
        # Schedule the stop using idle_add to run *after* this handler completes
        GLib.idle_add(test_stop_scheduled)
        # No need to return False here, signal handlers don't loop

    def on_break_initial(emitter): # Handler for the first break
        print("[Signal Handler] Initial Break Started!")
        # Schedule the postpone action
        GLib.timeout_add_seconds(2, test_postpone) # Wait 2s then postpone
        # No need to return False here

    def test_postpone():
        print("\n--- Testing Postpone (10 seconds) ---")
        # Use 10/60 minutes for 10 seconds
        timer.postpone(10 / 60)
        # Disconnect the initial break handler
        try:
            timer.disconnect_by_func(on_break_initial)
        except TypeError:
             print("Warning: Could not disconnect on_break_initial handler.")
        # Connect the final break handler
        timer.connect('break_started', on_break_final)
        return False # timeout_add runs repeatedly unless False is returned

    def test_pause():
        print("\n--- Testing Pause ---")
        timer.pause()
        # Schedule resume after 2 seconds of pause
        GLib.timeout_add_seconds(2, test_resume)
        return False # timeout_add runs repeatedly unless False is returned

    def test_resume():
        print("\n--- Testing Resume ---")
        timer.resume()
        # Let it run to completion now, on_break_initial will handle next step
        return False # timeout_add runs repeatedly unless False is returned

    # --- Connect Initial Handlers ---
    timer.connect('timer_started', on_started)
    timer.connect('timer_paused', on_paused)
    timer.connect('timer_resumed', on_resumed)
    timer.connect('timer_stopped', on_stopped) # Connect the stop handler
    timer.connect('timer_tick', on_tick)
    timer.connect('break_started', on_break_initial) # Connect the first break handler


    # --- Test Sequence Setup ---
    print("\n--- Test Sequence Start ---")

    # 1. Set interval (use 6/60 minutes for 6 seconds)
    print("Setting interval to 6 seconds (0.10 minutes)...")
    test_interval_minutes = 6 / 60
    timer.set_interval(test_interval_minutes)
    print(f"Configured interval: {timer.configured_interval_seconds}s")
    print(f"Initial state: {timer.state}, Remaining: {timer.remaining_seconds}s")

    # 2. Start the timer
    print("\nStarting timer...")
    timer.start()

    # 3. Schedule Pause after 2 seconds
    # GLib timers are relative to when the main loop starts processing them
    GLib.timeout_add_seconds(2, test_pause)


    # --- Run Main Loop ---
    print("\nStarting GLib MainLoop... (Ctrl+C to interrupt if needed)")
    try:
        main_loop.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        if main_loop.is_running():
            main_loop.quit()

    print("\n--- Test Sequence End ---")
