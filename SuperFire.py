import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QProgressBar, QFileDialog, QLineEdit, QTextEdit, QHBoxLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class DownloadWorker(QThread):
    progress = pyqtSignal(int)
    log = pyqtSignal(str)
    status_update = pyqtSignal(int, str)  # Red or Green for threads

    def __init__(self, local_root, remote_root, num_threads=5):
        super().__init__()
        self.local_root = local_root
        self.remote_root = remote_root
        self.num_threads = num_threads
        self.total_files = 0
        self.downloaded_files = 0
        self.lock = threading.Lock()

    def run(self):
        files_to_download = self.get_files_to_download()
        self.total_files = len(files_to_download)

        if self.total_files == 0:
            self.log.emit("No files found to download.")
            self.progress.emit(100)
            return

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = {executor.submit(self.download_file, file_info, i % self.num_threads): i for i, file_info in enumerate(files_to_download)}

            for future in as_completed(futures):
                future.result()  # Wait for download completion

    def get_files_to_download(self):
        """ Scans local directory and generates remote file paths. """
        file_list = []
        for root, _, files in os.walk(self.local_root):
            for file in files:
                local_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_path, self.local_root).replace("\\", "/")
                remote_url = f"{self.remote_root}/{relative_path}"
                file_list.append((local_path, remote_url))
        return file_list

    def download_file(self, file_info, thread_id):
        """ Downloads a file using requests. """
        local_path, remote_url = file_info
        self.status_update.emit(thread_id, "red")  # Light turns red while downloading

        try:
            response = requests.get(remote_url, stream=True, timeout=10)
            if response.status_code == 200:
                with open(local_path, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)

                with self.lock:
                    self.downloaded_files += 1
                    progress_percentage = int((self.downloaded_files / self.total_files) * 100)
                    self.progress.emit(progress_percentage)  # Update UI with correct progress
                    self.log.emit(f"✅ Downloaded: {local_path}")
            else:
                self.log.emit(f"❌ Failed: {remote_url} (HTTP {response.status_code})")
        except Exception as e:
            self.log.emit(f"⚠️ Error downloading {remote_url}: {str(e)}")
        finally:
            with self.lock:
                self.status_update.emit(thread_id, "green")  # Light turns green when done

class ImageDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SuperFire Template Image Downloader")
        self.setGeometry(200, 200, 850, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        self.local_label = QLabel("Local Root Path:")
        self.local_input = QLineEdit()
        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self.select_local_folder)

        self.remote_label = QLabel("Remote Root URL:")
        self.remote_input = QLineEdit()

        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download)

        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)  # Show percentage inside progress bar

        # Thread indicator lights (🔴 = Active, 🟢 = Done) - 75% of original size
        self.thread_labels = [QLabel("🟢") for _ in range(5)]
        self.thread_layout = QHBoxLayout()
        for lbl in self.thread_labels:
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-size: 15px;")  # Reduce size to 75%
            self.thread_layout.addWidget(lbl)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)

        layout.addWidget(self.local_label)
        layout.addWidget(self.local_input)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.remote_label)
        layout.addWidget(self.remote_input)
        layout.addWidget(self.start_button)
        layout.addWidget(self.progress_bar)
        layout.addLayout(self.thread_layout)  # Thread indicators
        layout.addWidget(self.log_output)

        self.setLayout(layout)

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

        self.progress_bar.setValue(0)
        self.log_output.clear()

        # Reset thread lights
        for lbl in self.thread_labels:
            lbl.setText("🟢")  # All start as green

        self.worker = DownloadWorker(local_root, remote_root, num_threads=5)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.update_log)
        self.worker.status_update.connect(self.update_thread_lights)
        self.worker.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)  # Only show progress bar percentage

    def update_log(self, message):
        self.log_output.append(message)

    def update_thread_lights(self, thread_id, status):
        """ Updates the thread indicator lights based on thread activity. """
        if 0 <= thread_id < len(self.thread_labels):
            self.thread_labels[thread_id].setText("🔴" if status == "red" else "🟢")

if __name__ == "__main__":
    app = QApplication([])
    window = ImageDownloaderApp()
    window.show()
    app.exec()
