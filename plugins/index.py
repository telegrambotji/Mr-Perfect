#Credit - TG - @SilentXBotz | Git - NBBotz

import logging
import asyncio
import re
import random
from datetime import datetime, timedelta
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL, API_ID, API_HASH, BOT_TOKEN
from database.ia_filterdb import batch_save_file
from utils import temp
import math

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

BATCH_SIZE = 200      
UPDATE_INTERVAL = 10  
MAX_RETRIES = 3       
DB_BATCH_SIZE = 25
MAX_MESSAGES = 2000000
REQUEST_DELAY = 0.6   
MAX_REQUESTS_PER_MIN = 100  

ADDITIONAL_TOKENS = []
i = 2
while True:
    try:
        token = globals().get(f"BOT_TOKEN{i}", "") or getattr(__import__("info"), f"BOT_TOKEN{i}", "")
        if not token:
            break
        ADDITIONAL_TOKENS.append(token)
        i += 1
    except AttributeError:
        break

NUM_CLIENTS = 1 + len(ADDITIONAL_TOKENS)

print(f"Using {NUM_CLIENTS} Clients For Indexing Files In Database.")

async def index_files_to_db(lst_msg_id, chat, msg, bot, client_id=0, start_id=1, overall_message=None):
    total_files = 0
    saved_files = 0
    duplicate = 0
    errors = 0
    deleted = 0
    no_media = 0
    unsupported = 0
    processed = 0
    start_time = datetime.now()
    current = temp.CURRENT if client_id == 0 else start_id - 1
    temp.CANCEL = False
    total_msgs = lst_msg_id - current
    request_count = 0
    request_window_start = datetime.now()
    
    if total_msgs <= 0:
        return await msg.edit(f"📭 Client {client_id}: No New Messages To Index".title())
    if total_msgs > MAX_MESSAGES:
        return await msg.edit(f"📦 Client {client_id}: Message Limit Exceeded ({total_msgs:,})".title())

    await msg.edit(f"🚀 Total {lst_msg_id} Messages Are splitted Into {NUM_CLIENTS} Clients...".title())

    try:
        media_batch = []
        while current < lst_msg_id and not temp.CANCEL:
            batch_size = min(BATCH_SIZE, lst_msg_id - current)
            if batch_size <= 0:
                break

            if request_count >= MAX_REQUESTS_PER_MIN:
                elapsed = (datetime.now() - request_window_start).total_seconds()
                if elapsed < 60:
                    await asyncio.sleep(60 - elapsed)
                request_count = 0
                request_window_start = datetime.now()
            
            for attempt in range(MAX_RETRIES):
                try:
                    messages = await bot.get_messages(
                        chat_id=chat,
                        message_ids=range(current + 1, current + batch_size + 1),
                        replies=0
                    )
                    request_count += 1
                    break
                except FloodWait as e:
                    print(f"Client {client_id}: FloodWait: Sleeping for {e.value} seconds")
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Client {client_id}: Error fetching messages: {e}")
                    errors += 1
                    if attempt == MAX_RETRIES - 1:
                        return
                    await asyncio.sleep(0.1 * (2 ** attempt))

            await asyncio.sleep(REQUEST_DELAY + random.uniform(0, 0.1))

            for message in messages: 
                if temp.CANCEL:
                    break
                current += 1
                processed += 1

                if message.empty:
                    deleted += 1
                    total_files += 1
                    continue
                elif not message.media:
                    no_media += 1
                    total_files += 1
                    continue
                elif message.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT]:
                    unsupported += 1
                    total_files += 1
                    continue
                media = getattr(message, message.media.value, None)
                if not media:
                    unsupported += 1
                    total_files += 1
                    continue
                media.file_type = message.media.value
                media.caption = message.caption
                media_batch.append((media, message.id))

                if len(media_batch) >= DB_BATCH_SIZE or current >= lst_msg_id:
                    results = await batch_save_file(bot, media_batch)
                    for (media, msg_id), (saved, status) in zip(media_batch, results):
                        total_files += 1
                        if saved:
                            saved_files += 1
                        elif status == 0:
                            duplicate += 1
                        elif status == 2:
                            errors += 1
                    media_batch = []

                if processed % 80 == 0 or current >= lst_msg_id:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    speed = processed / elapsed if elapsed > 0 else 0
                    eta = (total_msgs - processed) / speed if speed > 0 else 0
                    eta_str = str(timedelta(seconds=int(eta)))
                    stats_msg = (
                        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
                        f"✅ Total Files: {overall_message}\n"
                        f"🤖 Client {client_id} Processed: {processed}/{total_msgs} ({processed/total_msgs*100:.1f}%)\n"
                        f"💾 Saved: {saved_files}\n"
                        f"♻️ Duplicate Files : {duplicate}\n"
                        f"🗑️ Deleted Messages: {deleted}\n"
                        f"⛔ Non-Media Messages: {no_media + unsupported} (Unsupported Media - {unsupported})\n"
                        f"❌ Errors : {errors}\n"
                        f"⚡ Speed: {speed:.0f} Files/Sec | ⏱️ ETA: {eta_str}\n"   
                        f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
                    ).title()
                    await msg.edit(stats_msg, reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton('Cancel 🚫', callback_data='index_cancel')]
                    ]))
                    await asyncio.sleep(0)

        elapsed = (datetime.now() - start_time).total_seconds()
        temp.CLIENT_STATS[client_id] = {
            'processed': processed,
            'saved_files': saved_files,
            'duplicate': duplicate,
            'deleted': deleted,
            'no_media': no_media,
            'unsupported': unsupported,
            'errors': errors,
            'elapsed': elapsed
        }

    except asyncio.CancelledError:
        elapsed = (datetime.now() - start_time).total_seconds()
        temp.CLIENT_STATS[client_id] = {
            'processed': processed,
            'saved_files': saved_files,
            'duplicate': duplicate,
            'deleted': deleted,
            'no_media': no_media,
            'unsupported': unsupported,
            'errors': errors,
            'elapsed': elapsed
        }
        print(f"Client {client_id}: Indexing cancelled by user")
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        temp.CLIENT_STATS[client_id] = {
            'processed': processed,
            'saved_files': saved_files,
            'duplicate': duplicate,
            'deleted': deleted,
            'no_media': no_media,
            'unsupported': unsupported,
            'errors': errors,
            'elapsed': elapsed
        }
        print(f"Client {client_id}: Indexing Error: {e}")
        await msg.edit(f"❌ Client {client_id}: Failed: {str(e)}".title())

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        temp.CANCEL = True
        await query.answer("Cancelling Indexing 🚫")
        return 

    _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(int(from_user),
                               f'Your Submission For Indexing {chat} Has Been Declined By Our Moderators.'.title(),
                               reply_to_message_id=int(lst_msg_id))
        return

    msg = query.message
    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(int(from_user),
                               f'Your Submission For Indexing {chat} Has Been Accepted By Our Moderators And Will Be Added Soon.'.title(),
                               reply_to_message_id=int(lst_msg_id))
    await msg.edit(
        f"Starting Indexing with {NUM_CLIENTS} Clients 🚀".title(),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel 🚫', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat) if str(chat).lstrip('-').isdigit() else chat
        lst_msg_id = int(lst_msg_id)       
        total_msgs = lst_msg_id - temp.CURRENT
        overall_message = int(lst_msg_id)
        if total_msgs <= 0:
            return await msg.edit("📭 No New Messages To Index".title())
        if total_msgs > MAX_MESSAGES:
            return await msg.edit(f"📦 Message Limit Exceeded ({total_msgs:,})".title())
        temp.CLIENT_STATS = {}
        temp.CANCEL = False

        additional_clients = []
        for i, token in enumerate(ADDITIONAL_TOKENS, 1):  
            client = Client(f"bot_{i}", api_id=API_ID, api_hash=API_HASH, bot_token=token)
            await client.start()
            additional_clients.append(client)

        messages_per_client = math.ceil(total_msgs / NUM_CLIENTS)
        tasks = []
        start_id = temp.CURRENT + 1
        end_id = min(start_id + messages_per_client - 1, lst_msg_id)
        if start_id <= lst_msg_id:
            tasks.append(index_files_to_db(end_id, chat, msg, bot, 0, start_id, overall_message))

        for i, client in enumerate(additional_clients, 1):
            start_id = temp.CURRENT + 1 + i * messages_per_client
            end_id = min(start_id + messages_per_client - 1, lst_msg_id)
            if start_id > lst_msg_id:
                break
            tasks.append(index_files_to_db(end_id, chat, msg, client, i, start_id, overall_message))

        await asyncio.gather(*tasks)

        total_processed = sum(stats['processed'] for stats in temp.CLIENT_STATS.values())
        total_saved = sum(stats['saved_files'] for stats in temp.CLIENT_STATS.values())
        total_duplicate = sum(stats['duplicate'] for stats in temp.CLIENT_STATS.values())
        total_deleted = sum(stats['deleted'] for stats in temp.CLIENT_STATS.values())
        total_no_media = sum(stats['no_media'] for stats in temp.CLIENT_STATS.values())
        total_unsupported = sum(stats['unsupported'] for stats in temp.CLIENT_STATS.values())
        total_errors = sum(stats['errors'] for stats in temp.CLIENT_STATS.values())
        total_elapsed = max(stats['elapsed'] for stats in temp.CLIENT_STATS.values()) if temp.CLIENT_STATS else 0
        total_speed = total_processed / total_elapsed if total_elapsed > 0 else 0

        stats_msg = (
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰\n"
            f"{'⛔ Indexing Cancelled!' if temp.CANCEL else '✅ Indexing Completed!'}\n"
            f"📊 Total Files: {total_processed:,}\n"
            f"💾 Saved: {total_saved:,}\n"
            f"♻️ Duplicate Files: {total_duplicate:,}\n"
            f"🗑️ Deleted Messages: {total_deleted:,}\n"
            f"⛔ Non-Media Messages: {total_no_media + total_unsupported:,} (Unsupported Media - {total_unsupported:,})\n"
            f"❌ Errors: {total_errors:,}\n"
            f"⚡ Average Speed: {total_speed:.0f}/S\n"
            f"⏱️ Time Taken: {str(timedelta(seconds=int(total_elapsed)))}\n"
            f"▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰"
        ).title()
        await msg.edit(stats_msg)

        for client in additional_clients:
            await client.stop()
            
        temp.CLIENT_STATS = {}
    except Exception as e:
        print(f"Index Error: {e}")
        await msg.edit(f"❌ Failed: {e}".title())

@Client.on_message((filters.forwarded | (filters.regex(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")) & filters.text) & filters.private & filters.incoming)
async def send_for_index(bot, message):
    if message.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(message.text)
        if not match:
            return await message.reply('Invalid Link'.title())
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id = int(("-100" + chat_id))
    elif message.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = message.forward_from_message_id
        chat_id = message.forward_from_chat.username or message.forward_from_chat.id
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await message.reply('This May Be A Private Channel/Group. Make Me An Admin Over There To Index The Files.'.title())
    except (UsernameInvalid, UsernameNotModified):
        return await message.reply('Invalid Link Specified.'.title())
    except Exception as e:
        logger.exception(e)
        return await message.reply(f'Errors - {e}'.title())
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That I Am An Admin In The Channel, If Channel Is Private'.title())
    if k.empty:
        return await message.reply('This May Be A Group And I Am Not An Admin Of The Group.'.title())

    if message.from_user.id in ADMINS:
        buttons = [
            [InlineKeyboardButton('Yes ✅', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
            [InlineKeyboardButton('Close 🚫', callback_data='close_data')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do You Want To Index This Channel/Group ?\n\nChat Id/Username: <code>{chat_id}</code>\nLast Message Id: <code>{last_msg_id}</code>\n\nNeed Setskip 👉🏻 /Setskip'.title(),
            reply_markup=reply_markup)

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make Sure I Am An Admin In The Chat And Have Permission To Invite Users.'.title())
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [
        [InlineKeyboardButton('Accept Index ✅', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')],
        [InlineKeyboardButton('Reject Index 🚫', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(LOG_CHANNEL,
                           f'#Indexrequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat Id/Username - <code> {chat_id}</code>\nLast Message Id - <code>{last_msg_id}</code>\nInvitelink - {link}'.title(),
                           reply_markup=reply_markup)
    await message.reply('Thank You For The Contribution, Wait For My Moderators To Verify The Files.'.title())

@Client.on_message(filters.command('setskip') & filters.user(ADMINS))
async def set_skip_number(bot, message):
    try:
        if ' ' in message.text:
            _, skip = message.text.split(" ")
            try:
                skip = int(skip)
            except:
                return await message.reply("Skip Number Should Be An Integer.".title())
            await message.reply(f"Successfully Set Skip Number As {skip}".title())
            temp.CURRENT = int(skip)
        else:
            await message.reply("Give Me A Skip Number".title())
    except Exception as e:
        print(f"Error In Index Cancel Button: {e}")
        
