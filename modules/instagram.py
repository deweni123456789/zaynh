from pyrogram import filters
from utils.downloader import run_yt_dlp, cleanup_path, tempdir

def register_instagram(app):
    @app.on_message(filters.command("instagram"))
    async def cmd_instagram(client, message):
        if not message.command or len(message.command) < 2:
            await message.reply_text("Usage: /instagram <url>")
            return
        url = message.command[1]
        await message.reply_text("⬇️ Downloading from Instagram...")

        tmpdir = tempdir("insta_")
        try:
            out = str(tmpdir / "%(title)s.%(ext)s")
            await run_yt_dlp(url, out, ["-f", "bestvideo+bestaudio/best", "--no-playlist"])
            files = list(tmpdir.glob("*.mp4")) + list(tmpdir.glob("*.mkv"))
            if not files:
                raise RuntimeError("Download failed")
            await message.reply_video(str(files[0]), caption=f"From Instagram: {url}")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
        finally:
            cleanup_path(tmpdir)
