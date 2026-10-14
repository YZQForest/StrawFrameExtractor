# StrawFrameExtractor — 秸秆科研视频抽帧工具

用于农田视频数据集预处理：流式抽取 JPG/PNG，保留实际源帧 PTS、原始编码尺寸、输出尺寸、视频参数、日志和抽帧配置。默认 2 fps、高质量 JPEG、原始尺寸、新任务目录。GUI 简体中文，支持多视频、拖拽、深浅主题、取消、进度和输出估算。

## 人工像素标注（Windows / Mac / 独立浏览器）

新增简洁离线像素标注工作台：批量图片、原尺度画笔/多边形/矩形、缩放平移、撤销重做、自动保存、空白独立复标、跨电脑恢复，以及一键导出原图、材料掩码、有效地面 ROI、训练掩码、覆盖率区间和来源 SHA-256。完成项与草稿隔离。本机入口自动校验并保存完整数据包。

抽帧 GUI 点「像素标注…」，选择输出任务中的 images；Windows 独立运行 `annotate.bat`，Mac 双击 `打开标注工具.command`。独立标注无需安装 PySide6 / FFmpeg，仅 Python 3.12+；也可直接打开 `src/strawframe/annotation/web/index.html`。完整操作和科研格式见 [标注说明](docs/ANNOTATION.md)。

## 快速开始（Windows）

1. 解压整个项目到普通文件夹，支持中文和空格路径。
2. 安装 **64 位 Python 3.12–3.14**，包含 Python Launcher（`py`）和 pip。开发环境已使用 Python 3.14.6；Windows 运行与打包需要在 Windows 上进行。
3. 从 [FFmpeg 官方下载入口](https://ffmpeg.org/download.html) 的 Windows builds 下载 FFmpeg 6 或更新版本。将同一版本的 `ffmpeg.exe`、`ffprobe.exe` 放入项目的 `ffmpeg/`；同时保留该构建附带的许可证说明。
4. 双击 **`run.bat`**。首次运行自动创建 `.venv` 并安装依赖，需要联网。以后直接启动 GUI。
5. 导入视频，选择输出位置，点击「始抽帧」。一般保持默认参数即可。

若已有系统 FFmpeg，可直接使用 PATH；也可在 GUI 手动选择同时包含两个工具的目录。查找顺序：手动路径（指定后必须有效）→ exe 旁 `ffmpeg/` → PyInstaller `_MEIPASS/ffmpeg` → 源码项目 `ffmpeg/` → 当前目录 `ffmpeg/` → PATH。启动抽帧前会重新检查工具。

源码入口是 `src/main.py`。手动运行：

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe src\main.py
```

macOS/Linux 也可使用 `python3 src/main.py`（先安装依赖和本机 FFmpeg）。Windows 构建步骤见 [BUILD.md](BUILD.md)。

## 抽帧规则与科研时间定义

本程序**不使用 fps 滤镜重采样**，也不按输出序号推算时间戳。使用 FFmpeg `select`：以首个解码帧为零点，对源帧时间计算 `floor((t-start_t)*抽帧频率+1e-8)`，每个非空时间区间选第一张源帧。每个源帧最多输出一次，缺失的区间不补帧；若所需频率高于原始频率，输出不会超过实际源帧数。

例如 60000/1001 fps 视频按 2 fps 抽取，第二张实际源帧可能在 **0.500500000 秒**，而不是人为填入 0.500 秒。FFmpeg `-copyts` 保留源时间戳，`showinfo` 提供所选图片的整数 PTS 和滤镜时间基；CSV 使用整数 PTS 与有理数时间基计算，而不解析舍入后的 `pts_time`。

- `timestamp_sec`：相对首个解码源帧的实际时间，保存 9 位小数。
- `source_timestamp_sec`：源 PTS × 源时间基；容器起点可能不是 0。
- `source_pts`、`source_time_base`：可准确重建选取时间。
- 时间间隔通过有理数倒数换算，避免逐次浮点累加漂移。GUI 数值精度为 6 位小数。
- 1e-8 是时间区间边界的浮点容差，写入配置和命令日志。
- `source_frame_index` 留空：未额外扫描所有源帧，避免对 VFR 猜测帧号。`extract_index` 是该视频的输出序号，不能当作源帧号。
- 变帧率、丢帧和尾部时长可能使最终数量与估计不同；数量估计不是强制输出数量。

规则依据：[FFmpeg select / showinfo 文档](https://ffmpeg.org/ffmpeg-filters.html)。

## 输出与重复运行

默认每次创建独立目录，时间后追加随机标识，即使同秒运行也不会碰撞：

```text
project_output/
└── run_20261003_143000_8e123456/
    ├── images/
    │   ├── V01_a1b2c3d4e5f6_t000000000000_f000000001.jpg
    │   └── V01_a1b2c3d4e5f6_t000000000501_f000000002.jpg
    ├── metadata/
    │   └── metadata.csv
    ├── logs/
    │   └── extraction.log
    ├── run_config.json
    └── run_summary.json
```

使用统一 images 目录，便于 AnyLabeling 直接打开。视频编号包含列表序号和源文件路径、大小、修改时间的摘要；图片名包含固定宽度的实际毫秒时间和抽取序号，支持 Windows，跨视频不重名。`frame_id` 加入任务 UUID，实现跨任务唯一性。

三种输出策略：

- **创建新任务目录**：默认，输出根目录下自动创建独立任务。
- **已有内容则停止**：所选目录必须为空。
- **跳过已有帧**：选择已有任务目录，并导入完全相同的视频列表与顺序；参数、文件大小/修改时间、FFmpeg 版本必须相同。重新解码源视频，验证已记录图片并跳过，补齐尚未抽取的图片。不会重复追加元数据；不能用于合并不同参数或不同视频的任务。

不默认覆盖任何科研图片。若任务目录发现孤立图片或缺失图片，停止并提示。请保留原任务，改用新任务目录重做；不要手动篡改 CSV 后续跑。

## metadata.csv 字段

CSV 使用 UTF-8 BOM，可用 Excel 打开。所有正常结束、用户取消、解码错误产生的完整图片都有对应记录；每行写入后刷新到磁盘。

| 字段 | 含义 |
|---|---|
| frame_id / run_id | 全局帧标识 / 任务 UUID |
| source_video / source_video_path | 源文件名 / 原始绝对路径 |
| video_id | 视频序号和源文件摘要 |
| output_filename / output_path | 图片名 / 生成时绝对路径 |
| timestamp_sec / timestamp_hms | 源帧相对首帧时间 / 时分秒毫秒 |
| extract_index | 该视频输出序号，从 1 开始 |
| original_fps / original_fps_ratio | 平均帧率小数 / 原始有理数，VFR 不表示每帧间隔 |
| original_width / original_height | 源视频编码宽高 |
| original_duration_sec | ffprobe 提供的时长 |
| extract_fps | 目标抽帧频率，间隔模式也统一换算 |
| output_format / output_width / output_height | 图片格式和实际输出尺寸 |
| source_frame_index | 预留，当前为空，不推测 |
| video_codec / created_at | 视频编码 / 此行生成时间（带时区） |
| source_pts / source_time_base / source_timestamp_sec | 源整数 PTS / 时间基 / 源绝对媒体时间 |
| timestamp_definition | 相对首个解码帧的时间定义 |

`run_config.json` 保存版本、工具路径和版本、原视频信息、抽帧参数、旋转、时间定义及源文件大小/修改时间。`run_summary.json` 保存完成/取消/失败状态、成功帧数、新增帧数、失败任务数、错误和用时。日志保存实际命令、参数、输入、开始/结束、错误和成功数量。摘要使用路径/大小/修改时间，**不是全文件内容哈希**；严格归档时可另行计算源视频 SHA-256。

移动整个输出目录后，CSV 内绝对路径会保留生成时位置；可用 `output_filename` 相对于 images 重新定位。

## 图片与方向

JPEG 默认 FFmpeg `q=2`，可选 q=1 或 q=5；**JPEG 仍是有损编码**，质量参数不是百分比。需要无损保存解码后的 RGB 像素时选择 PNG。默认不缩放，提供宽度、最大边、自定义宽高设置。

FFmpeg 默认自动根据显示旋转矩阵旋转像素，输出没有依赖 EXIF 的方向。90° 旋转视频会交换宽高，但不降低空间分辨率；CSV 同时保留源编码宽高和实际输出宽高。对普通田间 SDR 视频输出 8-bit RGB PNG / 高质量 JPEG；HDR、10-bit、特殊色彩管理和非方形像素的科研规范不在此版保证范围内，解码到 RGB 并不等于保存原始视频编码数据。

## 取消、异常与数据完整性

视频探测和抽帧均在 QThread 后台运行，GUI 可以继续更新。取消通知后台停止 FFmpeg；使用 image2 原子写入及图片完整性校验，只将完整图片移入 images 并写 CSV，清理未完成的临时文件。关闭运行中的窗口先请求取消，任务结束后可关闭。

磁盘不足、输出无权限、文件损坏、找不到 FFmpeg 等会报错；抽帧过程中遇到异常会保留已提交的图片和 CSV。**断电或强制杀死整个程序不提供跨文件事务保证**，可能存在没有 CSV 的孤立图片；续跑会拒绝这些不一致任务，避免覆盖。不要同时启动多个进程写入同一个已有任务目录；默认新任务目录可隔离独立运行。

## 4K 使用建议

视频流式解码，内存不随整个视频时长增长。解码、滤镜和图片编码线程限制为 2；保持 4K 时仍需要数百 MB 或更多内存，具体取决于编解码器与 FFmpeg。

17 分钟、2 fps 预计约 **2040 张**。4K JPEG 的内容差异很大，PNG 通常明显更大；GUI 估算只作粗略参考。使用本地 SSD 并留足空间，避免把网络盘作为唯一输出位置。CPU 解码是默认路径，本版不依赖显卡或硬件解码。已验证短 3840×2160、60000/1001 fps 视频，未执行真实 17 分钟田间视频全量性能测试。

## AnyLabeling + SAM

用 AnyLabeling 打开任务的 `images/` 文件夹，选择适合的 SAM 辅助标注模型。JPG/PNG 是普通图片，不含特殊科研容器。建议保留 metadata 和 run_config，并将图片与标注 JSON 用相同主文件名关联。本程序不调用 SAM、不自动启动 AnyLabeling，也不生成分割标签。划分训练/验证/测试集时注意按视频或拍摄批次分组，避免相邻帧泄漏。

## 常见问题

- **缺少 FFmpeg**：把同版本两个 exe 放到 ffmpeg 文件夹，或在 GUI 手动选其目录；不能只提供 ffmpeg。
- **Windows 首次启动失败**：确认 64 位 Python 和 `py`、pip 已安装；依赖安装需要网络。终端运行 run.bat 查看错误。
- **总帧数未知**：部分容器未保存 nb_frames；本版不会为了显示总数扫描整段视频。
- **输出不足预计值**：变帧率、源帧缺失、目标 fps 高于源 fps 或取消会影响数量；查看 summary 和日志。
- **旋转后宽高反了**：这是源视频显示方向，90° 自动旋转后交换宽高；未缩放。
- **CSV 打不开或正在被 Excel 占用**：关闭 Excel 文件后再运行；Windows 文件锁可能使写入失败。
- **跳过模式被拒绝**：要求原任务、同输入顺序和同参数；需要变更时创建新任务目录。

## 测试与后续

测试脚本在 `tests/`，可用 `.venv\Scripts\python.exe -m pytest -q` 执行。详见 [TEST_REPORT.md](TEST_REPORT.md)。

Future Work：相似帧去重、模糊检测、CLIP/DINO 聚类、按拍摄批次划分数据集、统计报告、SAM 集成。第一版以实际源帧与可复现抽帧为主。
