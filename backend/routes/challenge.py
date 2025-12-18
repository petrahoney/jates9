from fastapi import APIRouter, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from models import ChallengeEnrollment, CheckIn, Challenge, ChallengeTask
from database import get_database
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/challenge", tags=["challenge"])

@router.post("/enroll", response_model=dict)
async def enroll_challenge(
    enrollment: ChallengeEnrollment,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Enroll user in 30 Day Challenge"""
    try:
        # Find or create user
        user = await db.users.find_one({"phone_number": enrollment.phone_number})
        
        if not user:
            # Create new user
            user_data = {
                "phone_number": enrollment.phone_number,
                "name": enrollment.name,
                "health_type": enrollment.health_type,
                "challenge_enrolled": True,
                "challenge_start_date": enrollment.start_date,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.users.insert_one(user_data)
            user_id = str(result.inserted_id)
        else:
            user_id = str(user["_id"])
            # Update user enrollment status
            await db.users.update_one(
                {"_id": user["_id"]},
                {
                    "$set": {
                        "challenge_enrolled": True,
                        "challenge_start_date": enrollment.start_date,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
        
        # Check if challenge already exists
        existing_challenge = await db.challenges.find_one({"user_id": user_id, "status": "active"})
        
        if existing_challenge:
            challenge_id = str(existing_challenge["_id"])
        else:
            # Create new challenge
            challenge_data = {
                "user_id": user_id,
                "current_day": 1,
                "start_date": enrollment.start_date,
                "completed_tasks": [],
                "streak_days": 0,
                "status": "active",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.challenges.insert_one(challenge_data)
            challenge_id = str(result.inserted_id)
        
        return {
            "success": True,
            "challenge_id": challenge_id,
            "user_id": user_id,
            "start_date": enrollment.start_date.isoformat(),
            "whatsapp_confirmed": True,
            "message": "Selamat! Anda telah terdaftar di Program 30 Hari. Cek WhatsApp untuk instruksi."
        }
        
    except Exception as e:
        logger.error(f"Error enrolling in challenge: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/progress/{user_id}", response_model=dict)
async def get_progress(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's challenge progress"""
    try:
        challenge = await db.challenges.find_one({"user_id": user_id, "status": "active"})
        
        if not challenge:
            raise HTTPException(status_code=404, detail="Active challenge not found")
        
        # Calculate current day based on start date
        start_date = challenge["start_date"]
        days_passed = (datetime.utcnow() - start_date).days + 1
        current_day = min(days_passed, 30)
        
        # Update current day
        await db.challenges.update_one(
            {"_id": challenge["_id"]},
            {"$set": {"current_day": current_day, "updated_at": datetime.utcnow()}}
        )
        
        completed_tasks = challenge.get("completed_tasks", [])
        total_tasks = 90  # 30 days * 3 tasks per day
        
        # Determine next task
        times = ["morning", "noon", "evening"]
        next_task = None
        for time in times:
            task_exists = any(
                t["day"] == current_day and t["time"] == time
                for t in completed_tasks
            )
            if not task_exists:
                next_task = {
                    "day": current_day,
                    "time": time,
                    "task": f"Tugas {time} hari ke-{current_day}",
                    "completed": False
                }
                break
        
        return {
            "current_day": current_day,
            "completed_tasks": len(completed_tasks),
            "total_tasks": total_tasks,
            "streak_days": challenge.get("streak_days", 0),
            "next_task": next_task
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/checkin", response_model=dict)
async def check_in(
    checkin: CheckIn,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Check-in for daily task completion"""
    try:
        challenge = await db.challenges.find_one({"user_id": checkin.user_id, "status": "active"})
        
        if not challenge:
            raise HTTPException(status_code=404, detail="Active challenge not found")
        
        if checkin.task_completed:
            # Add completed task
            task = {
                "day": checkin.day,
                "time": checkin.time,
                "task": checkin.notes or f"Tugas {checkin.time} hari ke-{checkin.day}",
                "completed_at": datetime.utcnow()
            }
            
            # Update challenge
            completed_tasks = challenge.get("completed_tasks", [])
            completed_tasks.append(task)
            
            # Calculate streak
            last_check_in_day = max([t["day"] for t in completed_tasks]) if completed_tasks else 0
            current_streak = challenge.get("streak_days", 0)
            
            if checkin.day == last_check_in_day or checkin.day == last_check_in_day + 1:
                new_streak = checkin.day
            else:
                new_streak = current_streak
            
            await db.challenges.update_one(
                {"_id": challenge["_id"]},
                {
                    "$set": {
                        "completed_tasks": completed_tasks,
                        "streak_days": new_streak,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            # Determine next task
            times = ["morning", "noon", "evening"]
            current_time_idx = times.index(checkin.time)
            
            if current_time_idx < len(times) - 1:
                next_time = times[current_time_idx + 1]
                next_day = checkin.day
            else:
                next_time = "morning"
                next_day = checkin.day + 1
            
            next_task = f"Tugas {next_time} hari ke-{next_day}"
            
            return {
                "success": True,
                "streak_days": new_streak,
                "next_task": next_task
            }
        
        return {
            "success": False,
            "message": "Task not marked as completed"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking in: {e}")
        raise HTTPException(status_code=500, detail=str(e))