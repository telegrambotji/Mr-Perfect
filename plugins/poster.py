from pyrogram import filters
from pyrogram.types import Message
from AaryanBot import Client as AaryanBot
import aiohttp
import os
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 🔴 Yahan apni TMDb API Key daalo
TMDB_API_KEY = "2937f761448c84e103d3ea8699d5a33c"

# Scheduler start
scheduler = AsyncIOScheduler()
scheduler.start()

# 🟢 Poster Command
@AaryanBot.on_message(filters.command("poster"))
async def fetch_movie_posters(client, message: Message):
    if len(message.command) < 2:
        return await message.reply("Movie ka naam do. Jaise: /poster Avengers Endgame")

    movie_name = message.text.split(" ", 1)[1]
    posters = await get_movie_posters(movie_name)

    if not posters:
        return await message.reply("Koi poster nahi mila.")

    sent_messages = []
    for i, poster_url in enumerate(posters[:5]):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(poster_url) as resp:
                    if resp.status == 200:
                        file_path = f"poster_{i}.jpg"
                        with open(file_path, "wb") as f:
                            f.write(await resp.read())
                        msg = await message.reply_photo(file_path)
                        sent_messages.append(msg)
                        os.remove(file_path)
        except Exception as e:
            print("Error sending poster:", e)
            continue

    # Schedule deletion after 5 minutes
    for msg in sent_messages:
        scheduler.add_job(delete_message, args=[msg.chat.id, msg.message_id], trigger="date", run_date=asyncio.get_event_loop().time() + 300)

# 🔄 Delete Messages
async def delete_message(chat_id, message_id):
    try:
        await AaryanBot.delete_messages(chat_id, message_id)
    except Exception as e:
        print(f"Delete error: {e}")

# 🔍 Fetch Posters from TMDb
async def get_movie_posters(movie_name):
    try:
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_name}"
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as resp:
                data = await resp.json()
                if not data["results"]:
                    return None
                movie_id = data["results"][0]["id"]

            posters_url = f"https://api.themoviedb.org/3/movie/{movie_id}/images?api_key={TMDB_API_KEY}"
            async with session.get(posters_url) as resp:
                posters_data = await resp.json()
                base_url = "https://image.tmdb.org/t/p/original"
                poster_paths = [base_url + p["file_path"] for p in posters_data.get("posters", [])]
                return poster_paths
    except Exception as e:
        print("Poster fetch error:", e)
        return None
