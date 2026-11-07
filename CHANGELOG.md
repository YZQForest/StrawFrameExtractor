# 变更记录

## 未发布

- 跳过模式续跑时，自动清理上次被强制结束后残留的 `.staging_*` 临时目录（其中内容从未写入 images 或 CSV），并写入日志；新增对应测试。
- 用 ruff format 统一代码排版（行宽 100，配置见 `ruff.toml`），语法树与排版前完全一致；去掉 5 个未使用的 import。
- 示例输出中的开发机器绝对路径改为相对仓库根目录的路径。
- 新增 GitHub Actions：Windows 上 Python 3.12 / 3.14 安装 FFmpeg 后运行全部测试，并检查代码格式。

## 1.1.0 · 2026-11-04

- 仓库和应用改名为 StrawFrameStudio，保留 StrawFrameExtractor 提交历史。
- 人工标注独立至 https://github.com/YZQForest/StrawAnnotationStudio；本仓库不再携带标注页面和服务。
- GUI 保留跨仓库启动入口，自动发现同级标注项目，也可手动选择启动程序。
- 更新构建文件、产物名称、窗口标题和文档；迁移旧 QSettings 偏好。
- 抽帧算法、源帧 PTS、CSV 字段、跳过/取消机制和已有研究输出保持兼容。
