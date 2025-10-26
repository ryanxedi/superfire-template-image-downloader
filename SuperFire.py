import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar, QFileDialog,
    QLineEdit, QTextEdit, QHBoxLayout, QComboBox, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Allowed image file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".svg"}

# ---- User-Agent presets -------------------------------------------------------
UA_PRESETS = {
    "Chrome (Windows 10)": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Firefox (Windows 10)": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
    "Edge (Windows 11)": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0"
    ),
    "Safari (iPhone iOS 17)": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Safari (macOS 14)": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Requests default": "python-requests/2.x",
    "Custom…": "",  # enables the custom input
}

# ---- Worker -------------------------------------------------------------------
class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    status_update = pyqtSignal(int, str)  # "red" or "green"

    def __init__(self, local_root, remote_root, num_threads=5, headers=None, timeout=20, max_retries=5, backoff=0.5):
        super().__init__()
        self.local_root = local_root
        self.remote_root = remote_root.rstrip("/")
        self.num_threads = num_threads
        self.total_files = 0
        self.downloaded_files = 0
        self.lock = threading.Lock()
        self.timeout = timeout
        self.headers = headers or {}
        self.max_retries = max_retries
        self.backoff = backoff

        # Build a fresh Session configured for resilience
        self.session = requests.Session()
        retry = Retry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            backoff_factor=self.backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=self.num_threads)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # If user wanted identity (no compression)
        if self.headers.get("_identity_encoding"):
            self.headers["Accept-Encoding"] = "identity"
            del self.headers["_identity_encoding"]

        # If user wants Connection: close (some servers dislike keep-alive over pools)
        if self.headers.get("_connection_close"):
            self.headers["Connection"] = "close"
            del self.headers["_connection_close"]

        # Provide sensible defaults if not specified
        self.headers.setdefault(
            "Accept",
            "image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
        )

    def run(self):
        files_to_download = self.get_files_to_download()
        self.total_files = len(files_to_download)

        if self.total_files == 0:
            self.log.emit("No image files found to download.")
            self.progress.emit(100)
            return

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {
                executor.submit(self.download_file, file_info, i % self.num_threads): i
                for i, file_info in enumerate(files_to_download)
            }
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.log.emit(f"⚠️ Unhandled worker error: {e}")

    def get_files_to_download(self):
        """Scans local directory and maps to remote image URLs preserving structure."""
        file_list = []
        for root, _, files in os.walk(self.local_root):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext in ALLOWED_EXTENSIONS:
                    local_path = os.path.join(root, file)
                    relative_path = os.path.relpath(local_path, self.local_root).replace("\\", "/")
                    remote_url = f"{self.remote_root}/{relative_path}"
                    file_list.append((local_path, remote_url))
        return file_list

    def download_file(self, file_info, thread_id):
        local_path, remote_url = file_info
        self.status_update.emit(thread_id, "red")

        # Ensure local folder exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        try:
            # Build per-request headers (optionally add Referer per URL path)
            req_headers = dict(self.headers)
            if req_headers.get("_dynamic_referer"):
                # Use the directory page as a plausible referer
                # e.g., https://site.com/path/file.jpg -> https://site.com/path/
                try:
                    from urllib.parse import urlsplit, urlunsplit
                    parts = urlsplit(remote_url)
                    folder = "/".join(parts.path.split("/")[:-1]) + "/"
                    referer = urlunsplit((parts.scheme, parts.netloc, folder, "", ""))
                    req_headers["Referer"] = referer
                except Exception:
                    pass
                del req_headers["_dynamic_referer"]

            r = self.session.get(
                remote_url,
                headers=req_headers,
                timeout=self.timeout,
                allow_redirects=True,
                stream=True
            )

            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 16):
                        if chunk:
                            f.write(chunk)

                with self.lock:
                    self.downloaded_files += 1
                    pct = int((self.downloaded_files / self.total_files) * 100)
                    self.progress.emit(pct)
                    self.log.emit(f"✅ Downloaded: {local_path}")
            else:
                self.log.emit(f"❌ Failed: {remote_url} (HTTP {r.status_code})")

        except requests.exceptions.RequestException as e:
            self.log.emit(f"⚠️ Error downloading {remote_url}: {e}")
        finally:
            with self.lock:
                self.status_update.emit(thread_id, "green")


# ---- UI -----------------------------------------------------------------------
class ImageDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SuperFire Template Image Downloader")
        self.setGeometry(200, 200, 950, 560)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Local path
        self.local_label = QLabel("Local Root Path:")
        self.local_input = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.select_local_folder)

        # Remote
        self.remote_label = QLabel("Remote Root URL:")
        self.remote_input = QLineEdit()

        # User-Agent controls
        ua_row = QHBoxLayout()
        self.ua_label = QLabel("User-Agent:")
        self.ua_combo = QComboBox()
        self.ua_combo.addItems(list(UA_PRESETS.keys()))
        self.ua_combo.setCurrentText("Chrome (Windows 10)")
        self.ua_combo.currentTextChanged.connect(self._toggle_custom_ua)
        self.ua_custom = QLineEdit()
        self.ua_custom.setPlaceholderText("Enter custom User-Agent…")
        self.ua_custom.setEnabled(False)
        ua_row.addWidget(self.ua_label)
        ua_row.addWidget(self.ua_combo, stretch=1)
        ua_row.addWidget(self.ua_custom, stretch=2)

        # Referer options
        ref_row = QHBoxLayout()
        self.referer_label = QLabel("Referer:")
        self.referer_input = QLineEdit()
        self.referer_input.setPlaceholderText("Optional explicit Referer (leave blank to skip)")
        self.cb_dynamic_ref = QCheckBox("Use dynamic Referer from each file's folder")
        self.cb_dynamic_ref.setChecked(True)
        ref_row.addWidget(self.referer_label)
        ref_row.addWidget(self.referer_input, stretch=2)
        ref_row.addWidget(self.cb_dynamic_ref)

        # Header knobs
        knobs_row = QHBoxLayout()
        self.cb_identity = QCheckBox("Disable compression (Accept-Encoding: identity)")
        self.cb_conn_close = QCheckBox("Connection: close")
        knobs_row.addWidget(self.cb_identity)
        knobs_row.addWidget(self.cb_conn_close)
        knobs_row.addStretch()

        # Start
        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)

        # Thread indicator lights
        self.thread_labels = [QLabel("🟢") for _ in range(5)]
        self.thread_layout = QHBoxLayout()
        for lbl in self.thread_labels:
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 15px;")
            self.thread_layout.addWidget(lbl)

        # Log
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        # Assemble
        layout.addWidget(self.local_label)
        layout.addWidget(self.local_input)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.remote_label)
        layout.addWidget(self.remote_input)
        layout.addLayout(ua_row)
        layout.addLayout(ref_row)
        layout.addLayout(knobs_row)
        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addLayout(self.thread_layout)
        layout.addWidget(self.log_output)
        self.setLayout(layout)

    def _toggle_custom_ua(self):
        self.ua_custom.setEnabled(self.ua_combo.currentText() == "Custom…")

    def select_local_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Local Root Folder")
        if folder:
            self.local_input.setText(folder)

    def start_download(self):
        local_root = self.local_input.text().strip()
        remote_root = self.remote_input.text().strip()

        if not local_root or not remote_root:
            self.log_output.append("⚠️ Please enter both the local root path and remote URL.")
            return

        # Build headers from UI selections
        ua_choice = self.ua_combo.currentText()
        user_agent = self.ua_custom.text().strip() if ua_choice == "Custom…" else UA_PRESETS.get(ua_choice, "")
        headers = {}

        if user_agent and user_agent != "python-requests/2.x":
            headers["User-Agent"] = user_agent
        # Explicit Referer overrides dynamic
        if self.referer_input.text().strip():
            headers["Referer"] = self.referer_input.text().strip()
        else:
            if self.cb_dynamic_ref.isChecked():
                headers["_dynamic_referer"] = True

        if self.cb_identity.isChecked():
            headers["_identity_encoding"] = True
        if self.cb_conn_close.isChecked():
            headers["_connection_close"] = True

        self.progress_bar.setValue(0)
        self.log_output.clear()

        # Reset thread lights
        for lbl in self.thread_labels:
            lbl.setText("🟢")

        # Spin up worker
        self.worker = DownloadWorker(
            local_root=local_root,
            remote_root=remote_root,
            num_threads=len(self.thread_labels),
            headers=headers,
            timeout=25,
            max_retries=5,
            backoff=0.6
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.status_update.connect(self.update_thread_lights)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def update_log(self, message):
        self.log_output.append(message)

    def update_thread_lights(self, thread_id, status):
        if 0 <= thread_id < len(self.thread_labels):
            self.thread_labels[thread_id].setText("🔴" if status == "red" else "🟢")


if __name__ == "__main__":
    app = QApplication([])
    window = ImageDownloaderApp()
    window.show()
    app.exec()
