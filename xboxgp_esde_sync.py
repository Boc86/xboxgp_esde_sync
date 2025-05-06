
#!/usr/bin/env python3
import json
import os
import re
import time
import logging
import requests
import shutil
import asyncio
import aiohttp
from aiofiles import open as aio_open
from datetime import datetime
import concurrent.futures
import webbrowser
import sys
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QProgressBar, QFileDialog, QMessageBox, QGroupBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

os.environ["QT_QPA_PLATFORM"] = "xcb"
SETTINGS_FILE = "settings.json"
CACHE_FILE = "additional_data.json"
CACHE_TIMESTAMP_FILE = "additional_data.timestamp"
CACHE_EXPIRY_SECONDS = 24 * 60 * 60

def check_and_clear_log_file():
    log_file = "xboxgames_debug.log"
    max_size = 1024 * 1024
    if os.path.exists(log_file) and os.path.getsize(log_file) >= max_size:
        with open(log_file, 'w') as f:
            f.write("")

check_and_clear_log_file()
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("xboxgames_debug.log"),
        logging.StreamHandler()
    ]
)

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        raise EnvironmentError("ffmpeg is not installed or not in PATH. Please install ffmpeg to proceed.")

def is_cache_valid():
    if not os.path.exists(CACHE_FILE) or not os.path.exists(CACHE_TIMESTAMP_FILE):
        return False
    try:
        with open(CACHE_TIMESTAMP_FILE, "r") as f:
            timestamp = float(f.read().strip())
        if time.time() - timestamp < CACHE_EXPIRY_SECONDS:
            return True
    except Exception as e:
        logging.warning(f"Could not read cache timestamp: {e}")
    return False

def update_cache_timestamp():
    with open(CACHE_TIMESTAMP_FILE, "w") as f:
        f.write(str(time.time()))

def fetch_ids():
    url = "https://catalog.gamepass.com/sigls/v2?id=fdd9e2a7-0fee-49f6-ad69-4354098401ff&language=en-us&market=GB"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        ids = [item['id'] for item in data if 'id' in item]
        ids_string = ",".join(ids)
        return ids_string
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching IDs: {e}")
        raise

def save_additional_data_to_json(id_strings):
    base_url = "https://displaycatalog.mp.microsoft.com/v7.0/products?bigIds=INSERT&market=GB&languages=en-us&MS-CV=DGU1mcuYo0WMMp+F.1"
    url = base_url.replace("INSERT", id_strings)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
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
        output_path = os.path.join(os.getcwd(), CACHE_FILE)
        with open(output_path, "w", encoding="utf-8") as json_file:
            json.dump(extracted_data, json_file, indent=4)
        update_cache_timestamp()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching additional data: {e}")
        raise

def download_video(dash_url, output_path):
    try:
        command = f'ffmpeg -i "{dash_url}" -vf scale=640:480 -preset fast -c:a copy "{output_path}"'
        process = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            logging.error(f"ffmpeg failed for {dash_url} with error: {process.stderr.decode().strip()}")
            return False
        return True
    except Exception as e:
        logging.error(f"Exception occurred while converting {dash_url} to MP4: {e}")
        return False

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
    for subdir in [marquee_dir, cover_dir, fanart_dir]:
        os.makedirs(subdir, exist_ok=True)
    file_path = os.path.join(output_dir, f"{sanitized_title}.sh")
    if not os.path.exists(file_path):
        script_name = f"xcloud_{sanitized_title}"
        async with aio_open(file_path, "w", encoding="utf-8") as sh_file:
            await sh_file.write("#!/bin/bash\n")
            await sh_file.write(
                f"flatpak run --socket=wayland --env=ELECTRON_ENABLE_WAYLAND=1 io.github.unknownskl.greenlight --fullscreen --connect='{script_name}'\n"
            )
        os.chmod(file_path, 0o755)
        files_created["sh"] += 1
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
    if poster_url:
        poster_image_path = os.path.join(cover_dir, f"{sanitized_title}.png")
        if not os.path.exists(poster_image_path):
            await download_image(session, poster_url, poster_image_path)
            files_created["poster"] += 1
    superhero_url = entry.get("Images", {}).get("TitledHeroArt")
    if superhero_url:
        fanart_path = os.path.join(fanart_dir, f"{sanitized_title}.png")
        if not os.path.exists(fanart_path):
            await download_image(session, superhero_url, fanart_path)
            files_created["fanart"] += 1

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
            if meta.get("rating"):
                game_entry += f'        <rating>{meta["rating"]}</rating>\n'
            if meta.get("OriginalReleaseDate"):
                try:
                    date_obj = datetime.strptime(meta["OriginalReleaseDate"].split('T')[0], "%Y-%m-%d")
                    release_date = date_obj.strftime("%Y%m%d")
                    game_entry += f'        <releasedate>{release_date}T000000</releasedate>\n'
                except Exception:
                    pass
            if meta.get("DeveloperName"):
                game_entry += f'        <developer>{meta["DeveloperName"]}</developer>\n'
            if meta.get("Publisher"):
                game_entry += f'        <publisher>{meta["Publisher"]}</publisher>\n'
            if meta.get("Genre"):
                game_entry += f'        <genre>{meta["Genre"]}</genre>\n'
            if meta.get("Players"):
                game_entry += f'        <players>{meta["Players"]}</players>\n'
            if meta.get("playcount"):
                game_entry += f'        <playcount>{meta["playcount"]}</playcount>\n'
            if meta.get("lastplayed"):
                game_entry += f'        <lastplayed>{meta["lastplayed"]}</lastplayed>\n'
            game_entry += '    </game>'
            entries.append(game_entry)
    xml_content = '<?xml version="1.0"?>\n<gameList>\n' + '\n'.join(entries) + '\n</gameList>'
    async with aio_open(gamelist_path, "w", encoding="utf-8") as f:
        await f.write(xml_content)

def ensure_greenlight_subdir(path):
    path = os.path.abspath(path)
    if not os.path.basename(path).lower() == "greenlight":
        path = os.path.join(path, "greenlight")
    os.makedirs(path, exist_ok=True)
    return path

def download_file_to_subfolder(parent_folder, subfolders, filename, url):
    try:
        dest_dir = os.path.join(parent_folder, *subfolders)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, filename)
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        with open(dest_path, 'wb') as f:
            f.write(resp.content)
        return True, dest_path
    except Exception as e:
        logging.error(f"Failed to download {url} to {dest_path}: {e}")
        return False, str(e)

async def main(base_dir, gamelist_dir, rom_dir, download_videos=False, progress_callback=None):
    try:
        if progress_callback:
            progress_callback(5)
        if not is_cache_valid():
            if progress_callback:
                progress_callback(10)
            ids_string = fetch_ids()
            if progress_callback:
                progress_callback(20)
            save_additional_data_to_json(ids_string)
        else:
            logging.info("Cache files are valid. No need to download catalog data.")
        if progress_callback:
            progress_callback(40)
        assets_dir = ensure_greenlight_subdir(base_dir)
        games_dir = ensure_greenlight_subdir(rom_dir)
        gamelist_folder = ensure_greenlight_subdir(gamelist_dir)
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            metadata_list = json.load(f)
        metadata_dict = {}
        for entry in metadata_list:
            title = entry.get("ProductTitle", "")
            sanitized_title = re.sub(r"[^a-zA-Z0-9]", "", title).upper()
            metadata_dict[sanitized_title] = entry
        valid_titles = set()
        files_created = {"sh": 0, "logo": 0, "poster": 0, "fanart": 0}
        marquee_dir = os.path.join(assets_dir, "marquee")
        cover_dir = os.path.join(assets_dir, "cover")
        fanart_dir = os.path.join(assets_dir, "fanart")
        async with aiohttp.ClientSession() as session:
            coros = []
            for entry in metadata_list:
                coros.append(process_entry(entry, session, valid_titles, files_created, games_dir, marquee_dir, cover_dir, fanart_dir))
            total = len(coros)
            chunk = max(1, total // 20) if total else 1
            for i in range(0, total, chunk):
                await asyncio.gather(*coros[i:i + chunk])
                if progress_callback:
                    progress_callback(40 + int(50 * i / total))
        gamelist_path = os.path.join(gamelist_folder, "gamelist.xml")
        await generate_gamelist(games_dir, gamelist_path, metadata_dict)
        if progress_callback:
            progress_callback(100)
    except Exception as e:
        logging.error(f"Exception in main(): {e}")
        raise

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(settings):
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
    XBOX_GREEN = "#107C10"
    BUTTON_STYLE = f"""
        QPushButton {{
            background-color: #222;
            color: {XBOX_GREEN};
            font-weight: bold;
            border-radius: 6px;
            border: 1px solid #484848;
            padding: 7px 16px;
        }}
        QPushButton:pressed {{
            background-color: #107C1099;
            color: white;
        }}
    """
    TITLE_STYLE = f"""
        QGroupBox::title {{
            color: {XBOX_GREEN};
            subcontrol-origin: margin;
            left: 20px;
            font-weight: bold;
            font-size: 15pt;
        }}
    """
    CLEAN_BUTTON_STYLE = f"""
        QPushButton {{
            background-color: #222;
            color: #ff2222;
            font-weight: bold;
            border-radius: 6px;
            border: 1px solid #484848;
            padding: 7px 16px;
        }}
        QPushButton:pressed {{
            background-color: #107C1099;
            color: white;
        }}
    """
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.init_ui()
    def open_greenlight_link(self):
        url = "https://flathub.org/apps/io.github.unknownskl.greenlight"
        webbrowser.open(url)
    def browse_folder(self, entry_widget):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder:
            entry_widget.setText(folder)
    def init_ui(self):
        self.setWindowTitle('Xbox Game Pass Sync')
        self.setMinimumSize(900, 600)
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")))
        central_widget = QWidget()
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        header_group = QGroupBox("Step 1: Install Greenlight")
        header_group.setStyleSheet(self.TITLE_STYLE)
        header_group.setMinimumWidth(500)
        header_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header_layout = QVBoxLayout(header_group)
        info_label = QLabel(
            "This tool syncs Xbox Game Pass games with EmulationStation-DE.\n"
            "You must have Greenlight installed to use this tool."
        )
        info_label.setWordWrap(True)
        header_layout.addWidget(info_label)
        open_link_button = QPushButton("Open Greenlight Installation Page")
        open_link_button.setStyleSheet(self.BUTTON_STYLE)
        header_layout.addWidget(open_link_button)
        open_link_button.clicked.connect(self.open_greenlight_link)
        main_layout.addWidget(header_group)
        directory_section = self.create_directory_section_widget()
        main_layout.addWidget(directory_section)
        controls_group = QGroupBox("Step 3: Integration and Sync")
        controls_group.setStyleSheet(self.TITLE_STYLE)
        controls_group.setMinimumWidth(500)
        controls_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        controls_layout = QVBoxLayout(controls_group)
        integrate_layout = QHBoxLayout()
        integrate_button = QPushButton("Integrate Greenlight with ES-DE")
        integrate_button.setStyleSheet(self.BUTTON_STYLE)
        integrate_button.clicked.connect(self.integrate_greenlight)
        integrate_layout.addWidget(integrate_button)
        modify_theme_button = QPushButton("Modify Theme")
        modify_theme_button.setStyleSheet(self.BUTTON_STYLE)
        modify_theme_button.clicked.connect(self.modify_theme)
        integrate_layout.addWidget(modify_theme_button)
        controls_layout.addLayout(integrate_layout)
        self.start_button = QPushButton("Start Sync")
        self.start_button.setFont(QFont('Sans', 12, QFont.Bold))
        self.start_button.setMinimumHeight(50)
        self.start_button.setStyleSheet(self.BUTTON_STYLE)
        self.start_button.clicked.connect(self.start_sync)
        controls_layout.addWidget(self.start_button)
        self.progress = QProgressBar()
        self.progress.setMinimum(0)
        self.progress.setMaximum(100)
        self.progress.setValue(0)
        controls_layout.addWidget(self.progress)
        self.status_label = QLabel("Status: Ready")
        self.status_label.setStyleSheet("color: #e0e0e0; font-size: 10pt;")
        controls_layout.addWidget(self.status_label)
        main_layout.addWidget(controls_group)
        maintenance_group = QGroupBox("Maintenance")
        maintenance_group.setStyleSheet(self.TITLE_STYLE)
        maintenance_group.setMinimumWidth(500)
        maintenance_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        maintenance_layout = QVBoxLayout(maintenance_group)
        clean_button = QPushButton("Clean All Media")
        clean_button.setStyleSheet(self.CLEAN_BUTTON_STYLE)
        clean_button.clicked.connect(self.clean_all_media)
        maintenance_layout.addWidget(clean_button)
        main_layout.addWidget(maintenance_group)
        main_layout.addStretch()
        self.setCentralWidget(central_widget)
    def create_directory_section_widget(self):
        group = QGroupBox("Step 2: Select Folders")
        group.setStyleSheet(self.TITLE_STYLE)
        group.setMinimumWidth(500)
        group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        assets_row = QHBoxLayout()
        assets_label = QLabel("Assets Directory:")
        assets_label.setFixedWidth(130)
        self.folder_entry = QLineEdit(self.settings.get("base_dir", ""))
        assets_browse = QPushButton("Browse")
        assets_browse.setStyleSheet(self.BUTTON_STYLE)
        assets_browse.clicked.connect(lambda: self.browse_folder(self.folder_entry))
        assets_row.addWidget(assets_label)
        assets_row.addWidget(self.folder_entry)
        assets_row.addWidget(assets_browse)
        layout.addLayout(assets_row)
        games_row = QHBoxLayout()
        games_label = QLabel("Games Directory:")
        games_label.setFixedWidth(130)
        self.sh_folder_entry = QLineEdit(self.settings.get("sh_dir", ""))
        games_browse = QPushButton("Browse")
        games_browse.setStyleSheet(self.BUTTON_STYLE)
        games_browse.clicked.connect(lambda: self.browse_folder(self.sh_folder_entry))
        games_row.addWidget(games_label)
        games_row.addWidget(self.sh_folder_entry)
        games_row.addWidget(games_browse)
        layout.addLayout(games_row)
        gamelist_row = QHBoxLayout()
        gamelist_label = QLabel("Gamelist Directory:")
        gamelist_label.setFixedWidth(130)
        self.gamelist_folder_entry = QLineEdit(self.settings.get("gamelist_dir", ""))
        gamelist_browse = QPushButton("Browse")
        gamelist_browse.setStyleSheet(self.BUTTON_STYLE)
        gamelist_browse.clicked.connect(lambda: self.browse_folder(self.gamelist_folder_entry))
        gamelist_row.addWidget(gamelist_label)
        gamelist_row.addWidget(self.gamelist_folder_entry)
        gamelist_row.addWidget(gamelist_browse)
        layout.addLayout(gamelist_row)
        return group
    def modify_theme(self):
        theme_folder = QFileDialog.getExistingDirectory(
            self,
            "Select Theme Folder to Modify (select the THEME ROOT directory)",
            os.path.expanduser('~'),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if not theme_folder:
            self.show_info("Modify Theme", "No folder selected.")
            return
        svg_url = "https://raw.githubusercontent.com/Boc86/xboxgp_esde_sync/main/themes/gp_logo.svg"
        fanart_url = "https://raw.githubusercontent.com/Boc86/xboxgp_esde_sync/main/themes/gp_fanart.jpg"
        systems_ok, sys_res = download_file_to_subfolder(theme_folder, ["_inc", "systems"], "greenlight.svg", svg_url)
        fanart_ok, fanart_res = download_file_to_subfolder(theme_folder, ["_inc", "fanart"], "greenlight.jpg", fanart_url)
        if systems_ok and fanart_ok:
            self.show_info(
                "Theme Modified",
                "Greenlight theme assets have been added to the theme. "
                "Check:\n"
                f"- {os.path.join(theme_folder, '_inc', 'systems', 'greenlight.svg')}\n"
                f"- {os.path.join(theme_folder, '_inc', 'fanart', 'greenlight.jpg')}"
            )
        else:
            errors = []
            if not systems_ok:
                errors.append(f"SVG error: {sys_res}")
            if not fanart_ok:
                errors.append(f"Fanart error: {fanart_res}")
            self.show_error(
                "Modify Theme Error",
                "Some or all theme files could not be downloaded/placed.\n" +
                "\n".join(errors)
            )
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
            custom_systems_path = os.path.join(esde_folder, "es_systems.xml")
            if not os.path.exists(custom_systems_path):
                self.show_error("Error", "es_systems.xml not found in the selected folder.")
                return
            import xml.etree.ElementTree as ET
            from xml.dom import minidom
            try:
                tree = ET.parse(custom_systems_path)
                root = tree.getroot()
            except ET.ParseError as pe:
                self.show_error("Error", f"Error parsing es_systems.xml: {pe}")
                return
            if root.tag.lower() != "systemlist":
                systemlist = root.find("systemList")
                if systemlist is None:
                    systemlist = ET.Element("systemList")
                    systemlist.extend(list(root))
                    root = systemlist
                else:
                    root = systemlist
            else:
                systemlist = root
            exists = any(
                system.find('name') is not None and system.find('name').text.strip().lower() == "greenlight"
                for system in systemlist.findall('system')
            )
            if exists:
                self.show_info("Info", "Greenlight is already integrated into ES-DE.")
                return
            games_dir = self.sh_folder_entry.text().strip()
            if not games_dir:
                self.show_error("Error", "Please set the Games Directory in Step 2.")
                return
            system_elem = ET.Element("system")
            ET.SubElement(system_elem, "name").text = "greenlight"
            ET.SubElement(system_elem, "fullname").text = "Xbox Game Pass"
            ET.SubElement(system_elem, "path").text = f'bash "{games_dir}"'
            ET.SubElement(system_elem, "extension").text = ".sh"
            command_elem = ET.SubElement(system_elem, "command")
            command_elem.set("label", "Greenlight")
            command_elem.text = "bash %ROM%"
            ET.SubElement(system_elem, "platform").text = "xbox"
            ET.SubElement(system_elem, "theme").text = "greenlight"
            systemlist.append(system_elem)
            xmlstr = ET.tostring(systemlist, encoding='utf-8')
            reparsed = minidom.parseString(xmlstr)
            pretty_xml = reparsed.toprettyxml(indent="    ")
            with open(custom_systems_path, "w", encoding="utf-8") as file:
                file.write(pretty_xml)
            self.show_info("Success", "Greenlight has been successfully integrated into ES-DE.")
        except Exception as e:
            self.show_error("Error", f"An error occurred: {e}")
            logging.error(f"Error in integrate_greenlight: {e}")
    def show_error(self, title, message):
        QMessageBox.critical(self, title, message)
    def show_info(self, title, message):
        QMessageBox.information(self, title, message)
    def start_sync(self):
        base_dir = self.folder_entry.text().strip()
        sh_dir = self.sh_folder_entry.text().strip()
        gamelist_dir = self.gamelist_folder_entry.text().strip()
        if not base_dir or not sh_dir or not gamelist_dir:
            self.show_error("Error", "Please select folders for Assets, Games, and Gamelist.")
            return
        base_dir = ensure_greenlight_subdir(base_dir)
        sh_dir = ensure_greenlight_subdir(sh_dir)
        gamelist_dir = ensure_greenlight_subdir(gamelist_dir)
        self.settings["base_dir"] = base_dir
        self.settings["sh_dir"] = sh_dir
        self.settings["gamelist_dir"] = gamelist_dir
        save_settings(self.settings)
        self.progress.setValue(0)
        self.status_label.setText("Status: Sync in progress...")
        self.status_label.setStyleSheet("color: #e0e0e0; font-size: 10pt;")
        self.start_button.setEnabled(False)
        self.worker = SyncWorker(base_dir, sh_dir, gamelist_dir)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.sync_complete)
        self.worker.error.connect(self.sync_error)
        self.worker.start()
    def sync_complete(self):
        self.status_label.setText("Status: Sync complete!")
        self.status_label.setStyleSheet("color: #4CAF50; font-size: 10pt;")
        self.progress.setValue(100)
        self.start_button.setEnabled(True)
    def sync_error(self, message):
        self.status_label.setText(f"Sync error: {message}")
        self.status_label.setStyleSheet("color: #ff3333; font-size: 10pt;")
        self.progress.setValue(0)
        self.start_button.setEnabled(True)
    def clean_all_media(self):
        base_dir = self.folder_entry.text().strip()
        sh_dir = self.sh_folder_entry.text().strip()
        gamelist_dir = self.gamelist_folder_entry.text().strip()
        base_dir = ensure_greenlight_subdir(base_dir)
        sh_dir = ensure_greenlight_subdir(sh_dir)
        gamelist_dir = ensure_greenlight_subdir(gamelist_dir)
        reply = QMessageBox.question(
            self,
            "Confirm Clean",
            "Are you sure you want to delete ALL synced media, videos, scripts, and gamelists for Greenlight? (This cannot be undone.)",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            paths_to_clean = [
                os.path.join(base_dir, "marquee"),
                os.path.join(base_dir, "cover"),
                os.path.join(base_dir, "fanart"),
                sh_dir,
                gamelist_dir,
                CACHE_FILE,
                CACHE_TIMESTAMP_FILE
            ]
            for p in paths_to_clean:
                if os.path.isdir(p):
                    shutil.rmtree(p, ignore_errors=True)
                elif os.path.isfile(p):
                    os.remove(p)
            self.show_info("Clean Complete", "All Greenlight media and data have been deleted.")

def main_app():
    app = QApplication(sys.argv)
    window = GreenlightSyncApp()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main_app()
