import os
import requests
from urllib.parse import urljoin
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog,
                             QProgressBar, QHBoxLayout)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon

class ImageDownloaderThread(QThread):
    update_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    
    def __init__(self, local_root, remote_root):
        super().__init__()
        self.local_root = local_root
        self.remote_root = remote_root
    
    def run(self):
        if not os.path.exists(self.local_root):
            self.update_signal.emit(f"Local directory '{self.local_root}' does not exist.")
            return
        
        files_list = []
        for root, _, files in os.walk(self.local_root):
            for file in files:
                files_list.append(os.path.join(root, file))
        
        total_files = len(files_list)
        if total_files == 0:
            self.update_signal.emit("No files found in the local directory.")
            return
        
        for index, local_file_path in enumerate(files_list, start=1):
            relative_path = os.path.relpath(local_file_path, self.local_root)
            remote_url = urljoin(self.remote_root + '/', relative_path.replace('\\', '/'))
            
            try:
                response = requests.get(remote_url, stream=True)
                if response.status_code == 200:
                    with open(local_file_path, 'wb') as f:
                        for chunk in response.iter_content(1024):
                            f.write(chunk)
                    self.update_signal.emit(f"Downloaded: {remote_url} -> {local_file_path}")
                else:
                    self.update_signal.emit(f"Failed: {remote_url} (Status {response.status_code})")
            except requests.RequestException as e:
                self.update_signal.emit(f"Error downloading {remote_url}: {e}")
            
            progress = int((index / total_files) * 100)
            self.progress_signal.emit(progress)

class ImageDownloaderApp(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("SuperFire Template Image Downloader")
        self.setGeometry(200, 200, 850, 500)
        self.setWindowIcon(QIcon("icon.png"))  # Set application icon
        
        layout = QVBoxLayout()
        
        self.local_label = QLabel("Local Root Path:")
        layout.addWidget(self.local_label)
        self.local_input = QLineEdit()
        layout.addWidget(self.local_input)
        self.local_button = QPushButton("Browse")
        self.local_button.clicked.connect(self.select_local_folder)
        layout.addWidget(self.local_button)
        
        self.remote_label = QLabel("Remote Root URL:")
        layout.addWidget(self.remote_label)
        self.remote_input = QLineEdit()
        layout.addWidget(self.remote_input)
        
        self.start_button = QPushButton("Start Download")
        self.start_button.clicked.connect(self.start_download)
        layout.addWidget(self.start_button)
        
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)  # Hide built-in percentage
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)
        
        layout.addLayout(progress_layout)
        
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        
        self.setLayout(layout)
        
  # Make progress bar expand with window
    
    def select_local_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Local Root Folder")
        if folder:
            self.local_input.setText(folder)
    
    def start_download(self):
        local_root = self.local_input.text()
        remote_root = self.remote_input.text()
        
        if not local_root or not remote_root:
            self.log.append("Please specify both the local root and remote URL.")
            return
        
        self.thread = ImageDownloaderThread(local_root, remote_root)
        self.thread.update_signal.connect(self.log.append)
        self.thread.progress_signal.connect(self.update_progress)
        self.thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(value)
        self.progress_label.setText(f"{value}%")

if __name__ == "__main__":
    app = QApplication([])
    window = ImageDownloaderApp()
    window.show()
    app.exec()
