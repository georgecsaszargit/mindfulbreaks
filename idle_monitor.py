# File: idle_monitor.py
import sys
import ctypes
import ctypes.util
import time # For testing delays

import gi
try:
    gi.require_version('GLib', '2.0')
    gi.require_version('GObject', '2.0')
except ValueError as e:
    print(f"Error: Could not satisfy GLib/GObject version requirement. {e}", file=sys.stderr)
    sys.exit(1)

from gi.repository import GLib, GObject

# --- ctypes definitions for X11 and XScreenSaver ---

# Basic X11 types
Display = ctypes.c_void_p # Treat Display* as opaque pointer
Window = ctypes.c_ulong
Drawable = ctypes.c_ulong
XID = ctypes.c_ulong

# Define the XScreenSaverInfo struct based on <X11/extensions/scrnsaver.h>
class XScreenSaverInfo(ctypes.Structure):
    _fields_ = [
        ('window', Window),            # screen saver window
        ('state', ctypes.c_int),       # ScreenSaverOff, ScreenSaverOn, ScreenSaverDisabled
        ('kind', ctypes.c_int),        # ScreenSaverBlanked, ScreenSaverInternal, ScreenSaverExternal
        ('til_or_since', ctypes.c_ulong), # milliseconds
        ('idle', ctypes.c_ulong),      # milliseconds
        ('eventMask', ctypes.c_ulong)  # events
    ]

# Find libraries
libX11_path = ctypes.util.find_library('X11')
libXss_path = ctypes.util.find_library('Xss') # Usually libXss.so.1

if not libX11_path:
    raise ImportError("Could not find libX11. System library missing?")
if not libXss_path:
    raise ImportError("Could not find libXss. Is libxss1 installed?")

# Load libraries
try:
    libX11 = ctypes.CDLL(libX11_path)
    libXss = ctypes.CDLL(libXss_path)
except OSError as e:
     raise ImportError(f"Error loading X11/Xss libraries: {e}")


# Define function prototypes we need using ctypes

# XOpenDisplay = (display_name) -> Display*
libX11.XOpenDisplay.argtypes = [ctypes.c_char_p]
libX11.XOpenDisplay.restype = Display

# XCloseDisplay = (display) -> int
libX11.XCloseDisplay.argtypes = [Display]
libX11.XCloseDisplay.restype = ctypes.c_int

# XDefaultRootWindow = (display) -> Window
libX11.XDefaultRootWindow.argtypes = [Display]
libX11.XDefaultRootWindow.restype = Window

# XScreenSaverAllocInfo = () -> XScreenSaverInfo*
libXss.XScreenSaverAllocInfo.argtypes = []
libXss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)

# XScreenSaverQueryInfo = (display, drawable, saver_info) -> int
libXss.XScreenSaverQueryInfo.argtypes = [Display, Drawable, ctypes.POINTER(XScreenSaverInfo)]
libXss.XScreenSaverQueryInfo.restype = ctypes.c_int

# XFree = (data) -> int (usually returns void, but ctypes default is int)
libX11.XFree.argtypes = [ctypes.c_void_p]
libX11.XFree.restype = ctypes.c_int

# --- IdleMonitor Class ---

class IdleMonitor(GObject.Object):
    """
    Monitors user idle time using the XScreenSaver extension and emits signals
    when the user becomes idle or active after being idle.

    Note: This relies on the X11 ScreenSaver extension and will likely not work
    correctly under native Wayland sessions unless running via XWayland and
    the compositor supports the necessary XWayland extensions.
    """
    __gsignals__ = {
        'user_idle': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'user_active': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    DEFAULT_POLL_INTERVAL_SECONDS = 30

    def __init__(self, idle_threshold_seconds: int):
        """
        Initializes the IdleMonitor.

        Args:
            idle_threshold_seconds: The time in seconds after which the user
                                     is considered idle.
        """
        GObject.Object.__init__(self)

        if idle_threshold_seconds < 1:
            print("Warning: Idle threshold must be at least 1 second. Setting to 1.", file=sys.stderr)
            idle_threshold_seconds = 1
        self._idle_threshold_ms = idle_threshold_seconds * 1000

        self._is_idle = False # Current state
        self._timer_source_id = None
        self._display = None
        self._root_window = None
        self._saver_info = None
        self._initialized_successfully = False

        try:
            # Open connection to the X server
            # Passing None uses the DISPLAY environment variable
            self._display = libX11.XOpenDisplay(None)
            if not self._display:
                raise RuntimeError("Could not open X Display. Is DISPLAY set correctly?")

            # Get the root window
            self._root_window = libX11.XDefaultRootWindow(self._display)
            if not self._root_window:
                libX11.XCloseDisplay(self._display)
                raise RuntimeError("Could not get default root window.")

            # Allocate the structure to store query results
            self._saver_info = libXss.XScreenSaverAllocInfo()
            if not self._saver_info:
                libX11.XCloseDisplay(self._display)
                raise RuntimeError("Could not allocate XScreenSaverInfo struct.")

            print(f"IdleMonitor: Initialized successfully. Threshold: {idle_threshold_seconds}s")
            self._initialized_successfully = True

        except (ImportError, RuntimeError, AttributeError) as e:
            # AttributeError can happen if a required X function isn't found
            print(f"Error initializing IdleMonitor (X11/Xss): {e}", file=sys.stderr)
            print("Idle monitoring will be disabled.", file=sys.stderr)
            # Ensure cleanup if partially initialized
            if self._saver_info:
                # XFree works even if display wasn't fully opened? Let's try.
                # Might need a specific function for freeing XScreenSaverInfo?
                # Docs suggest XFree is correct.
                 try:
                      libX11.XFree(self._saver_info)
                 except Exception as free_e:
                      print(f"Warning: Error during cleanup free: {free_e}", file=sys.stderr)
                 self._saver_info = None
            if self._display:
                 libX11.XCloseDisplay(self._display)
                 self._display = None


    def start(self, poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS):
        """
        Starts the periodic polling for idle time.

        Args:
            poll_interval_seconds: How often to check for idle time.
        """
        if not self._initialized_successfully:
             print("IdleMonitor: Cannot start, initialization failed.", file=sys.stderr)
             return

        if self._timer_source_id:
            print("IdleMonitor: Already running.", file=sys.stderr)
            return

        if poll_interval_seconds < 1:
            poll_interval_seconds = 1

        print(f"IdleMonitor: Starting polling every {poll_interval_seconds} seconds.")
        # Check immediately once, then start interval
        GLib.idle_add(self._check_idle) # Check once on next idle
        self._timer_source_id = GLib.timeout_add_seconds(poll_interval_seconds, self._check_idle)


    def stop(self):
        """Stops the periodic polling."""
        print("IdleMonitor: Stop requested.")
        if self._timer_source_id:
            GLib.source_remove(self._timer_source_id)
            self._timer_source_id = None
            print("IdleMonitor: Polling stopped.")
        # Cleanup X resources
        if self._initialized_successfully:
             if self._saver_info:
                  try:
                    libX11.XFree(self._saver_info)
                  except Exception as e:
                       print(f"Warning: Error freeing XScreenSaverInfo: {e}", file=sys.stderr)
                  self._saver_info = None
             if self._display:
                  libX11.XCloseDisplay(self._display)
                  self._display = None
             self._initialized_successfully = False # Mark as cleaned up


    def _check_idle(self) -> bool:
        """
        Internal method called periodically to check the idle time.
        Returns True to keep the timer going (if called by timeout_add),
        or False if called by idle_add (only run once).
        """
        if not self._initialized_successfully or not self._display or not self._saver_info:
             print("IdleMonitor: Check called but not initialized.", file=sys.stderr)
             return False # Stop timer if it somehow got started

        try:
            # Query XScreenSaver
            status = libXss.XScreenSaverQueryInfo(self._display, self._root_window, self._saver_info)

            if status == 0:
                 # This seems to indicate an error according to some examples
                 print("Warning: XScreenSaverQueryInfo returned status 0 (potential error).", file=sys.stderr)
                 # We might want to stop polling or handle this more gracefully
                 # For now, just report and continue trying
                 return True # Keep timer running

            current_idle_ms = self._saver_info.contents.idle
            # print(f"Idle time: {current_idle_ms} ms") # Debug print

            currently_considered_idle = current_idle_ms >= self._idle_threshold_ms

            # --- State Transition Logic ---
            if currently_considered_idle and not self._is_idle:
                self._is_idle = True
                print("IdleMonitor: User became idle.")
                self.emit('user_idle')
            elif not currently_considered_idle and self._is_idle:
                self._is_idle = False
                print("IdleMonitor: User became active.")
                self.emit('user_active')

        except Exception as e:
            # Catch potential errors during X calls within the callback
            print(f"Error during idle check: {e}", file=sys.stderr)
            # Decide if we should stop the timer on error
            # return False # Option: Stop polling on error
            pass # Option: Log error and keep trying

        # Keep the timer running if we were called by timeout_add
        return True if self._timer_source_id else False


# --- Test Code ---
if __name__ == '__main__':
    print("Running IdleMonitor Test...")
    print("This requires an X11 session (or XWayland).")
    print("Test will run for 60 seconds.")
    print("Try being idle for > 5 seconds, then active again.")

    main_loop = GLib.MainLoop()
    monitor = None

    # Handler functions
    def on_user_idle(emitter):
        print("[Signal Handler] ****** USER IDLE ******")

    def on_user_active(emitter):
        print("[Signal Handler] ****** USER ACTIVE ******")

    def stop_monitor_and_quit():
        print("\nStopping monitor and quitting...")
        if monitor:
            monitor.stop()
        if main_loop.is_running():
            main_loop.quit()
        return False # Stop timeout

    try:
        # Create monitor with a 5-second threshold for testing
        monitor = IdleMonitor(idle_threshold_seconds=5)

        # Only proceed if initialized correctly
        if monitor._initialized_successfully:
            # Connect signals
            monitor.connect('user_idle', on_user_idle)
            monitor.connect('user_active', on_user_active)

            # Start polling (e.g., every 2 seconds for faster testing feedback)
            monitor.start(poll_interval_seconds=2)

            # Schedule test shutdown
            GLib.timeout_add_seconds(60, stop_monitor_and_quit)

            print("\nStarting GLib MainLoop... Monitor is active.")
            main_loop.run()
        else:
            print("\nMonitor did not initialize. Exiting test.")

    except ImportError as e:
         print(f"\nTest failed due to missing library: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred during test setup: {e}")
        if main_loop.is_running():
            main_loop.quit()
    finally:
        # Ensure cleanup happens even if loop wasn't run
        if monitor and not monitor._initialized_successfully: # Already stopped if quit normally
             monitor.stop()


    print("\n--- Test End ---")
