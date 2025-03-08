# 🚀 SuperFire Template Image Downloader

## Overview
SuperFire Template Image Downloader is a simple **Python GUI tool** that automatically downloads missing images for web templates.

When you download an HTML template, the demo images are often replaced with **gray placeholders**. This tool lets you specify your **local template folder** and the **remote demo site URL**, then it downloads the images to your local folder automatically.

Built with **PyQt6**, it provides a clean UI, a progress bar, and logs each download.

---
## Features
✅ **Automatically pulls missing images** from a demo site
✅ **GUI with file picker** for selecting local root folder
✅ **Progress bar with percentage display**
✅ **Live logs** for tracking downloads
✅ **Resizable window with dynamic UI adjustments**
✅ **Cross-platform** (Windows, macOS, Linux)

---
## Installation
### 1️⃣ Install Dependencies
Ensure you have **Python 3.10+** installed, then run:
```sh
pip install requests pyqt6
```

### 2️⃣ Run the Application
```sh
python SuperFire.py
```

---
## Usage
1️⃣ **Select your local root folder** – The folder containing your template files.
2️⃣ **Enter the remote demo site URL** – The online location where images are hosted.
3️⃣ **Click 'Start Download'** – The tool will fetch all images from the remote site and save them locally.

✅ **Example:**
- **Local Root Folder:** `C:/Users/YourName/Desktop/WebsiteTemplate`
- **Remote Root URL:** `https://example.com/template-demo/`

The app will replace all missing images inside the `assets/images/` folder with those from `https://example.com/template-demo/assets/images/`.

---
## Packaging as an executable
To create a standalone executable file on Windows, MacOS or Linux, so users can run it without Python installed:
```sh
pip install pyinstaller
pyinstaller --onefile --windowed --icon=icon.ico SuperFire.py
```
The output will be in the `dist/` folder.

---
## License
MIT License – Free to use and modify!

---
## Future Enhancements
🚀 **Drag-and-drop folder support**
🚀 **Multi-threaded downloading for speed improvements**
🚀 **Save and load previous paths for convenience**

