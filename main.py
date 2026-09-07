import os
import sys
import time
import math
import shutil
import zipfile
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    Message, 
    CallbackQuery
)
from config import Config

app = Client(
    "AdvFileRenamerBot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# ----------------- IN-MEMORY USER SETTINGS DATABASE -----------------
USER_SETTINGS = {}

def get_user_settings(user_id):
    if user_id not in USER_SETTINGS:
        USER_SETTINGS[user_id] = {
            "default_upload": "Telegram",  # Options: Telegram / GoFile
            "tg_tools": True,
            "gofile_tools": False,
            "extra_tools": False,
            "video_tools": True,
            "sample_video": False,
            "screenshot": False,
            # Watermark Settings
            "wm_position": "bottom_right", # top_left, top_right, bottom_left, bottom_right
            "wm_size": 25,                 # Percentage (e.g. 25%)
            # Extra Tools Settings
            "extract_zip": False,
            "split_file": False,
            "split_size_mb": 2000          # Split size in MB
        }
    return USER_SETTINGS[user_id]


# ----------------- PROGRESS BAR HELPER -----------------
def humanbytes(size):
    if not size:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

async def progress_bar(current, total, status_msg, start_time, action_name):
    now = time.time()
    diff = now - start_time
    if round(diff % 4) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff if diff > 0 else 0
        elapsed_time = round(diff)
        time_to_completion = round((total - current) / speed) if speed > 0 else 0

        progress = "".join(["■" for _ in range(math.floor(percentage / 10))]) + \
                   "".join(["□" for _ in range(10 - math.floor(percentage / 10))])

        tmp = (
            f"**{action_name}...**\n\n"
            f"[{progress}] {percentage:.2f}%\n"
            f"**Processed:** {humanbytes(current)} / {humanbytes(total)}\n"
            f"**Speed:** {humanbytes(speed)}/s\n"
            f"**ETA:** {time_to_completion}s"
        )
        try:
            await status_msg.edit_text(tmp)
        except Exception:
            pass


# ----------------- SETTINGS MENU UI (EXACT MATCH TO SS) -----------------
def build_settings_keyboard(user_id):
    s = get_user_settings(user_id)
    
    upload_text = f"Default Upload | {s['default_upload']}"
    video_tools_text = f"📹 Video Tools {'✅' if s['video_tools'] else '❌'}"
    extra_tools_text = f"🛠 Extra Tools {'✅' if s['extra_tools'] else '❌'}"
    sample_text = f"🎞 Sample Video {'✅' if s['sample_video'] else '❌'}"
    ss_text = f"📸 Screenshot {'✅' if s['screenshot'] else '❌'}"

    keyboard = [
        [InlineKeyboardButton(upload_text, callback_data="toggle_upload")],
        [
            InlineKeyboardButton("📺 TG Tools", callback_data="tool_tg"),
            InlineKeyboardButton("📂 GoFile Tools", callback_data="tool_gofile")
        ],
        [InlineKeyboardButton("🤖 Bots for Upload", callback_data="tool_bots")],
        [
            InlineKeyboardButton(extra_tools_text, callback_data="toggle_extra"),
            InlineKeyboardButton(video_tools_text, callback_data="toggle_video")
        ],
        [
            InlineKeyboardButton(sample_text, callback_data="toggle_sample"),
            InlineKeyboardButton(ss_text, callback_data="toggle_ss")
        ],
        [
            InlineKeyboardButton("🔄 Reset All", callback_data="reset_settings"),
            InlineKeyboardButton("❌ Close", callback_data="close_menu")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

@app.on_message(filters.command("settings") | filters.command("start"))
async def settings_command(client, message: Message):
    user_id = message.from_user.id
    settings = get_user_settings(user_id)
    text = (
        f"**Settings for {message.from_user.first_name}**\n\n"
        f"Default Upload is **{settings['default_upload']}**"
    )
    await message.reply_text(text, reply_markup=build_settings_keyboard(user_id))

@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    s = get_user_settings(user_id)

    if data == "toggle_upload":
        s["default_upload"] = "GoFile" if s["default_upload"] == "Telegram" else "Telegram"
    elif data == "toggle_video":
        s["video_tools"] = not s["video_tools"]
    elif data == "toggle_extra":
        s["extra_tools"] = not s["extra_tools"]
    elif data == "toggle_sample":
        s["sample_video"] = not s["sample_video"]
    elif data == "toggle_ss":
        s["screenshot"] = not s["screenshot"]
    elif data == "reset_settings":
        USER_SETTINGS[user_id] = get_user_settings(0)
    elif data == "close_menu":
        await query.message.delete()
        return

    text = (
        f"**Settings for {query.from_user.first_name}**\n\n"
        f"Default Upload is **{s['default_upload']}**"
    )
    await query.message.edit_text(text, reply_markup=build_settings_keyboard(user_id))


# ----------------- FFMPEG ENGINE (STREAM REMOVE, EXTRACT, ADD, WATERMARK) -----------------
async def run_shell_command(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode

async def ffmpeg_extract_stream(input_file, output_file, stream_type="audio"):
    """
    Extracts Audio or Subtitle stream from video
    stream_type: 'audio' (-vn -acodec copy) or 'subtitle' (-vn -an -scodec copy)
    """
    if stream_type == "audio":
        cmd = f'ffmpeg -i "{input_file}" -vn -acodec copy "{output_file}" -y'
    elif stream_type == "subtitle":
        cmd = f'ffmpeg -i "{input_file}" -vn -an -c:s copy "{output_file}" -y'
    await run_shell_command(cmd)

async def ffmpeg_add_audio(video_file, audio_file, output_file):
    """Adds or merges extra audio stream into video"""
    cmd = f'ffmpeg -i "{video_file}" -i "{audio_file}" -c:v copy -c:a copy -map 0:v:0 -map 1:a:0 "{output_file}" -y'
    await run_shell_command(cmd)

async def ffmpeg_apply_watermark(video_file, wm_image_path, output_file, position="bottom_right", size_pct=25):
    """Applies logo watermark with custom scaling & direction position"""
    pos_map = {
        "top_left": "10:10",
        "top_right": "main_w-overlay_w-10:10",
        "bottom_left": "10:main_h-overlay_h-10",
        "bottom_right": "main_w-overlay_w-10:main_h-overlay_h-10"
    }
    overlay = pos_map.get(position, "main_w-overlay_w-10:main_h-overlay_h-10")
    
    cmd = (
        f'ffmpeg -i "{video_file}" -i "{wm_image_path}" '
        f'-filter_complex "[1:v]scale=iw*{size_pct}/100:-1[wm];[0:v][wm]overlay={overlay}" '
        f'-c:a copy "{output_file}" -y'
    )
    await run_shell_command(cmd)


# ----------------- ZIP & SPLIT UTILITIES -----------------
def extract_zip_file(zip_path, extract_to_dir):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to_dir)

def split_file(file_path, chunk_size_mb=1900):
    """Splits a file into chunk_size_mb parts if oversized"""
    chunk_size = chunk_size_mb * 1024 * 1024
    part_num = 1
    split_files = []
    
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            part_name = f"{file_path}.part{part_num:03d}"
            with open(part_name, 'wb') as chunk_file:
                chunk_file.write(chunk)
            split_files.append(part_name)
            part_num += 1
            
    return split_files


# ----------------- MAIN PROCESSING HANDLER -----------------
@app.on_message(filters.document | filters.video | filters.audio)
async def process_incoming_file(client, message: Message):
    user_id = message.from_user.id
    s = get_user_settings(user_id)
    
    user_dir = os.path.join(Config.DOWNLOAD_DIR, str(user_id))
    os.makedirs(user_dir, exist_ok=True)
    
    status_msg = await message.reply_text("📥 **Starting Download...**")
    start_time = time.time()

    # 1. DOWNLOAD FILE WITH PROGRESS BAR
    file_path = await message.download(
        file_name=os.path.join(user_dir, ""),
        progress=progress_bar,
        progress_args=(status_msg, start_time, "📥 Downloading File")
    )

    processed_files = [file_path]

    # 2. ZIP EXTRACTION OPTION
    if s["extra_tools"] and file_path.endswith(".zip"):
        await status_msg.edit_text("📦 **Extracting ZIP File...**")
        extract_folder = os.path.join(user_dir, "extracted")
        os.makedirs(extract_folder, exist_ok=True)
        extract_zip_file(file_path, extract_folder)
        
        extracted_list = []
        for root, _, files in os.walk(extract_folder):
            for file in files:
                extracted_list.append(os.path.join(root, file))
        if extracted_list:
            processed_files = extracted_list

    # 3. VIDEO / STREAM / WATERMARK PROCESSING
    final_ready_files = []
    for cur_file in processed_files:
        if s["video_tools"] and (cur_file.endswith(".mp4") or cur_file.endswith(".mkv")):
            await status_msg.edit_text("⚙️ **Processing Video Tools (Streams / Watermark)...**")
            out_v = f"{cur_file}_mod.mkv"
            
            # Example: Apply direction & scale watermark if logo exists
            wm_file = "watermark.png"
            if os.path.exists(wm_file):
                await ffmpeg_apply_watermark(
                    cur_file, wm_file, out_v, 
                    position=s["wm_position"], size_pct=s["wm_size"]
                )
            else:
                # Default stream copy
                cmd = f'ffmpeg -i "{cur_file}" -c copy "{out_v}" -y'
                await run_shell_command(cmd)
                
            if os.path.exists(out_v):
                final_ready_files.append(out_v)
            else:
                final_ready_files.append(cur_file)
        else:
            final_ready_files.append(cur_file)

    # 4. AUTO-RENAMER PROMPT (EVERY TASK COMPLETED -> ASK FOR RENAME)
    renamed_files = []
    for cur_file in final_ready_files:
        orig_name = os.path.basename(cur_file)
        await status_msg.edit_text(
            f"✨ **Work Finished for:** `{orig_name}`\n\n"
            f"✏️ **Please send the NEW RENAME FILE NAME now:**"
        )
        
        try:
            # Wait 60 seconds for user text input
            response: Message = await client.wait_for_message(
                chat_id=message.chat.id,
                filters=filters.text & filters.user(user_id),
                timeout=60
            )
            new_name = response.text.strip()
        except asyncio.TimeoutError:
            new_name = orig_name
            await message.reply_text("⏰ **Timeout! Using original filename.**")

        # Perform File Rename
        target_path = os.path.join(os.path.dirname(cur_file), new_name)
        os.rename(cur_file, target_path)
        renamed_files.append(target_path)

    # 5. SPLIT FILE OPTION (IF ENABLED OR >2GB)
    upload_queue = []
    for cur_file in renamed_files:
        file_size_mb = os.path.getsize(cur_file) / (1024 * 1024)
        if s["split_file"] or file_size_mb > 2000:
            await status_msg.edit_text("✂️ **Splitting large file...**")
            parts = split_file(cur_file, chunk_size_mb=s["split_size_mb"])
            upload_queue.extend(parts)
        else:
            upload_queue.append(cur_file)

    # 6. FINAL UPLOAD WITH PROGRESS BAR
    await status_msg.edit_text("📤 **Starting Upload Process...**")
    for up_file in upload_queue:
        up_start = time.time()
        file_title = os.path.basename(up_file)
        
        await client.send_document(
            chat_id=message.chat.id,
            document=up_file,
            caption=f"✅ **Processed File:** `{file_title}`",
            progress=progress_bar,
            progress_args=(status_msg, up_start, f"📤 Uploading {file_title}")
        )

    # CLEANUP USER TEMP FOLDER
    shutil.rmtree(user_dir, ignore_errors=True)
    await status_msg.delete()


if __name__ == "__main__":
    print("Bot started running...")
    app.run()
        
