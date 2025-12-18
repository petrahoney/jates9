from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum

class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: Optional[str] = None
    phone_number: str
    name: str
    password_hash: Optional[str] = None
    role: UserRole = UserRole.USER
    
    # Health info
    health_type: Optional[str] = None
    health_score: Optional[int] = None
    quiz_date: Optional[datetime] = None
    
    # Challenge info
    challenge_enrolled: bool = False
    challenge_start_date: Optional[datetime] = None
    current_challenge_day: int = 0
    
    # Affiliate info
    referral_code: str = Field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    referred_by: Optional[str] = None
    total_referrals: int = 0
    total_commission: float = 0.0
    commission_pending: float = 0.0
    commission_withdrawn: float = 0.0
    
    # Purchases
    total_purchases: float = 0.0
    
    # Status
    is_active: bool = True
    is_verified: bool = False
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class LoginRequest(BaseModel):
    phone_number: str
    password: Optional[str] = None

class RegisterRequest(BaseModel):
    name: str
    phone_number: str
    email: Optional[str] = None
    password: str
    referral_code: Optional[str] = None

class CheckinEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    challenge_id: str
    day: int
    date: datetime = Field(default_factory=datetime.utcnow)
    
    # Check-in data
    comfort_level: int  # 1-10
    symptoms: List[str] = []
    notes: Optional[str] = None
    
    # Daily tasks completion
    morning_task_completed: bool = False
    noon_task_completed: bool = False
    evening_task_completed: bool = False
    
    created_at: datetime = Field(default_factory=datetime.utcnow)

class HealthReport(BaseModel):
    user_id: str
    total_days: int
    completion_rate: float
    achievements: List[str] = []
    comfort_trend: List[int] = []
    average_comfort: float
    symptoms_reduced: List[str] = []
    
class Purchase(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    product_id: str
    product_name: str
    amount: float
    status: str = "pending"  # pending, verified, cancelled
    payment_proof: Optional[str] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Commission(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    from_user_id: str  # who made the purchase
    purchase_id: str
    amount: float
    status: str = "pending"  # pending, approved, paid
    created_at: datetime = Field(default_factory=datetime.utcnow)

class WithdrawalRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    amount: float
    bank_name: str
    account_number: str
    account_name: str
    status: str = "pending"  # pending, approved, rejected, paid
    admin_note: Optional[str] = None
    processed_by: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)