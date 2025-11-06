#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
ENV_NAME="mindfulbreaks"
PYTHON_VERSION="3.11" # Or choose another supported version
CONDA_CHANNEL="conda-forge"
# Conda packages - Python, Pip, PyGObject, GTK/GLib runtime libs, build tools
CONDA_REQUIREMENTS=(
    "python=$PYTHON_VERSION"
    "pip"
    "pygobject"
    "gtk3"
    "glib"
    "c-compiler"
    "cxx-compiler"
    "make"
    "pkg-config"
)
PIP_REQUIREMENTS=(
    "playsound==1.2.2"
)
# System apt packages - ONLY C/C++ Runtime Libs & Introspection Data
APT_REQUIREMENTS=(
    # Introspection Data (Crucial for PyGObject bindings)
    "gir1.2-glib-2.0"
    "gir1.2-gtk-3.0"
    "gir1.2-ayatanaappindicator3-0.1"
    # Runtime C Libraries for Indicators & Idle
    "libayatana-appindicator3-1"
    "libdbusmenu-glib4"
    "libdbusmenu-gtk3-4"
    "libxss1"
    # Potential Runtime Dependencies for GStreamer (used by playsound/GTK)
    "gstreamer1.0-plugins-base"
    "gstreamer1.0-plugins-good"
)
SOUND_FILE="notification.wav"

# --- Helper Functions ---
print_info() {
    echo "INFO: $1"
}
print_warning() {
    echo "WARN: $1"
}
print_error() {
    echo "ERROR: $1" >&2
    exit 1
}
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- Check Prerequisites ---
print_info "Checking prerequisites..."
if ! command_exists conda; then
    print_error "Conda command not found. Please install Miniconda or Anaconda and initialize it."
fi
if [ ! -f "$SOUND_FILE" ]; then
    print_warning "Sound file '$SOUND_FILE' not found in current directory. Sound playback will fail."
    print_warning "Please place a suitable .wav or .mp3 file named '$SOUND_FILE' here."
fi
if [ ! -f "mindful_break_app.py" ]; then
    print_error "Main script 'mindful_break_app.py' not found. Run this script from your project directory."
fi
print_info "Prerequisites check passed."

# --- Create/Update Conda Environment ---
print_info "Checking for Conda environment '$ENV_NAME'..."
if conda env list | grep -q "^${ENV_NAME}\s"; then
    print_info "Conda environment '$ENV_NAME' already exists. Ensuring packages..."
    conda install -y -n "$ENV_NAME" -c "$CONDA_CHANNEL" --file <(printf "%s\n" "${CONDA_REQUIREMENTS[@]}")
else
    print_info "Creating Conda environment '$ENV_NAME'..."
    conda create -y -n "$ENV_NAME" -c "$CONDA_CHANNEL" --file <(printf "%s\n" "${CONDA_REQUIREMENTS[@]}")
    print_info "Conda environment created."
fi

# --- Install System (apt) Dependencies (Non-Python) ---
# These provide the C libraries and introspection data needed at runtime
print_info "Updating apt package list..."
sudo apt update
print_info "Installing required system libraries and introspection data via apt..."
req_string=$(printf "%s " "${APT_REQUIREMENTS[@]}" | xargs)
if [ -n "$req_string" ]; then
    sudo apt install -y --no-install-recommends $req_string # Use --no-install-recommends
    print_info "System packages installed."
else
    print_info "No system packages specified via apt."
fi

# --- Install Pip Dependencies ---
print_info "Installing Python packages via pip into '$ENV_NAME' environment..."
pip_install_cmd="pip install"
for pkg in "${PIP_REQUIREMENTS[@]}"; do
    pip_install_cmd+=" '$pkg'"
done
conda run -n "$ENV_NAME" bash -c "$pip_install_cmd"
print_info "Pip packages installed."

# --- Setup Environment Variable for Conda Env (Needed Again) ---
# Because APT installs introspection data system-wide, the Conda PyGObject
# needs to be told where to find it in addition to its own path.
print_info "Setting up GI_TYPELIB_PATH for Conda environment '$ENV_NAME'..."
CONDA_BASE=$(conda info --base)
if [ -z "$CONDA_BASE" ]; then
    print_error "Could not determine Conda base directory."
fi
CONDA_PREFIX_PATH="$CONDA_BASE/envs/$ENV_NAME"
if [ ! -d "$CONDA_PREFIX_PATH" ]; then
    print_error "Could not find Conda environment path at '$CONDA_PREFIX_PATH'."
fi

SYSTEM_TYPELIB_PATH="/usr/lib/x86_64-linux-gnu/girepository-1.0" # Adjust if needed
if [ ! -d "$SYSTEM_TYPELIB_PATH" ]; then
     print_warning "System typelib path '$SYSTEM_TYPELIB_PATH' not found. Indicator might not work."
     GI_TYPELIB_VALUE="$CONDA_PREFIX_PATH/lib/girepository-1.0" # Only use conda path
else
     # Combine paths: Conda Env Path + System Path
     GI_TYPELIB_VALUE="$CONDA_PREFIX_PATH/lib/girepository-1.0:$SYSTEM_TYPELIB_PATH"
fi

# Create activation script
ACTIVATE_DIR="$CONDA_PREFIX_PATH/etc/conda/activate.d"
mkdir -p "$ACTIVATE_DIR"
ACTIVATE_SCRIPT="$ACTIVATE_DIR/env_vars.sh"
# Use improved script to handle pre-existing values
echo 'if [ -n "$GI_TYPELIB_PATH" ]; then' > "$ACTIVATE_SCRIPT"
echo '  export _CONDA_SET_GI_TYPELIB_PATH="$GI_TYPELIB_PATH"' >> "$ACTIVATE_SCRIPT"
echo 'fi' >> "$ACTIVATE_SCRIPT"
echo "export GI_TYPELIB_PATH=\"$GI_TYPELIB_VALUE:\$GI_TYPELIB_PATH\"" >> "$ACTIVATE_SCRIPT"
print_info "Created activation script: $ACTIVATE_SCRIPT"

# Create deactivation script
DEACTIVATE_DIR="$CONDA_PREFIX_PATH/etc/conda/deactivate.d"
mkdir -p "$DEACTIVATE_DIR"
DEACTIVATE_SCRIPT="$DEACTIVATE_DIR/env_vars.sh"
echo 'if [ -n "$_CONDA_SET_GI_TYPELIB_PATH" ]; then' > "$DEACTIVATE_SCRIPT"
echo '  export GI_TYPELIB_PATH="$_CONDA_SET_GI_TYPELIB_PATH"' >> "$DEACTIVATE_SCRIPT"
echo '  unset _CONDA_SET_GI_TYPELIB_PATH' >> "$DEACTIVATE_SCRIPT"
echo 'else' >> "$DEACTIVATE_SCRIPT"
echo '  # If original was empty or unset, unset it on deactivate' >> "$DEACTIVATE_SCRIPT"
echo '  unset GI_TYPELIB_PATH' >> "$DEACTIVATE_SCRIPT"
echo 'fi' >> "$DEACTIVATE_SCRIPT"
print_info "Created deactivation script: $DEACTIVATE_SCRIPT"
print_info "GI_TYPELIB_PATH setup complete."

# --- Finished ---
print_info ""
print_info "-----------------------------------------------------"
print_info "MindfulBreak Environment Setup Complete!"
print_info "-----------------------------------------------------"
print_info "To run the application:"
print_info "1. Deactivate and Reactivate the environment if already active:"
print_info "   conda deactivate"
print_info "   conda activate $ENV_NAME"
print_info "2. Run the main script: python mindful_break_app.py"
print_info "-----------------------------------------------------"
if [ ! -f "$SOUND_FILE" ]; then
    print_warning "Remember to place '$SOUND_FILE' in the current directory for sound notifications."
fi
echo ""

exit 0
