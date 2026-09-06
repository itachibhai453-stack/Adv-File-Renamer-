import os

class Config:
    API_ID = int(os.environ.get("API_ID", "1234567"))
    API_HASH = os.environ.get("API_HASH", "your_api_hash_here")
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token_here")
    
    # Optional Admin ID
    ADMIN = [int(admin) if admin.isdigit() else admin for admin in os.environ.get('ADMIN', '').split()]
    
    # Download Location
    DOWNLOAD_LOCATION = "./DOWNLOADS"
  
