from pathlib import Path
import time
from PySide6.QtCore import Qt, QSettings, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QGroupBox,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QFileDialog,QMessageBox,QComboBox,QDoubleSpinBox,QSpinBox,QLineEdit,QProgressBar,QPlainTextEdit,QHeaderView,QApplication)
from strawframe.core.ffmpeg_manager import FFmpegManager
from strawframe.core.models import Settings
from strawframe.core.extractor import Extractor
from strawframe.annotation.server import launch as launch_annotation
from .workers import ProbeWorker,ExtractWorker

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('秸秆科研视频抽帧工具 · StrawFrameExtractor 1.0'); self.resize(1120,850); self.setAcceptDrops(True)
        self.prefs=QSettings('StrawFrameExtractor','StrawFrameExtractor'); self.videos=[]; self.prober=None; self.worker=None; self.last_output=''; self.busy=False; self.annotation_servers=[]
        main=QWidget(); self.setCentralWidget(main); layout=QVBoxLayout(main)
        title=QLabel('秸秆科研视频抽帧工具'); title.setStyleSheet('font-size:24px;font-weight:600'); layout.addWidget(title)
        intro=QLabel('原始尺寸 · 实际源帧 PTS · CSV 元数据 · 可复现实验'); layout.addWidget(intro)
        toolbar=QHBoxLayout(); self.add=QPushButton('导入视频…'); self.remove=QPushButton('移除选中'); self.clear=QPushButton('清空列表'); self.theme=QComboBox(); self.theme.addItems(['浅色','深色'])
        for w in (self.add,self.remove,self.clear): toolbar.addWidget(w)
        toolbar.addStretch(); toolbar.addWidget(QLabel('主题')); toolbar.addWidget(self.theme); layout.addLayout(toolbar)
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(['文件名','时长 / 秒','分辨率','帧率 / fps','总帧数','编码','大小 / MB','完整路径']); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setEditTriggers(QTableWidget.NoEditTriggers); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents); self.table.horizontalHeader().setMinimumSectionSize(90); self.table.horizontalHeader().setStretchLastSection(True); self.table.setMinimumHeight(160); layout.addWidget(self.table,2)
        self.details=QLabel('导入视频后可查看参数；支持拖拽 MP4 / MOV / AVI / MKV / M4V'); self.details.setWordWrap(True); layout.addWidget(self.details)
        self.settings_box=QGroupBox('抽帧与输出设置'); grid=QGridLayout(self.settings_box); layout.addWidget(self.settings_box)
        self.mode=QComboBox(); self.mode.addItems(['按 fps','按时间间隔（秒）']); self.value=QDoubleSpinBox(); self.value.setDecimals(6); self.value.setRange(.000001,86400); self.value.setValue(2)
        self.format=QComboBox(); self.format.addItems(['JPEG','PNG（无损）']); self.quality=QComboBox(); self.quality.addItems(['高质量（q=2，推荐）','最高质量（q=1）','较小文件（q=5）'])
        self.scale=QComboBox(); self.scale.addItems(['保持原始尺寸','指定宽度，保持比例','指定最大边（只缩小）','自定义宽高']); self.width=QSpinBox(); self.width.setRange(1,32768); self.width.setValue(1920); self.height=QSpinBox(); self.height.setRange(1,32768); self.height.setValue(1080)
        self.policy=QComboBox(); self.policy.addItems(['创建新任务目录（默认）','已有内容则停止','跳过已有帧（选择原任务目录）'])
        self.output=QLineEdit(self.prefs.value('output',str(Path.home()/'Documents'/'StrawFrameOutput'))); self.choose_output=QPushButton('选择输出…')
        self.ffpath=QLineEdit(self.prefs.value('ffmpeg','')); self.ffpath.setPlaceholderText('自动检测随附 FFmpeg 或系统 PATH'); self.choose_ff=QPushButton('选择 FFmpeg 文件夹…')
        widgets=[('抽帧方式',self.mode,'频率 / 间隔',self.value),('图片格式',self.format,'JPEG 质量',self.quality),('分辨率',self.scale,'宽度 / 最大边',self.width)]
        for row,(a,b,c,d) in enumerate(widgets): grid.addWidget(QLabel(a),row,0); grid.addWidget(b,row,1); grid.addWidget(QLabel(c),row,2); grid.addWidget(d,row,3)
        grid.addWidget(QLabel('输出策略'),3,0); grid.addWidget(self.policy,3,1); grid.addWidget(QLabel('自定义高度'),3,2); grid.addWidget(self.height,3,3)
        grid.addWidget(QLabel('输出目录'),4,0); grid.addWidget(self.output,4,1,1,2); grid.addWidget(self.choose_output,4,3)
        grid.addWidget(QLabel('FFmpeg'),5,0); grid.addWidget(self.ffpath,5,1,1,2); grid.addWidget(self.choose_ff,5,3)
        warning=QLabel('缩放可能影响小目标 / 细秸秆分割，不建议作为原始科研数据的唯一保存版本。JPEG 有损；需要无损请选 PNG。'); warning.setWordWrap(True); grid.addWidget(warning,6,0,1,4)
        self.estimate=QLabel(); self.estimate.setStyleSheet('font-size:16px;font-weight:600;padding:6px'); layout.addWidget(self.estimate)
        actions=QHBoxLayout(); self.start=QPushButton('开始抽帧'); self.start.setMinimumHeight(36); self.cancel=QPushButton('取消'); self.cancel.setEnabled(False); self.open_output=QPushButton('打开结果目录'); self.open_output.setEnabled(False)
        self.annotate=QPushButton('像素标注…'); self.annotate.setToolTip('打开人工像素标注工作台，导出材料掩码、有效地面范围及研究数据包')
        for w in (self.start,self.cancel,self.open_output,self.annotate): actions.addWidget(w)
        layout.addLayout(actions)
        self.status=QLabel('就绪'); layout.addWidget(self.status); self.overall=QProgressBar(); self.fileprogress=QProgressBar(); self.overall.setFormat('总体进度 %p%'); self.fileprogress.setFormat('当前视频 %p%'); layout.addWidget(self.overall); layout.addWidget(self.fileprogress)
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumBlockCount(1000); self.log.setMaximumHeight(130); layout.addWidget(self.log,1)
        self.add.clicked.connect(self.pick_videos); self.remove.clicked.connect(self.remove_selected); self.clear.clicked.connect(self.clear_videos); self.choose_output.clicked.connect(self.pick_output); self.choose_ff.clicked.connect(self.pick_ff); self.start.clicked.connect(self.start_run); self.cancel.clicked.connect(self.cancel_run); self.open_output.clicked.connect(lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output))); self.table.itemSelectionChanged.connect(self.show_details)
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.annotate.clicked.connect(self.open_annotation)
        for w in (self.value,self.width,self.height): w.valueChanged.connect(self.update_estimate)
        for w in (self.format,self.quality,self.scale,self.policy): w.currentIndexChanged.connect(self.update_estimate)
        self.theme.currentIndexChanged.connect(self.apply_theme); self.theme.setCurrentIndex(int(self.prefs.value('theme',0))); self.apply_theme(); self.update_estimate()
        self.timer=QTimer(self); self.timer.timeout.connect(self.update_clock); self.timer.setInterval(500)
    def apply_theme(self):
        dark=self.theme.currentIndex()==1
        QApplication.instance().setStyleSheet('QWidget {font-size:13px;} QGroupBox {font-weight:600;margin-top:8px;} QGroupBox::title {subcontrol-origin:margin;}' + ('QWidget {background:#20252b;color:#e5eaf0;} QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QPlainTextEdit,QTableWidget {background:#2d343c;} QPushButton {background:#36424d;padding:7px;border-radius:4px;} QPushButton:disabled {color:#818991;} QProgressBar::chunk {background:#5298d1;} QHeaderView::section {background:#36424d;}' if dark else 'QPushButton {padding:7px;}'))
        self.prefs.setValue('theme',self.theme.currentIndex())
    def settings(self):
        return Settings(mode=['fps','interval'][self.mode.currentIndex()],value=f'{self.value.value():.6f}',image_format=['jpg','png'][self.format.currentIndex()],jpeg_quality=[2,1,5][self.quality.currentIndex()],scale_mode=['original','width','max','custom'][self.scale.currentIndex()],width=self.width.value(),height=self.height.value(),policy=['new','stop','skip'][self.policy.currentIndex()])
    def change_mode(self):
        v=self.value.value()
        if v: self.value.setValue(1/v)
        self.update_estimate()
    def update_estimate(self):
        self.width.setEnabled(self.scale.currentIndex()!=0); self.height.setEnabled(self.scale.currentIndex()==3); self.quality.setEnabled(self.format.currentIndex()==0)
        try:
            s=self.settings(); s.validate(); count=s.estimate(self.videos); bytes_est=0
            for v in self.videos:
                w,h=s.dimensions(v); n=s.estimate([v]); bytes_est+=w*h*(.35 if s.image_format=='jpg' else 2)*n
            self.estimate.setText(f'预计约 {count:,} 张 · {float(s.rate):.6g} fps · 粗略磁盘占用 {bytes_est/1024**3:.2f} GB（因画面内容差异较大）')
        except Exception as exc: self.estimate.setText(str(exc))
    def pick_videos(self):
        paths,_=QFileDialog.getOpenFileNames(self,'导入视频','','视频 (*.mp4 *.mov *.avi *.mkv *.m4v);;所有文件 (*)'); self.import_paths(paths)
    def import_paths(self,paths):
        if self.busy or (self.prober and self.prober.isRunning()): return
        paths=list(dict.fromkeys(str(Path(p).resolve()) for p in paths if str(Path(p).resolve()) not in {v.path for v in self.videos}))
        if not paths: return
        try: manager=FFmpegManager(self.ffpath.text().strip())
        except Exception as exc: self.error(str(exc)); return
        self.set_busy(True); self.status.setText('正在后台读取视频信息…'); self.prober=ProbeWorker(paths,manager,self); self.prober.found.connect(self.add_video); self.prober.error.connect(self.error); self.prober.finished.connect(self.probe_done); self.prober.start()
    def probe_done(self): self.set_busy(False); self.status.setText('视频读取完成'); self.update_estimate()
    def add_video(self,v):
        self.videos.append(v); row=self.table.rowCount(); self.table.insertRow(row)
        values=[Path(v.path).name,f'{v.duration:.3f}',f'{v.width}×{v.height}',f'{v.fps:.6f}',str(v.frames) if v.frames else '未知',v.codec,f'{v.size/1024**2:.1f}',v.path]
        for col,value in enumerate(values): self.table.setItem(row,col,QTableWidgetItem(value))
        self.log.appendPlainText('已导入：'+v.path); self.update_estimate()
    def remove_selected(self):
        rows=sorted({i.row() for i in self.table.selectedIndexes()},reverse=True)
        for row in rows: self.videos.pop(row); self.table.removeRow(row)
        self.update_estimate()
    def clear_videos(self): self.videos=[]; self.table.setRowCount(0); self.update_estimate()
    def show_details(self):
        row=self.table.currentRow()
        if 0<=row<len(self.videos):
            v=self.videos[row]; self.details.setText(f'{v.path}\n精确帧率比：{v.fps_ratio} · 时间基：{v.time_base} · 旋转：{v.rotation}° · 总帧数仅在容器可提供时显示')
    def pick_output(self):
        p=QFileDialog.getExistingDirectory(self,'选择输出目录',self.output.text())
        if p: self.output.setText(p)
    def pick_ff(self):
        p=QFileDialog.getExistingDirectory(self,'选择同时包含 ffmpeg 和 ffprobe 的文件夹')
        if p: self.ffpath.setText(p); self.prefs.setValue('ffmpeg',p)
    def open_annotation(self):
        initial=Path(self.last_output)/'images' if self.last_output else Path(self.output.text())
        directory=QFileDialog.getExistingDirectory(self,'选择要标注的图片目录（抽帧任务中的 images）',str(initial))
        if not directory: return
        try:
            images=Path(directory)
            server=launch_annotation(images, images.parent/'human_annotations')
            if server is not None: self.annotation_servers.append(server)
            self.log.appendPlainText('标注工作台：http://127.0.0.1:8765/\n导出位置：'+str(images.parent/'human_annotations'))
        except Exception as exc: self.error('标注工具启动失败：'+str(exc))
    def set_busy(self,busy):
        self.busy=busy
        for w in (self.add,self.remove,self.clear,self.settings_box,self.start): w.setEnabled(not busy)
    def start_run(self):
        if not self.videos: self.error('请先导入视频'); return
        try:
            s=self.settings(); s.validate()
            if not self.output.text().strip(): raise ValueError('请选择输出目录')
            engine=Extractor(FFmpegManager(self.ffpath.text().strip()))
        except Exception as exc: self.error(str(exc)); return
        self.prefs.setValue('output',self.output.text()); self.prefs.setValue('ffmpeg',self.ffpath.text().strip()); self.set_busy(True); self.cancel.setEnabled(True); self.overall.setValue(0); self.fileprogress.setValue(0)
        self.run_started=time.monotonic(); self.last_progress={'processed':0,'estimated':s.estimate(self.videos),'current':'准备任务','status':'启动中'}; self.timer.start()
        self.worker=ExtractWorker(engine,list(self.videos),s,self.output.text(),self); self.worker.progress.connect(self.progress); self.worker.result.connect(self.result); self.worker.error.connect(self.error); self.worker.finished.connect(self.run_done); self.worker.start()
    def progress(self,data):
        self.last_progress=data; self.last_output=data['output']; self.open_output.setEnabled(True); self.overall.setValue(min(99,int(data['processed']/max(1,data['estimated'])*100))); self.fileprogress.setValue(int(data.get('file_percent',0))); self.update_clock()
    def update_clock(self):
        d=self.last_progress; elapsed=int(time.monotonic()-self.run_started); self.status.setText(f"{d.get('status','')} · {d.get('current','')} · 已保存 {d['processed']:,} / 预计 {d['estimated']:,} 张 · 已运行 {elapsed//60:02d}:{elapsed%60:02d}")
    def cancel_run(self):
        if self.worker and self.worker.isRunning(): self.worker.engine.cancel(); self.cancel.setEnabled(False); self.log.appendPlainText('已请求取消，正在停止解码并保存完整帧记录…')
    def result(self,data):
        self.last_output=data['output']; self.open_output.setEnabled(True); labels={'completed':'完成','cancelled':'已取消','failed':'失败'}; self.log.appendPlainText(f"{labels[data['status']]}：成功保存 {data['successful_frames']} 张\n输出：{data['output']}")
        self.status.setText(f"{labels[data['status']]} · 共 {data['successful_frames']} 张 · {data['elapsed_sec']:.1f} 秒")
        if data['status']=='completed': self.overall.setValue(100)
        if data['error']: self.error(data['error'])
    def run_done(self): self.timer.stop(); self.cancel.setEnabled(False); self.set_busy(False)
    def error(self,message): self.log.appendPlainText('错误：'+message); QMessageBox.warning(self,'任务提示',message)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and not self.busy: event.acceptProposedAction()
    def dropEvent(self,event):
        self.import_paths([u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]); event.acceptProposedAction()
    def closeEvent(self,event):
        if self.worker and self.worker.isRunning():
            self.cancel_run(); self.status.setText('正在安全取消；任务停止后可关闭窗口'); event.ignore(); return
        if self.prober and self.prober.isRunning():
            self.prober.requestInterruption(); self.status.setText('正在读取当前文件；读取结束后可关闭窗口'); event.ignore(); return
        for server in self.annotation_servers:
            server.shutdown(); server.server_close()
        event.accept()
