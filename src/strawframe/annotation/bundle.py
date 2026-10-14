"""Validate annotation packages without third-party dependencies.

This verifies format, provenance hashes, and arithmetic, never human correctness.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import uuid
import zipfile
import zlib

SCHEMA = "straw-annotation/2"
MAX_BYTES = 2 * 1024**3


def gray_png(data: bytes) -> tuple[int, int, bytes]:
    """Decode the lossless 8-bit grayscale masks emitted by the annotation UI."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Mask must be PNG")
    offset, compressed, width, height = 8, bytearray(), 0, 0
    ended = False
    while offset + 12 <= len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        tag = data[offset + 4:offset + 8]
        body = data[offset + 8:offset + 8 + size]
        if offset + size + 12 > len(data):
            raise ValueError("Truncated PNG")
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        if zlib.crc32(tag + body) & 0xFFFFFFFF != crc:
            raise ValueError("PNG checksum mismatch")
        if tag == b"IHDR":
            width, height, depth, color, compression, filtering, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or color != 0 or compression or filtering or interlace:
                raise ValueError("Mask must be non-interlaced 8-bit grayscale PNG")
            if not (0 < width * height <= 40_000_000):
                raise ValueError("Unsupported mask size")
        elif tag == b"IDAT":
            compressed.extend(body)
        elif tag == b"IEND":
            ended = True
            break
        offset += size + 12
    if not width or not ended:
        raise ValueError("Incomplete PNG")
    expected = (width + 1) * height
    decoder = zlib.decompressobj()
    raw = decoder.decompress(bytes(compressed), expected + 1)
    if len(raw) != expected or not decoder.eof or decoder.unused_data:
        raise ValueError("PNG pixel length mismatch")
    pixels = bytearray(width * height)
    prior = bytearray(width)
    for y in range(height):
        kind = raw[y * (width + 1)]
        row = bytearray(raw[y * (width + 1) + 1:(y + 1) * (width + 1)])
        if kind > 4:
            raise ValueError("Unknown PNG filter")
        for x in range(width):
            left = row[x - 1] if x else 0
            up = prior[x]
            corner = prior[x - 1] if x else 0
            if kind == 1:
                row[x] = (row[x] + left) & 255
            elif kind == 2:
                row[x] = (row[x] + up) & 255
            elif kind == 3:
                row[x] = (row[x] + (left + up) // 2) & 255
            elif kind == 4:
                p = left + up - corner
                distances = (abs(p - left), abs(p - up), abs(p - corner))
                predictor = (left, up, corner)[distances.index(min(distances))]
                row[x] = (row[x] + predictor) & 255
        pixels[y * width:(y + 1) * width] = row
        prior = row
    return width, height, bytes(pixels)


def image_dimensions(data: bytes) -> tuple[int, int]:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack_from(">II", data, 16)
    if data[:2] != b"\xff\xd8":
        raise ValueError("Source image must be PNG or JPEG")
    pos = 2
    while pos < len(data):
        if data[pos] != 255:
            raise ValueError("Malformed JPEG header")
        while pos < len(data) and data[pos] == 255:
            pos += 1
        marker = data[pos]
        pos += 1
        if marker in (0xD8, 0xD9, 0x01) or 0xD0 <= marker <= 0xD7:
            continue
        if pos + 2 > len(data):
            break
        length = struct.unpack_from(">H", data, pos)[0]
        if length < 2 or pos + length > len(data):
            break
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack_from(">HH", data, pos + 3)
            return w, h
        pos += length
    raise ValueError("JPEG dimensions unavailable")


def validate_bundle(data: bytes | Path) -> tuple[dict, dict[str, bytes]]:
    archive = zipfile.ZipFile(io.BytesIO(data) if isinstance(data, bytes) else data)
    with archive:
        infos = archive.infolist()
        if len(infos) > 20_000 or sum(i.file_size for i in infos) > MAX_BYTES:
            raise ValueError("Package is too large")
        files = {}
        for info in infos:
            path = PurePosixPath(info.filename)
            if (info.is_dir() or path.is_absolute() or ".." in path.parts
                    or "\\" in info.filename or ":" in info.filename
                    or str(path) != info.filename or info.filename in files):
                raise ValueError("Unsafe or duplicate archive path")
            files[info.filename] = archive.read(info)
    manifest = json.loads(files.get("manifest.json", b"{}"))
    if manifest.get("schema_version") != SCHEMA:
        raise ValueError("Not a Straw Annotation v2 research package")
    hashes = manifest.get("file_sha256", {})
    if set(hashes) != set(files) - {"manifest.json"}:
        raise ValueError("Every package file must have a declared SHA-256")
    for name, sha in hashes.items():
        if hashlib.sha256(files[name]).hexdigest() != sha:
            raise ValueError(f"File hash mismatch: {name}")
    session = manifest.get("session", {})
    if not session.get("annotator", "").strip() or session.get("role") not in ("primary", "independent_repeat", "adjudication"):
        raise ValueError("Annotator name and annotation role are required")
    records = manifest.get("records", [])
    if not records:
        raise ValueError("Empty annotation package")
    seen, completed, drafts = set(), 0, 0
    for record in records:
        sample = record["sample_id"]
        if not sample or sample in seen:
            raise ValueError("Duplicate sample ID")
        seen.add(sample)
        if (record.get('annotator') != session['annotator']
                or record.get('annotation_role') != session['role']
                or record.get('session_id') != session.get('id')):
            raise ValueError('Per-image annotator/session does not match the package')
        meta = json.loads(files[record["metadata_path"]])
        if meta != record:
            raise ValueError("Per-image metadata disagrees with manifest")
        dimensions = (record["width"], record["height"])
        image = files[record["image_path"]]
        if hashlib.sha256(image).hexdigest() != record["image_sha256"]:
            raise ValueError("Source image hash mismatch")
        if image_dimensions(image) != dimensions:
            raise ValueError("Source image size/orientation mismatch")
        planes = []
        for key in ("mask_path", "valid_roi_path", "training_mask_path"):
            w, h, plane = gray_png(files[record[key]])
            if (w, h) != dimensions:
                raise ValueError("Image and masks must have identical dimensions")
            planes.append(plane)
        labels, valid, training = planes
        if not set(labels) <= {0, 64, 128, 255} or not set(valid) <= {0, 255} or not set(training) <= {0, 1, 255}:
            raise ValueError("Unexpected class encoding")
        n = s = u = unmarked = 0
        for label, roi, target in zip(labels, valid, training):
            expected = 255 if not roi or label in (64, 128) else int(label == 255)
            if target != expected:
                raise ValueError("Training mask mapping mismatch")
            if roi:
                n += 1
                s += label == 255
                u += label == 128
                unmarked += label == 64
        stats = record["statistics"]
        for key, value in {"valid_pixels": n, "straw_pixels": s, "uncertain_pixels": u,
                           "unmarked_pixels": unmarked, "excluded_pixels": len(labels) - n}.items():
            if stats.get(key) != value:
                raise ValueError(f"Incorrect pixel count: {key}")
        for key, value in {
            "coverage_lower_pp": 100 * s / n if n else None,
            "coverage_upper_pp": 100 * (s + u + unmarked) / n if n else None,
            "coverage_pp": 100 * s / n if n and not u and not unmarked else None,
        }.items():
            actual = stats.get(key)
            if (value is None and actual is not None) or (value is not None and (actual is None or abs(actual - value) > 1e-6)):
                raise ValueError(f"Incorrect coverage statistic: {key}")
        if record["status"] == "completed":
            if unmarked or not n or not all(record.get("inspection", {}).get(k) is True for k in ("ground_roi_checked", "full_image_checked", "human_annotation_confirmed")):
                raise ValueError("Completed annotation lacks inspection or contains unmarked ground")
            if not record["mask_path"].startswith("human_masks/"):
                raise ValueError("Completed mask must be in human_masks")
            completed += 1
        elif record["status"] == "draft":
            if not record["mask_path"].startswith("drafts/"):
                raise ValueError("Draft must be isolated from human_masks")
            drafts += 1
        else:
            raise ValueError("Unknown completion status")
    report = {"schema_version": SCHEMA, "records": len(records), "completed": completed,
              "drafts": drafts, "all_format_checks_pass": True, "human_correctness_verified": False}
    return report, files


def save_bundle(data: bytes, output: Path) -> dict:
    report, files = validate_bundle(data)
    output.mkdir(parents=True, exist_ok=True)
    stem = "annotations_" + uuid.uuid4().hex[:12]
    folder = output / stem
    folder.mkdir()
    for name, content in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    (folder / "format_validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    package = output / (stem + ".zip")
    package.write_bytes(data)
    return {**report, "folder": str(folder.resolve()), "package": str(package.resolve())}
