import sys
import os
from playsound import playsound, PlaysoundException

class SoundPlayer:
    """
    A simple utility class to play a notification sound using the 'playsound' library.
    """

    def __init__(self, sound_file_path: str):
        """
        Initializes the SoundPlayer.

        Args:
            sound_file_path: The path to the sound file (e.g., .wav, .mp3).
        """
        self.sound_file_path = sound_file_path
        self._verify_file()

    def _verify_file(self):
        """Checks if the sound file exists and is readable."""
        if not os.path.exists(self.sound_file_path):
            print(f"Warning: Sound file not found at '{self.sound_file_path}'. Playback will fail.", file=sys.stderr)
            # Optional: Raise an error instead? For now, just warn.
            # raise FileNotFoundError(f"Sound file not found: {self.sound_file_path}")
        elif not os.path.isfile(self.sound_file_path):
            print(f"Warning: Path '{self.sound_file_path}' is not a file. Playback will fail.", file=sys.stderr)
        elif not os.access(self.sound_file_path, os.R_OK):
             print(f"Warning: Sound file at '{self.sound_file_path}' is not readable. Playback might fail.", file=sys.stderr)


    def play_break_sound(self):
        """
        Plays the configured sound file synchronously (blocking).
        Includes basic error handling.
        """
        if not os.path.exists(self.sound_file_path) or not os.path.isfile(self.sound_file_path):
             print(f"Error: Cannot play sound, file not found or not a file: '{self.sound_file_path}'", file=sys.stderr)
             return

        print(f"SoundPlayer: Attempting to play '{self.sound_file_path}' (blocking)...")
        try:
            # Set block=True (or omit it, as True is often the default)
            playsound(self.sound_file_path, block=True)
            print(f"SoundPlayer: Playback finished for '{self.sound_file_path}'.")
        except PlaysoundException as e:
            print(f"Error: Failed to play sound '{self.sound_file_path}'. PlaysoundException: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error: An unexpected error occurred during sound playback: {e}", file=sys.stderr)

# --- Test Code ---
if __name__ == '__main__':
    print("Running SoundPlayer Test...")

    # *** IMPORTANT: Replace 'notification.wav' with the actual path to YOUR sound file ***
    # If it's in the same directory, just the filename is fine.
    # Otherwise, use the full path like '/home/george/Sounds/my_alert.mp3'
    sound_file = "notification.wav" # <-- CHANGE THIS AS NEEDED

    if not os.path.exists(sound_file):
        print(f"\nERROR: Test sound file '{sound_file}' not found in the current directory.")
        print("Please download a .wav or .mp3 file, save it here as 'notification.wav', or update the 'sound_file' variable in this script.")
        sys.exit(1)

    try:
        player = SoundPlayer(sound_file_path=sound_file)

        print("\nAttempting to play the sound...")
        player.play_break_sound()

        # Since playback is asynchronous (block=False), add a small delay
        # in the test script to give the sound time to actually play before exiting.
        # In the real application, the main loop will keep running anyway.
        print("Waiting a few seconds for sound to play (playback is async)...")
        import time
        try:
            time.sleep(3) # Wait for 3 seconds
        except KeyboardInterrupt:
            print("\nSleep interrupted.")

        print("\nTesting with a non-existent file path:")
        non_existent_file = "no_such_sound_exists_here.wav"
        try:
            player_bad = SoundPlayer(non_existent_file) # Should print warning
            player_bad.play_break_sound() # Should print error
        except FileNotFoundError:
             print("(Successfully caught FileNotFoundError during init - if raised)")


    except ImportError:
         print("\nError: Could not import the 'playsound' library.")
         print("Please install it: pip install playsound==1.2.2")
    except Exception as e:
        print(f"\nAn unexpected error occurred during the test: {e}")

    print("\n--- Test End ---")
