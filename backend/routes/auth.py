from fastapi import APIRouter, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from auth_models import User, LoginRequest, RegisterRequest, UserRole
from database import get_database
from passlib.context import CryptContext
import logging
from datetime import datetime, timedelta
import jwt
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/register")
async def register(
    request: RegisterRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Register new user"""
    try:
        # Check if user already exists
        existing_user = await db.users.find_one({"phone_number": request.phone_number})
        
        if existing_user:
            raise HTTPException(
                status_code=400,
                detail="Phone number already registered"
            )
        
        # Check referral code if provided
        referrer = None
        if request.referral_code:
            referrer = await db.users.find_one({"referral_code": request.referral_code})
            if not referrer:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid referral code"
                )
        
        # Create new user
        user_data = {
            "name": request.name,
            "phone_number": request.phone_number,
            "email": request.email,
            "password_hash": hash_password(request.password),
            "role": UserRole.USER.value,
            "referred_by": str(referrer["_id"]) if referrer else None,
            "challenge_enrolled": False,
            "total_referrals": 0,
            "total_commission": 0.0,
            "commission_pending": 0.0,
            "commission_withdrawn": 0.0,
            "total_purchases": 0.0,
            "is_active": True,
            "is_verified": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = await db.users.insert_one(user_data)
        user_id = str(result.inserted_id)
        
        # Update referrer's total referrals
        if referrer:
            await db.users.update_one(
                {"_id": referrer["_id"]},
                {"$inc": {"total_referrals": 1}}
            )
        
        # Create access token
        access_token = create_access_token({
            "user_id": user_id,
            "role": UserRole.USER.value
        })
        
        return {
            "success": True,
            "user_id": user_id,
            "access_token": access_token,
            "role": UserRole.USER.value
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/login")
async def login(
    request: LoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Login user"""
    try:
        # Find user
        user = await db.users.find_one({"phone_number": request.phone_number})
        
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Invalid phone number or password"
            )
        
        # Verify password if provided (for backward compatibility with old users)
        if request.password and user.get("password_hash"):
            if not verify_password(request.password, user["password_hash"]):
                raise HTTPException(
                    status_code=401,
                    detail="Invalid phone number or password"
                )
        
        # Check if user is active
        if not user.get("is_active", True):
            raise HTTPException(
                status_code=403,
                detail="Account is deactivated"
            )
        
        # Create access token
        access_token = create_access_token({
            "user_id": str(user["_id"]),
            "role": user.get("role", UserRole.USER.value)
        })
        
        return {
            "success": True,
            "user_id": str(user["_id"]),
            "name": user["name"],
            "role": user.get("role", UserRole.USER.value),
            "access_token": access_token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me")
async def get_current_user(
    token: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get current user info from token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        from bson import ObjectId
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_id": str(user["_id"]),
            "name": user["name"],
            "phone_number": user["phone_number"],
            "email": user.get("email"),
            "role": user.get("role", UserRole.USER.value),
            "referral_code": user.get("referral_code"),
            "total_commission": user.get("total_commission", 0.0),
            "commission_pending": user.get("commission_pending", 0.0)
        }
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=500, detail=str(e))