from pyrogram import Client, filters
from pyrogram.types import Message
import os
import yt_dlp

@Client.on_message(filters.command("song") & (filters.private | filters.group))
async def song_handler(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("❌ Usage: /song <song name>")
        return

    query = " ".join(message.command[1:])
    sent = await message.reply(f"🔍 Searching for: **{query}**")

    try:
        ydl_opts = {
            'format': 'mp4',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
            file_path = ydl.prepare_filename(info)

        await sent.edit("📤 Uploading...")

        await message.reply_video(
            video=file_path,
            caption=f"🎵 **{info['title']}**"
        )

        os.remove(file_path)
        await sent.delete()

    except Exception as e:
        await sent.edit(f"❌ Error: {e}")
