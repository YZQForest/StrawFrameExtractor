# Windows 构建说明

当前交付包含完整源码和配置，**不含已经生成的 Windows exe**。开发和验证在 macOS Apple Silicon 上完成。PyInstaller 不跨系统编译，Windows 可执行程序应在 Windows 上生成：[官方说明](https://pyinstaller.org/en/stable/)。

## 一键构建

1. 使用 Windows 10/11 64 位，安装 64 位 Python 3.12–3.14（带 Launcher 和 pip）。
2. 放入 FFmpeg 6+ 同版本构建的 `ffmpeg/ffmpeg.exe` 和 `ffmpeg/ffprobe.exe`，保留许可证。
3. 双击 **build.bat**。脚本安装依赖、执行全部测试、调用 PyInstaller、复制 FFmpeg 和说明书。测试或构建失败立即停止。
4. 成功产物位于：

```text
dist/StrawFrameStudio/
├── StrawFrameStudio.exe
├── _internal/                 # Python、Qt 和其依赖
├── ffmpeg/
│   ├── ffmpeg.exe
│   ├── ffprobe.exe
│   └── 许可证说明…
├── README.md
└── BUILD.md
```

请分发整个 `dist/StrawFrameStudio` 文件夹，不能只复制 exe。用户启动打包版不需要安装 Python。

## 配置

- `StrawFrameStudio.spec`：PyInstaller onedir 配置，关闭控制台窗口，排除不用的 QtWebEngine/QML 模块，不使用 UPX。
- `build.bat`：构建后将 ffmpeg 文件夹置于 exe 旁边。
- 后端同时支持 `_MEIPASS/ffmpeg`，便于将来调整为内置资源模式。
- `requirements.txt`：运行依赖；`requirements-dev.txt`：测试和构建依赖。

当前未在 Windows 真机测试 Qt、Unicode 路径、进程停止行为或产物启动。build.bat 会在你的 Windows 环境重新运行抽帧和 GUI 基本测试；完整 GUI 交互、长时性能以及分发给另一台电脑仍需实际验收。首个 exe 没有代码签名，Windows 可能展示未知发布者提示。

FFmpeg 第三方构建的分发条款取决于构建配置（可能包括 GPL）；本项目不自动下载或附带 FFmpeg 二进制。对外发布前一并保留适用许可、来源和源码获取信息。
