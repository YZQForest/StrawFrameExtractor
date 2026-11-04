# StrawFrameStudio 验证报告

以下为拆分前的历史抽帧验证记录；拆分后的验证另列于文末。

日期：2026-10-03（Asia/Shanghai）。环境：macOS Apple Silicon、Python 3.14.6、PySide6 6.11.2、Pillow 12.3.0、pytest 9.1.1；FFmpeg / ffprobe 9.0.2（Martin Riedl 静态构建，仅作为本机测试依赖，未附入交付包）。

最终结果：**17 passed in 3.84s**。全部源文件通过 Python compileall。GUI 浅色/深色界面经过离屏截图检查；GUI 后台线程导入及抽帧另外有自动测试。

| 测试 | 结果 |
|---|---|
| 普通 MP4 读取、中文和空格路径 | 通过 |
| 60000/1001 fps 精确比值、59.94005994 小数及 nb_frames | 通过 |
| 默认 2 fps，JPEG / PNG | 通过（2 个用例） |
| 保持原始尺寸、图片数 = CSV 行数、BOM 编码 | 通过 |
| 时间戳严格递增、第二张实际源时间 0.5005 秒 | 通过 |
| 0.5 fps、每 0.5 秒、100 fps 不复制源帧 | 通过（3 个用例） |
| 多视频图片名、全局 frame_id 无冲突 | 通过 |
| 跳过已有图片、不重复元数据、停止策略、不同参数拒绝 | 通过 |
| 用户取消、保留完整图片/元数据、清理临时文件、续跑补齐 | 通过 |
| 文件缺失、视频损坏、FFmpeg 目录无效 | 通过 |
| 短 3840×2160、60000/1001 fps 4K 视频 | 通过 |
| 指定宽度、最大边、自定义尺寸 | 通过（3 个用例） |
| VFR + 非零源起点，所选 PTS 存在于 ffprobe 原始帧列表 | 通过 |
| 90° 显示旋转、输出尺寸、无 EXIF 旋转依赖 | 通过 |
| GUI 后台导入/抽帧、进度结束、控件恢复 | 通过 |

测试用 FFmpeg 自动生成短合成视频，没有使用用户科研视频。时间数据检查覆盖真实 PTS、时间基、非零源起点和 VFR，不仅检查输出序号。

## 复跑

Windows 准备 ffmpeg/ffmpeg.exe 与 ffmpeg/ffprobe.exe 后：

```bat
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

自定义工具目录可设置 `STRAW_FFMPEG_DIR`。GUI 测试使用 Qt offscreen 平台，不弹出测试窗口。

## 实测边界

- 未运行 Windows exe，也未在 Windows 真机验证构建和完整 GUI 交互；build.bat 会在 Windows 重新执行所有测试。
- 4K 仅验证 0.55 秒短片段，未验证 17 分钟长视频吞吐、峰值内存或长时稳定性。
- 权限拒绝、真实磁盘写满、断电和损坏媒体的全部组合未进行系统级故障注入。
- 图片格式和方向已验证；未实际启动 AnyLabeling / SAM。
- PyInstaller 配置已提供，未在本机执行跨系统打包；不能将源码测试成功当作 Windows exe 已验证。

## 2026-11-04 独立仓库 v1.1.0

- Python 3.12.16、Pillow 12.3.0、pytest 9.1.1、FFmpeg/ffprobe 9.0.2。
- 抽帧核心及跨仓库桥接测试：20/20 通过。覆盖源帧 PTS、中文路径、JPG/PNG、取消/续跑、缩放、VFR、显示旋转，以及独立标注启动参数。
- 实际子进程衔接检查通过：自动发现同级 StrawAnnotationStudio，并验证网页、目录清单与指定输出位置。
- Python 语法和 git diff --check 通过。
- 本轮未重跑 Qt GUI 完整交互、Windows 构建或 Windows 真机验收；上方 GUI 测试结果属于历史证据。
