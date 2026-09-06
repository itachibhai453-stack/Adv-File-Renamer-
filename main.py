import os
import asyncio
import subprocess
import json
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from config import Config
from database import db

bot = Client(
    "RenamerBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# Temporary session data for active processes
TEMP_DATA = {}

os.makedirs(Config.DOWNLOAD_LOCATION, exist_ok=True)
os.makedirs("./THUMBS", exist_ok=True)

# --- HELPER FUNCTIONS ---

def get_streams_info(file_path):
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        return json.loads(result.stdout).get("streams", [])
    except Exception:
        return []

def get_media_duration(file_path):
    try:
        parser = createParser(file_path)
        if not parser:
            return 0
        with parser:
            metadata = extractMetadata(parser)
            if metadata and metadata.has("duration"):
                return metadata.get("duration").seconds
    except Exception:
        pass
    return 0

# --- COMMAND HANDLERS ---

@bot.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    if not await db.is_user_exist(user_id):
        await db.add_user(user_id)
        
    welcome_text = (
        f"👋 Hi **{message.from_user.first_name}**!\n\n"
        "I am an **Advanced File Renamer Bot** with extra features:\n"
        "• Rename Files & Media\n"
        "• Custom Thumbnail Support (Saved in MongoDB)\n"
        "• Change Upload Mode (Video / Document)\n"
        "• Extract Audio/Subtitle Streams\n"
        "• Remove Audio/Subtitle Streams\n"
        "• Custom Metadata Editor\n\n"
        "Just send me any File or Video to begin!"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings_menu"),
         InlineKeyboardButton("🖼️ View Thumbnail", callback_data="view_thumb")],
        [InlineKeyboardButton("🗑️ Delete Thumbnail", callback_data="del_thumb")]
    ])
    
    await message.reply_text(welcome_text, reply_markup=buttons)

@bot.on_message(filters.command("settings") & filters.private)
async def settings_command(client: Client, message: Message):
    await show_settings(message)

async def show_settings(message_or_query):
    user_id = message_or_query.from_user.id if isinstance(message_or_query, Message) else message_or_query.from_user.id
    user_data = await db.get_user_data(user_id)
    
    mode = user_data.get("upload_mode", "video").capitalize()
    meta = user_data.get("metadata", "Renamed By Advanced Bot")
    
    text = (
        "⚙️ **Bot Settings**\n\n"
        f"• **Current Upload Mode:** `{mode}`\n"
        f"• **Current Metadata Title:** `{meta}`"
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Mode: {mode}", callback_data="toggle_mode")],
        [InlineKeyboardButton("✏️ Change Metadata", callback_data="set_metadata")]
    ])
    
    if isinstance(message_or_query, Message):
        await message_or_query.reply_text(text, reply_markup=buttons)
    else:
        await message_or_query.message.edit_text(text, reply_markup=buttons)

# --- THUMBNAIL MANAGEMENT (MONGODB) ---

@bot.on_message(filters.photo & filters.private)
async def save_thumbnail(client: Client, message: Message):
    user_id = message.from_user.id
    file_id = message.photo.file_id
    await db.set_thumbnail(user_id, file_id)
    await message.reply_text("✅ **Custom Thumbnail Saved to Database!**")

# --- MAIN MEDIA HANDLER ---

@bot.on_message((filters.document | filters.video | filters.audio) & filters.private)
async def handle_media(client: Client, message: Message):
    user_id = message.from_user.id
    TEMP_DATA[user_id] = {"current_file": message}
    
    file = message.document or message.video or message.audio
    filename = file.file_name if hasattr(file, "file_name") and file.file_name else "Unknown_File"
    
    text = f"📂 **File Received:** `{filename}`\n\nChoose an action below:"
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Rename", callback_data="act_rename"),
         InlineKeyboardButton("🎞️ Extract Stream", callback_data="act_extract")],
        [InlineKeyboardButton("✂️ Remove Stream", callback_data="act_remove")],
        [InlineKeyboardButton("❌ Cancel", callback_data="act_cancel")]
    ])
    
    await message.reply_text(text, reply_markup=buttons)

# --- CALLBACK QUERY HANDLER ---

@bot.on_callback_query()
async def callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data

    if data == "settings_menu":
        await show_settings(query)
        
    elif data == "toggle_mode":
        user_data = await db.get_user_data(user_id)
        current = user_data.get("upload_mode", "video")
        new_mode = "document" if current == "video" else "video"
        await db.set_upload_mode(user_id, new_mode)
        await show_settings(query)

    elif data == "set_metadata":
        await query.message.edit_text("Send your custom metadata title as a text reply now.")
        TEMP_DATA.setdefault(user_id, {})["awaiting_meta"] = True

    elif data == "view_thumb":
        user_data = await db.get_user_data(user_id)
        thumb_id = user_data.get("thumbnail")
        if thumb_id:
            await query.message.reply_photo(photo=thumb_id, caption="Your Saved Thumbnail")
        else:
            await query.answer("❌ No thumbnail found in Database!", show_alert=True)

    elif data == "del_thumb":
        await db.delete_thumbnail(user_id)
        await query.answer("🗑️ Thumbnail Deleted from Database!", show_alert=True)

    elif data == "act_cancel":
        await query.message.delete()

    elif data == "act_rename":
        await query.message.edit_text("📝 **Send me the new file name (with extension):**")
        TEMP_DATA.setdefault(user_id, {})["awaiting_rename"] = True

    elif data in ["act_extract", "act_remove"]:
        msg = TEMP_DATA.get(user_id, {}).get("current_file")
        if not msg:
            await query.answer("Expired session!", show_alert=True)
            return
        
        status = await query.message.edit_text("⏳ **Downloading media to inspect streams...**")
        file_path = await msg.download(file_name=f"{Config.DOWNLOAD_LOCATION}/{user_id}_temp")
        TEMP_DATA[user_id]["temp_file"] = file_path
        
        streams = get_streams_info(file_path)
        if not streams:
            await status.edit_text("❌ No valid audio/video/subtitle streams found.")
            return

        buttons = []
        for idx, s in enumerate(streams):
            codec_type = s.get("codec_type", "unknown").upper()
            codec_name = s.get("codec_name", "unknown")
            lang = s.get("tags", {}).get("language", "und")
            btn_text = f"Stream #{idx} [{codec_type}] - {codec_name} ({lang})"
            
            action_code = "ext" if data == "act_extract" else "rem"
            buttons.append([InlineKeyboardButton(btn_text, callback_data=f"str_{action_code}_{idx}")])
        
        await status.edit_text(
            f"Select a stream to {'Extract' if data == 'act_extract' else 'Remove'}:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("str_"):
        parts = data.split("_")
        action = parts[1]
        stream_idx = int(parts[2])
        file_path = TEMP_DATA.get(user_id, {}).get("temp_file")

        if not file_path or not os.path.exists(file_path):
            await query.answer("File session expired!", show_alert=True)
            return

        status = await query.message.edit_text("⚙️ **Processing stream with FFmpeg...**")
        output_path = f"{file_path}_processed.mp4"

        if action == "ext":
            cmd = ["ffmpeg", "-y", "-i", file_path, "-map", f"0:{stream_idx}", "-c", "copy", output_path]
        else: # rem
            cmd = ["ffmpeg", "-y", "-i", file_path, "-map", "0", "-map", f"-0:{stream_idx}", "-c", "copy", output_path]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if proc.returncode != 0 or not os.path.exists(output_path):
            await status.edit_text("❌ **Stream processing failed!**")
            return

        await upload_processed_file(client, query.message, user_id, output_path, "Processed_Stream.mp4")
        
        # Cleanup
        if os.path.exists(file_path): os.remove(file_path)
        if os.path.exists(output_path): os.remove(output_path)

# --- TEXT INPUT LISTENER (RENAME & METADATA) ---

@bot.on_message(filters.text & filters.private & ~filters.command(["start", "settings"]))
async def text_handler(client: Client, message: Message):
    user_id = message.from_user.id

    if TEMP_DATA.get(user_id, {}).get("awaiting_meta"):
        await db.set_metadata(user_id, message.text)
        TEMP_DATA[user_id]["awaiting_meta"] = False
        await message.reply_text(f"✅ **Metadata updated in DB to:** `{message.text}`")
        return

    if TEMP_DATA.get(user_id, {}).get("awaiting_rename"):
        TEMP_DATA[user_id]["awaiting_rename"] = False
        new_name = message.text
        msg = TEMP_DATA.get(user_id, {}).get("current_file")

        if not msg:
            await message.reply_text("❌ No active file found to rename!")
            return

        status = await message.reply_text("⏳ **Downloading file...**")
        download_path = await msg.download(file_name=f"{Config.DOWNLOAD_LOCATION}/{new_name}")
        
        # Apply Metadata Title via FFmpeg from Database
        user_data = await db.get_user_data(user_id)
        meta_title = user_data.get("metadata", "Renamed By Advanced Bot")
        
        meta_output = f"{download_path}_meta.mp4"
        cmd = [
            "ffmpeg", "-y", "-i", download_path,
            "-metadata", f"title={meta_title}",
            "-c", "copy", meta_output
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        final_path = meta_output if os.path.exists(meta_output) else download_path

        await status.edit_text("📤 **Uploading file...**")
        await upload_processed_file(client, status, user_id, final_path, new_name)

        # Clean local files
        if os.path.exists(download_path): os.remove(download_path)
        if os.path.exists(meta_output): os.remove(meta_output)

# --- UPLOAD HELPER ---

async def upload_processed_file(client, status_msg, user_id, file_path, file_name):
    user_data = await db.get_user_data(user_id)
    mode = user_data.get("upload_mode", "video")
    thumb_id = user_data.get("thumbnail")
    
    # Download thumbnail locally if exists in DB
    thumb_path = None
    if thumb_id:
        try:
            thumb_path = await client.download_media(thumb_id, file_name=f"./THUMBS/{user_id}.jpg")
        except Exception:
            thumb_path = None

    duration = get_media_duration(file_path)

    if mode == "video":
        await client.send_video(
            chat_id=user_id,
            video=file_path,
            caption=f"**File Name:** `{file_name}`",
            thumb=thumb_path,
            duration=duration,
            file_name=file_name
        )
    else:
        await client.send_document(
            chat_id=user_id,
            document=file_path,
            caption=f"**File Name:** `{file_name}`",
            thumb=thumb_path,
            file_name=file_name
        )

    if thumb_path and os.path.exists(thumb_path):
        os.remove(thumb_path)

    await status_msg.delete()

# Run Bot
if __name__ == "__main__":
    bot.run()
    
        
