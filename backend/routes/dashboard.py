from fastapi import APIRouter, HTTPException, Depends, Header
from motor.motor_asyncio import AsyncIOMotorDatabase
from auth_models import UserRole, CheckinEntry, HealthReport, WithdrawalRequest
from database import get_database
from bson import ObjectId
import logging
from datetime import datetime
import jwt
import os
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def verify_token(authorization: str = Header(None)):
    """Verify JWT token from Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    token = authorization.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# USER DASHBOARD ENDPOINTS

@router.get("/user/overview")
async def get_user_overview(
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user dashboard overview"""
    try:
        payload = verify_token(authorization)
        user_id = payload["user_id"]
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Get active challenge
        challenge = await db.challenges.find_one({
            "user_id": user_id,
            "status": "active"
        })
        
        # Get check-ins count
        checkins_count = await db.checkins.count_documents({"user_id": user_id})
        
        # Get purchases
        purchases = await db.purchases.find({"user_id": user_id}).to_list(length=100)
        total_spent = sum([p["amount"] for p in purchases if p["status"] == "verified"])
        
        # Get commission info
        commissions = await db.commissions.find({"user_id": user_id}).to_list(length=100)
        commission_pending = sum([c["amount"] for c in commissions if c["status"] == "pending"])
        commission_approved = sum([c["amount"] for c in commissions if c["status"] == "approved"])
        
        # Get referrals
        referrals = await db.users.count_documents({"referred_by": user_id})
        
        return {
            "user": {
                "name": user["name"],
                "phone_number": user["phone_number"],
                "referral_code": user.get("referral_code", ""),
                "health_type": user.get("health_type")
            },
            "challenge": {
                "enrolled": challenge is not None,
                "current_day": challenge["current_day"] if challenge else 0,
                "total_checkins": checkins_count,
                "start_date": challenge["start_date"] if challenge else None
            },
            "financial": {
                "total_spent": total_spent,
                "commission_pending": commission_pending,
                "commission_approved": commission_approved,
                "total_referrals": referrals
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/health-report")
async def get_health_report(
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user health report based on check-ins"""
    try:
        payload = verify_token(authorization)
        user_id = payload["user_id"]
        
        # Get all check-ins
        checkins = await db.checkins.find(
            {"user_id": user_id}
        ).sort("day", 1).to_list(length=100)
        
        if not checkins:
            return {
                "total_days": 0,
                "completion_rate": 0,
                "comfort_trend": [],
                "achievements": []
            }
        
        # Calculate stats
        total_days = len(checkins)
        completed_tasks = sum([
            1 for c in checkins 
            if c["morning_task_completed"] and c["noon_task_completed"] and c["evening_task_completed"]
        ])
        completion_rate = (completed_tasks / total_days * 100) if total_days > 0 else 0
        
        # Comfort trend
        comfort_trend = [c["comfort_level"] for c in checkins]
        average_comfort = sum(comfort_trend) / len(comfort_trend) if comfort_trend else 0
        
        # Achievements
        achievements = []
        if total_days >= 7:
            achievements.append("week_1")
        if total_days >= 14:
            achievements.append("week_2")
        if total_days >= 21:
            achievements.append("week_3")
        if total_days >= 30:
            achievements.append("champion")
        if completion_rate >= 90:
            achievements.append("perfectionist")
        
        return {
            "total_days": total_days,
            "completion_rate": round(completion_rate, 2),
            "average_comfort": round(average_comfort, 2),
            "comfort_trend": comfort_trend,
            "achievements": achievements,
            "latest_checkin": checkins[-1] if checkins else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/user/checkin")
async def submit_checkin(
    checkin: CheckinEntry,
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Submit daily check-in"""
    try:
        payload = verify_token(authorization)
        user_id = payload["user_id"]
        
        checkin.user_id = user_id
        
        # Check if already checked in today
        today_checkin = await db.checkins.find_one({
            "user_id": user_id,
            "day": checkin.day
        })
        
        if today_checkin:
            # Update existing check-in
            await db.checkins.update_one(
                {"_id": today_checkin["_id"]},
                {"$set": checkin.dict()}
            )
            return {"success": True, "message": "Check-in updated"}
        else:
            # Create new check-in
            await db.checkins.insert_one(checkin.dict())
            return {"success": True, "message": "Check-in submitted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting check-in: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/user/withdrawal")
async def request_withdrawal(
    withdrawal: WithdrawalRequest,
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Request commission withdrawal"""
    try:
        payload = verify_token(authorization)
        user_id = payload["user_id"]
        
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if user has enough commission
        commission_approved = user.get("commission_pending", 0.0)
        if withdrawal.amount > commission_approved:
            raise HTTPException(
                status_code=400,
                detail="Insufficient commission balance"
            )
        
        withdrawal.user_id = user_id
        await db.withdrawal_requests.insert_one(withdrawal.dict())
        
        return {
            "success": True,
            "message": "Withdrawal request submitted",
            "request_id": withdrawal.id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error requesting withdrawal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ADMIN DASHBOARD ENDPOINTS

@router.get("/admin/users")
async def get_all_users(
    authorization: str = Header(None),
    skip: int = 0,
    limit: int = 50,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all users (Admin/Super Admin only)"""
    try:
        payload = verify_token(authorization)
        role = payload.get("role")
        
        if role not in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        users = await db.users.find().skip(skip).limit(limit).to_list(length=limit)
        total = await db.users.count_documents({})
        
        return {
            "users": [
                {
                    "id": str(u["_id"]),
                    "name": u["name"],
                    "phone_number": u["phone_number"],
                    "role": u.get("role", "user"),
                    "challenge_enrolled": u.get("challenge_enrolled", False),
                    "total_referrals": u.get("total_referrals", 0),
                    "total_commission": u.get("total_commission", 0.0),
                    "is_active": u.get("is_active", True),
                    "created_at": u["created_at"]
                }
                for u in users
            ],
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/admin/users/{user_id}")
async def delete_user(
    user_id: str,
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete user (Super Admin only)"""
    try:
        payload = verify_token(authorization)
        role = payload.get("role")
        
        if role != UserRole.SUPER_ADMIN.value:
            raise HTTPException(status_code=403, detail="Super Admin access required")
        
        result = await db.users.delete_one({"_id": ObjectId(user_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {"success": True, "message": "User deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/purchases")
async def get_pending_purchases(
    authorization: str = Header(None),
    status: str = "pending",
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get purchases for verification (Admin/Super Admin only)"""
    try:
        payload = verify_token(authorization)
        role = payload.get("role")
        
        if role not in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        purchases = await db.purchases.find(
            {"status": status}
        ).sort("created_at", -1).to_list(length=100)
        
        # Get user info for each purchase
        result = []
        for p in purchases:
            user = await db.users.find_one({"_id": ObjectId(p["user_id"])})
            result.append({
                "id": str(p["_id"]),
                "user_name": user["name"] if user else "Unknown",
                "user_phone": user["phone_number"] if user else "Unknown",
                "product_name": p["product_name"],
                "amount": p["amount"],
                "status": p["status"],
                "payment_proof": p.get("payment_proof"),
                "created_at": p["created_at"]
            })
        
        return {"purchases": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting purchases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/purchases/{purchase_id}/verify")
async def verify_purchase(
    purchase_id: str,
    approved: bool,
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Verify purchase (Admin/Super Admin only)"""
    try:
        payload = verify_token(authorization)
        role = payload.get("role")
        admin_id = payload["user_id"]
        
        if role not in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        purchase = await db.purchases.find_one({"_id": ObjectId(purchase_id)})
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        
        new_status = "verified" if approved else "cancelled"
        
        await db.purchases.update_one(
            {"_id": ObjectId(purchase_id)},
            {
                "$set": {
                    "status": new_status,
                    "verified_by": admin_id,
                    "verified_at": datetime.utcnow()
                }
            }
        )
        
        # If verified, create commission for referrer
        if approved:
            user = await db.users.find_one({"_id": ObjectId(purchase["user_id"])})
            if user and user.get("referred_by"):
                commission_amount = purchase["amount"] * 0.10  # 10% commission
                commission_data = {
                    "user_id": user["referred_by"],
                    "from_user_id": purchase["user_id"],
                    "purchase_id": purchase_id,
                    "amount": commission_amount,
                    "status": "approved",
                    "created_at": datetime.utcnow()
                }
                await db.commissions.insert_one(commission_data)
                
                # Update referrer's commission
                await db.users.update_one(
                    {"_id": ObjectId(user["referred_by"])},
                    {
                        "$inc": {
                            "commission_pending": commission_amount,
                            "total_commission": commission_amount
                        }
                    }
                )
        
        return {"success": True, "message": f"Purchase {new_status}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying purchase: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/admin/withdrawals")
async def get_withdrawal_requests(
    authorization: str = Header(None),
    status: str = "pending",
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get withdrawal requests (Admin/Super Admin only)"""
    try:
        payload = verify_token(authorization)
        role = payload.get("role")
        
        if role not in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        withdrawals = await db.withdrawal_requests.find(
            {"status": status}
        ).sort("created_at", -1).to_list(length=100)
        
        result = []
        for w in withdrawals:
            user = await db.users.find_one({"_id": ObjectId(w["user_id"])})
            result.append({
                "id": str(w["_id"]),
                "user_name": user["name"] if user else "Unknown",
                "user_phone": user["phone_number"] if user else "Unknown",
                "amount": w["amount"],
                "bank_name": w["bank_name"],
                "account_number": w["account_number"],
                "account_name": w["account_name"],
                "status": w["status"],
                "created_at": w["created_at"]
            })
        
        return {"withdrawals": result}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting withdrawals: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/admin/withdrawals/{withdrawal_id}")
async def process_withdrawal(
    withdrawal_id: str,
    approved: bool,
    note: Optional[str] = None,
    authorization: str = Header(None),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process withdrawal request (Admin/Super Admin only)"""
    try:
        payload = verify_token(authorization)
        role = payload.get("role")
        admin_id = payload["user_id"]
        
        if role not in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]:
            raise HTTPException(status_code=403, detail="Access denied")
        
        withdrawal = await db.withdrawal_requests.find_one({"_id": ObjectId(withdrawal_id)})
        if not withdrawal:
            raise HTTPException(status_code=404, detail="Withdrawal request not found")
        
        new_status = "paid" if approved else "rejected"
        
        await db.withdrawal_requests.update_one(
            {"_id": ObjectId(withdrawal_id)},
            {
                "$set": {
                    "status": new_status,
                    "admin_note": note,
                    "processed_by": admin_id,
                    "processed_at": datetime.utcnow()
                }
            }
        )
        
        # Update user's commission balance
        if approved:
            await db.users.update_one(
                {"_id": ObjectId(withdrawal["user_id"])},
                {
                    "$inc": {
                        "commission_pending": -withdrawal["amount"],
                        "commission_withdrawn": withdrawal["amount"]
                    }
                }
            )
        
        return {"success": True, "message": f"Withdrawal {new_status}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing withdrawal: {e}")
        raise HTTPException(status_code=500, detail=str(e))