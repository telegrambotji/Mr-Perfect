from pyrogram import Client, filters
from pyrogram.types import Message
import requests
import urllib.parse
import os
import re

@Client.on_message(filters.command("song") & (filters.private | filters.group))
async def song_command(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text(
            "🎵 Please enter song name.\nUsage: `/song humnava mere`",
            quote=True
        )
        return

    query = " ".join(message.command[1:])
    await message.reply_text(f"🔎 Searching for `{query}`...", quote=True)

    encoded_query = urllib.parse.quote(query)
    api_url = f"https://saavn.dev/api/search/songs?query={encoded_query}"

    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("data"):
            await message.reply_text("❌ Song not found.", quote=True)
            return

        song = data["data"][0]
        song_url = song["downloadUrl"][-1]["link"]  # highest quality mp3
        song_title = song["name"]
        song_artist = ", ".join(a["name"] for a in song["primaryArtists"])
        cover_url = song["image"][2]["link"]

        # Clean filename for Windows/Linux safe saving
        file_name = re.sub(r'[\\/*?:"<>|]', "", f"{song_title}.mp3")

        # Download the song file (streamed to avoid memory overhead)
        with requests.get(song_url, stream=True, timeout=15) as r:
            r.raise_for_status()
            with open(file_name, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        # Send audio file with metadata
        await client.send_audio(
            chat_id=message.chat.id,
            audio=file_name,
            caption=f"🎵 **{song_title}**\n👤 *{song_artist}*",
            title=song_title,
            performer=song_artist,
            thumb=cover_url,
            reply_to_message_id=message.message_id
        )

    except requests.RequestException as req_err:
        await message.reply_text(f"⚠️ Network error: {req_err}", quote=True)
    except Exception as e:
        await message.reply_text(f"⚠️ Error: {e}", quote=True)
    finally:
        # Clean up the downloaded file if it exists
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
            except Exception:
                pass
