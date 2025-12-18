from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv
from pathlib import Path
import os

# Load environment variables
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'jates9')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

def get_database() -> AsyncIOMotorDatabase:
    """Dependency to get database instance"""
    return db