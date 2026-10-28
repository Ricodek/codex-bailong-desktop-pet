"""One portable workspace for this local build; Codex account paths remain external."""
import os
import sys
import tempfile
from pathlib import Path


def workspace():
    if os.environ.get('BAILONG_HOME'):
        return Path(os.environ['BAILONG_HOME']).resolve()
    if getattr(sys, 'frozen', False):
        exe = Path(sys.executable).resolve()
        return exe.parents[3] if exe.parent.parent.name == 'versions' else exe.parent.parent
    return Path(__file__).resolve().parents[3]


def data_dir():
    if os.environ.get('BAILONG_DATA_DIR'):
        return Path(os.environ['BAILONG_DATA_DIR']).resolve()
    if os.environ.get('BAILONG_ISOLATED') == '1':
        return Path(os.environ.get('LOCALAPPDATA', str(workspace()))) / 'BailongEnhanced'
    return workspace() / '数据'


def prepare_runtime():
    root = data_dir()
    root.mkdir(parents=True, exist_ok=True)
    temporary = root / '临时'
    temporary.mkdir(exist_ok=True)
    os.environ['TEMP'] = os.environ['TMP'] = str(temporary)
    tempfile.tempdir = str(temporary)
    # Qt's shader/disk caches also belong to this portable application.
    os.environ['QT_SHADER_CACHE_PATH'] = str(root / '缓存' / 'Qt')
    os.environ['PYTHONPYCACHEPREFIX'] = str(root / '缓存' / 'python')
    return root
