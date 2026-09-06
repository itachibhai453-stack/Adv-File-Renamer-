import os

class Config:
    API_ID = int(os.environ.get("API_ID", "1234567"))
    API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
    
    # MongoDB Database Details
    DB_URL = os.environ.get("DB_URL", "mongodb+srv://username:password@cluster.mongodb.net/myDatabase")
    DB_NAME = os.environ.get("DB_NAME", "RenamerBotDB")
    
    # Optional Admin ID
    ADMIN = [int(admin) if admin.isdigit() else admin for admin in os.environ.get('ADMIN', '').split()]
    
    # Download Location
    DOWNLOAD_LOCATION = "./DOWNLOADS"
    
