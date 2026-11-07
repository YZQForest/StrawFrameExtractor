from dataclasses import dataclass, asdict
from fractions import Fraction
import math


@dataclass
class VideoInfo:
    path: str
    duration: float
    width: int
    height: int
    fps_ratio: str
    codec: str
    size: int
    frames: int | None = None
    rotation: int = 0
    start_time: str = "0"
    time_base: str = ""

    @property
    def fps(self):
        try:
            return float(Fraction(self.fps_ratio))
        except (ValueError, ZeroDivisionError):
            return 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class Settings:
    mode: str = "fps"
    value: str = "2"
    image_format: str = "jpg"
    jpeg_quality: int = 2
    scale_mode: str = "original"
    width: int = 1920
    height: int = 1080
    policy: str = "new"

    @property
    def rate(self):
        value = Fraction(self.value)
        if value <= 0:
            raise ValueError("频率或时间间隔必须大于零")
        rate = value if self.mode == "fps" else 1 / value
        if rate > 240:
            raise ValueError("抽帧频率不能超过 240 fps")
        return rate

    def validate(self):
        self.rate
        if self.mode not in ("fps", "interval"):
            raise ValueError("未知抽帧方式")
        if self.image_format not in ("jpg", "png"):
            raise ValueError("未知图片格式")
        if not 1 <= self.jpeg_quality <= 31:
            raise ValueError("JPEG q 值应为 1–31")
        if self.scale_mode not in ("original", "width", "max", "custom"):
            raise ValueError("未知缩放方式")
        if min(self.width, self.height) < 1:
            raise ValueError("尺寸必须为正数")
        if self.policy not in ("new", "stop", "skip"):
            raise ValueError("未知输出策略")

    def estimate(self, videos):
        count = 0
        for v in videos:
            target = math.ceil(v.duration * float(self.rate))
            capacity = (
                v.frames
                if v.frames is not None
                else (math.ceil(v.duration * v.fps) if v.fps > 0 else target)
            )
            count += min(target, capacity)
        return count

    def dimensions(self, v):
        w, h = (v.height, v.width) if abs(v.rotation) % 180 == 90 else (v.width, v.height)
        if self.scale_mode == "width":
            return self.width, max(1, round(h * self.width / w))
        if self.scale_mode == "max":
            factor = min(1, self.width / max(w, h))
            return max(1, round(w * factor)), max(1, round(h * factor))
        if self.scale_mode == "custom":
            return self.width, self.height
        return w, h

    def scale_filter(self):
        if self.scale_mode == "width":
            return f"scale={self.width}:-1"
        if self.scale_mode == "max":
            return f"scale=w='round(iw*min(1,{self.width}/max(iw,ih)))':h='round(ih*min(1,{self.width}/max(iw,ih)))'"
        if self.scale_mode == "custom":
            return f"scale={self.width}:{self.height}"
        return ""
