"""
Telegram multi-downloader bot (single-file starter)
Features included:
- Auto-detect YouTube links and show inline buttons (Download Audio / Download Video)
- /song <query> - search & download audio
- /video <query> - search & download video
- /tiktok <url> - tiktok downloader (via yt-dlp)
- /fb <url> - facebook downloader (via yt-dlp)
- /instagram <url> - instagram downloader (via yt-dlp)

This is a single-file, well-documented starter. You can split each register_* into its own module (youtube.py, tiktok.py, etc.) later.

Requirements (install in your environment):
- pyrogram[speed] (or pyrogram)
- tgcrypto (recommended)
- yt-dlp
- python-multipart? (optional)

Example:
pip install pyrogram tgcrypto yt-dlp aiofiles

Run:
- Set environment variables: API_ID, API_HASH, BOT_TOKEN (or put them below)
- python telegram_multi_downloader_bot_main.py

NOTE: This code uses yt-dlp and saves temporary files to /tmp or ./downloads. Make sure you have disk space and respect copyright.
"""

import os
import re
import asyncio
import shutil
import hashlib
import base64
import tempfile
from pathlib import Path
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import (Message, InlineKeyboardMarkup, InlineKeyboardButton,
                            CallbackQuery)

# ---------- Configuration ----------
API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN")

# Where downloads will be stored temporarily
DOWNLOAD_DIR = Path("./downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# Regex patterns
YOUTUBE_URL_REGEX = re.compile(r"(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_\-]+)" , re.IGNORECASE)
GENERIC_URL_REGEX = re.compile(r"https?://\S+")

# Very small in-memory store mapping tokens -> url to avoid long callback_data
PENDING = {}  # token -> {"url":..., "chat_id":..., "msg_id":...}

# ---------- Utilities ----------

def token_for(url: str) -> str:
    """Create a short token for callback data."""
    h = hashlib.sha256(url.encode()).digest()
    t = base64.urlsafe_b64encode(h)[:18].decode()
    PENDING[t] = {"url": url}
    return t


async def run_yt_dlp(url_or_search: str, out_template: str, extra_args: Optional[list] = None):
    """Run yt-dlp (must be installed). Returns path to downloaded file(s).
    out_template should include full path like ./downloads/%(title)s.%(ext)s
    """
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


# ---------- Bot and Handlers ----------

app = Client("multi_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)


@app.on_message(filters.private | filters.group)
async def auto_detect_youtube(client: Client, message: Message):
    # only text messages
    if not message.text:
        return

    m = YOUTUBE_URL_REGEX.search(message.text)
    if not m:
        return

    url = m.group(1)
    token = token_for(url)

    # build inline keyboard
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Download Audio 🎧", callback_data=f"dl:audio:{token}"),
             InlineKeyboardButton("Download Video 🎬", callback_data=f"dl:video:{token}")],
            [InlineKeyboardButton("Developer @DEWENI2", url="https://t.me/deweni2")]
        ]
    )

    # Try to send thumbnail preview using yt-dlp to get thumbnail url (lightweight), else simple reply
    try:
        # Use yt-dlp to extract metadata (no download)
        await run_yt_dlp(url, "-", extra_args=["--skip-download", "--print", "%({thumbnail})s"])
    except Exception:
        pass

    await message.reply_text(f"Found YouTube link. Choose an option:", reply_markup=kb)


@app.on_callback_query(filters.regex(r"^dl:(audio|video):([A-Za-z0-9_\-]+)$"))
async def handle_dl_callback(client: Client, cq: CallbackQuery):
    await cq.answer("Processing... this may take a moment")
    kind, token = cq.data.split(":")[1:]
    info = PENDING.get(token)
    if not info:
        await cq.edit_message_text("Token expired or invalid.")
        return
    url = info["url"]

    # Prepare download folder
    tmpdir = Path(tempfile.mkdtemp(prefix="yt_", dir=DOWNLOAD_DIR))

    try:
        if kind == "audio":
            out = str(tmpdir / "%(title)s.%(ext)s")
            # extract audio as mp3
            await cq.edit_message_text("Downloading audio (best)...")
            await run_yt_dlp(url, out, extra_args=["-x", "--audio-format", "mp3", "--no-playlist"])  # add more args if needed

            # find resulting file
            files = list(tmpdir.glob("*.mp3")) + list(tmpdir.glob("*.m4a")) + list(tmpdir.glob("*.opus"))
            if not files:
                raise RuntimeError("No audio file produced")
            target = files[0]

            # send as audio
            await cq.message.reply_audio(str(target), caption=f"Downloaded from {url}")

        else:  # video
            out = str(tmpdir / "%(title)s.%(ext)s")
            await cq.edit_message_text("Downloading video (best)...")
            await run_yt_dlp(url, out, extra_args=["-f", "bestvideo+bestaudio/best", "--no-playlist"])
            # find any video file
            files = list(tmpdir.glob("*.mp4")) + list(tmpdir.glob("*.mkv")) + list(tmpdir.glob("*.webm"))
            if not files:
                # maybe merged into .mkv by ffmpeg
                files = list(tmpdir.rglob("*.*"))
            if not files:
                raise RuntimeError("No video file produced")
            target = files[0]
            await cq.message.reply_video(str(target), caption=f"Downloaded from {url}")

        await cq.edit_message_text("Upload complete.")

    except Exception as e:
        await cq.edit_message_text(f"Error: {e}")
    finally:
        # cleanup
        cleanup_path(tmpdir)
        # expire token
        if token in PENDING:
            del PENDING[token]


# ---------- /song and /video commands (search-based) ----------

@app.on_message(filters.command("song") & filters.private)
async def cmd_song(client: Client, message: Message):
    if not message.command or len(message.command) < 2:
        await message.reply_text("Usage: /song <song name or query>")
        return
    query = " ".join(message.command[1:])
    await message.reply_text(f"Searching and downloading audio for: {query}")

    tmpdir = Path(tempfile.mkdtemp(prefix="song_", dir=DOWNLOAD_DIR))
    try:
        out = str(tmpdir / "%(title)s.%(ext)s")
        # use ytsearch to fetch best match
        await run_yt_dlp(f"ytsearch1:{query}", out, extra_args=["-x", "--audio-format", "mp3"])
        files = list(tmpdir.glob("*.mp3")) + list(tmpdir.glob("*.m4a"))
        if not files:
            raise RuntimeError("No result")
        await message.reply_audio(str(files[0]), caption=f"Result for: {query}")
    except Exception as e:
        await message.reply_text(f"Error: {e}")
    finally:
        cleanup_path(tmpdir)


@app.on_message(filters.command("video") & filters.private)
async def cmd_video(client: Client, message: Message):
    if not message.command or len(message.command) < 2:
        await message.reply_text("Usage: /video <query>")
        return
    query = " ".join(message.command[1:])
    await message.reply_text(f"Searching and downloading video for: {query}")

    tmpdir = Path(tempfile.mkdtemp(prefix="video_", dir=DOWNLOAD_DIR))
    try:
        out = str(tmpdir / "%(title)s.%(ext)s")
        await run_yt_dlp(f"ytsearch1:{query}", out, extra_args=["-f", "bestvideo+bestaudio/best"])
        files = list(tmpdir.glob("*.mp4")) + list(tmpdir.glob("*.mkv"))
        if not files:
            files = list(tmpdir.rglob("*.*"))
        if not files:
            raise RuntimeError("No result")
        await message.reply_video(str(files[0]), caption=f"Result for: {query}")
    except Exception as e:
        await message.reply_text(f"Error: {e}")
    finally:
        cleanup_path(tmpdir)


# ---------- Generic downloaders for tiktok / facebook / instagram using yt-dlp ----------

async def generic_url_downloader(message: Message, url: str, prefer_video=True):
    tmpdir = Path(tempfile.mkdtemp(prefix="generic_", dir=DOWNLOAD_DIR))
    try:
        out = str(tmpdir / "%(title)s.%(ext)s")
        if prefer_video:
            await run_yt_dlp(url, out, extra_args=["-f", "bestvideo+bestaudio/best", "--no-playlist"]) 
            files = list(tmpdir.glob("*.mp4")) + list(tmpdir.glob("*.mkv"))
            if not files:
                files = list(tmpdir.rglob("*.*"))
            if not files:
                raise RuntimeError("No downloadable file found")
            await message.reply_video(str(files[0]), caption=f"Downloaded from {url}")
        else:
            await run_yt_dlp(url, out, extra_args=["-x", "--audio-format", "mp3", "--no-playlist"]) 
            files = list(tmpdir.glob("*.mp3")) + list(tmpdir.glob("*.m4a"))
            if not files:
                raise RuntimeError("No downloadable file found")
            await message.reply_audio(str(files[0]), caption=f"Downloaded from {url}")
    except Exception as e:
        await message.reply_text(f"Error: {e}")
    finally:
        cleanup_path(tmpdir)


@app.on_message(filters.command("tiktok") & (filters.private | filters.group))
async def cmd_tiktok(client: Client, message: Message):
    if not message.command or len(message.command) < 2:
        await message.reply_text("Usage: /tiktok <url>")
        return
    url = message.command[1]
    if not GENERIC_URL_REGEX.match(url):
        await message.reply_text("Please provide a valid URL.")
        return
    await message.reply_text("Downloading from TikTok...")
    await generic_url_downloader(message, url, prefer_video=True)


@app.on_message(filters.command("fb") & (filters.private | filters.group))
async def cmd_fb(client: Client, message: Message):
    if not message.command or len(message.command) < 2:
        await message.reply_text("Usage: /fb <url>")
        return
    url = message.command[1]
    await message.reply_text("Downloading from Facebook...")
    await generic_url_downloader(message, url, prefer_video=True)


@app.on_message(filters.command("instagram") & (filters.private | filters.group))
async def cmd_instagram(client: Client, message: Message):
    if not message.command or len(message.command) < 2:
        await message.reply_text("Usage: /instagram <url>")
        return
    url = message.command[1]
    await message.reply_text("Downloading from Instagram...")
    await generic_url_downloader(message, url, prefer_video=True)


# ---------- Run Bot ----------

if __name__ == "__main__":
    print("Starting Multi Downloader Bot...")
    app.run()
