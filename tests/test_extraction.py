import csv, os, shutil
from fractions import Fraction
from pathlib import Path
import pytest
from PIL import Image
from strawframe.core.ffmpeg_manager import FFmpegManager, run_command
from strawframe.core.video_probe import probe
from strawframe.core.models import Settings
from strawframe.core.extractor import Extractor


@pytest.fixture(scope="session")
def manager():
    return FFmpegManager(os.environ.get("STRAW_FFMPEG_DIR", ""))


@pytest.fixture
def video(tmp_path, manager):
    p = tmp_path / "中文 路径" / "测试 视频.mp4"
    p.parent.mkdir()
    make_video(manager, p)
    return p


def make_video(manager, path, size="320x180", duration="2", rate="60000/1001"):
    run_command(
        [
            manager.ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={size}:rate={rate}",
            "-t",
            duration,
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(path),
        ],
        check=True,
        timeout=120,
    )


def rows(result):
    with (Path(result["output"]) / "metadata" / "metadata.csv").open(
        encoding="utf-8-sig", newline=""
    ) as f:
        return list(csv.DictReader(f))


def check_consistency(result):
    data = rows(result)
    files = list((Path(result["output"]) / "images").glob("*"))
    assert len(data) == len(files) == result["successful_frames"]
    assert len({r["frame_id"] for r in data}) == len(data)
    for r in data:
        assert Path(r["output_path"]).is_file()
        with Image.open(r["output_path"]) as im:
            assert im.size == (int(r["output_width"]), int(r["output_height"]))
            im.verify()
    return data


def test_probe_mp4_fraction_unicode_spaces(video, manager):
    v = probe(video, manager)
    assert v.width == 320 and v.height == 180
    assert Fraction(v.fps_ratio) == Fraction(60000, 1001)
    assert abs(v.fps - 59.94005994) < 1e-7 and v.frames == 120


@pytest.mark.parametrize("format", ["jpg", "png"])
def test_2fps_size_metadata_pts(video, manager, tmp_path, format):
    result = Extractor(manager).run(
        [probe(video, manager)], Settings(image_format=format), tmp_path / "结果 输出"
    )
    assert result["status"] == "completed", result
    data = check_consistency(result)
    assert len(data) == 4
    stamps = [Fraction(r["timestamp_sec"]) for r in data]
    assert stamps == sorted(set(stamps))
    assert abs(float(stamps[1]) - 0.5005) < 1e-9
    assert all((r["output_width"], r["output_height"]) == ("320", "180") for r in data)
    assert (
        (Path(result["output"]) / "metadata" / "metadata.csv")
        .read_bytes()
        .startswith(b"\xef\xbb\xbf")
    )


@pytest.mark.parametrize(
    "mode,value,expected", [("fps", "0.5", 1), ("interval", "0.5", 4), ("fps", "100", 120)]
)
def test_fractional_interval_no_duplicated_frames(video, manager, tmp_path, mode, value, expected):
    result = Extractor(manager).run(
        [probe(video, manager)], Settings(mode=mode, value=value), tmp_path / "out"
    )
    assert result["status"] == "completed", result
    assert len(check_consistency(result)) == expected


def test_batch_names(video, manager, tmp_path):
    other = tmp_path / "other.mp4"
    shutil.copyfile(video, other)
    result = Extractor(manager).run(
        [probe(video, manager), probe(other, manager)], Settings(), tmp_path / "out"
    )
    assert result["status"] == "completed", result
    data = check_consistency(result)
    assert len(data) == 8 and len({r["output_filename"] for r in data}) == 8


def test_skip_and_stop(video, manager, tmp_path):
    videos = [probe(video, manager)]
    s = Settings()
    first = Extractor(manager).run(videos, s, tmp_path / "out")
    assert first["status"] == "completed", first
    path = Path(first["output"])
    images = {p.name: p.read_bytes() for p in (path / "images").iterdir()}
    s.policy = "skip"
    again = Extractor(manager).run(videos, s, path)
    assert again["status"] == "completed" and again["new_frames"] == 0
    assert len(check_consistency(again)) == 4
    assert images == {p.name: p.read_bytes() for p in (path / "images").iterdir()}
    s.value = "1"
    with pytest.raises(ValueError):
        Extractor(manager).run(videos, s, path)
    s.policy = "stop"
    with pytest.raises(FileExistsError):
        Extractor(manager).run(videos, s, path)


def test_cancel_preserves_complete_frames(video, manager, tmp_path):
    engine = Extractor(manager)

    def cancel_after_one(d):
        if d["processed"] >= 1:
            engine.cancel()

    result = engine.run([probe(video, manager)], Settings(), tmp_path / "out", cancel_after_one)
    assert result["status"] == "cancelled", result
    assert len(check_consistency(result)) >= 1
    assert not list(Path(result["output"]).glob(".staging*"))
    resumed = Extractor(manager).run(
        [probe(video, manager)], Settings(policy="skip"), result["output"]
    )
    assert resumed["status"] == "completed", resumed
    assert len(check_consistency(resumed)) == 4


def test_skip_removes_stale_staging_from_killed_run(video, manager, tmp_path):
    videos = [probe(video, manager)]
    first = Extractor(manager).run(videos, Settings(), tmp_path / "out")
    path = Path(first["output"])
    stale = path / ".staging_0123456789abcdef"
    stale.mkdir()
    (stale / "half_written.jpg").write_bytes(b"partial")
    again = Extractor(manager).run(videos, Settings(policy="skip"), path)
    assert again["status"] == "completed", again
    assert not list(path.glob(".staging*"))
    assert len(check_consistency(again)) == 4


def test_missing_corrupt_and_ffmpeg(tmp_path, manager):
    with pytest.raises(FileNotFoundError):
        probe(tmp_path / "missing.mp4", manager)
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"not a video")
    with pytest.raises(ValueError):
        probe(bad, manager)
    with pytest.raises(FileNotFoundError):
        FFmpegManager(tmp_path / "nonexistent")


def test_short_4k_5994(manager, tmp_path):
    p = tmp_path / "4k.mp4"
    make_video(manager, p, size="3840x2160", duration="0.55")
    result = Extractor(manager).run([probe(p, manager)], Settings(), tmp_path / "out")
    assert result["status"] == "completed", result
    data = check_consistency(result)
    assert len(data) == 2
    assert all((r["output_width"], r["output_height"]) == ("3840", "2160") for r in data)


@pytest.mark.parametrize(
    "scale,width,height,expected",
    [("width", 160, 100, (160, 90)), ("max", 100, 100, (100, 56)), ("custom", 111, 77, (111, 77))],
)
def test_scale_options(video, manager, tmp_path, scale, width, height, expected):
    result = Extractor(manager).run(
        [probe(video, manager)],
        Settings(image_format="png", scale_mode=scale, width=width, height=height),
        tmp_path / "out",
    )
    assert result["status"] == "completed", result
    assert all(
        (int(r["output_width"]), int(r["output_height"])) == expected
        for r in check_consistency(result)
    )


def test_vfr_actual_pts_and_nonzero_origin(video, manager, tmp_path):
    p = tmp_path / "variable.mkv"
    run_command(
        [
            manager.ffmpeg,
            "-v",
            "error",
            "-i",
            str(video),
            "-vf",
            "select='if(lt(t,1),not(mod(n,3)),not(mod(n,5)))',setpts=PTS+5/TB",
            "-fps_mode",
            "passthrough",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-y",
            str(p),
        ],
        check=True,
    )
    v = probe(p, manager)
    result = Extractor(manager).run([v], Settings(), tmp_path / "out")
    assert result["status"] == "completed", result
    data = check_consistency(result)
    assert float(data[0]["source_timestamp_sec"]) >= 4.9
    raw = run_command(
        [
            manager.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=pts",
            "-of",
            "csv=p=0",
            str(p),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    actual = {
        int(line.split(",")[0])
        for line in raw.splitlines()
        if line.split(",")[0].lstrip("-").isdigit()
    }
    assert all(int(r["source_pts"]) in actual for r in data)
    origin = Fraction(data[0]["source_timestamp_sec"])
    assert all(
        abs(float(Fraction(r["source_timestamp_sec"]) - origin - Fraction(r["timestamp_sec"])))
        < 1e-8
        for r in data
    )
    for i, r in enumerate(data):
        assert i * 0.5 <= float(r["timestamp_sec"]) < (i + 1) * 0.5


def test_rotation_metadata_and_pixels(video, manager, tmp_path):
    p = tmp_path / "rotated.mp4"
    run_command(
        [
            manager.ffmpeg,
            "-v",
            "error",
            "-display_rotation",
            "90",
            "-i",
            str(video),
            "-c",
            "copy",
            "-y",
            str(p),
        ],
        check=True,
    )
    v = probe(p, manager)
    assert abs(v.rotation) == 90
    result = Extractor(manager).run([v], Settings(image_format="png"), tmp_path / "out")
    assert result["status"] == "completed", result
    data = check_consistency(result)
    assert all((r["original_width"], r["original_height"]) == ("320", "180") for r in data)
    assert all((r["output_width"], r["output_height"]) == ("180", "320") for r in data)
    assert all(not Image.open(r["output_path"]).getexif().get(274) for r in data)
