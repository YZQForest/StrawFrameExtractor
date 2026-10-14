# Build on Windows. FFmpeg is placed adjacent to the executable by build.bat.
from pathlib import Path
root = Path(SPECPATH)
a = Analysis([str(root/'src'/'main.py')],pathex=[str(root/'src')],binaries=[],datas=[(str(root/'src'/'strawframe'/'annotation'/'web'/'index.html'),'strawframe/annotation/web')],hiddenimports=[],hookspath=[],hooksconfig={},runtime_hooks=[],excludes=['PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml','PySide6.QtQuick'],noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz,a.scripts,[],exclude_binaries=True,name='StrawFrameExtractor',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='StrawFrameExtractor')
