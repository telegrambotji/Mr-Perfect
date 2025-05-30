from pyrogram import Client, filters
from pyrogram.types import Message
from yt_dlp import YoutubeDL
import os

@Client.on_message(filters.command("song") & (filters.private | filters.group))
async def song_720p(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply("❌ कृपया गीत का नाम प्रदान करें!\nउदाहरण: `/song हुमनवा मेरे`")

    query = " ".join(message.command[1:])
    status = await message.reply(f"🔍 `{query}` के लिए खोज रहा हूँ...")

    try:
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best',
            'outtmpl': '%(title)s.%(ext)s',
            'merge_output_format': 'mp4',
            'quiet': True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)["entries"][0]
            filename = ydl.prepare_filename(info)
            if not filename.endswith(".mp4"):
                filename = filename.rsplit(".", 1)[0] + ".mp4"

        await status.edit("📤 वीडियो अपलोड हो रहा है...")

        await client.send_video(
            chat_id=message.chat.id,
            video=filename,
            caption=f"🎬 **{info.get('title')}**\n🔗 [YouTube पर देखें]({info.get('webpage_url')})",
            duration=int(info.get("duration", 0)),
            supports_streaming=True,
        )

        os.remove(filename)
        await status.delete()

    except Exception as e:
        await status.edit(f"❌ त्रुटि:\n`{str(e)}`")
