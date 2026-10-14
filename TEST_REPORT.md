# 验证报告

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


## 2026-10-15 人工像素标注 v2

- Python 标准库包校验与本机保存测试：9/9通过，包括覆盖率区间、训练映射、草稿隔离、完成门、SHA损坏、路径越界、独立导出不覆盖及本机令牌。
- Chrome 实际浏览器端到端流程：11项通过，未产生 JavaScript pageerror。覆盖目录载入、画笔/矩形/多边形、撤销重做、材料争议与ROI分离、未标完成门、真正PNG导出独立解码、原图字节不变、服务端校验、刷新恢复、ZIP恢复与空白独立复标。
- 测试只用合成图片，测试输出与科研人工标签分开。标注者声明完成不等于人工正确性认证。
- Mac副本与仓库HTML/服务/校验模块逐文件SHA一致；Python语法与git diff空白检查通过。
- Windows GUI增加标注入口，PyInstaller包含HTML；本次未在Windows运行或生成exe。原抽帧功能没有改动。
