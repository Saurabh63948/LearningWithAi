from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class UserProfile(BaseModel):
    education_lavel: Optional[str] = "Student"
    subjects_of_interest: List[str] = []
    total_documents: int = 0


class SignupRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6)
    education_level: Optional[str] = "General"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: str = "student" 
    education_level: str
    profile_pic: Optional[str] = None 
    created_at: datetime

class ProfileUpdate(BaseModel):
    profile_image_b64: str