#!/bin/bash

APP_NAME="Xbox Sync"
INSTALL_DIR="$HOME/XboxSync"
REPO_URL="https://github.com/Boc86/xboxgp_esde_sync"
REPO_RAW="https://raw.githubusercontent.com/Boc86/xboxgp_esde_sync/main"
PYTHON_SCRIPT="xboxgp_esde_sync.py"
REQUIREMENTS="requirements.txt"
ICON_FILE="icon.png"
INSTALLER_FILE="xbox_sync_installer.sh"
DESKTOP_FILE="$HOME/.local/share/applications/xboxgp_esde_sync.desktop"
VENV_DIR="$INSTALL_DIR/venv"
BINARY_FILE="xboxgp_esde_sync"

create_desktop_file() {
    mkdir -p "$(dirname "$DESKTOP_FILE")"
    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Name=$APP_NAME
Exec=$VENV_DIR/bin/python $INSTALL_DIR/$PYTHON_SCRIPT
Icon=$INSTALL_DIR/$ICON_FILE
Type=Application
Categories=Game;
Terminal=false
EOF
    chmod +x "$DESKTOP_FILE"
    cp "$DESKTOP_FILE" "$HOME/Desktop/" 2>/dev/null
}

install_app() {
    echo "Installing $APP_NAME..."
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR" || exit

    echo "Downloading files..."
    curl -O "$REPO_RAW/$PYTHON_SCRIPT"
    curl -O "$REPO_RAW/$REQUIREMENTS"
    curl -O "$REPO_RAW/$ICON_FILE"
    curl -O "$REPO_RAW/$INSTALLER_FILE"

    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r "$REQUIREMENTS"
    deactivate

    echo "Creating desktop shortcut..."
    create_desktop_file

    echo "$APP_NAME installed successfully."
}

install_binary() {
    echo "Installing $APP_NAME (Binary Executable)..."
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR" || exit

    echo "Downloading binary executable..."
    curl -O "$REPO_RAW/$BINARY_FILE"
    curl -O "$REPO_RAW/$ICON_FILE"
    curl -o "$REPO_RAW/$INSTALLER_FILE"

    echo "Creating desktop shortcut..."
    create_desktop_file

    echo "$APP_NAME installed successfully."
}

update_app() {
    echo "Updating $APP_NAME..."
    cd "$INSTALL_DIR" || { echo "App not found. Please install it first."; exit 1; }

    #check for binary file in install dir
    if [ -f "$INSTALL_DIR/$BINARY_FILE" ]; then
        echo "Updating binary executable..."
        curl -O "$REPO_RAW/$BINARY_FILE"
        curl -O "$REPO_RAW/$ICON_FILE"
        curl -o "$REPO_RAW/$INSTALLER_FILE"
    fi
        echo "Updating Python files..."
        curl -O "$REPO_RAW/$PYTHON_SCRIPT"
        curl -O "$REPO_RAW/$REQUIREMENTS"
        curl -O "$REPO_RAW/$ICON_FILE"
        curl -o "$REPO_RAW/$INSTALLER_FILE"

        source "$VENV_DIR/bin/activate"
        pip install -r "$REQUIREMENTS"
        deactivate

    create_desktop_file

    echo "$APP_NAME updated successfully."
}

uninstall_app() {
    echo "Uninstalling $APP_NAME..."
    rm -rf "$INSTALL_DIR"
    rm -f "$DESKTOP_FILE"
    rm -f "$HOME/Desktop/$(basename "$DESKTOP_FILE")"
    echo "$APP_NAME uninstalled successfully."
}

# Welcome message
echo "==========================================="
echo "       Welcome to the $APP_NAME Installer"
echo "==========================================="
echo ""
echo "Please choose an option:"
echo "1) Install $APP_NAME (Python Virtual Environment)"
echo "2) Install $APP_NAME (Binary Executable)"
echo "3) Update $APP_NAME"
echo "4) Uninstall $APP_NAME"
echo ""

read -p "Enter your choice (1, 2, 3, or 4): " CHOICE

case "$CHOICE" in
    1)
        install_app
        ;;
    2)
        install_binary
        ;;
    3)
        update_app
        ;;
    4)
        uninstall_app
        ;;
    *)
        echo "Invalid selection. Please run the script again and select 1, 2, or 3."
        exit 1
        ;;
esac

