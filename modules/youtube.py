import re, base64, hashlib
from pathlib import Path
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.downloader import run_yt_dlp, cleanup_path, tempdir

YOUTUBE_URL_REGEX = re.compile(r"(https?://(?:www\\.)?(?:youtube\\.com/watch\\?v=|youtu\\.be/)[A-Za-z0-9_\\-]+)", re.IGNORECASE)
PENDING = {}

def token_for(url: str):
    h = hashlib.sha256(url.encode()).digest()
    t = base64.urlsafe_b64encode(h)[:18].decode()
    PENDING[t] = {"url": url}
    return t

def register_youtube(app):
    @app.on_message(filters.private | filters.group)
    async def auto_detect_youtube(client, message):
        if not message.text:
            return
        m = YOUTUBE_URL_REGEX.search(message.text)
        if not m:
            return
        url = m.group(1)
        token = token_for(url)
        kb = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Download Audio 🎧", callback_data=f"dl:audio:{token}"),
              InlineKeyboardButton("Download Video 🎬", callback_data=f"dl:video:{token}")],
             [InlineKeyboardButton("Developer @DEWENI2", url="https://t.me/deweni2")]]
        )
        await message.reply_text("Found YouTube link. Choose an option:", reply_markup=kb)

    @app.on_callback_query(filters.regex(r"^dl:(audio|video):([A-Za-z0-9_\\-]+)$"))
    async def handle_dl_callback(client, cq: CallbackQuery):
        kind, token = cq.data.split(":")[1:]
        info = PENDING.get(token)
        if not info:
            await cq.edit_message_text("Token expired.")
            return
        url = info["url"]
        tmpdir = tempdir("yt_")
        try:
            if kind == "audio":
                out = str(tmpdir / "%(title)s.%(ext)s")
                await cq.edit_message_text("Downloading audio...")
                await run_yt_dlp(url, out, ["-x", "--audio-format", "mp3"])
                files = list(tmpdir.glob("*.mp3"))
                await cq.message.reply_audio(str(files[0]), caption=f"From {url}")
            else:
                out = str(tmpdir / "%(title)s.%(ext)s")
                await cq.edit_message_text("Downloading video...")
                await run_yt_dlp(url, out, ["-f", "bestvideo+bestaudio/best"])
                files = list(tmpdir.glob("*.mp4"))
                await cq.message.reply_video(str(files[0]), caption=f"From {url}")
            await cq.edit_message_text("✅ Upload complete.")
        except Exception as e:
            await cq.edit_message_text(f"Error: {e}")
        finally:
            cleanup_path(tmpdir)
            if token in PENDING:
                del PENDING[token]
