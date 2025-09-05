from pathlib import Path
from pyrogram import filters
from utils.downloader import run_yt_dlp, cleanup_path, tempdir

def register_song(app):
    @app.on_message(filters.command("song") & filters.private)
    async def cmd_song(client, message):
        if not message.command or len(message.command) < 2:
            await message.reply_text("Usage: /song <song name>")
            return
        query = " ".join(message.command[1:])
        await message.reply_text(f"🎶 Searching & downloading audio for: {query}")

        tmpdir = tempdir("song_")
        try:
            out = str(tmpdir / "%(title)s.%(ext)s")
            await run_yt_dlp(f"ytsearch1:{query}", out, ["-x", "--audio-format", "mp3"])
            files = list(tmpdir.glob("*.mp3")) + list(tmpdir.glob("*.m4a"))
            if not files:
                raise RuntimeError("No result found")
            await message.reply_audio(str(files[0]), caption=f"Result for: {query}")
        except Exception as e:
            await message.reply_text(f"❌ Error: {e}")
        finally:
            cleanup_path(tmpdir)
