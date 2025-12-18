from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

def get_database() -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return db