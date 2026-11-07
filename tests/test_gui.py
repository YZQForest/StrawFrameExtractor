import os, time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from strawframe.ui.main_window import MainWindow
from strawframe.core.ffmpeg_manager import FFmpegManager, run_command


def pump(app, condition, timeout=30):
    end = time.monotonic() + timeout
    while not condition() and time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)
    app.processEvents()
    assert condition()


def test_gui_background_import_and_extraction(tmp_path):
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(tmp_path / "prefs"))
    app = QApplication.instance() or QApplication([])
    manager = FFmpegManager(os.environ.get("STRAW_FFMPEG_DIR", ""))
    source = tmp_path / "中文 测试.mp4"
    run_command(
        [
            manager.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x90:rate=30",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-y",
            str(source),
        ],
        check=True,
    )
    w = MainWindow()
    errors = []
    w.error = errors.append
    w.ffpath.setText(str(__import__("pathlib").Path(manager.ffmpeg).parent))
    w.output.setText(str(tmp_path / "out"))
    w.show()
    w.import_paths([str(source)])
    pump(app, lambda: not w.busy)
    assert len(w.videos) == 1 and w.table.rowCount() == 1
    assert "2 张" in w.estimate.text()
    w.start_run()
    assert w.busy and w.cancel.isEnabled()
    pump(app, lambda: not w.busy)
    assert not errors and w.overall.value() == 100
    assert len(list(__import__("pathlib").Path(w.last_output).glob("images/*.jpg"))) == 2
    assert not w.cancel.isEnabled()
    w.close()
    app.processEvents()
