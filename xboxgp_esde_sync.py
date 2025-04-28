#!/usr/bin/env python3
import json
import os
import re
import requests
import logging
import asyncio
import aiohttp
from aiofiles import open as aio_open
from datetime import datetime
import shutil
import webbrowser
import sys

# Force X11 usage instead of Wayland
os.environ["QT_QPA_PLATFORM"] = "xcb"

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                           QProgressBar, QFileDialog, QMessageBox, QCheckBox,
                           QFrame, QGroupBox, QTabWidget, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

SETTINGS_FILE = "settings.json"

def check_and_clear_log_file():
    log_file = "xboxgames_debug.log"
    max_size = 1024 * 1024  # 1MB in bytes
    
    if os.path.exists(log_file) and os.path.getsize(log_file) >= max_size:
        # Clear the file
        with open(log_file, 'w') as f:
            f.write("")

# Check and clear log file if needed before configuring logging
check_and_clear_log_file()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("xboxgames_debug.log"),
        logging.StreamHandler()
    ]
)

def check_ffmpeg():
    """Check if ffmpeg is installed and accessible."""
    if not shutil.which("ffmpeg"):
        raise EnvironmentError("ffmpeg is not installed or not in PATH. Please install ffmpeg to proceed.")

# Updated fetch_ids to handle API changes
def fetch_ids():
    url = "https://catalog.gamepass.com/sigls/v2?id=fdd9e2a7-0fee-49f6-ad69-4354098401ff&language=en-us&market=GB"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract all IDs from the JSON response
        ids = [item['id'] for item in data if 'id' in item]

        # Create a string with all IDs separated by a comma
        ids_string = ",".join(ids)
        return ids_string
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching IDs: {e}")
        raise

# Fix the syntax error in the images handling section
def save_additional_data_to_json(id_strings):
    base_url = "https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds=INSERT&market=GB&languages=en-us&MS-CV=DGU1mcuYo0WMMp+F.1"
    url = base_url.replace("INSERT", id_strings)

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract relevant information for each entry
        extracted_data = []
        for item in data.get("Products", []):
            images = {}
            titled_hero_found = False
            for image in item.get("LocalizedProperties", [{}])[0].get("Images", []):
                purpose = image.get("ImagePurpose")
                if purpose in ["Logo", "Poster", "BoxArt"]:
                    images[purpose] = image.get("Uri")
                elif purpose == "TitledHeroArt":
                    images["TitledHeroArt"] = image.get("Uri")
                    titled_hero_found = True
                elif purpose == "SuperHeroArt" and not titled_hero_found:
                    images["TitledHeroArt"] = image.get("Uri")

            entry = {
                "ProductId": item.get("ProductId"),
                "ProductTitle": item.get("LocalizedProperties", [{}])[0].get("ProductTitle"),
                "ShortDescription": item.get("LocalizedProperties", [{}])[0].get("ShortDescription"),
                "DeveloperName": item.get("LocalizedProperties", [{}])[0].get("DeveloperName"),
                "OriginalReleaseDate": item.get("MarketProperties", [{}])[0].get("OriginalReleaseDate"),
                "Images": images,
                "DASH": next((video.get("DASH") for video in item.get("LocalizedProperties", [{}])[0].get("CMSVideos", []) if video.get("DASH")), None)
            }
            extracted_data.append(entry)

        # Save the extracted data to a JSON file
        output_path = os.path.join(os.getcwd(), "additional_data.json")
        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(extracted_data, json_file, indent=4)
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching additional data: {e}")
        raise

async def download_image(session, url, path):
    if url.startswith("//"):
        url = "https:" + url
    async with session.get(url) as response:
        if response.status == 200:
            content = await response.read()
            async with aio_open(path, "wb") as f:
                await f.write(content)

async def process_entry(entry, session, valid_titles, files_created, output_dir, marquee_dir, cover_dir, fanart_dir):
    product_title = entry.get("ProductTitle", "Unknown")
    sanitized_title = re.sub(r"[^a-zA-Z0-9]", "", product_title).upper()
    valid_titles.add(sanitized_title)

    # Create .sh file
    file_path = os.path.join(output_dir, f"{sanitized_title}.sh")
    if not os.path.exists(file_path):
        script_name = f"xcloud_{sanitized_title}"
        async with aio_open(file_path, "w", encoding="utf-8") as sh_file:
            await sh_file.write("#!/bin/bash\n")
            await sh_file.write(f"flatpak run --socket=wayland --env=ELECTRON_ENABLE_WAYLAND=1 io.github.unknownskl.greenlight --fullscreen --connect='{script_name}'\n")
        os.chmod(file_path, 0o755)
        files_created["sh"] += 1

    # Download Logo (with poster fallback)
    logo_url = entry.get("Images", {}).get("Logo")
    poster_url = entry.get("Images", {}).get("Poster")
    logo_image_path = os.path.join(marquee_dir, f"{sanitized_title}.png")
    
    if not os.path.exists(logo_image_path):
        if logo_url:
            await download_image(session, logo_url, logo_image_path)
            files_created["logo"] += 1
        elif poster_url:
            await download_image(session, poster_url, logo_image_path)
            files_created["logo"] += 1

    # Download Poster
    if poster_url:
        poster_image_path = os.path.join(cover_dir, f"{sanitized_title}.png")
        if not os.path.exists(poster_image_path):
            await download_image(session, poster_url, poster_image_path)
            files_created["poster"] += 1

    # Download TitledHeroArt as fanart
    superhero_url = entry.get("Images", {}).get("TitledHeroArt")
    if superhero_url:
        fanart_path = os.path.join(fanart_dir, f"{sanitized_title}.png")
        if not os.path.exists(fanart_path):
            await download_image(session, superhero_url, fanart_path)
            files_created["fanart"] += 1


def download_video(dash_url, output_path):
    try:
        import subprocess
        command = f"ffmpeg -i \"{dash_url}\" -vf scale=640:480 -c:v libx264 -preset slow -crf 18 -c:a copy \"{output_path}\""
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            logging.error(f"ffmpeg failed for {dash_url} with error: {process.stderr.decode().strip()}")
            return False
        return True
    except Exception as e:
        logging.error(f"Exception occurred while converting {dash_url} to MP4: {e}")
        return False

async def generate_gamelist(output_dir, gamelist_path, metadata_dict):
    entries = []
    for file_name in sorted(os.listdir(output_dir)):
        if file_name.endswith('.sh'):
            sanitized_title = file_name[:-3]
            meta = metadata_dict.get(sanitized_title, {})
            game_entry = '    <game>\n'
            game_entry += f'        <path>./{file_name}</path>\n'
            game_entry += f'        <name>{meta.get("ProductTitle", sanitized_title)}</name>\n'
            game_entry += f'        <desc>{meta.get("ShortDescription", "")}</desc>\n'
            if meta.get("rating"): game_entry += f'        <rating>{meta["rating"]}</rating>\n'
            if meta.get("OriginalReleaseDate"):
                try:
                    date_obj = datetime.strptime(meta["OriginalReleaseDate"].split('T')[0], "%Y-%m-%d")
                    release_date = date_obj.strftime("%Y%m%d")
                    game_entry += f'        <releasedate>{release_date}T000000</releasedate>\n'
                except Exception:
                    pass
            if meta.get("DeveloperName"): game_entry += f'        <developer>{meta["DeveloperName"]}</developer>\n'
            if meta.get("Publisher"): game_entry += f'        <publisher>{meta["Publisher"]}</publisher>\n'
            if meta.get("Genre"): game_entry += f'        <genre>{meta["Genre"]}</genre>\n'
            if meta.get("Players"): game_entry += f'        <players>{meta["Players"]}</players>\n'
            if meta.get("playcount"): game_entry += f'        <playcount>{meta["playcount"]}</playcount>\n'
            if meta.get("lastplayed"): game_entry += f'        <lastplayed>{meta["lastplayed"]}</lastplayed>\n'
            game_entry += '    </game>'
            entries.append(game_entry)
    xml_content = '<?xml version="1.0"?>\n<gameList>\n' + '\n'.join(entries) + '\n</gameList>'
    async with aio_open(gamelist_path, "w", encoding="utf-8") as f:
        await f.write(xml_content)

async def main(base_dir=None, gamelist_dir=None, rom_dir=None, progress_callback=None):
    logging.info("Starting the script...")
    error_message = None
    files_created = {"sh": 0, "logo": 0, "poster": 0, "video": 0, "fanart": 0}
    files_removed = {"sh": 0, "logo": 0, "poster": 0, "fanart": 0}
    try:
        logging.debug("Checking ffmpeg installation...")
        check_ffmpeg()
        logging.debug("Fetching game IDs...")
        if progress_callback: progress_callback(0)
        id_strings = fetch_ids()
        logging.debug(f"Fetched IDs: {id_strings}")
        logging.debug("Saving additional data to JSON...")
        save_additional_data_to_json(id_strings)
        logging.debug("Additional data saved.")
        if progress_callback: progress_callback(5)

        # Define directories
        logging.debug("Defining directories...")
        if base_dir is None:
            base_dir = "/home/boc/Emulation/tools/downloaded_media/greenlight"
        if rom_dir is None:
            output_dir = "/home/boc/Emulation/roms/greenlight/"
        else:
            output_dir = rom_dir
        marquee_dir = os.path.join(base_dir, "marquees/")
        cover_dir = os.path.join(base_dir, "covers/")
        video_dir = os.path.join(base_dir, "videos/")
        fanart_dir = os.path.join(base_dir, "fanart/")
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(marquee_dir, exist_ok=True)
        os.makedirs(cover_dir, exist_ok=True)
        os.makedirs(video_dir, exist_ok=True)
        os.makedirs(fanart_dir, exist_ok=True)

        logging.debug("Loading JSON data...")
        json_file_path = os.path.join(os.getcwd(), "additional_data.json")
        async with aio_open(json_file_path, "r", encoding="utf-8") as json_file:
            data = json.loads(await json_file.read())
        total = len(data)
        logging.info(f"Loaded {total} entries from JSON data.")

        # Initialize counters and directories
        valid_titles = set()

        # Handle async tasks first
        logging.debug("Processing entries asynchronously...")
        async with aiohttp.ClientSession() as session:
            tasks = []
            for idx, entry in enumerate(data):
                tasks.append(process_entry(entry, session, valid_titles, files_created, output_dir, marquee_dir, cover_dir, fanart_dir))
                if progress_callback and total > 0:
                    progress_callback(5 + 40 * (idx + 1) / total)
            await asyncio.gather(*tasks)

        logging.debug("Generating gamelist.xml...")
        metadata_dict = {}
        for entry in data:
            product_title = entry.get("ProductTitle", "Unknown")
            sanitized_title = re.sub(r"[^a-zA-Z0-9]", "", product_title).upper()
            metadata_dict[sanitized_title] = entry
        if gamelist_dir is None:
            gamelist_dir = "/home/boc/ES-DE/gamelists/greenlight"
        os.makedirs(gamelist_dir, exist_ok=True)
        gamelist_path = os.path.join(gamelist_dir, "gamelist.xml")
        if progress_callback: progress_callback(50)
        await generate_gamelist(output_dir, gamelist_path, metadata_dict)
        if progress_callback: progress_callback(60)

        logging.debug("Processing videos synchronously...")
        for idx, entry in enumerate(data):
            dash_url = entry.get("DASH")
            if dash_url:
                product_title = entry.get("ProductTitle", "Unknown")
                sanitized_title = re.sub(r"[^a-zA-Z0-9]", "", product_title).upper()
                output_video_path = os.path.join(video_dir, f"{sanitized_title}.mp4")
                if not os.path.exists(output_video_path):
                    if download_video(dash_url, output_video_path):
                        files_created["video"] += 1
            if progress_callback and total > 0:
                progress_callback(60 + 30 * (idx + 1) / total)

        logging.debug("Removing invalid files...")
        # Remove invalid files
        # Remove .sh files
        for file_name in os.listdir(output_dir):
            if file_name.endswith(".sh"):
                sanitized_name = file_name[:-3]  # Remove the .sh extension
                if sanitized_name not in valid_titles:
                    os.remove(os.path.join(output_dir, file_name))
                    files_removed["sh"] += 1

        # Remove logo images
        for file_name in os.listdir(marquee_dir):
            if file_name.endswith(".png"):
                sanitized_name = file_name[:-4]  # Remove the .png extension
                if sanitized_name not in valid_titles:
                    os.remove(os.path.join(marquee_dir, file_name))
                    files_removed["logo"] += 1

        # Remove poster images
        for file_name in os.listdir(cover_dir):
            if file_name.endswith(".png"):
                sanitized_name = file_name[:-4]  # Remove the .png extension
                if sanitized_name not in valid_titles:
                    os.remove(os.path.join(cover_dir, file_name))
                    files_removed["poster"] += 1

        # Remove fanart images
        for file_name in os.listdir(fanart_dir):
            if file_name.endswith(".png"):
                sanitized_name = file_name[:-4]  # Remove the .png extension
                if sanitized_name not in valid_titles:
                    os.remove(os.path.join(fanart_dir, file_name))
                    files_removed["fanart"] += 1
        if progress_callback: progress_callback(95)

        logging.info("Script completed successfully.")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        error_message = str(e)
    finally:
        try:
            # Get the current task
            current = asyncio.current_task()
            # Get all tasks except the current one
            pending = [task for task in asyncio.all_tasks() 
                      if not task.done() and task is not current]
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
            
            if pending:
                await asyncio.wait(pending, timeout=5)
                
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")
            if not error_message:
                error_message = f"Error during cleanup: {e}"
                
        # Remove popup, do not show messagebox
        if progress_callback:
            progress_callback(100)

def load_settings():
    """Load settings from the settings file."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    """Save settings to the settings file."""
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4)

class SyncWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, base_dir, sh_dir, gamelist_dir):
        super().__init__()
        self.base_dir = base_dir
        self.sh_dir = sh_dir
        self.gamelist_dir = gamelist_dir

    def run(self):
        try:
            def progress_callback(value):
                self.progress.emit(value)

            asyncio.run(main(
                base_dir=self.base_dir,
                rom_dir=self.sh_dir,
                gamelist_dir=self.gamelist_dir,
                progress_callback=progress_callback
            ))
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class GreenlightSyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Xbox Game Pass Sync')
        self.setMinimumSize(900, 600)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QWidget { background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI'; }
            QPushButton { background-color: #4CAF50; color: white; border: none; padding: 8px 16px; min-width: 80px; min-height: 20px; border-radius: 4px; font-size: 10pt; }
            QPushButton[text="Browse"] { min-width: 70px; padding: 6px 12px; }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #404040; color: #808080; }
            QPushButton[class="action"] { background-color: #2196F3; font-weight: bold; min-width: 120px; padding: 10px 20px; }
            QPushButton[class="action"]:hover { background-color: #1976D2; }
            QPushButton[class="warning"] { background-color: #ff5722; min-width: 150px; padding: 8px 16px; }
            QPushButton[class="warning"]:hover { background-color: #f4511e; }
            QLineEdit { background-color: #2d2d2d; color: #e0e0e0; border: 1px solid #404040; padding: 6px 8px; border-radius: 4px; min-height: 20px; }
            QGroupBox { border: 1px solid #404040; border-radius: 4px; margin-top: 1.5em; padding: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #4CAF50; font-weight: bold; }
            QCheckBox { color: #e0e0e0; }
            QCheckBox::indicator { width: 13px; height: 13px; }
            QCheckBox::indicator:unchecked { border: 1px solid #404040; background-color: #2d2d2d; }
            QCheckBox::indicator:checked { border: 1px solid #4CAF50; background-color: #4CAF50; }
        """)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Responsive grid layout for sections
        from PyQt5.QtWidgets import QGridLayout, QSizePolicy
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        # Section widgets
        intro = self.create_introduction_section_widget()
        dirs = self.create_directory_section_widget()
        greenlight = self.create_greenlight_section_widget()
        sync = self.create_sync_section_widget()
        clean = self.create_clean_section_widget()

        # Add widgets to grid (2 columns, 3 rows max)
        grid.addWidget(intro, 0, 0, 1, 2)
        grid.addWidget(dirs, 1, 0)
        grid.addWidget(greenlight, 1, 1)
        grid.addWidget(sync, 2, 0)
        grid.addWidget(clean, 2, 1)

        # Set size policies for responsiveness
        for w in [intro, greenlight, dirs, sync, clean]:
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Enable word wrap for all QPushButtons
        def enable_word_wrap(widget):
            for child in widget.findChildren(QPushButton):
                child.setStyleSheet(child.styleSheet() + "\nQPushButton { white-space: normal; }")
        for w in [intro, greenlight, dirs, sync, clean]:
            enable_word_wrap(w)

        main_layout.addLayout(grid)

        # Responsive resize
        self.setMinimumSize(900, 600)
        self.resize(1100, 700)
        self.center_window()
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icon.png')))

    # New: Section widget creators for grid layout
    def create_introduction_section_widget(self):
        group = QGroupBox("Introduction")
        layout = QVBoxLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 10, 15, 10)
        title_label = QLabel("Xbox Game Pass Sync")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title_label.setStyleSheet("color: #4CAF50;")
        desc_label = QLabel("""This tool helps you integrate Xbox Cloud Gaming (Greenlight) with EmulationStation-DE by automating game synchronisation, artwork downloads, and system configuration. With this tool, you can:\n\n• Create launch scripts for your Xbox Game Pass games using the Greenlight flatpak\n• Download game artwork (logos, covers, fanart) and videos\n• Generate EmulationStation metadata\n• Set up proper ES-DE integration""")
        desc_label.setAlignment(Qt.AlignLeft)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 10pt; color: #e0e0e0;")
        layout.addWidget(title_label)
        layout.addWidget(desc_label)
        return group

    def create_greenlight_section_widget(self):
        group = QGroupBox("Greenlight Integration")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        from PyQt5.QtWidgets import QSizePolicy
        download_btn = QPushButton("Download Greenlight")
        download_btn.clicked.connect(self.open_greenlight_link)
        integrate_btn = QPushButton("Integrate with ES-DE")
        integrate_btn.clicked.connect(self.integrate_greenlight)
        theme_btn = QPushButton("Create Theme")
        theme_btn.clicked.connect(self.create_greenlight_theme_xml)
        for btn in [download_btn, integrate_btn, theme_btn]:
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setMinimumHeight(48)
            btn.setMaximumWidth(200)
            btn.setStyleSheet(btn.styleSheet() + "\nQPushButton { white-space: normal; }")
            layout.addWidget(btn)
        return group

    def create_directory_section_widget(self):
        group = QGroupBox("Directory Configuration")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        # Assets
        assets_row = QHBoxLayout()
        assets_label = QLabel("Assets Directory:")
        assets_label.setFixedWidth(120)
        self.folder_entry = QLineEdit(self.settings.get("base_dir", ""))
        assets_browse = QPushButton("Browse")
        assets_browse.clicked.connect(lambda: self.browse_folder(self.folder_entry))
        assets_row.addWidget(assets_label)
        assets_row.addWidget(self.folder_entry)
        assets_row.addWidget(assets_browse)
        layout.addLayout(assets_row)
        # Games
        games_row = QHBoxLayout()
        games_label = QLabel("Games Directory:")
        games_label.setFixedWidth(120)
        self.sh_folder_entry = QLineEdit(self.settings.get("sh_dir", ""))
        games_browse = QPushButton("Browse")
        games_browse.clicked.connect(lambda: self.browse_folder(self.sh_folder_entry))
        games_row.addWidget(games_label)
        games_row.addWidget(self.sh_folder_entry)
        games_row.addWidget(games_browse)
        layout.addLayout(games_row)
        # Gamelist
        gamelist_row = QHBoxLayout()
        gamelist_label = QLabel("Gamelist Directory:")
        gamelist_label.setFixedWidth(120)
        self.gamelist_folder_entry = QLineEdit(self.settings.get("gamelist_dir", ""))
        gamelist_browse = QPushButton("Browse")
        gamelist_browse.clicked.connect(lambda: self.browse_folder(self.gamelist_folder_entry))
        gamelist_row.addWidget(gamelist_label)
        gamelist_row.addWidget(self.gamelist_folder_entry)
        gamelist_row.addWidget(gamelist_browse)
        layout.addLayout(gamelist_row)
        return group

    def create_sync_section_widget(self):
        group = QGroupBox("Synchronization")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        layout.addWidget(self.progress)
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 10pt;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        self.warning_label = QLabel("Note: Initial sync may take time due to initial video downloads. Subsequent runs will be faster.")
        self.warning_label.setStyleSheet("color: #ff9800; font-size: 10pt;")
        self.warning_label.setWordWrap(True)
        self.warning_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.warning_label)
        self.start_button = QPushButton("Start Sync")
        self.start_button.setProperty("class", "action")
        self.start_button.setFixedWidth(150)
        self.start_button.clicked.connect(self.start_sync)
        layout.addWidget(self.start_button, alignment=Qt.AlignCenter)
        return group

    def create_clean_section_widget(self):
        group = QGroupBox("Clean Start Options")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        grid_layout = QHBoxLayout()
        left_column = QVBoxLayout()
        self.delete_sh_var = QCheckBox("Delete Games")
        self.delete_gamelist_var = QCheckBox("Empty Gamelist")
        self.delete_marquees_var = QCheckBox("Delete Marquees")
        left_column.addWidget(self.delete_sh_var)
        left_column.addWidget(self.delete_gamelist_var)
        left_column.addWidget(self.delete_marquees_var)
        right_column = QVBoxLayout()
        self.delete_covers_var = QCheckBox("Delete Covers")
        self.delete_fanart_var = QCheckBox("Delete Fanart")
        self.delete_videos_var = QCheckBox("Delete Videos")
        right_column.addWidget(self.delete_covers_var)
        right_column.addWidget(self.delete_fanart_var)
        right_column.addWidget(self.delete_videos_var)
        grid_layout.addLayout(left_column)
        grid_layout.addLayout(right_column)
        layout.addLayout(grid_layout)
        self.clean_button = QPushButton("Perform Clean Start")
        self.clean_button.setProperty("class", "warning")
        self.clean_button.setFixedWidth(150)
        self.clean_button.clicked.connect(self.perform_clean_start)
        layout.addWidget(self.clean_button, alignment=Qt.AlignCenter)
        return group

    def center_window(self):
        qr = self.frameGeometry()
        cp = QApplication.desktop().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def browse_folder(self, line_edit):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Directory",
            line_edit.text() or os.path.expanduser('~'),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            line_edit.setText(folder)
            
    def integrate_greenlight(self):
        try:
            esde_folder = QFileDialog.getExistingDirectory(
                self,
                "Select ES-DE custom_systems Folder",
                os.path.expanduser('~'),
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if not esde_folder:
                self.show_error("Error", "No folder selected.")
                return

            custom_systems_path = os.path.join(esde_folder, "custom_systems.xml")
            if not os.path.exists(custom_systems_path):
                self.show_error("Error", "custom_systems.xml not found in the selected folder.")
                return

            # Read the existing custom_systems.xml file
            with open(custom_systems_path, "r", encoding="utf-8") as file:
                content = file.read()

            # Check if the entry already exists
            if "<n>greenlight</n>" in content:
                self.show_info("Info", "Greenlight is already integrated into ES-DE.")
                return

            # Add the Greenlight system entry before </SystemList>
            new_entry = """  <s>
    <n>greenlight</n>
    <fullname>Xbox Cloud Gaming via Greenlight</fullname>
    <path>//home/boc/Emulation/roms/greenlight</path>
    <extension>.sh</extension>
    <command>bash %ROM%</command>
    <platform>xboxseriesx</platform>
    <theme>greenlight</theme>
  </s>
"""
            updated_content = content.replace("</SystemList>", new_entry + "</SystemList>")

            # Write the updated content back to the file
            with open(custom_systems_path, "w", encoding="utf-8") as file:
                file.write(updated_content)

            self.show_info("Success", "Greenlight has been successfully integrated into ES-DE.")
        except Exception as e:
            self.show_error("Error", f"An error occurred: {e}")
            logging.error(f"Error in integrate_greenlight: {e}")

    def start_sync(self):
        self.base_dir = self.folder_entry.text()
        self.sh_dir = self.sh_folder_entry.text()
        self.gamelist_dir = self.gamelist_folder_entry.text()

        if not self.base_dir or not self.sh_dir or not self.gamelist_dir:
            self.show_error("Error", "Please select all required folders.")
            return

        # Save the selected folders to settings
        self.settings["base_dir"] = self.base_dir
        self.settings["sh_dir"] = self.sh_dir
        self.settings["gamelist_dir"] = self.gamelist_dir
        save_settings(self.settings)

        # Update UI states
        self.start_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self.status_label.setText("Status: Running...")
        self.status_label.setStyleSheet("color: #4CAF50;")
        
        # Start sync worker
        self.sync_worker = SyncWorker(self.base_dir, self.sh_dir, self.gamelist_dir)
        self.sync_worker.progress.connect(self.on_progress_update)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.error.connect(self.on_sync_error)
        self.sync_worker.start()

    def on_progress_update(self, value):
        self.progress.setValue(value)
        self.status_label.setText(f"Status: Running... {value}%")

    def on_sync_finished(self):
        self.status_label.setText("Status: Completed")
        self.status_label.setStyleSheet("color: #4CAF50;")
        self.show_info("Success", "Sync completed successfully!")
        self.start_button.setEnabled(True)
        self.clean_button.setEnabled(True)
        self.progress.setValue(100)

    def on_sync_error(self, error_message):
        self.status_label.setText("Status: Error")
        self.status_label.setStyleSheet("color: #ff5722;")
        self.show_error("Error", f"An error occurred: {error_message}")
        self.start_button.setEnabled(True)
        self.clean_button.setEnabled(True)

    def perform_clean_start(self):
        if not self.show_confirm("Confirm Clean Start", 
                                "Are you sure you want to perform a clean start? This will delete selected files."):
            return

        try:
            base_dir = self.folder_entry.text()
            sh_dir = self.sh_folder_entry.text()
            gamelist_dir = self.gamelist_folder_entry.text()

            if not all([base_dir, sh_dir, gamelist_dir]):
                self.show_error("Error", "Please select all required folders first.")
                return

            self.clean_button.setEnabled(False)
            self.start_button.setEnabled(False)

            if self.delete_sh_var.isChecked():
                for file_name in os.listdir(sh_dir):
                    if file_name.endswith(".sh"):
                        os.remove(os.path.join(sh_dir, file_name))

            if self.delete_gamelist_var.isChecked():
                gamelist_path = os.path.join(gamelist_dir, "gamelist.xml")
                with open(gamelist_path, "w", encoding="utf-8") as f:
                    f.write("<?xml version=\"1.0\"?>\n<gameList>\n</gameList>")

            if self.delete_marquees_var.isChecked():
                self.delete_files_in_dir(os.path.join(base_dir, "marquees"))

            if self.delete_covers_var.isChecked():
                self.delete_files_in_dir(os.path.join(base_dir, "covers"))

            if self.delete_fanart_var.isChecked():
                self.delete_files_in_dir(os.path.join(base_dir, "fanart"))

            if self.delete_videos_var.isChecked():
                self.delete_files_in_dir(os.path.join(base_dir, "videos"))

            self.show_info("Success", "Clean start completed successfully!")
        except Exception as e:
            self.show_error("Error", f"An error occurred during clean start: {e}")
        finally:
            self.clean_button.setEnabled(True)
            self.start_button.setEnabled(True)

    def delete_files_in_dir(self, directory):
        if os.path.exists(directory):
            for file_name in os.listdir(directory):
                file_path = os.path.join(directory, file_name)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logging.error(f"Error deleting {file_path}: {e}")
                    raise

    def download_greenlight_logo(self, theme_folder):
        try:
            logo_url = "https://upload.wikimedia.org/wikipedia/commons/3/31/Xbox_Game_Pass_new_logo_-_colored_version.svg"
            logos_path = os.path.join(theme_folder, "_inc", "systems", "logos")
            os.makedirs(logos_path, exist_ok=True)

            logo_file_path = os.path.join(logos_path, "greenlight.svg")
            response = requests.get(logo_url, timeout=10)
            response.raise_for_status()

            with open(logo_file_path, "wb") as logo_file:
                logo_file.write(response.content)

            self.show_info("Success", f"Greenlight logo has been saved at {logo_file_path}.")
        except Exception as e:
            self.show_error("Error", f"An error occurred while downloading the logo: {e}")

    def download_greenlight_fanart(self, theme_folder):
        try:
            fanart_url = "https://interpret.la/wp-content/uploads/2021/11/GAMING-Xbox-boss-says-Microsoft-not-done-acquiring-studios.jpg"
            fanart_path = os.path.join(theme_folder, "_inc", "systems", "fanart")
            os.makedirs(fanart_path, exist_ok=True)

            fanart_file_path = os.path.join(fanart_path, "greenlight.jpg")
            response = requests.get(fanart_url, timeout=10)
            response.raise_for_status()

            with open(fanart_file_path, "wb") as fanart_file:
                fanart_file.write(response.content)

            self.show_info("Success", f"Greenlight fanart has been saved at {fanart_file_path}.")
        except Exception as e:
            self.show_error("Error", f"An error occurred while downloading the fanart: {e}")

    def create_greenlight_theme_xml(self):
        try:
            theme_folder = QFileDialog.getExistingDirectory(self, "Select ES-DE Theme Folder")
            if not theme_folder:
                self.show_error("Error", "No folder selected.")
                return

            # Construct the file path for greenlight.xml
            greenlight_xml_path = os.path.join(theme_folder, "_inc", "systems", "system_metadata", "greenlight.xml")
            os.makedirs(os.path.dirname(greenlight_xml_path), exist_ok=True)

            # Define the XML content
            greenlight_xml_content = """<theme>
    <variables>
        <systemName>Xbox</systemName>
        <systemDescription>Xbox is a video gaming brand created and owned by Microsoft. It represents a series of video game consoles developed by Microsoft, with three consoles released in the sixth, seventh, and eighth generations, respectively. The brand also represents applications (games), streaming services, an online service by the name of Xbox Live, and the development arm by the name of Xbox Game Studios.

The brand was first introduced in the United States in November 2001, with the launch of the original Xbox console.</systemDescription>
        <systemManufacturer>Microsoft</systemManufacturer>
        <systemReleaseYear>2001</systemReleaseYear>
        <systemReleaseDate>2001-11-15</systemReleaseDate>
        <systemReleaseDateFormated>November 15, 2001</systemReleaseDateFormated>
        <systemHardwareType>Console</systemHardwareType>
        <systemCoverSize>243-340</systemCoverSize>
        <systemColor>68B653</systemColor>
        <systemColorPalette1>CDDF01</systemColorPalette1>
        <systemColorPalette2>9ABF5E</systemColorPalette2>
        <systemColorPalette3>534F57</systemColorPalette3>
        <systemColorPalette4>000000</systemColorPalette4>
        <systemCartSize>1-1</systemCartSize>
    </variables>
</theme>"""

            # Write the XML content to the file
            with open(greenlight_xml_path, "w", encoding="utf-8") as xml_file:
                xml_file.write(greenlight_xml_content)

            # Download the logo
            self.download_greenlight_logo(theme_folder)

            # Download the fanart
            self.download_greenlight_fanart(theme_folder)

            self.show_info("Success", f"Greenlight theme XML, logo, and fanart have been created at {theme_folder}.")
        except Exception as e:
            self.show_error("Error", f"An error occurred: {e}")

    def open_greenlight_link(self):
        webbrowser.open("https://flathub.org/apps/io.github.unknownskl.greenlight")

    def show_error(self, title, message):
        QMessageBox.critical(self, title, message, QMessageBox.Ok)

    def show_info(self, title, message):
        QMessageBox.information(self, title, message, QMessageBox.Ok)

    def show_warning(self, title, message):
        QMessageBox.warning(self, title, message, QMessageBox.Ok)
    
    def show_confirm(self, title, message):
        return QMessageBox.question(self, title, message, 
                                  QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # Use Fusion style for better dark theme support
    window = GreenlightSyncApp()
    window.show()
    sys.exit(app.exec_())