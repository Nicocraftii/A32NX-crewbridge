import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import requests, zipfile, tempfile, shutil
from pathlib import Path
import xml.etree.ElementTree as ET
import time
import threading

CONFIG_FILE = "config.xml"
WASM_ZIP_URL = "https://github.com/MobiFlight/MobiFlight-WASM-Module/releases/download/1.0.1/mobiflight-event-module.1.0.1.zip"
LOGO_PATH = "./public/assets/icon.png"
ICON_PATH = "./public/assets/icon.ico"
TEMP_FOLDER = Path(tempfile.gettempdir()) / "mobiflight_temp"

# ---------------- Utility Functions ----------------

def clean_temp():
    if TEMP_FOLDER.exists():
        try:
            shutil.rmtree(TEMP_FOLDER)
        except Exception as e:
            print(f"Warning: could not remove temp folder: {e}")
    TEMP_FOLDER.mkdir(parents=True, exist_ok=True)

def save_config(comm_path):
    root = ET.Element("config")
    p = ET.SubElement(root, "community_path")
    p.text = comm_path
    tree = ET.ElementTree(root)
    tree.write(CONFIG_FILE)

# ---------------- Download & Install ----------------
def download_and_install_wasm(comm_path, progress):
    try:
        clean_temp()
        tmp_file = TEMP_FOLDER / "module.zip"

        # Download ZIP
        response = requests.get(WASM_ZIP_URL, stream=True)
        total_length = int(response.headers.get('content-length', 0))
        dl = 0
        with open(tmp_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    dl += len(chunk)
                    if total_length > 0:
                        progress["value"] = (dl / total_length) * 50
                    else:
                        progress["value"] += 0.5
                    progress.update()

        # Extract ZIP
        with zipfile.ZipFile(tmp_file, 'r') as zip_ref:
            zip_ref.extractall(TEMP_FOLDER)

        wasm_folder = TEMP_FOLDER / "mobiflight-event-module"
        if not wasm_folder.exists():
            raise FileNotFoundError("Could not find 'mobiflight-event-module' in the extracted ZIP")

        target = Path(comm_path) / "mobiflight-event-module"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(wasm_folder, target)

        progress["value"] = 100
        progress.update()
        time.sleep(0.5)

        tmp_file.unlink()
        shutil.rmtree(TEMP_FOLDER)

    except Exception as e:
        messagebox.showerror("Error", f"Installation failed:\n{str(e)}")
        raise

# ---------------- Installer GUI ----------------
def run_installer():
    if not Path(CONFIG_FILE).exists():
        clean_temp()

    root = tk.Tk()
    root.title("MSFS Python Installer")
    root.geometry("500x280")
    root.resizable(False, False)

    # Window icon
    if Path(ICON_PATH).exists():
        try:
            root.iconbitmap(ICON_PATH)
        except Exception as e:
            print(f"Could not set icon: {e}")

    # Load logo
    if Path(LOGO_PATH).exists():
        img = Image.open(LOGO_PATH)
        img = img.resize((120, 120))
        logo_img = ImageTk.PhotoImage(img)
    else:
        logo_img = None

    # Frames
    page_welcome = tk.Frame(root)
    page_select = tk.Frame(root)
    page_warn = tk.Frame(root)
    page_install = tk.Frame(root)
    page_finish = tk.Frame(root)
    for page in (page_welcome, page_select, page_warn, page_install, page_finish):
        page.place(x=0, y=0, relwidth=1, relheight=1)

    # ---------------- Page 1: Welcome ----------------
    if logo_img:
        tk.Label(page_welcome, image=logo_img).pack(pady=10)
    tk.Label(page_welcome, text="Welcome to the MSFS Python Installer",
             font=("Segoe UI", 14, "bold")).pack(pady=10)
    tk.Label(page_welcome, text="This installer will install the MobiFlight WASM module.",
             font=("Segoe UI", 10)).pack(pady=5)

    btn_frame_welcome = tk.Frame(page_welcome)
    btn_frame_welcome.pack(side="bottom", anchor="e", pady=15, padx=15)
    tk.Button(btn_frame_welcome, text="Next", width=15, command=lambda: page_select.tkraise()).pack()

    # ---------------- Page 2: Select Community Folder ----------------
    tk.Label(page_select, text="Select your MSFS Community Folder", font=("Segoe UI", 12)).pack(pady=20)
    comm_path_var = tk.StringVar()
    tk.Entry(page_select, textvariable=comm_path_var, width=50).pack(pady=5)

    tk.Button(page_select, text="Browse", command=lambda: comm_path_var.set(filedialog.askdirectory())).pack(pady=5)

    btn_frame_select = tk.Frame(page_select)
    btn_frame_select.pack(side="bottom", anchor="e", pady=15, padx=15)
    tk.Button(btn_frame_select, text="Next", width=15,
              command=lambda: page_warn.tkraise() if comm_path_var.get() else messagebox.showerror("Error", "Please select a valid folder")
    ).pack()

    # ---------------- Page 3: Close MSFS Warning ----------------
    tk.Label(page_warn, text="WARNING", font=("Segoe UI", 16, "bold"), fg="red").pack(pady=20)
    tk.Label(page_warn, text="Please CLOSE Microsoft Flight Simulator before continuing the installation.\nLeaving it open may cause errors.",
             font=("Segoe UI", 12), wraplength=450, justify="center").pack(pady=10)

    btn_frame_warn = tk.Frame(page_warn)
    btn_frame_warn.pack(side="bottom", anchor="e", pady=15, padx=15)
    tk.Button(btn_frame_warn, text="I have closed MSFS", width=25, command=lambda: page_install.tkraise()).pack()

    # ---------------- Page 4: Installing ----------------
    status_label = tk.Label(page_install, text="Waiting for user...", font=("Segoe UI", 12))
    status_label.pack(pady=20)
    install_progress = ttk.Progressbar(page_install, length=400, mode="determinate")
    install_progress.pack(pady=10)

    btn_frame_install = tk.Frame(page_install)
    btn_frame_install.pack(side="bottom", anchor="e", pady=15, padx=15)
    def start_install():
        status_label.config(text="Installing...")
        try:
            clean_temp()
            download_and_install_wasm(comm_path_var.get(), install_progress)
            save_config(comm_path_var.get())
            status_label.config(text="Installation Complete!")
            time.sleep(0.5)
            page_finish.tkraise()
        except:
            status_label.config(text="Installation failed. Please try again.")
            page_select.tkraise()

    tk.Button(btn_frame_install, text="Install", width=15, command=lambda: threading.Thread(target=start_install, daemon=True).start()).pack()

    # ---------------- Page 5: Finish ----------------
    tk.Label(page_finish, text="Installation Complete!", font=("Segoe UI", 14, "bold")).pack(pady=20)

    btn_frame_finish = tk.Frame(page_finish)
    btn_frame_finish.pack(side="bottom", anchor="e", pady=15, padx=15)
    tk.Button(btn_frame_finish, text="Finish", width=15, command=root.destroy).pack()

    # Start installer
    page_welcome.tkraise()
    root.mainloop()

# ---------------- Entry Point ----------------
run_installer()
