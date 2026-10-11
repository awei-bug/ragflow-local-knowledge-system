import shutil, subprocess, sys
from pathlib import Path
root = Path(__file__).resolve().parents[1]
log = root / 'uv_sync_min_bg.log'
uv = shutil.which('uv')
if not uv:
    raise SystemExit('uv not found')
skip = [
    'graspologic',
    'datrie',
    'infinity-sdk',
    'editdistance',
    'xgboost',
    'onnxruntime',
    'onnxruntime-gpu',
    'opencv-python',
    'opencv-python-headless',
    'playwright',
    'patchright',
    'spacy',
    'blis',
    'llvmlite',
    'numba',
    'polars-lts-cpu',
    'pyarrow',
    'gensim',
    'scipy',
    'scikit-learn',
    'matplotlib',
    'statsmodels',
]
cmd = [uv, 'sync', '--python', '3.13', '--no-install-project']
for p in skip:
    cmd.extend(['--no-install-package', p])
with log.open('w', encoding='utf-8', errors='replace') as f:
    f.write('CMD ' + ' '.join(cmd) + chr(10))
    f.flush()
    p = subprocess.Popen(cmd, cwd=str(root), stdout=f, stderr=subprocess.STDOUT, text=True)
    f.write('PID ' + str(p.pid) + chr(10))
    f.flush()
    code = p.wait()
    f.write('EXIT ' + str(code) + chr(10))
sys.exit(code)
