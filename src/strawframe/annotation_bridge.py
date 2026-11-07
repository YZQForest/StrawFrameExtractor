"""Optional subprocess bridge; annotation stays in its independent repository."""

from pathlib import Path
import shutil
import subprocess
import sys


def annotation_command(images, output, launcher=None):
    if launcher:
        target = Path(launcher).expanduser().resolve()
    else:
        root = (
            Path(sys.executable).resolve().parent
            if getattr(sys, "frozen", False)
            else Path(__file__).resolve().parents[2]
        )
        candidates = [
            root.parent / "StrawAnnotationStudio" / "StrawAnnotationStudio.exe",
            root.parent / "StrawAnnotationStudio" / "StrawAnnotationStudio",
            root.parent / "StrawAnnotationStudio" / "annotate.py",
        ]
        target = next((p for p in candidates if p.is_file()), candidates[-1])
    if not target.is_file():
        raise FileNotFoundError("请安装 StrawAnnotationStudio 并选择其 annotate.py 或可执行程序。")
    if target.suffix.lower() == ".py":
        if getattr(sys, "frozen", False):
            python = shutil.which("py" if sys.platform == "win32" else "python3")
            if not python:
                raise RuntimeError(
                    "运行源码标注需要 Python；也可选择独立的 StrawAnnotationStudio 可执行程序。"
                )
            prefix = [python, "-3"] if sys.platform == "win32" else [python]
        else:
            prefix = [sys.executable]
        command = prefix + [str(target)]
    else:
        command = [str(target)]
    return command + [
        "--images",
        str(Path(images).resolve()),
        "--output",
        str(Path(output).resolve()),
    ]


def launch_annotation(images, output, launcher=None):
    command = annotation_command(images, output, launcher)
    kwargs = {"cwd": str(Path(images).resolve()), "stdin": subprocess.DEVNULL}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
    return subprocess.Popen(command, **kwargs)
