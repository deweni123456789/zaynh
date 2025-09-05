from pathlib import Path
from pyrogram import filters
from utils.downloader import run_yt_dlp, cleanup_path, tempdir

def register_video(app):
    @app.on_message(filters.command("video") & filters.private)
    async def cmd_video(client, message):
        if not message.command or len(message.command) < 2:
            await message.reply_text("Usage: /video <query>")
            return
        query = " ".join(message.command[1:])
        await message.reply_text(f"🎥 Searching & downloading video for: {query}")

        tmpdir = tempdir("video_")
        try:
            out = str(tmpdir / "%(title)s.%(ext)s")
            await run_yt_dlp(f"ytsearch1:{query}", out, ["-f", "bestvideo+bestaudio/best"])
            files = list(tmpdir.glob("*.mp4")) + list(tmpdir.glob("*.mkv"))
            if not files:
                raise RuntimeError("No result found")
            await message.reply_video(str(files[0]), caption=f"Result for: {query}")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
        finally:
            cleanup_path(tmpdir)
