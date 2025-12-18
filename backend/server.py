from fastapi import FastAPI, APIRouter
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from routes import quiz, challenge, chat


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db_instance = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI(title="JATES9 Ecosystem API", version="1.0.0")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Health check endpoint
@api_router.get("/")
async def root():
    return {
        "message": "JATES9 Ecosystem API",
        "version": "1.0.0",
        "status": "running"
    }

@api_router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected"
    }

# Include feature routers
from routes import auth, dashboard

api_router.include_router(quiz.router)
api_router.include_router(challenge.router)
api_router.include_router(chat.router)
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)

# Include the main API router in the app
app.include_router(api_router)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_event():
    logger.info("JATES9 Ecosystem API starting up...")
    logger.info(f"Connected to MongoDB: {os.environ['MONGO_URL']}")

@app.on_event("shutdown")
async def shutdown_db_client():
    logger.info("Shutting down JATES9 Ecosystem API...")
    client.close()