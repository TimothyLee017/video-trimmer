import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt
import subprocess

class VideoTrimmerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('视频修剪器')  # Video Trimmer in Chinese
        self.setGeometry(100, 100, 400, 200)

        self.layout = QVBoxLayout()

        self.label = QLabel('选择视频文件:')
        self.layout.addWidget(self.label)

        self.file_input = QLineEdit(self)
        self.layout.addWidget(self.file_input)

        self.browse_button = QPushButton('浏览', self)
        self.browse_button.clicked.connect(self.browse_file)
        self.layout.addWidget(self.browse_button)

        self.start_label = QLabel('开始时间 (秒):')
        self.layout.addWidget(self.start_label)
        self.start_time_input = QLineEdit(self)
        self.layout.addWidget(self.start_time_input)

        self.end_label = QLabel('结束时间 (秒):')
        self.layout.addWidget(self.end_label)
        self.end_time_input = QLineEdit(self)
        self.layout.addWidget(self.end_time_input)

        self.trim_button = QPushButton('修剪视频', self)
        self.trim_button.clicked.connect(self.trim_video)
        self.layout.addWidget(self.trim_button)

        self.setLayout(self.layout)

    def browse_file(self):
        file_name, _ = QFileDialog.getOpenFileName(self, '选择视频文件', '', '视频文件 (*.mp4 *.avi *.mkv)')
        if file_name:
            self.file_input.setText(file_name)

    def trim_video(self):
        input_file = self.file_input.text()
        start_time = self.start_time_input.text()
        end_time = self.end_time_input.text()

        if not input_file:
            QMessageBox.critical(self, '错误', '请提供视频文件路径.')
            return
        if not start_time or not end_time:
            QMessageBox.critical(self, '错误', '请提供开始和结束时间.')
            return

        output_file = 'trimmed_video.mp4'
        command = f'ffmpeg -i "{input_file}" -ss {start_time} -to {end_time} -c copy "{output_file}"'

        try:
            subprocess.run(command, shell=True, check=True)
            QMessageBox.information(self, '完成', '视频已成功修剪.')
        except subprocess.CalledProcessError:
            QMessageBox.critical(self, '错误', '视频修剪失败.')

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VideoTrimmerApp()
    window.show()
    sys.exit(app.exec())