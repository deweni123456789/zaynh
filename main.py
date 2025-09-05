import os
from pyrogram import Client

from modules.youtube import register_youtube
from modules.song import register_song
from modules.video import register_video
from modules.tiktok import register_tiktok
from modules.facebook import register_facebook
from modules.instagram import register_instagram

API_ID = int(os.getenv("API_ID", "YOUR_API_ID"))
API_HASH = os.getenv("API_HASH", "YOUR_API_HASH"))
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN"))

app = Client("multi_downloader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Register all handlers
register_youtube(app)
register_song(app)
register_video(app)
register_tiktok(app)
register_facebook(app)
register_instagram(app)

if __name__ == "__main__":
    print("🚀 Starting Multi Downloader Bot...")
    app.run()
