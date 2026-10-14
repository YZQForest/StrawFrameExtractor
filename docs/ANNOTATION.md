# 人工像素标注工作台 v2.1（简洁界面）

工具在浏览器中描绘材料，在本机保存和校验完整研究数据包。页面无 CDN、外部 JS 包和模型依赖；标注服务只用 Python 标准库。

主界面只有图片列表、画布和常用标注操作。标注者填一次；复标、工程切换、备注、文件导入和完整统计放在「更多」。完成检查一次明确勾选，导出仍分别记录 ground_roi_checked、full_image_checked、human_annotation_confirmed 三项声明及 combined_checklist 来源。原 v2.0 缓存和研究包可以直接恢复，数据编码与导出目录不变。

## 使用入口

- Windows 抽帧 GUI：点「像素标注…」，选择抽帧任务的 `images` 目录。保持软件打开；工作台自动读取同任务 `metadata/metadata.csv` 的帧来源。
- Windows 独立使用：安装 Python 3.12 或更新版本后双击 `annotate.bat`，无需 PySide6 或 FFmpeg。
- Mac：双击 `打开标注工具.command`；首次下载后如无执行权限，执行 `chmod +x 打开标注工具.command`。也可用 `python3 annotate.py`。
- 无 Python：用现代 Chrome / Safari 打开 `src/strawframe/annotation/web/index.html`，导入 PNG/JPEG，导出 ZIP。
- 预载目录：`python3 annotate.py --images "图片目录" --output "标注结果目录"`。

默认仅监听 `127.0.0.1:8765`，保持启动窗口打开。固定端口便于恢复浏览器缓存；切换工程请先备份，再关闭原服务。

## 最短操作流程

1. 填写真实姓名或稳定代号，选择初标、独立复标或裁决。首次编辑后身份锁定，换人需新建工程。
2. 选择图片；蓝色表示未标。一般先「先铺背景」，再描绘绿色秸秆、橙色材料争议和灰色遮挡。
3. 绿色包括可辨认的可见玉米残留：枯叶、茎秆、碎片和地表残留根茎。背景为土壤、石块、活体杂草。不要凭亮度填充，不要填掉秸秆间的土壤孔隙，不推断埋藏材料。
4. 橙色是地面材料不确定，保留在地面分母中；灰色只用于非地面、人物/工具等遮挡。阴影下可辨认的地面仍有效，不能靠排除工具消除材料争议。
5. 放大检查整幅，勾选「已检查整幅与地面范围，均为人工标注」，点「完成，下一张」。有效地面仍有未标像素时不能完成。
6. 右上「导出」得到完整研究包。本机入口自动校验保存 ZIP 和解包目录，无需手动转换；单独 HTML 入口下载 ZIP。

画笔、多边形和矩形直接给原始像素数组赋整数类别，没有抗锯齿混合标签。多边形双击 / Enter 闭合，Esc 取消。Space+拖动移动，Ctrl/⌘+滚轮缩放，1/2/3/4/5/0 选类别，B/P/R/H 选工具，Ctrl/⌘+Z 撤销，Ctrl/⌘+Shift+Z 重做，左右箭头换图。页面帮助有完整说明。

## 保存、恢复与复标

原图字节、像素数组、备注和元数据自动保存在此浏览器 IndexedDB，刷新/换图可恢复。不同浏览器、端口或清除浏览器数据不会共享缓存，请定期「更多 → 备份全部进度」，不要将缓存当永久归档。

「更多 → 恢复数据包」核验 ZIP、SHA-256、尺寸、标签、训练映射和统计，以独立工程恢复，不覆盖原工程，可跨电脑继续。独立复标必须通过「更多 → 新建独立复标 / 新工程」空白开始，保留原工程并隐藏原掩码。同一人重标不是两人独立一致性；建议至少四幅由第二位标注者独立标注，再比较、复核与裁决。

「更多 → 标注说明」可导入旧版单张 `_mask.png`；尺寸、灰度值严格检查，导入后是草稿，须重新检查材料和有效地面。

## 直接用于研究的数据格式

```text
manifest.json                 # schema_version=straw-annotation/2；完整记录和逐文件 SHA-256
annotations.csv               # UTF-8 BOM；状态、标注者、像素计数、覆盖率区间和路径
images/<sample_id>.png|jpg     # 保留原图片字节，无重编码/缩放
human_masks/<sample_id>_mask.png
valid_roi/<sample_id>_valid.png
training_masks/<sample_id>.png
metadata/<sample_id>.json
drafts/<sample_id>_mask.png    # 备份才包含草稿；正式完成项目不在这里
draft_training_masks/<sample_id>.png
```

材料：8-bit 灰度 PNG，`0=背景,255=秸秆,128=材料不确定`；草稿额外允许 `64=未标`。ROI：`255=有效,0=无效`。训练掩码已转成 `0=背景,1=秸秆,255=ignore`，争议、未标和无效全部忽略。正式训练只使用完成项 `training_masks`，不使用 `draft_training_masks`。

有效地面 N、已知秸秆 S、材料争议 U、未标 D：下界 100S/N，上界 100(S+U+D)/N；只有 U=D=0 才给出单一 `coverage_pp`，否则为 null。N=0 不能完成。材料争议和地面有效性必须分开。

元数据包含图像 SHA-256、原文件名、来源、标注者、角色、工程 ID、日期、工具版本、检查和备注。抽帧目录保留 video_id/frame_id/run_id/source_pts/source_time_base 等，通用导入缺少的来源明确未知。源视频组不保证独立地面，不自动随机拆训练/验证/测试。裁块覆盖率只代表裁块。

本机保存时生成 `format_validation.json`，也可独立校验：

```sh
PYTHONPATH=src python3 -c 'from pathlib import Path; from strawframe.annotation.bundle import validate_bundle; print(validate_bundle(Path("结果.zip"))[0])'
```

格式有效不证明人工正确。完成项保留 `human_correctness_verified=false`，仍需独立人工复核。工具不把自动标签、模拟样例或图片整体估计当作人工像素真值。

## 开发与核验

`PYTHONPATH=src python3 -m unittest discover -s tests -p 'test_annotation.py'` 测试格式与本机保存。浏览器集成测试见 `tests/annotation_ui_smoke.cjs`。

Windows PyInstaller spec 已包含 HTML；源码更新不会自动更新旧 exe，exe 需按 BUILD.md 在 Windows 重打包。
