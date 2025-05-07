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
- Currently tested on Ubuntu 21.04 LTS/Debian and Nobara 41 & 42/Fedora) but should run on any Linux flavour including Steam Deck

## Script Installation (Prefered method)
- The script will set up a virtual environment to run the python code in, this avoids any conflict with system python packages
- Download the installer from the [Releases](https://github.com/Boc86/xboxgp_esde_sync/releases) section
- Make the installer executable (you may need to use sudo depending on your setup) 
```bash
chmod +x xbox_sync_installer.sh
```
- Run the installer
- The installer will put all files in /Home/%USER%/XboxSync/, including a copy of the installer which can be used to update and uninstall the script
- A desktop shortcut will be created along with a system menu shortcut that can be found under the Games category

## Manual Installation (May cause conflicts with system python packages, only use if you know what you are doing)

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
or
```bash
pip install -r requirements.txt
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
- **Download Source Code**
  - Download the source code from above
  - Make the python file executable (you may need to use sudo depending on your setup) 
  ```bash
  chmod +x xboxgp_esde_sync.py
  ```
  - Open a terminal from the directory and run the script
  ```bash
  python3 xboxgp_esde_sync.py
  ```

---

## Usage

1. **Launch the App:**
   - If you used the installer script a desktop shortcut will be created so you can easily launch the sync gui
   - If you installed manually open a terminal from the download directory and run
   ```bash
   python3 xboxgp_esde_sync.py
   ```
3. **Configure Directories:**
   - Set the assets, games (scripts), and gamelist directories using the GUI.
   - Depending on your ES-DE install method these are usually located in /Home/$USER%/Emulation/tools/downloaded_media/, /Home/$USER%/Emulation/tools/roms/, and /Home/$USER%/ES-DE/gamelists/
4. **Greenlight Integration:**
   - Use the "Download Greenlight" button to visit Flathub and install Greenlight.
   - Use "Integrate with ES-DE" to add Greenlight as a system in ES-DE.
   - Use "Create Theme" to generate a basic theme and download logo/fanart. This can be applied to any theme you use, just select the theme folder in the file browser i.e. /Home/$USER%/ES-DE/themes/coinops-es-de/
5. **Sync:**
   - Click "Start Sync" to fetch games, download assets, and generate scripts/metadata.
   - Progress and status are shown in the GUI.
   - The first time you run the sync will take some time as Game Pass usually hosts 350 plus games and you will download videos for all of them, future syncs will only add new additions to the catalogue so will run much faster.
6. **Clean Start (Optional):**
   - Use the "Clean Start Options" to delete old scripts, artwork, or videos before syncing.
   - This is not necessary for removing games no longer on Game Pass as this is handled during the sync process.

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
- It will add a system entry for Greenlight in the custom systems es_systems.xml 

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
