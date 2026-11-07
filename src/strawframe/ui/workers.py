from PySide6.QtCore import QThread, Signal
from strawframe.core.video_probe import probe


class ProbeWorker(QThread):
    found = Signal(object)
    error = Signal(str)

    def __init__(self, paths, manager, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.manager = manager

    def run(self):
        for path in self.paths:
            if self.isInterruptionRequested():
                break
            try:
                self.found.emit(probe(path, self.manager))
            except Exception as exc:
                self.error.emit(f"{path}: {exc}")


class ExtractWorker(QThread):
    progress = Signal(dict)
    result = Signal(dict)
    error = Signal(str)

    def __init__(self, engine, videos, settings, output, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.videos = videos
        self.settings = settings
        self.output = output

    def run(self):
        try:
            self.result.emit(
                self.engine.run(self.videos, self.settings, self.output, self.progress.emit)
            )
        except Exception as exc:
            self.error.emit(str(exc))
