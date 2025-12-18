from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import QuizAnswer, QuizResult
from database import get_database
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quiz", tags=["quiz"])

@router.post("/submit", response_model=dict)
async def submit_quiz(
    quiz_answer: QuizAnswer,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Submit quiz answers and get personalized recommendation"""
    try:
        # Check if user exists
        user = await db.users.find_one({"phone_number": quiz_answer.phone_number})
        
        if not user:
            # Create new user
            user_data = {
                "phone_number": quiz_answer.phone_number,
                "name": quiz_answer.name,
                "health_type": quiz_answer.health_type,
                "health_score": quiz_answer.score,
                "quiz_date": quiz_answer.timestamp,
                "challenge_enrolled": False,
                "created_at": quiz_answer.timestamp,
                "updated_at": quiz_answer.timestamp
            }
            result = await db.users.insert_one(user_data)
            user_id = str(result.inserted_id)
        else:
            # Update existing user
            user_id = str(user["_id"])
            await db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "name": quiz_answer.name,
                        "health_type": quiz_answer.health_type,
                        "health_score": quiz_answer.score,
                        "quiz_date": quiz_answer.timestamp,
                        "updated_at": quiz_answer.timestamp
                    }
                }
            )
        
        # Generate recommendation based on health type
        recommendations = {
            "A": "Program 30 Hari untuk Tipe A - Sembelit. Fokus pada serat dan hidrasi.",
            "B": "Program 30 Hari untuk Tipe B - Kembung. Fokus pada enzim pencernaan.",
            "C": "Program 30 Hari untuk Tipe C - Maag. Fokus pada penyembuhan lambung.",
            "ABC": "Program 30 Hari komprehensif untuk masalah pencernaan kompleks."
        }
        
        suggested_products = {
            "A": "jates9_premium",
            "B": "jates9_premium",
            "C": "jates9_premium",
            "ABC": "jates9_family"
        }
        
        recommendation = recommendations.get(quiz_answer.health_type, "Program 30 Hari umum")
        suggested_product = suggested_products.get(quiz_answer.health_type, "jates9_premium")
        
        # Save quiz result
        quiz_result_data = {
            "user_id": user_id,
            "answers": quiz_answer.answers,
            "score": quiz_answer.score,
            "health_type": quiz_answer.health_type,
            "recommendation": recommendation,
            "suggested_product": suggested_product,
            "timestamp": quiz_answer.timestamp
        }
        await db.quiz_results.insert_one(quiz_result_data)
        
        return {
            "success": True,
            "user_id": user_id,
            "recommendation": recommendation,
            "suggested_product": suggested_product
        }
        
    except Exception as e:
        logger.error(f"Error submitting quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/result/{user_id}", response_model=dict)
async def get_quiz_result(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get quiz result for a specific user"""
    try:
        result = await db.quiz_results.find_one({"user_id": user_id})
        
        if not result:
            raise HTTPException(status_code=404, detail="Quiz result not found")
        
        return {
            "score": result["score"],
            "health_type": result["health_type"],
            "timestamp": result["timestamp"],
            "recommendation": result.get("recommendation", "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz result: {e}")
        raise HTTPException(status_code=500, detail=str(e))