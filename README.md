# Xbox Game Pass Sync (Greenlight to ES-DE)

![Xbox Game Pass Sync Banner](icon.png)

## Overview

**Xbox Game Pass Sync** is a Python PyQt5 application that automates the integration of Xbox Cloud Gaming [Greenlight](https://github.com/unknownskl/greenlight) client with [EmulationStation-DE (ES-DE)](https://es-de.org/). It fetches the latest Xbox Game Pass cloud games, downloads artwork and videos, generates launch scripts, and creates ES-DE-compatible metadata for seamless library management. A full Xbox Game Pass Ultimate subscription is required to stream Xbox Game Pass games.

---

## Features

- **Automated Game Sync:** Fetches the current Xbox Cloud Gaming catalog and keeps your ES-DE library up to date.
- **Artwork & Video Download:** Downloads logos, covers, fanart, and gameplay videos for each game.
- **Script Generation:** Creates launch scripts for each game using the Greenlight Flatpak.
- **ES-DE Integration:** Generates `gamelist.xml` and assists with ES-DE system configuration.
- **GUI:** User-friendly PyQt5 interface for configuration, sync, and cleaning assets.
- **Theme Helper:** Assists in creating a Greenlight theme for ES-DE.
- **Clean Start:** Optionally delete old assets and scripts for a fresh sync.
- **Logging:** Detailed log file (`xboxgames_debug.log`) for troubleshooting.

---
## Instalation

## Script Installation
- Download the installer from the [Releases](https://github.com/Boc86/xboxgp_esde_sync/releases) section
- Make the installer executable with (you may need to use sudo depending on your setup) 
```bash
chmod +x xbox_sync_installer.sh
```
- Run the installer

## Manual Installation

### Requirements
- **OS:** Linux (tested on Ubuntu/Debian Nobara 41 & 42/Fedora)
- **Python:** 3.8+
- **Dependencies:**
  - PyQt5
  - requests
  - Pillow
  - aiohttp
  - aiofiles

Install dependencies with pip:
```bash
pip install PyQt5 requests Pillow aiohttp aiofiles
```

- **Greenlight Flatpak:**
  - Install from [Flathub](https://flathub.org/apps/io.github.unknownskl.greenlight):
    ```bash
    flatpak install flathub io.github.unknownskl.greenlight
    ```
- **ffmpeg:**
  - Required for video downloads/conversion.
    ```bash
    sudo apt install ffmpeg
    ```

---

## Usage

1. **Launch the App:**
   ```bash
   python3 xboxgp_esde_sync.py
   ```
2. **Configure Directories:**
   - Set the assets, games (scripts), and gamelist directories using the GUI.
3. **Greenlight Integration:**
   - Use the "Download Greenlight" button to visit Flathub.
   - Use "Integrate with ES-DE" to add Greenlight as a system in ES-DE.
   - Use "Create Theme" to generate a basic theme and download logo/fanart.
4. **Sync:**
   - Click "Start Sync" to fetch games, download assets, and generate scripts/metadata.
   - Progress and status are shown in the GUI.
5. **Clean Start (Optional):**
   - Use the "Clean Start Options" to delete old scripts, artwork, or videos before syncing.

### GUI Overview
- **Introduction:** Explains the tool and its purpose.
- **Directory Configuration:** Set folders for assets, scripts, and gamelist.
- **Greenlight Integration:** Quick actions for ES-DE setup and theme creation.
- **Synchronization:** Start sync, view progress, and status.
- **Clean Start Options:** Select which assets to delete for a fresh sync.

---

## Configuration
- Settings are saved in `settings.json` in the script directory.
- Default directories can be changed at any time via the GUI.
- The tool will create subfolders for marquees, covers, fanart, and videos under the assets directory.

---

## Troubleshooting
- **ffmpeg not found:** Ensure `ffmpeg` is installed and in your PATH.
- **Greenlight not launching:** Make sure the Flatpak is installed and accessible.
- **No games/scripts generated:** Check your internet connection and log file (`xboxgames_debug.log`).
- **Permission errors:** Ensure you have write access to the selected directories.
- **ES-DE not showing games:** Make sure the custom system is added and the gamelist directory is correct.

---

## Credits
- [Greenlight](https://github.com/UnknownSKL/Greenlight) by UnknownSKL
- [EmulationStation-DE](https://es-de.org/)
- [Microsoft Xbox Game Pass](https://www.xbox.com/en-GB/auth/msa?action=logIn&returnUrl=%2Fen-GB%2Fxbox-game-pass&prompt=none)
- [PyQt5](https://riverbankcomputing.com/software/pyqt/)
- [ffmpeg](https://ffmpeg.org/)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
