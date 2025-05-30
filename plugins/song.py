from pyrogram import Client, filters
from pyrogram.types import Message
import yt_dlp
import os

@Client.on_message(filters.private & filters.command("song"))
async def download_song(_, message: Message):
    if len(message.command) < 2:
        return await message.reply("🔗 YouTube link do, jaise:\n`/song https://youtu.be/dQw4w9WgXcQ`")
    
    url = message.text.split(None, 1)[1]
    msg = await message.reply("📥 Downloading...")

    try:
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info).replace(".webm", ".mp4").replace(".mkv", ".mp4")

        await msg.edit("📤 Uploading...")
        await message.reply_video(
            video=file_path,
            caption=f"🎵 {info.get('title')}"
        )
        await msg.delete()

        os.remove(file_path)

    except Exception as e:
        await msg.edit(f"❌ Error: `{str(e)}`")
