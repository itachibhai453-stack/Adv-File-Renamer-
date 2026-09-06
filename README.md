# 🚀 Advanced Telegram File Renamer Bot

An advanced, feature-rich Telegram Bot built using **Pyrogram v2** and **FFmpeg**. It allows users to rename files, extract or remove media streams (audio/subtitle tracks), edit metadata, set custom thumbnails, and toggle between Video and Document upload modes.

---

## ✨ Features

- 📝 **File Renaming:** Quick renaming for documents, videos, and audio files.
- 🖼️ **Custom Thumbnail:** Set, view, and delete custom thumbnails.
- 🎬 **Stream Extract:** Extract specific audio or subtitle tracks from video files.
- ✂️ **Stream Remove:** Remove unwanted audio or subtitle streams.
- 🏷️ **Metadata Editor:** Custom metadata title tag support via FFmpeg.
- ⚙️ **Dual Upload Modes:** Seamlessly switch between **Video** mode (with duration & thumbnail) and **Document** mode.
- 🐳 **Docker-Ready:** Optimized Docker setup for zero-friction deployment on Render, Heroku, or VPS.

---

## 🛠️ Repository Structure

```text
file-renamer-bot/
├── bot.py              # Main bot entry point & command handlers
├── config.py           # Environment variables configuration
├── Dockerfile          # Docker image configuration (includes FFmpeg)
├── render.yaml         # Blueprint for Render deployment
├── requirements.txt    # Python dependencies
└── README.md           # Documentation# Adv-File-Renamer-
🚀 Deployment
Option 1: Render (Recommended)
Fork or Push this repository to your GitHub account.
Go to Render Dashboard and click New + -> Background Worker.
Connect your GitHub repository.
Set the Runtime to Docker.
Add your Environment Variables (API_ID, API_HASH, BOT_TOKEN) under Environment.
Click Create Background Worker to deploy.
Option 2: Docker / VPS
Run the bot directly on any Linux server with Docker installed:
🤖 Bot Commands & Usage
/start - Start the bot & view the main menu.
/settings - Manage upload mode and custom metadata settings.
Send Photo: Set a custom thumbnail.
Send Video/Document: Trigger the action menu (Rename, Extract Streams, Remove Streams).
📄 License
Distributed under the MIT License. Feel free to modify and adapt for your own projects.
