import sys
import json
import subprocess
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                             QScrollArea, QCheckBox, QRadioButton, QButtonGroup,
                             QMessageBox, QGroupBox, QLineEdit, QComboBox, QListWidget)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QPalette, QColor, QDropEvent, QDragEnterEvent, QRegularExpressionValidator

def set_dark_theme(app):
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_color = QColor(45, 45, 45)
    disabled_color = QColor(127, 127, 127)
    dark_palette.setColor(QPalette.ColorRole.Window, dark_color)
    dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Base, QColor(18, 18, 18))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled_color)
    dark_palette.setColor(QPalette.ColorRole.Button, dark_color)
    dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
    dark_palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled_color)
    dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    dark_palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")

class FFmpegWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, cmds, temp_files=None):
        super().__init__()
        if isinstance(cmds[0], str):
            self.cmds = [cmds]
        else:
            self.cmds = cmds
        self.temp_files = temp_files or []

    def run(self):
        try:
            for i, cmd in enumerate(self.cmds):
                self.progress.emit(f"Running step {i+1}/{len(self.cmds)}...")
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                for line in process.stdout:
                    self.progress.emit(line.strip())
                process.wait()
                if process.returncode != 0:
                    self.finished.emit(False, f"Step {i+1} failed with code {process.returncode}")
                    return
            
            # Cleanup temp files
            for f in self.temp_files:
                if os.path.exists(f):
                    try: os.remove(f)
                    except: pass
                    
            self.finished.emit(True, "Process completed successfully.")
        except Exception as e:
            self.finished.emit(False, str(e))

class TrackWidget(QGroupBox):
    extract_requested = pyqtSignal(int, str, str)

    def __init__(self, track_type, index_or_path, codec_name, is_default=False, is_added=False, lang='', title=''):
        header = f"Added {track_type.capitalize()} File: {os.path.basename(str(index_or_path))}" if is_added else f"Existing Stream {index_or_path} ({track_type.capitalize()}) - Codec: {codec_name}"
        super().__init__(header)
        self.setStyleSheet("QGroupBox { font-weight: bold; border: 1px solid #444; border-radius: 5px; margin-top: 1ex; padding: 10px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }")
        self.track_type = track_type
        self.index_or_path = index_or_path
        self.is_added = is_added
        
        main_layout = QVBoxLayout(self)
        
        row1 = QHBoxLayout()
        self.chk_keep = QCheckBox("Keep Track in Output")
        self.chk_keep.setChecked(True)
        row1.addWidget(self.chk_keep)
        
        self.radio_default = None
        if track_type in ['audio', 'subtitle']:
            self.radio_default = QRadioButton("Set as Default (Auto-play)")
            if is_default: self.radio_default.setChecked(True)
            row1.addWidget(self.radio_default)
            self.chk_keep.toggled.connect(lambda checked: self.radio_default.setEnabled(checked))
            
        row1.addStretch()
        
        if not is_added:
            self.btn_extract = QPushButton("Extract This Track Only")
            self.btn_extract.setStyleSheet("background-color: #3a3a3a; padding: 5px;")
            self.btn_extract.clicked.connect(lambda: self.extract_requested.emit(self.index_or_path, self.track_type, codec_name))
            row1.addWidget(self.btn_extract)
            
        main_layout.addLayout(row1)
        
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Track Title:"))
        self.txt_title = QLineEdit(title)
        self.txt_title.setPlaceholderText("e.g. Director's Commentary")
        row2.addWidget(self.txt_title)
        
        row2.addWidget(QLabel("Language Code:"))
        self.txt_lang = QLineEdit(lang)
        self.txt_lang.setPlaceholderText("eng, jpn, spa...")
        self.txt_lang.setMaxLength(3)
        self.txt_lang.setFixedWidth(80)
        row2.addWidget(self.txt_lang)
        
        main_layout.addLayout(row2)

class MediaMuxerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TrackTweak - Lightweight Media Manager")
        self.setGeometry(100, 100, 950, 800)
        self.setAcceptDrops(True)

        self.input_file = None
        self.output_file = None
        self.audio_btn_group = QButtonGroup(self)
        self.subtitle_btn_group = QButtonGroup(self)
        self.track_widgets = []
        self.video_duration_sec = 0

        self.init_ui()
        self.check_ffmpeg()

    def check_ffmpeg(self):
        try:
            subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        except FileNotFoundError:
            QMessageBox.critical(self, "FFmpeg Not Found", "FFmpeg was not found in your system PATH.")
            sys.exit(1)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        hint_label = QLabel("Pro Tip: You can drag & drop Video, Audio, and Subtitle files directly into this window!")
        hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint_label.setStyleSheet("color: #aaa; font-style: italic;")
        main_layout.addWidget(hint_label)

        # 1. Input section
        input_layout = QHBoxLayout()
        self.lbl_input = QLabel("No input video selected")
        self.lbl_input.setStyleSheet("font-weight: bold; color: #2a82da;")
        btn_browse_input = QPushButton("1. Open Video")
        btn_browse_input.clicked.connect(self.browse_input)
        input_layout.addWidget(self.lbl_input)
        input_layout.addWidget(btn_browse_input)
        main_layout.addLayout(input_layout)
        
        # Codecs
        codec_group = QGroupBox("Global Transcoding (Optional)")
        cl = QHBoxLayout(codec_group)
        cl.addWidget(QLabel("Video Codec:"))
        self.combo_vcodec = QComboBox()
        self.combo_vcodec.addItems(["copy (Fastest/No Quality Loss)", "libx264 (H.264)", "libx265 (HEVC)"])
        self.combo_vcodec.setItemData(0, "Fastest / No Quality Loss. Copies the stream exactly as is.", Qt.ItemDataRole.ToolTipRole)
        self.combo_vcodec.setItemData(1, "H.264: Universal compatibility. Plays on almost any device.", Qt.ItemDataRole.ToolTipRole)
        self.combo_vcodec.setItemData(2, "HEVC: Half the file size of H.264 with the same quality. Great for 4K.", Qt.ItemDataRole.ToolTipRole)
        self.combo_vcodec.setToolTip("Select a video codec to re-encode the video, or 'copy' to leave it untouched.")
        cl.addWidget(self.combo_vcodec)
        
        cl.addWidget(QLabel("Audio Codec:"))
        self.combo_acodec = QComboBox()
        self.combo_acodec.addItems(["copy (Fastest/No Quality Loss)", "aac", "mp3", "ac3", "flac"])
        self.combo_acodec.setItemData(0, "Fastest / No Quality Loss. Copies the stream exactly as is.", Qt.ItemDataRole.ToolTipRole)
        self.combo_acodec.setItemData(1, "AAC: The modern standard for video audio. High quality, low file size.", Qt.ItemDataRole.ToolTipRole)
        self.combo_acodec.setItemData(2, "MP3: The classic standard. Maximum compatibility for older devices.", Qt.ItemDataRole.ToolTipRole)
        self.combo_acodec.setItemData(3, "AC3: Dolby Digital. Essential for 5.1 Surround Sound and Smart TVs.", Qt.ItemDataRole.ToolTipRole)
        self.combo_acodec.setItemData(4, "FLAC: 100% Lossless audio. Massive file size, perfect audiophile quality.", Qt.ItemDataRole.ToolTipRole)
        self.combo_acodec.setToolTip("Select an audio codec to re-encode the audio, or 'copy' to leave it untouched.")
        cl.addWidget(self.combo_acodec)
        main_layout.addWidget(codec_group)
        
        # Trim
        trim_group = QGroupBox("Video Trimming")
        tl = QVBoxLayout(trim_group)
        
        # Time Regex Validator: HH:MM:SS or HH:MM:SS.mmm
        time_regex = QRegularExpression(r"^$|^\d{2}:[0-5]\d:[0-5]\d(\.\d{1,3})?$")
        time_validator = QRegularExpressionValidator(time_regex)
        
        mode_layout = QHBoxLayout()
        self.radio_single_trim = QRadioButton("Single Trim")
        self.radio_single_trim.setChecked(True)
        self.radio_multi_trim = QRadioButton("Advanced Multi-Segment Trim")
        mode_layout.addWidget(self.radio_single_trim)
        mode_layout.addWidget(self.radio_multi_trim)
        tl.addLayout(mode_layout)
        
        self.w_single_trim = QWidget()
        sl = QHBoxLayout(self.w_single_trim)
        sl.setContentsMargins(0,0,0,0)
        sl.addWidget(QLabel("Start:"))
        self.txt_start = QLineEdit()
        self.txt_start.setValidator(time_validator)
        self.txt_start.setPlaceholderText("00:01:30")
        sl.addWidget(self.txt_start)
        sl.addWidget(QLabel("End:"))
        self.txt_end = QLineEdit()
        self.txt_end.setValidator(time_validator)
        self.txt_end.setPlaceholderText("00:02:45")
        sl.addWidget(self.txt_end)
        tl.addWidget(self.w_single_trim)
        
        self.w_multi_trim = QWidget()
        ml = QVBoxLayout(self.w_multi_trim)
        ml.setContentsMargins(0,0,0,0)
        input_ml = QHBoxLayout()
        input_ml.addWidget(QLabel("Start:"))
        self.txt_multi_start = QLineEdit()
        self.txt_multi_start.setValidator(time_validator)
        self.txt_multi_start.setPlaceholderText("00:01:30")
        input_ml.addWidget(self.txt_multi_start)
        input_ml.addWidget(QLabel("End:"))
        self.txt_multi_end = QLineEdit()
        self.txt_multi_end.setValidator(time_validator)
        self.txt_multi_end.setPlaceholderText("00:02:45")
        input_ml.addWidget(self.txt_multi_end)
        btn_add_segment = QPushButton("Add Segment")
        btn_add_segment.clicked.connect(self.add_segment)
        input_ml.addWidget(btn_add_segment)
        ml.addLayout(input_ml)
        
        self.list_segments = QListWidget()
        self.list_segments.setFixedHeight(60)
        ml.addWidget(self.list_segments)
        btn_remove_segment = QPushButton("Remove Selected Segment")
        btn_remove_segment.clicked.connect(self.remove_segment)
        ml.addWidget(btn_remove_segment)
        
        tl.addWidget(self.w_multi_trim)
        self.w_multi_trim.setVisible(False)
        
        self.radio_single_trim.toggled.connect(lambda checked: self.w_single_trim.setVisible(checked))
        self.radio_multi_trim.toggled.connect(lambda checked: self.w_multi_trim.setVisible(checked))

        main_layout.addWidget(trim_group)

        # 3. Tracks list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.tracks_layout = QVBoxLayout(self.scroll_content)
        self.tracks_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(scroll_area)

        # 4. Add buttons
        add_layout = QHBoxLayout()
        btn_add_audio = QPushButton("+ Add External Audio Track")
        btn_add_audio.clicked.connect(self.add_audio)
        btn_add_subtitle = QPushButton("+ Add External Subtitle Track")
        btn_add_subtitle.clicked.connect(self.add_subtitle)
        add_layout.addWidget(btn_add_audio)
        add_layout.addWidget(btn_add_subtitle)
        main_layout.addLayout(add_layout)

        # 5. Output and Process
        output_layout = QHBoxLayout()
        self.lbl_output = QLabel("No output file selected")
        btn_browse_output = QPushButton("2. Set Output")
        btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(self.lbl_output)
        output_layout.addWidget(btn_browse_output)
        main_layout.addLayout(output_layout)

        self.btn_process = QPushButton("3. Process Final Video")
        self.btn_process.setMinimumHeight(45)
        self.btn_process.setStyleSheet("font-weight: bold; font-size: 16px; background-color: #2a82da; color: white;")
        self.btn_process.clicked.connect(self.process_video)
        self.btn_process.setEnabled(False)
        main_layout.addWidget(self.btn_process)

        self.lbl_status = QLabel("Ready")
        main_layout.addWidget(self.lbl_status)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.accept()
        else: event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            ext = path.lower().split('.')[-1]
            if ext in ['mp4', 'mkv', 'avi', 'mov', 'webm', 'ts']: self.load_video_from_path(path)
            elif ext in ['mp3', 'aac', 'm4a', 'wav', 'flac', 'ac3']: self.add_audio_from_path(path)
            elif ext in ['srt', 'vtt', 'ass']: self.add_subtitle_from_path(path)

    def browse_input(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Video File", "", "Video Files (*.mp4 *.mkv *.avi *.mov *.ts)")
        if filename: self.load_video_from_path(filename)

    def load_video_from_path(self, path):
        self.input_file = path
        self.lbl_input.setText(self.input_file)
        dir_name = os.path.dirname(path)
        base_name, ext = os.path.splitext(os.path.basename(path))
        self.output_file = os.path.join(dir_name, base_name + "_muxed" + ext)
        self.lbl_output.setText(self.output_file)
        self.load_streams()
        self.check_ready()

    def browse_output(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Select Output File", self.output_file, "Matroska (*.mkv);;MP4 (*.mp4);;All Files (*.*)")
        if filename:
            self.output_file = filename
            self.lbl_output.setText(self.output_file)
            self.check_ready()

    def load_streams(self):
        self.clear_tracks()
        cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", self.input_file]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            data = json.loads(result.stdout)
            
            self.video_duration_sec = float(data.get('format', {}).get('duration', 0))
            
            for stream in data.get('streams', []):
                index = stream.get('index')
                codec_type = stream.get('codec_type')
                codec_name = stream.get('codec_name', 'unknown')
                disposition = stream.get('disposition', {})
                is_default = disposition.get('default', 0) == 1
                
                tags = stream.get('tags', {})
                language = tags.get('language', '')
                title = tags.get('title', '')
                
                tw = TrackWidget(codec_type, index, codec_name, is_default, False, language, title)
                tw.extract_requested.connect(self.extract_track)
                self.add_track_widget(tw)
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read file information: {str(e)}")

    def add_audio(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Audio File", "", "Audio Files (*.mp3 *.aac *.m4a *.wav *.flac)")
        if filename: self.add_audio_from_path(filename)

    def add_audio_from_path(self, path):
        tw = TrackWidget('audio', path, 'auto', False, True)
        self.add_track_widget(tw)
        self.check_ready()

    def add_subtitle(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Select Subtitle File", "", "Subtitle Files (*.srt *.vtt *.ass)")
        if filename: self.add_subtitle_from_path(filename)

    def add_subtitle_from_path(self, path):
        tw = TrackWidget('subtitle', path, 'auto', False, True)
        self.add_track_widget(tw)
        self.check_ready()

    def add_track_widget(self, tw):
        self.tracks_layout.addWidget(tw)
        self.track_widgets.append(tw)
        if tw.track_type == 'audio' and tw.radio_default: self.audio_btn_group.addButton(tw.radio_default)
        elif tw.track_type == 'subtitle' and tw.radio_default: self.subtitle_btn_group.addButton(tw.radio_default)

    def clear_tracks(self):
        for tw in self.track_widgets:
            self.tracks_layout.removeWidget(tw)
            if tw.track_type == 'audio' and tw.radio_default: self.audio_btn_group.removeButton(tw.radio_default)
            elif tw.track_type == 'subtitle' and tw.radio_default: self.subtitle_btn_group.removeButton(tw.radio_default)
            tw.deleteLater()
        self.track_widgets.clear()

    def check_ready(self):
        self.btn_process.setEnabled(bool(self.input_file and self.output_file))
        
    def add_segment(self):
        s = self.txt_multi_start.text().strip()
        e = self.txt_multi_end.text().strip()
        if not s and not e: return
        
        if not self.validate_segment_times(s, e):
            QMessageBox.warning(self, "Invalid Timings", "The start/end times exceed the video duration or are out of order.")
            return
            
        self.list_segments.addItem(f"{s} - {e}")
        self.txt_multi_start.clear()
        self.txt_multi_end.clear()
        
    def remove_segment(self):
        for item in self.list_segments.selectedItems():
            self.list_segments.takeItem(self.list_segments.row(item))

    def extract_track(self, stream_index, track_type, codec_name):
        ext = ".mp3" if track_type == "audio" else ".srt" if track_type == "subtitle" else ".mp4"
        if track_type == "audio" and "aac" in codec_name: ext = ".aac"
        if track_type == "audio" and "flac" in codec_name: ext = ".flac"
        if track_type == "subtitle" and "ass" in codec_name: ext = ".ass"
        
        default_name = f"extracted_stream_{stream_index}{ext}"
        filename, _ = QFileDialog.getSaveFileName(self, "Extract Track As...", default_name, f"Files (*{ext});;All Files (*.*)")
        
        if filename:
            cmd = ["ffmpeg", "-y", "-i", self.input_file, "-map", f"0:{stream_index}", "-c", "copy", filename]
            self.lbl_status.setText(f"Extracting stream {stream_index}...")
            self.worker = FFmpegWorker(cmd)
            self.worker.finished.connect(lambda s, m: QMessageBox.information(self, "Extraction", "Track extracted successfully!" if s else f"Extraction failed: {m}"))
            self.worker.start()

    def build_ffmpeg_cmd(self, start, end, out_path):
        cmd = ["ffmpeg", "-y"]
        if start: cmd.extend(["-ss", start])
        if end: cmd.extend(["-to", end])
        cmd.extend(["-i", self.input_file])

        added_inputs = []
        for tw in self.track_widgets:
            if tw.is_added and tw.chk_keep.isChecked():
                if tw.index_or_path not in added_inputs:
                    added_inputs.append(tw.index_or_path)
                    if start: cmd.extend(["-ss", start])
                    if end: cmd.extend(["-to", end])
                    cmd.extend(["-i", tw.index_or_path])

        out_audio_idx = 0
        out_sub_idx = 0
        out_stream_idx = 0
        
        has_default_audio = any(tw.radio_default and tw.radio_default.isChecked() for tw in self.track_widgets if tw.track_type == 'audio' and tw.chk_keep.isChecked())
        first_audio_seen = False

        for tw in self.track_widgets:
            if not tw.chk_keep.isChecked(): continue
                
            if not tw.is_added:
                cmd.extend(["-map", f"0:{tw.index_or_path}"])
            else:
                input_idx = added_inputs.index(tw.index_or_path) + 1
                cmd.extend(["-map", f"{input_idx}:{tw.track_type[0]}:0"])
                    
            title = tw.txt_title.text().strip()
            lang = tw.txt_lang.text().strip()
            if title: cmd.extend([f"-metadata:s:{out_stream_idx}", f"title={title}"])
            if lang: cmd.extend([f"-metadata:s:{out_stream_idx}", f"language={lang}"])
            
            if tw.track_type == 'audio':
                is_default = False
                if tw.radio_default and tw.radio_default.isChecked():
                    is_default = True
                elif not has_default_audio and not first_audio_seen:
                    is_default = True
                    
                first_audio_seen = True

                if is_default:
                    cmd.extend(["-disposition:a:" + str(out_audio_idx), "default"])
                else:
                    cmd.extend(["-disposition:a:" + str(out_audio_idx), "0"])
                out_audio_idx += 1
            elif tw.track_type == 'subtitle':
                if tw.radio_default and tw.radio_default.isChecked(): cmd.extend(["-disposition:s:" + str(out_sub_idx), "default"])
                else: cmd.extend(["-disposition:s:" + str(out_sub_idx), "0"])
                out_sub_idx += 1
            out_stream_idx += 1

        vcodec = self.combo_vcodec.currentText().split()[0]
        acodec = self.combo_acodec.currentText().split()[0]
        cmd.extend(["-c:v", vcodec, "-c:a", acodec])
        if out_path.lower().endswith(".mp4"): cmd.extend(["-c:s", "mov_text"])
        else: cmd.extend(["-c:s", "copy"])

        cmd.append(out_path)
        return cmd

    def time_str_to_seconds(self, time_str):
        if not time_str: return 0
        parts = time_str.split(':')
        sec = int(parts[0]) * 3600 + int(parts[1]) * 60
        if '.' in parts[2]:
            s, ms = parts[2].split('.')
            sec += int(s) + float('0.' + ms)
        else:
            sec += int(parts[2])
        return sec

    def validate_segment_times(self, start_str, end_str):
        if not self.video_duration_sec: return True # If duration couldn't be parsed, skip validation
        
        s_sec = self.time_str_to_seconds(start_str)
        e_sec = self.time_str_to_seconds(end_str) if end_str else self.video_duration_sec
        
        if s_sec > self.video_duration_sec: return False
        if e_sec > self.video_duration_sec: return False
        if e_sec <= s_sec and end_str: return False
        return True

    def process_video(self):
        if not self.input_file or not self.output_file: return
        
        segments = []
        if self.radio_single_trim.isChecked():
            s = self.txt_start.text().strip()
            e = self.txt_end.text().strip()
            if s or e:
                if not self.validate_segment_times(s, e):
                    QMessageBox.warning(self, "Invalid Timings", "The start/end times exceed the video duration or are out of order.")
                    return
                segments.append((s, e))
        else:
            for i in range(self.list_segments.count()):
                parts = self.list_segments.item(i).text().split(' - ')
                s = parts[0].strip()
                e = parts[1].strip() if len(parts) > 1 else ""
                segments.append((s, e))

        # Auto-increment filename if it exists
        output_path = self.output_file
        base, ext = os.path.splitext(output_path)
        counter = 1
        while os.path.exists(output_path):
            output_path = f"{base} ({counter}){ext}"
            counter += 1
            
        self.output_file = output_path
        self.lbl_output.setText(self.output_file)

        self.btn_process.setEnabled(False)
        self.lbl_status.setText("Processing Mux... Please wait.")

        if len(segments) <= 1:
            start = segments[0][0] if segments else ""
            end = segments[0][1] if segments else ""
            cmd = self.build_ffmpeg_cmd(start, end, self.output_file)
            self.worker = FFmpegWorker([cmd])
        else:
            cmds = []
            temp_files = []
            concat_list_path = os.path.join(os.path.dirname(self.output_file), "concat_list.txt")
            
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for i, (start, end) in enumerate(segments):
                    temp_file = os.path.join(os.path.dirname(self.output_file), f"temp_part_{i}.mkv")
                    temp_files.append(temp_file)
                    cmd = self.build_ffmpeg_cmd(start, end, temp_file)
                    cmds.append(cmd)
                    f.write(f"file '{temp_file.replace(os.sep, '/')}'\n")
            
            temp_files.append(concat_list_path)
            concat_cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list_path, "-c", "copy", self.output_file]
            cmds.append(concat_cmd)
            self.worker = FFmpegWorker(cmds, temp_files)

        self.worker.progress.connect(self.update_status)
        self.worker.finished.connect(self.process_finished)
        self.worker.start()

    def update_status(self, text): 
        # Optional: Print to label
        pass

    def process_finished(self, success, message):
        self.btn_process.setEnabled(True)
        if success:
            self.lbl_status.setText("Done!")
            QMessageBox.information(self, "Success", "Processing completed successfully.")
            try:
                safe_path = os.path.normpath(os.path.abspath(self.output_file))
                subprocess.Popen(f'explorer /select,"{safe_path}"')
            except Exception:
                pass
        else:
            self.lbl_status.setText("Failed.")
            QMessageBox.critical(self, "Error", f"Processing failed:\n{message}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    set_dark_theme(app)
    window = MediaMuxerApp()
    window.show()
    sys.exit(app.exec())
