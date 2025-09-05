import asyncio
import shutil
import tempfile
from pathlib import Path

DOWNLOAD_DIR = Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

async def run_yt_dlp(url_or_search: str, out_template: str, extra_args=None):
    args = ["yt-dlp", "-o", out_template]
    if extra_args:
        args += extra_args
    args.append(url_or_search)

    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {stderr.decode(errors='ignore')}")
    return stdout.decode(errors='ignore')

def cleanup_path(p: Path):
    try:
        if p.is_dir():
            shutil.rmtree(p)
        elif p.exists():
            p.unlink()
    except Exception:
        pass

def tempdir(prefix: str):
    return Path(tempfile.mkdtemp(prefix=prefix, dir=DOWNLOAD_DIR))
