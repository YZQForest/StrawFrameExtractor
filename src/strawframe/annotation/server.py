"""Loopback-only annotation launcher; serves only declared image files."""
from __future__ import annotations

import argparse
import csv
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser

from .bundle import MAX_BYTES, save_bundle


def build_catalog(images: Path | None, catalog: Path | None = None) -> tuple[list[dict], dict[str, Path]]:
    if images is None:
        return [], {}
    images = images.resolve()
    if not images.is_dir():
        raise ValueError("图片目录不存在")
    records = json.loads(catalog.read_text(encoding="utf-8")) if catalog else None
    if isinstance(records, dict):
        records = records["samples"]
    provenance = {}
    csv_path = images.parent / "metadata" / "metadata.csv"
    if not records and csv_path.is_file():
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                provenance[row.get("output_filename", "")] = {
                    key: row.get(key) for key in ("frame_id", "run_id", "video_id", "source_video", "source_pts", "source_time_base", "timestamp_sec", "timestamp_definition")
                }
    if records is None:
        records = []
        for image in sorted(images.rglob("*")):
            if image.suffix.lower() not in (".png", ".jpg", ".jpeg") or not image.is_file():
                continue
            if image.stem.endswith(("_mask", "_valid")):
                continue
            relative = image.relative_to(images).as_posix()
            records.append({"file_name": relative, "sample_id": image.stem + "__" + hashlib.sha256(relative.encode()).hexdigest()[:8],
                            "source": provenance.get(image.name, {"original_file_name": image.name}), "starter": True})
    paths, result = {}, []
    for record in records:
        name = record["file_name"]
        image = (images / name).resolve()
        if not image.is_relative_to(images) or not image.is_file() or image.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            raise ValueError(f"图片不在指定目录中或不存在：{name}")
        sample_id = record["sample_id"]
        if sample_id in paths:
            raise ValueError("图片任务 ID 重复")
        paths[sample_id] = image
        result.append({**record, "url": "/api/images/" + urllib.parse.quote(sample_id, safe="")})
    return result, paths


def create_server(images: Path | None = None, catalog: Path | None = None,
                  output: Path | None = None, app: Path | None = None, port: int = 8765):
    tasks, paths = build_catalog(images, catalog)
    app = app or Path(__file__).parent / "web" / "index.html"
    page = app.read_bytes()
    token = secrets.token_urlsafe(32)
    output = (output or Path.home() / "Documents" / "StrawAnnotations").resolve()
    project_id = hashlib.sha256((str(images.resolve() if images else '')+'|'+str(output)).encode()).hexdigest()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def answer(self, code, payload, kind="application/json; charset=utf-8"):
            body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def local_host(self):
            return self.headers.get("Host") in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}")

        def do_GET(self):
            if not self.local_host():
                self.answer(403, {"error": "仅允许本机访问"})
                return
            route = urllib.parse.urlsplit(self.path).path
            if route in ("/", "/index.html"):
                self.answer(200, app.read_bytes(), "text/html; charset=utf-8")
            elif route == "/api/catalog":
                self.answer(200, {"samples": tasks, "token": token, "output": str(output), "project_id": project_id})
            elif route.startswith("/api/images/"):
                sample_id = urllib.parse.unquote(route[len("/api/images/"):])
                target = paths.get(sample_id)
                if target:
                    self.answer(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or "image/png")
                else:
                    self.answer(404, {"error": "图片未登记"})
            else:
                self.answer(404, {"error": "路径不存在"})

        def do_POST(self):
            if not self.local_host() or self.headers.get("X-Annotation-Token") != token:
                self.answer(403, {"error": "本机保存令牌无效，请刷新页面"})
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BYTES:
                    raise ValueError("导出包大小超出范围")
                data = self.rfile.read(size)
                if len(data) != size:
                    raise ValueError("导出包传输不完整")
                if self.path != "/api/export":
                    self.answer(404, {"error": "路径不存在"})
                    return
                self.answer(200, save_bundle(data, output))
            except Exception as exc:
                self.answer(400, {"error": str(exc)})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.annotation_url = f"http://127.0.0.1:{server.server_port}/"
    return server


def launch(images: Path | None = None, output: Path | None = None):
    target_output = (output or Path.home() / 'Documents' / 'StrawAnnotations').resolve()
    expected_project = hashlib.sha256((str(images.resolve() if images else '')+'|'+str(target_output)).encode()).hexdigest()
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/catalog', timeout=1) as response:
            existing = json.load(response)
        if existing.get('project_id') == expected_project:
            webbrowser.open('http://127.0.0.1:8765/')
            return None
    except Exception:
        pass
    try:
        server = create_server(images=images, output=output)
    except OSError:
        raise ValueError('8765 端口正在运行另一个标注工程。先在浏览器备份，再关闭原标注服务。')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    webbrowser.open(server.annotation_url)
    return server


def main():
    parser = argparse.ArgumentParser(description="秸秆像素标注工具（无需额外依赖）")
    parser.add_argument("--images", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--app", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    try:
        server = create_server(args.images, args.catalog, args.output, args.app, args.port)
    except OSError:
        url = f'http://127.0.0.1:{args.port}/'
        try:
            with urllib.request.urlopen(url+'api/catalog', timeout=2) as response:
                existing = json.load(response)
            expected = str((args.output or Path.home()/'Documents'/'StrawAnnotations').resolve())
            expected_project = hashlib.sha256((str(args.images.resolve() if args.images else '')+'|'+expected).encode()).hexdigest()
            if existing.get('project_id') != expected_project:
                raise ValueError('该端口正在运行另一个标注工程，请先关闭原服务。')
        except (OSError, ValueError) as exc:
            parser.exit(1, f'启动失败：{exc}\n')
        print('标注工具已在运行：'+url, flush=True)
        if not args.no_open:
            webbrowser.open(url)
        return
    print(f"标注工具：{server.annotation_url}\n导出位置：{(args.output or Path.home()/'Documents'/'StrawAnnotations').resolve()}\n保持本窗口打开；退出请按 Ctrl+C。", flush=True)
    if not args.no_open:
        webbrowser.open(server.annotation_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
