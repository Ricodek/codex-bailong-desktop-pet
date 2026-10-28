"""Build this local card-only application into a fresh D workspace folder."""
import hashlib,json,os,shutil,subprocess,sys,time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT.parents[1]
sys.path[:0]=[str(ROOT/'app'),str(ROOT)]
from version import VERSION
from build_release import ssl_runtime_data,windows_version_resource


def main():
    base=WORKSPACE/'开发'/'build'/('portable-'+VERSION+'-'+time.strftime('%Y%m%d-%H%M%S'))
    if base.exists():raise FileExistsError('构建目录已存在，请使用新的版本或构建目录')
    base.mkdir(parents=True)
    version=base/'version.txt';version.write_text(windows_version_resource(VERSION),encoding='utf-8')
    env=os.environ.copy()
    env.update(TEMP=str(WORKSPACE/'开发/temp'),TMP=str(WORKSPACE/'开发/temp'),
               PYTHONPYCACHEPREFIX=str(WORKSPACE/'开发/cache/pyc'))
    subprocess.run([sys.executable,'-m','PyInstaller','--windowed','--onedir',
        '--name','BailongEnhanced','--icon',str(ROOT/'app/branding/bailong.ico'),
        '--version-file',str(version),'--distpath',str(base/'dist'),
        '--workpath',str(base/'work'),'--specpath',str(base),
        '--paths',str(ROOT/'app'),'--exclude-module','imageio_ffmpeg',
        '--exclude-module','PySide6.QtQuick','--exclude-module','PySide6.QtQml',
        *ssl_runtime_data(),str(ROOT/'app/enhanced.py')],cwd=ROOT,env=env,check=True)
    output=base/'dist/BailongEnhanced'
    for name in ('fonts','licenses','sounds','branding'):
        shutil.copytree(ROOT/'app'/name,output/'app'/name)
    for name in ('material_catalog.json','book_catalog.json'):
        shutil.copy2(ROOT/'app'/name,output/'app'/name)
    shutil.copy2(ROOT/'NOTICE.md',output/'NOTICE.md')
    files={p.relative_to(output).as_posix():hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
           for p in output.rglob('*') if p.is_file()}
    (base/'build-manifest.json').write_text(json.dumps(dict(version=VERSION,files=files),indent=2),encoding='utf-8')
    print(output)


if __name__=='__main__':main()
