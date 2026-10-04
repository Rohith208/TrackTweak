# TrackTweak

TrackTweak is a fast, lightweight, Python-based GUI application for managing video, audio, and subtitle streams without the need for complex command-line interfaces. Built on top of FFmpeg, it specializes in lightning-fast, lossless stream copying.

## ✨ Features

* **Lossless Muxing/Demuxing**: Add or remove audio and subtitle tracks instantly without re-encoding the video (`-c copy`).
* **Drag and Drop Support**: Simply drag your `.mkv`, `.mp4`, `.srt`, or `.mp3` files directly into the window.
* **Fast Video Trimming**: 
  * **Single Trim**: Cut the beginning or end off a video instantly.
  * **Advanced Multi-Segment Trim**: Cut out multiple parts of a video (e.g., removing commercial breaks) and intelligently merge the remaining parts together while preserving all metadata.
* **Track Extraction**: One-click extraction of any existing audio or subtitle track to its own standalone file (e.g., rip an `.mp3` or `.srt` directly from a movie).
* **Metadata & Defaults**: Easily edit track titles and language codes, and set which audio or subtitle track plays by default. 
* **Smart Audio Fallback**: If no default audio track is selected, the app automatically selects the first available audio track as the default so you never get a silent video.
* **Global Transcoding**: If you *do* want to compress or convert, it supports on-the-fly re-encoding to popular formats like H.264, HEVC, AAC, MP3, and AC3 (Dolby Digital).
* **Smart Auto-Increment**: Never accidentally overwrite your files. The app automatically appends `(1)`, `(2)`, etc. to filenames just like Windows File Explorer.

## 🚀 Prerequisites

1. **Python 3.x**: Ensure Python is installed on your system.
2. **FFmpeg**: This application relies heavily on `ffmpeg` and `ffprobe`. You must have FFmpeg installed and added to your system's `PATH`.
   - On Windows, you can install it quickly using PowerShell: 
     ```powershell
     winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
     ```
   - Or download it manually from [ffmpeg.org](https://ffmpeg.org/download.html).

## 💻 Installation

1. Navigate to the project directory.
2. Create and activate a virtual environment (recommended):
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install the required dependencies:
   ```powershell
   pip install PyQt6
   ```

## 🎮 How to Use

1. **Launch**: Run `python main.py` to open the application.
2. **Open Video**: Drag and drop a video file into the app, or click "Open Video".
3. **Manage Tracks**: 
   * Uncheck "Keep Track in Output" to completely delete a track.
   * Check "Set as Default" on an audio or subtitle track to force media players to play it automatically.
   * Edit the "Track Title" and "Language Code" text boxes.
4. **Add External Tracks**: Drag in `.srt` or `.mp3` files, or use the "+ Add External" buttons.
5. **Trim (Optional)**: Use the Video Trimming section to cut the video. Enter timestamps strictly in `HH:MM:SS` or `HH:MM:SS.mmm` format (e.g., `00:01:30`). The app has strict duration validation to prevent errors.
6. **Process**: Click **Process Final Video**. Once finished, Windows File Explorer will automatically pop open and highlight your newly created file!

<img width="766" height="814" alt="image" src="https://github.com/user-attachments/assets/00b5ff73-7deb-4194-89b8-52fdfb121299" />

