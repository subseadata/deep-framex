#!/usr/bin/env python3
"""
Video Creation Time Setter
--------------------------

PySide6 GUI for extracting a timestamp from video filenames and writing it to
the MP4/MOV creation_time metadata using FFmpeg without re-encoding.

Requirements:
    pip install PySide6

FFmpeg:
    ffmpeg must be installed and available in PATH.

Examples of filename parsing:

Separator mode:
    Dive_20261008T143025_camera01.mp4
    Separator = "_"
    Time group = 2
    Format = "%Y%m%dT%H%M%S"

Range mode:
    20261008_143025_camera01.mp4
    Start = 0
    End = 15
    Format = "%Y%m%d_%H%M%S"

Offset:
    means the parsed timestamp is shifted by the specified days, hours, minutes or seconds

Notes:
- Character positions are zero-based and the end position is exclusive.
- In separator mode, groups are one-based.
- The timestamp written to FFmpeg is an ISO-8601 UTC timestamp.
- For filenames containing local time, use the Offset field to convert it
  to UTC, if appropriate.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import re
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import Qt, QProcess, QThread, QTimer, Signal, QObject
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".m4v",
    ".mkv",
    ".avi",
    ".mts",
    ".m2ts",
    ".ts",
    ".webm",
    ".wmv",
    ".flv",
    ".mpeg",
    ".mpg",
}


class ParseResult:
    def __init__(self, extracted="", converted="", error=""):
        self.extracted = extracted
        self.converted = converted
        self.error = error


def parse_timestamp(
    filename: str,
    mode: str,
    separator: str,
    group_number: int,
    start_char: int,
    end_char: int,
    time_format: str,
    offset: timedelta,
    regex: str,
):
    """
    Parse a timestamp from filename.

    Separator mode:
        filename.split(separator), group_number is 1-based.

    Range mode:
        filename[start_char:end_char], end is exclusive.

    The offset is applied after parsing.
    The resulting datetime is treated as UTC and written as such.
    """
    try:
        match mode:
            case "separator":
                if not separator:
                    return ParseResult(error="Separator cannot be empty.")

                parts = filename.split(separator)

                if group_number < 1 or group_number > len(parts):
                    return ParseResult(
                        error=f"Group {group_number} does not exist "
                            f"(filename has {len(parts)} groups)."
                    )

                extracted = parts[group_number - 1]

            case "range":
                if start_char < 0:
                    return ParseResult(error="Start character cannot be negative.")

                if end_char <= start_char:
                    return ParseResult(error="End character must be greater than start.")

                if start_char >= len(filename):
                    return ParseResult(error="Start character is outside the filename.")

                extracted = filename[start_char:end_char]

            case "regex":
                match = re.search(regex, filename)
                if not match:
                    return ParseResult(error="Regex did not match the filename.")
                extracted = match.group(1)


        if not extracted:
            return ParseResult(error="Extracted timestamp is empty.")

        try:
            parsed = datetime.strptime(extracted, time_format)
        except ValueError as exc:
            return ParseResult(
                extracted=extracted,
                error=f"Invalid timestamp: {exc}"
            )

        # The input is intentionally considered a naive timestamp.
        # The offset lets the user convert it to the desired UTC time.
        parsed += offset

        # creation_time is written as UTC. FFmpeg accepts ISO-8601 with an explicit Z.
        converted = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")

        return ParseResult(extracted=extracted, converted=converted)

    except Exception as exc:
        return ParseResult(error=str(exc))


class SettingsWidget(QWidget):
    settings_changed = Signal()

    def __init__(self):
        super().__init__()

        main_layout = QVBoxLayout(self)

        # Extraction mode
        mode_group = QGroupBox("Timestamp extraction")
        mode_layout = QVBoxLayout(mode_group)

        # Separator controls

        self.separator_radio = QRadioButton("Split filename by separator")
        self.separator_radio.setChecked(True)

        self.separator_widget = QWidget()
        separator_layout = QFormLayout(self.separator_widget)

        self.separator_edit = QLineEdit("_")
        self.separator_edit.setMaxLength(5)

        self.group_spin = QSpinBox()
        self.group_spin.setMinimum(1)
        self.group_spin.setMaximum(999)
        self.group_spin.setValue(2)

        separator_layout.addRow("Separator:", self.separator_edit)
        separator_layout.addRow("Time group:", self.group_spin)

        # Range controls
        self.range_radio = QRadioButton("Use character range")

        
        self.range_widget = QWidget()
        range_layout = QFormLayout(self.range_widget)

        self.start_spin = QSpinBox()
        self.start_spin.setMinimum(0)
        self.start_spin.setMaximum(100000)

        self.end_spin = QSpinBox()
        self.end_spin.setMinimum(1)
        self.end_spin.setMaximum(100000)
        self.end_spin.setValue(15)

        range_layout.addRow("Start character:", self.start_spin)
        range_layout.addRow("End character:", self.end_spin)

        # Regex controls
        self.regex_radio = QRadioButton("Regex (advanced)")

        
        self.regex_widget = QWidget()
        regex_layout = QFormLayout(self.regex_widget)
        self.regex_edit = QLineEdit("")


        regex_layout.addRow("Regex:", self.regex_edit)


        # add layouts
        mode_layout.addWidget(self.separator_radio)
        mode_layout.addWidget(self.separator_widget)
        mode_layout.addWidget(self.range_radio)
        mode_layout.addWidget(self.range_widget)
        mode_layout.addWidget(self.regex_radio)
        mode_layout.addWidget(self.regex_widget)

        main_layout.addWidget(mode_group)

        # Timestamp settings
        time_group = QGroupBox("Timestamp settings")
        time_layout = QFormLayout(time_group)
        time_layout.setRowWrapPolicy(QFormLayout.WrapAllRows)

        self.format_edit = QLineEdit("%Y%m%dT%H%M%S")
        self.format_edit.setToolTip(
            "Python datetime format. Example: %Y%m%dT%H%M%S"
        )

        self.offset_time = QHBoxLayout()

        # offset_spin
        self.offset_day = QSpinBox()
        self.offset_day.setRange(-172800, 172800)
        self.offset_day.setValue(0)
        self.offset_day.setSuffix(" d")
        self.offset_day.setToolTip("Days")

        self.offset_hour = QSpinBox()
        self.offset_hour.setRange(-172800, 172800)
        self.offset_hour.setValue(0)
        self.offset_hour.setSuffix(" h")
        self.offset_hour.setToolTip("Hours")

        self.offset_min = QSpinBox()
        self.offset_min.setRange(-172800, 172800)
        self.offset_min.setValue(0)
        self.offset_min.setSuffix(" m")
        self.offset_min.setToolTip("Minutes")

        self.offset_sec = QSpinBox()
        self.offset_sec.setRange(-172800, 172800)
        self.offset_sec.setValue(0)
        self.offset_sec.setSuffix(" s")
        self.offset_sec.setToolTip("Seconds")

        self.offset_time.addWidget(self.offset_day)
        self.offset_time.addWidget(self.offset_hour)
        self.offset_time.addWidget(self.offset_min)
        self.offset_time.addWidget(self.offset_sec)

        time_layout.addRow("Time format:", self.format_edit)
        time_layout.addRow("\nTime offset:", self.offset_time)

        main_layout.addWidget(time_group)

        # Help
        help_label = QLabel(
            "<b>Format examples:</b><br>"
            "%Y%m%d_%H%M%S → 20261008_143025<br>"
            "%Y-%m-%dT%H%M%S → 2026-10-08T143025<br>"
            "%Y%m%d%H%M%S → 20261008143025<br><br>"
            "<b>Regex examples:</b><br>"
            "_(.*?)- → between underscores and hyphen<br>"
            "_(.*?_.*?)_ → between first and third underscores"
        )
        help_label.setWordWrap(True)
        main_layout.addWidget(help_label)

        main_layout.addStretch()

        # Signals
        self.separator_radio.toggled.connect(self._update_mode)
        self.range_radio.toggled.connect(self._update_mode)
        self.regex_radio.toggled.connect(self._update_mode)

        for widget in (
            self.separator_edit,
            self.group_spin,
            self.start_spin,
            self.end_spin,
            self.format_edit,
            self.regex_edit,
            self.offset_day,
            self.offset_hour,
            self.offset_min,
            self.offset_sec
        ):
            if isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self.settings_changed)
            else:
                widget.textChanged.connect(self.settings_changed)

        self._update_mode()

    def _update_mode(self):
        if self.separator_radio.isChecked():
            self.separator_widget.setEnabled(True)
            self.range_widget.setEnabled(False)
            self.regex_widget.setEnabled(False)
        elif self.range_radio.isChecked():
            self.separator_widget.setEnabled(False)
            self.range_widget.setEnabled(True)
            self.regex_widget.setEnabled(False)
        else: # self.regex_radio.isChecked():
            self.separator_widget.setEnabled(False)
            self.range_widget.setEnabled(False)
            self.regex_widget.setEnabled(True)

        self.settings_changed.emit()

    def get_settings(self):
        offset = timedelta(days=self.offset_day.value(),
                  hours=self.offset_hour.value(),
                  minutes=self.offset_min.value(),
                  seconds=self.offset_sec.value())

        if self.separator_radio.isChecked():
            mode = "separator"
        elif self.range_radio.isChecked():
            mode = "range"
        else:
            mode = "regex"
        
        return {
            "mode": mode,
            "separator": self.separator_edit.text(),
            "group_number": self.group_spin.value(),
            "start_char": self.start_spin.value(),
            "end_char": self.end_spin.value(),
            "time_format": self.format_edit.text(),
            "offset": offset,
            "regex": self.regex_edit.text(),
        }


class FFmpegWorker(QObject):
    progress = Signal(int)
    file_started = Signal(int, str)
    file_finished = Signal(int, str, bool, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, files, timestamps, keep_originals):
        super().__init__()
        self.files = files
        self.timestamps = timestamps
        self.keep_originals = keep_originals
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self.files)

        try:
            for index, source in enumerate(self.files):
                if self._cancelled:
                    break

                timestamp = self.timestamps.get(str(source), "")
                self.file_started.emit(index, source.name)

                if not timestamp:
                    self.file_finished.emit(
                        index,
                        source.name,
                        False,
                        "No valid timestamp."
                    )
                    continue

                ok, message = self.process_file(source, timestamp)

                self.file_finished.emit(
                    index,
                    source.name,
                    ok,
                    message
                )

                self.progress.emit(int(((index + 1) / total) * 100))

        except Exception as exc:
            self.error.emit(str(exc))

        finally:
            self.progress.emit(int(((index + 1) / total) * 100))

        self.finished.emit()

    def process_file(self, source: Path, timestamp: str):
        """
        Create a temporary output beside the original, copy all streams,
        change creation_time, then replace the original if successful.
        """
        ffmpeg = shutil.which("ffmpeg")

        if not ffmpeg:
            return False, "FFmpeg was not found in PATH."

        source = source.resolve()

        # Temporary file must be in the same directory for a safe atomic replace.
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{source.stem}_metadata_",
            suffix=source.suffix,
            dir=str(source.parent),
        )
        os.close(fd)

        temp_path = Path(temp_name)

        try:
            command = [
                ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(source),
                 "-c", "copy",
                "-metadata", f"creation_time={timestamp}",
                str(temp_path),
            ]

            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            if completed.returncode != 0:
                error_text = completed.stderr.strip()
                if not error_text:
                    error_text = "FFmpeg returned an error."
                return False, error_text

            if not temp_path.exists() or temp_path.stat().st_size == 0:
                return False, "FFmpeg produced an empty output file."

            if self.keep_originals:
                backup = source.with_name(
                    source.stem + "_original" + source.suffix
                )

                # Avoid overwriting an existing backup.
                counter = 1
                while backup.exists():
                    backup = source.with_name(
                        f"{source.stem}_original_{counter}{source.suffix}"
                    )
                    counter += 1

                shutil.copy2(source, backup)

            os.replace(temp_path, source)

            return True, "Updated successfully."

        except Exception as exc:
            return False, str(exc)

        finally:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Video Creation Time Setter")
        self.resize(1450, 850)

        self.video_files = []
        self.thread = None
        self.worker = None
        self._valid_count = 0

        # Reused brushes (avoids creating a QColor per cell on every refresh).
        self._brush_error = QBrush(QColor("#b00020"))
        self._brush_ok = QBrush(QColor("#087f23"))
        self._brush_default = QBrush()  # NoBrush -> theme default color

        # Debounce: wait for the user to stop typing/clicking before
        # re-parsing every filename.
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self.refresh_preview)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # Folder selection
        folder_layout = QHBoxLayout()

        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select a folder containing videos...")

        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self.select_folder)

        folder_layout.addWidget(QLabel("Folder:"))
        folder_layout.addWidget(self.folder_edit)
        folder_layout.addWidget(self.browse_button)

        main_layout.addLayout(folder_layout)

        # Main content
        content_layout = QHBoxLayout()

        self.settings = SettingsWidget()
        self.settings.setMaximumWidth(360)
        self.settings.settings_changed.connect(self.schedule_preview)

        content_layout.addWidget(self.settings)

        # Table
        table_layout = QVBoxLayout()

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [
                "File",
                "Extracted timestamp",
                "New creation_time",
                "Status",
            ]
        )

        header = self.table.horizontalHeader()
  
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)

        header.resizeSection(0, 400)
        header.resizeSection(1, 200)
        header.resizeSection(2, 200)
        header.resizeSection(3, 100)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        table_layout.addWidget(self.table)

        content_layout.addLayout(table_layout, 1)

        main_layout.addLayout(content_layout, 1)

        # Bottom controls
        bottom_layout = QHBoxLayout()

        self.keep_originals = QCheckBox(
            "Keep original files as *_original"
        )
        self.keep_originals.setChecked(False)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_files)

        self.run_button = QPushButton("Write Metadata")
        self.run_button.setMinimumHeight(36)
        self.run_button.clicked.connect(self.run_ffmpeg)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_ffmpeg)

        bottom_layout.addWidget(self.keep_originals)
        bottom_layout.addWidget(self.refresh_button)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.cancel_button)
        bottom_layout.addWidget(self.run_button)

        main_layout.addLayout(bottom_layout)

        # Progress
        progress_layout = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)

        self.status_label = QLabel("Select a folder to begin.")

        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress)

        main_layout.addLayout(progress_layout)

        self._update_run_button()

    # ------------------------------------------------------------------
    # Folder / file handling
    # ------------------------------------------------------------------

    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select video folder",
        )

        if folder:
            self.folder_edit.setText(folder)
            self.refresh_files()

    def refresh_files(self):
        folder_text = self.folder_edit.text().strip()

        if not folder_text:
            return

        folder = Path(folder_text)

        if not folder.is_dir():
            QMessageBox.warning(
                self,
                "Invalid folder",
                "The selected folder does not exist.",
            )
            return

        self.video_files = sorted(
            [
                p
                for p in folder.iterdir()
                if p.is_file()
                and p.suffix.lower() in VIDEO_EXTENSIONS
            ],
            key=lambda p: p.name.lower(),
        )

        self.populate_table()
        self.refresh_preview()

        self.status_label.setText(
            f"{len(self.video_files)} video file(s) found."
        )

    def populate_table(self):
        self.table.setUpdatesEnabled(False)

        try:
            self.table.setRowCount(len(self.video_files))

            for row, path in enumerate(self.video_files):
                filename_item = QTableWidgetItem(path.name)
                filename_item.setData(Qt.UserRole, str(path))

                self.table.setItem(row, 0, filename_item)
                self.table.setItem(row, 1, QTableWidgetItem(""))
                self.table.setItem(row, 2, QTableWidgetItem(""))
                self.table.setItem(row, 3, QTableWidgetItem(""))
        finally:
            self.table.setUpdatesEnabled(True)

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def schedule_preview(self):
        """Restart the debounce timer; the real refresh happens on timeout."""
        self._preview_timer.start()

    def _parse_all(self):
        settings = self.settings.get_settings()

        return [
            parse_timestamp(filename=path.stem, **settings)
            for path in self.video_files
        ]

    def refresh_preview(self):
        self._preview_timer.stop()

        if not self.video_files:
            self._valid_count = 0
            self._update_run_button()
            return

        results = self._parse_all()

        table = self.table
        brush_error = self._brush_error
        brush_ok = self._brush_ok
        brush_default = self._brush_default

        valid_count = 0

        # Disable repaints temporarily
        self.table.setUpdatesEnabled(False)

        try:
            for row, result in enumerate(results):
                extracted_item = table.item(row, 1)
                converted_item = table.item(row, 2)
                status_item = table.item(row, 3)

                # QTableWidgetItem.setText/setToolTip ignore unchanged
                # values, so reusing items makes repeated refreshes cheap.
                extracted_item.setText(result.extracted)
                converted_item.setText(result.converted)

                if result.error:
                    status_item.setText(result.error)
                    status_item.setToolTip(result.error)

                    extracted_item.setForeground(brush_error)
                    converted_item.setForeground(brush_error)
                    status_item.setForeground(brush_error)
                else:
                    status_item.setText("Ready")
                    status_item.setToolTip("")

                    extracted_item.setForeground(brush_default)
                    converted_item.setForeground(brush_default)
                    status_item.setForeground(brush_ok)

                    valid_count += 1
        finally:
            self.table.setUpdatesEnabled(True)

        self._valid_count = valid_count

        self.status_label.setText(
            f"{len(self.video_files)} file(s), "
            f"{valid_count} valid timestamp(s)."
        )

        self._update_run_button()

    def get_valid_timestamps(self):
        return {
            str(path): result.converted
            for path, result in zip(self.video_files, self._parse_all())
            if not result.error
        }

    # ------------------------------------------------------------------
    # FFmpeg
    # ------------------------------------------------------------------

    def _update_run_button(self):
        # Uses the count cached by refresh_preview instead of re-parsing
        # every filename.
        self.run_button.setEnabled(
            bool(self.video_files)
            and self._valid_count > 0
            and self.thread is None
        )

    def run_ffmpeg(self):
        if not self.video_files:
            QMessageBox.information(
                self,
                "No files",
                "No video files were found.",
            )
            return

        # Make sure the table reflects the latest settings before running.
        if self._preview_timer.isActive():
            self.refresh_preview()

        if shutil.which("ffmpeg") is None:
            QMessageBox.critical(
                self,
                "FFmpeg not found",
                "FFmpeg was not found in your PATH.\n\n"
                "Install FFmpeg and make sure the ffmpeg executable "
                "can be run from a terminal.",
            )
            return

        timestamps = self.get_valid_timestamps()

        if not timestamps:
            QMessageBox.warning(
                self,
                "No valid timestamps",
                "There are no files with valid timestamps.",
            )
            return

        invalid_count = len(self.video_files) - len(timestamps)

        message = (
            f"This will update {len(timestamps)} video file(s) "
            f"using FFmpeg without re-encoding."
        )

        if invalid_count:
            message += (
                f"\n\n{invalid_count} file(s) with invalid timestamps "
                f"will be skipped."
            )

        if self.keep_originals.isChecked():
            message += (
                "\n\nOriginal files will be duplicated with "
                "'_original' suffix before replacement. "
                "Make sure you have enough disk space."
            )
        else:
            message += (
                "\n\nThe original files will be replaced after successful "
                "FFmpeg processing."
            )

        message += "\n\nProceed?\n\n"

        answer = QMessageBox.question(
            self,
            "Confirm operation",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer != QMessageBox.Yes:
            return

        self.set_ui_running(True)

        self.progress.setValue(0)

        self.thread = QThread()
        self.worker = FFmpegWorker(
            self.video_files,
            timestamps,
            self.keep_originals.isChecked(),
        )

        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

        self.worker.progress.connect(self.progress.setValue)
        self.worker.file_started.connect(self.on_file_started)
        self.worker.file_finished.connect(self.on_file_finished)
        self.worker.error.connect(self.on_worker_error)

        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.on_worker_finished)

        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def cancel_ffmpeg(self):
        if self.worker:
            self.worker.cancel()
            self.status_label.setText("Cancelling...")

    def on_file_started(self, index, filename):
        self.status_label.setText(
            f"Processing {index + 1}/{len(self.video_files)}: {filename}"
        )

        if 0 <= index < self.table.rowCount():
            self.table.item(index, 3).setText("Processing...")
            self.table.item(index, 3).setForeground(
                QColor("#996c00")
            )

    def on_file_finished(self, index, filename, success, message):
        if 0 <= index < self.table.rowCount():
            item = self.table.item(index, 3)

            if success:
                item.setText("Done")
                item.setForeground(QColor("#087f23"))
            else:
                item.setText("Error")
                item.setToolTip(message)
                item.setForeground(QColor("#b00020"))

    def on_worker_error(self, message):
        QMessageBox.critical(
            self,
            "Processing error",
            message,
        )

    def on_worker_finished(self):
        self.status_label.setText("Finished.")
        self.set_ui_running(False)

        QMessageBox.information(
            self,
            "Finished",
            "FFmpeg processing has finished.\n\n"
            "Check the Status column for individual results.",
        )

    def set_ui_running(self, running):
        self.browse_button.setEnabled(not running)
        self.folder_edit.setEnabled(not running)
        self.refresh_button.setEnabled(not running)
        self.settings.setEnabled(not running)
        self.keep_originals.setEnabled(not running)

        self.cancel_button.setEnabled(running)

        self.run_button.setEnabled(False if running else True)

        if not running:
            self.thread = None
            self.worker = None
            self._update_run_button()

    # ------------------------------------------------------------------
    # Close handling
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        if self.worker:
            answer = QMessageBox.question(
                self,
                "Processing in progress",
                "FFmpeg processing is still running. Cancel and exit?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if answer == QMessageBox.Yes:
                self.worker.cancel()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("Video Creation Time Setter")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
