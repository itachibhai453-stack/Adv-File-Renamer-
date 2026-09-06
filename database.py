import motor.motor_asyncio
from config import Config

class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users

    def new_user(self, id):
        return {
            "_id": id,
            "upload_mode": "video",
            "metadata": "Renamed By Advanced Bot",
            "thumbnail": None
        }

    async def add_user(self, id):
        user = self.new_user(id)
        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'_id': int(id)})
        return True if user else False

    async def get_user_data(self, id):
        user = await self.col.find_one({'_id': int(id)})
        if not user:
            await self.add_user(id)
            user = await self.col.find_one({'_id': int(id)})
        return user

    async def set_upload_mode(self, id, mode):
        await self.col.update_one({'_id': int(id)}, {'$set': {'upload_mode': mode}})

    async def set_metadata(self, id, metadata):
        await self.col.update_one({'_id': int(id)}, {'$set': {'metadata': metadata}})

    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'thumbnail': file_id}})

    async def delete_thumbnail(self, id):
        await self.col.update_one({'_id': int(id)}, {'$set': {'thumbnail': None}})

db = Database(Config.DB_URL, Config.DB_NAME)
                              
