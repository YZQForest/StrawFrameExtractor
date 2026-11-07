import json
from pathlib import Path
from .ffmpeg_manager import run_command
from .models import VideoInfo


def probe(path, manager):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"文件不存在：{path}")
    result = run_command(
        [
            manager.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
    )
    if result.returncode:
        raise ValueError(f"无法读取视频：{path.name}\n{result.stderr[-1500:]}")
    data = json.loads(result.stdout)
    if not data.get("streams"):
        raise ValueError("文件没有视频流")
    s = data["streams"][0]
    f = data.get("format", {})
    duration = float(s.get("duration", f.get("duration", 0)))
    if duration <= 0:
        raise ValueError("无法可靠读取视频时长，暂不支持此文件")
    rotation = int(float(s.get("tags", {}).get("rotate", 0)))
    for side in s.get("side_data_list", []):
        if "rotation" in side:
            rotation = int(side["rotation"])
    count = s.get("nb_frames")
    return VideoInfo(
        str(path),
        duration,
        int(s["width"]),
        int(s["height"]),
        s.get("avg_frame_rate", "0/1"),
        s.get("codec_name", "unknown"),
        path.stat().st_size,
        int(count) if count and count.isdigit() else None,
        rotation,
        str(s.get("start_time", "0")),
        s.get("time_base", ""),
    )
