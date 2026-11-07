"""Bounded-memory decoding. Selected frames retain actual source PTS."""

import csv, hashlib, json, logging, re, shutil, subprocess, threading, time, uuid
from collections import deque
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from PIL import Image
from .metadata import MetadataWriter, decimal_time, hms, millis
from .ffmpeg_manager import CREATE_FLAGS
from strawframe import __version__


class Cancelled(Exception):
    pass


class Extractor:
    def __init__(self, manager):
        self.manager = manager
        self.cancel_event = threading.Event()
        self.process = None

    def cancel(self):
        self.cancel_event.set()

    def run(self, videos, settings, output, on_progress=lambda data: None):
        settings.validate()
        if not videos:
            raise ValueError("请先导入视频")
        base = Path(output).expanduser().resolve()
        if settings.policy == "new":
            root = base / f"run_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
        else:
            root = base
        if settings.policy == "stop" and root.exists() and any(root.iterdir()):
            raise FileExistsError("输出目录已有内容，请选空目录或创建新任务目录")
        root.mkdir(parents=True, exist_ok=True)
        inputs = []
        for i, v in enumerate(videos, 1):
            p = Path(v.path)
            stat = p.stat()
            digest = hashlib.sha256(f"{p}|{stat.st_size}|{stat.st_mtime_ns}".encode()).hexdigest()[
                :12
            ]
            inputs.append(
                {
                    "video_id": f"V{i:02d}_{digest}",
                    "video": v.to_dict(),
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                }
            )
        effective = settings.__dict__.copy()
        effective.pop("policy")
        config_path = root / "run_config.json"
        previous = None
        if config_path.exists():
            if settings.policy != "skip":
                raise FileExistsError("已有任务配置")
            previous = json.loads(config_path.read_text(encoding="utf-8"))
            if previous["settings"] != effective or previous["inputs"] != inputs:
                raise ValueError("跳过模式要求输入视频、顺序、文件状态和参数与已有任务完全相同")
        elif any(root.iterdir()):
            raise ValueError("输出目录已有未知文件；请使用空目录或新任务目录")
        for d in ("images", "metadata", "logs"):
            (root / d).mkdir(exist_ok=True)
        run_id = previous["run_id"] if previous else uuid.uuid4().hex
        config = previous or {
            "software_version": __version__,
            "run_id": run_id,
            "created_at": datetime.now().astimezone().isoformat(),
            "settings": effective,
            "extract_fps": str(settings.rate),
            "keep_original_resolution": settings.scale_mode == "original",
            "ffmpeg_path": self.manager.ffmpeg,
            "ffprobe_path": self.manager.ffprobe,
            "ffmpeg_version": self.manager.version,
            "inputs": inputs,
            "timestamp_definition": "timestamp_sec = (selected source PTS - first decoded source PTS) * source_time_base; first actual frame of each floor((t-start_t)*rate+1e-8) bucket; no duplicated frames; auto rotation enabled",
        }
        if previous and previous["ffmpeg_version"] != self.manager.version:
            raise ValueError("跳过模式要求相同 FFmpeg 版本，以确保抽帧可复现")
        if not previous:
            config_path.write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        csvpath = root / "metadata" / "metadata.csv"
        existing = {}
        if csvpath.exists():
            with csvpath.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    name = row["output_filename"]
                    if name in existing:
                        raise ValueError("metadata 中存在重复记录")
                    image = root / "images" / name
                    if not image.is_file():
                        raise ValueError(f"元数据对应图片不存在：{name}")
                    with Image.open(image) as im:
                        im.load()
                    existing[name] = row
        orphans = [
            p.name for p in (root / "images").iterdir() if p.is_file() and p.name not in existing
        ]
        if orphans:
            raise ValueError("发现无元数据的图片，停止以避免覆盖：" + ", ".join(orphans[:3]))
        logger = logging.getLogger("strawframe." + uuid.uuid4().hex)
        logger.setLevel(logging.INFO)
        handler = logging.FileHandler(root / "logs" / "extraction.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.info(
            "START version=%s ffmpeg=%s output=%s config=%s",
            __version__,
            self.manager.version,
            root,
            json.dumps(config, ensure_ascii=False),
        )
        writer = MetadataWriter(csvpath)
        count = len(existing)
        added = 0
        total = settings.estimate(videos)
        started = time.monotonic()
        status = "completed"
        failure = ""
        # A run that was force-killed leaves its staging folder behind. Nothing in it was
        # committed to images/ or the CSV, so it is safe to discard before a new run.
        for stale in root.glob(".staging_*"):
            if stale.is_dir():
                logger.info("REMOVE stale staging %s", stale.name)
                shutil.rmtree(stale, ignore_errors=True)
        staging = root / f".staging_{uuid.uuid4().hex}"
        staging.mkdir()

        def progress(**extra):
            on_progress(
                {
                    "output": str(root),
                    "processed": count,
                    "estimated": total,
                    "elapsed": time.monotonic() - started,
                    **extra,
                }
            )

        try:
            for item in inputs:
                if self.cancel_event.is_set():
                    raise Cancelled()
                v = next(v for v in videos if v.path == item["video"]["path"])
                vid = item["video_id"]
                pending = deque()
                origin = None
                timebase = None
                rate = settings.rate
                select = f"select='isnan(prev_selected_t)+gt(floor((t-start_t)*({rate.numerator}/{rate.denominator})+0.00000001),floor((prev_selected_t-start_t)*({rate.numerator}/{rate.denominator})+0.00000001))'"
                filters = [select]
                if settings.scale_filter():
                    filters.append(settings.scale_filter())
                filters.append("showinfo=checksum=0")
                args = [
                    self.manager.ffmpeg,
                    "-hide_banner",
                    "-nostdin",
                    "-loglevel",
                    "info",
                    "-copyts",
                    "-threads",
                    "2",
                    "-filter_threads",
                    "2",
                    "-i",
                    v.path,
                    "-map",
                    "0:v:0",
                    "-an",
                    "-sn",
                    "-dn",
                    "-vf",
                    ",".join(filters),
                    "-fps_mode",
                    "passthrough",
                    "-threads",
                    "2",
                ]
                if settings.image_format == "jpg":
                    args += [
                        "-c:v",
                        "mjpeg",
                        "-q:v",
                        str(settings.jpeg_quality),
                        "-pix_fmt",
                        "yuvj444p",
                    ]
                else:
                    args += ["-c:v", "png", "-pix_fmt", "rgb24"]
                pattern = str(staging / f"{vid}_%09d.{settings.image_format}")
                args += ["-f", "image2", "-atomic_writing", "1", "-n", pattern]
                logger.info("INPUT %s COMMAND %s", v.path, json.dumps(args, ensure_ascii=False))
                progress(current=Path(v.path).name, file_percent=0, status="正在解码")
                self.process = subprocess.Popen(
                    args,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=CREATE_FLAGS,
                )
                proc = self.process

                def watch():
                    while proc.poll() is None:
                        if self.cancel_event.wait(0.1):
                            try:
                                proc.terminate()
                                proc.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                proc.kill()
                            except OSError:
                                pass
                            return

                watcher = threading.Thread(target=watch, daemon=True)
                watcher.start()
                tail = deque(maxlen=35)

                def commit():
                    nonlocal count, added
                    while pending:
                        n, pts, w, h = pending[0]
                        temp = staging / f"{vid}_{n + 1:09d}.{settings.image_format}"
                        if not temp.exists():
                            break
                        # image2 atomic_writing renames only after a complete image is written.
                        with Image.open(temp) as im:
                            im.load()
                        stamp = (pts - origin) * timebase
                        name = f"{vid}_t{millis(stamp):012d}_f{n + 1:09d}.{settings.image_format}"
                        dest = root / "images" / name
                        if name in existing:
                            if existing[name]["source_pts"] != str(pts):
                                raise ValueError("已有图片与当前源帧 PTS 不一致")
                            temp.unlink()
                        else:
                            if dest.exists():
                                raise FileExistsError(f"拒绝覆盖：{dest}")
                            if shutil.disk_usage(root).free < temp.stat().st_size + 1024 * 1024:
                                raise OSError("剩余磁盘空间不足，已安全停止")
                            temp.rename(dest)
                            row = {
                                "frame_id": f"{run_id}:{vid}:{n + 1:09d}",
                                "source_video": Path(v.path).name,
                                "source_video_path": v.path,
                                "video_id": vid,
                                "output_filename": name,
                                "output_path": str(dest),
                                "timestamp_sec": decimal_time(stamp),
                                "timestamp_hms": hms(stamp),
                                "extract_index": n + 1,
                                "original_fps": f"{v.fps:.9f}",
                                "original_fps_ratio": v.fps_ratio,
                                "original_width": v.width,
                                "original_height": v.height,
                                "original_duration_sec": v.duration,
                                "extract_fps": decimal_time(rate),
                                "output_format": settings.image_format,
                                "output_width": w,
                                "output_height": h,
                                "source_frame_index": "",
                                "video_codec": v.codec,
                                "created_at": datetime.now().astimezone().isoformat(),
                                "source_pts": pts,
                                "source_time_base": str(timebase),
                                "source_timestamp_sec": decimal_time(pts * timebase),
                                "timestamp_definition": "relative_to_first_decoded_frame",
                                "run_id": run_id,
                            }
                            try:
                                writer.write(row)
                            except Exception:
                                dest.unlink(missing_ok=True)
                                raise
                            existing[name] = row
                            count += 1
                            added += 1
                        pending.popleft()
                        progress(
                            current=Path(v.path).name,
                            file_percent=min(100, float(stamp) / v.duration * 100),
                            status="正在抽帧",
                        )

                try:
                    for line in proc.stderr:
                        if "showinfo" in line:
                            tb = re.search(r"config in time_base:\s*(\d+/\d+)", line)
                            if tb:
                                timebase = Fraction(tb.group(1))
                            match = re.search(
                                r"\bn:\s*(\d+)\s+pts:\s*(-?\d+).*?\bs:(\d+)x(\d+)", line
                            )
                            if match:
                                n, pts, w, h = map(int, match.groups())
                                if timebase is None:
                                    raise ValueError("FFmpeg 未提供滤镜时间基")
                                if origin is None:
                                    origin = pts
                                pending.append((n, pts, w, h))
                        else:
                            tail.append(line.strip())
                            if "error" in line.lower() or "failed" in line.lower():
                                logger.warning(line.strip())
                        commit()
                    code = proc.wait()
                    watcher.join(timeout=6)
                    commit()
                    if self.cancel_event.is_set():
                        raise Cancelled()
                    if code:
                        raise RuntimeError(f"FFmpeg 退出码 {code}: " + "\n".join(tail))
                    if pending:
                        raise RuntimeError("部分源帧没有成功写入图片")
                    progress(current=Path(v.path).name, file_percent=100, status="视频完成")
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                            proc.wait()
                    proc.stderr.close()
                    self.process = None
            progress(current="全部完成", file_percent=100, status="完成")
        except Cancelled:
            status = "cancelled"
            logger.info("CANCELLED")
        except Exception as exc:
            status = "failed"
            failure = str(exc)
            logger.exception("FAILED")
        finally:
            writer.close()
            shutil.rmtree(staging, ignore_errors=True)
            summary = {
                "status": status,
                "successful_frames": count,
                "new_frames": added,
                "failed_tasks": int(status == "failed"),
                "error": failure,
                "ended_at": datetime.now().astimezone().isoformat(),
                "elapsed_sec": time.monotonic() - started,
            }
            (root / "run_summary.json").write_text(
                json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            logger.info("END %s", json.dumps(summary, ensure_ascii=False))
            handler.close()
            logger.removeHandler(handler)
        return {"output": str(root), **summary}
