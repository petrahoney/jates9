from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import uuid

# User Models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    phone_number: str
    name: str
    health_type: Optional[str] = None
    health_score: Optional[int] = None
    quiz_date: Optional[datetime] = None
    challenge_enrolled: bool = False
    challenge_start_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    phone_number: str
    name: str

# Quiz Models
class QuizAnswer(BaseModel):
    user_id: Optional[str] = None
    phone_number: str
    name: str
    answers: Dict[str, str]
    score: int
    health_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class QuizResult(BaseModel):
    score: int
    health_type: str
    timestamp: datetime
    recommendation: str
    suggested_product: str

# Challenge Models
class ChallengeEnrollment(BaseModel):
    user_id: Optional[str] = None
    phone_number: str
    name: str
    health_type: str
    start_date: Optional[datetime] = Field(default_factory=datetime.utcnow)

class ChallengeTask(BaseModel):
    day: int
    time: str
    task: str
    completed_at: Optional[datetime] = None

class Challenge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    current_day: int = 1
    start_date: datetime
    completed_tasks: List[ChallengeTask] = []
    streak_days: int = 0
    status: str = "active"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CheckIn(BaseModel):
    user_id: str
    day: int
    time: str
    task_completed: bool
    notes: Optional[str] = None

# Chat Models
class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str

class ChatResponse(BaseModel):
    success: bool
    response: str
    session_id: str

class ChatSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)