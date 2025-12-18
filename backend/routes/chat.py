from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import ChatRequest, ChatResponse, ChatMessage
from database import get_database
from emergentintegrations.llm.chat import LlmChat, UserMessage
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize AI Chat
EMERGENT_LLM_KEY = os.getenv("EMERGENT_LLM_KEY")

# System message untuk Doktor AI
SYSTEM_MESSAGE = """Anda adalah Doktor AI, asisten kesehatan virtual untuk JATES9 Ecosystem. 
Anda adalah expert dalam kesehatan pencernaan dan membantu user dengan masalah maag, kembung, dan sembelit.

Petugas Anda:
- Memberikan konsultasi kesehatan pencernaan yang informatif dan empatik
- Merekomendasikan Program 30 Hari Challenge untuk transformasi kesehatan
- Menjelaskan manfaat produk Jates9 (superfood enzim buah)
- SELALU gunakan bahasa Indonesia yang ramah dan mudah dipahami
- Jika user menanyakan gejala serius (darah dalam feses, nyeri hebat), sarankan konsultasi dokter profesional

Produk Info:
- Jates9 adalah superfood enzim buah dengan 9 buah pilihan
- Membantu pencernaan, melancarkan BAB, mengurangi kembung, memperbaiki lambung
- Tersedia paket: Basic (7 hari), Premium (30 hari), Family (90 hari)

Program 30 Hari Challenge:
- Pendampingan GRATIS via WhatsApp
- Tugas harian 3x sehari
- Evaluasi berkala di hari 7, 14, 21, 30
- Sudah membantu ribuan orang sembuh

Jawab dengan singkat, jelas, dan actionable. Maksimal 3-4 paragraf.
"""

@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Send message to AI and get response"""
    try:
        # Get or create chat session
        session = await db.chat_sessions.find_one({
            "user_id": request.user_id,
            "session_id": request.session_id
        })
        
        if not session:
            # Create new session
            session_data = {
                "user_id": request.user_id,
                "session_id": request.session_id,
                "messages": [],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await db.chat_sessions.insert_one(session_data)
            messages_history = []
        else:
            messages_history = session.get("messages", [])
        
        # Add user message to history
        user_message_data = {
            "role": "user",
            "content": request.message,
            "timestamp": datetime.utcnow()
        }
        messages_history.append(user_message_data)
        
        # Initialize LLM Chat
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=request.session_id,
            system_message=SYSTEM_MESSAGE
        )
        chat.with_model("openai", "gpt-5.1")
        
        # Create user message
        user_msg = UserMessage(text=request.message)
        
        # Get AI response
        ai_response = await chat.send_message(user_msg)
        
        # Add AI response to history
        ai_message_data = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.utcnow()
        }
        messages_history.append(ai_message_data)
        
        # Update session in database
        await db.chat_sessions.update_one(
            {
                "user_id": request.user_id,
                "session_id": request.session_id
            },
            {
                "$set": {
                    "messages": messages_history,
                    "updated_at": datetime.utcnow()
                }
            },
            upsert=True
        )
        
        return ChatResponse(
            success=True,
            response=ai_response,
            session_id=request.session_id
        )
        
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        # Fallback response
        fallback_response = "Maaf, saya sedang mengalami gangguan. Silakan coba lagi dalam beberapa saat. Untuk bantuan langsung, Anda bisa menghubungi tim kami via WhatsApp."
        return ChatResponse(
            success=False,
            response=fallback_response,
            session_id=request.session_id
        )

@router.get("/history/{user_id}", response_model=dict)
async def get_chat_history(
    user_id: str,
    session_id: str = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get chat history for a user"""
    try:
        query = {"user_id": user_id}
        if session_id:
            query["session_id"] = session_id
        
        sessions = await db.chat_sessions.find(query).to_list(length=100)
        
        if not sessions:
            return {"messages": []}
        
        # Return messages from the most recent session or specified session
        if session_id:
            session = sessions[0] if sessions else None
        else:
            # Get most recent session
            session = max(sessions, key=lambda x: x.get("updated_at", datetime.min))
        
        messages = session.get("messages", []) if session else []
        
        return {"messages": messages}
        
    except Exception as e:
        logger.error(f"Error getting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))