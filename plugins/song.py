from pyrogram import Client, filters
from pyrogram.types import Message
import requests
import urllib.parse
import os

@Client.on_message(filters.command("song"))
async def song_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply("🎵 Please enter song name.\nUsage: `/song humnava mere`", quote=True)
        return

    query = " ".join(message.command[1:])
    await message.reply(f"🔎 Searching for `{query}`...", quote=True)

    encoded = urllib.parse.quote(query)
    api_url = f"https://saavn.dev/api/search/songs?query={encoded}"

    try:
        r = requests.get(api_url)
        data = r.json()

        if not data["data"]:
            await message.reply("❌ Song not found.")
            return

        song = data["data"][0]
        song_url = song["downloadUrl"][-1]["link"]  # highest quality
        song_title = song["name"]
        song_artist = ", ".join([a["name"] for a in song["primaryArtists"]])
        cover = song["image"][2]["link"]  # medium quality

        # Download audio
        response = requests.get(song_url)
        file_name = f"{song_title}.mp3"

        with open(file_name, "wb") as f:
            f.write(response.content)

        await client.send_audio(
            chat_id=message.chat.id,
            audio=file_name,
            caption=f"🎵 **{song_title}**\n👤 *{song_artist}*",
            title=song_title,
            performer=song_artist,
            thumb=cover
        )

        os.remove(file_name)

    except Exception as e:
        await message.reply(f"⚠️ Error: {str(e)}")
