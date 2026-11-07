from pathlib import Path
import os, shutil, subprocess, sys

CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def run_command(args, **kwargs):
    return subprocess.run(args, creationflags=CREATE_FLAGS, **kwargs)


class FFmpegManager:
    def __init__(self, folder=""):
        suffix = ".exe" if os.name == "nt" else ""
        roots = []
        if folder:
            p = Path(folder).expanduser().resolve()
            roots.append(p.parent if p.is_file() else p)
        else:
            if getattr(sys, "frozen", False):
                roots.extend(
                    [
                        Path(sys.executable).parent / "ffmpeg",
                        Path(getattr(sys, "_MEIPASS", "")) / "ffmpeg",
                    ]
                )
            roots.extend([Path(__file__).resolve().parents[3] / "ffmpeg", Path.cwd() / "ffmpeg"])
        self.ffmpeg = self.ffprobe = ""
        for root in roots:
            a, b = root / ("ffmpeg" + suffix), root / ("ffprobe" + suffix)
            if a.is_file() and b.is_file():
                self.ffmpeg, self.ffprobe = str(a), str(b)
                break
        if not self.ffmpeg and not folder:
            self.ffmpeg = shutil.which("ffmpeg") or ""
            self.ffprobe = shutil.which("ffprobe") or ""
        if not self.ffmpeg or not self.ffprobe:
            raise FileNotFoundError(
                "找不到 FFmpeg/ffprobe。请把两者放入程序的 ffmpeg 文件夹，或选择它们所在文件夹。"
            )
        self.version = run_command(
            [self.ffmpeg, "-version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=True,
        ).stdout.splitlines()[0]
