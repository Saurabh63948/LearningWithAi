from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import Optional
from src.routes.chat import verify_token
from bson import ObjectId
from src.config.database import users_collection
from src.models.user import SignupRequest, UserResponse, LoginRequest
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
import cloudinary
import cloudinary.uploader

router = APIRouter(prefix="/auth", tags=["Authentication"])

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    education_level: Optional[str] = None
    profile_image_b64: Optional[str] = None

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-donot-share") 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_password_hash(password: str):
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

@router.post("/signup", response_model=UserResponse)
async def signup(request: SignupRequest):
    existing_user = await users_collection.find_one({"email": request.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="This email is already registered.")

    hashed_pass = get_password_hash(request.password)

    user_doc = {
        "full_name": request.full_name,
        "email": request.email,
        "password": hashed_pass,
        "role": "student",
        "education_level": request.education_level,
        "profile_pic": None,
        "library": [],
        "created_at": datetime.utcnow(),
    }

    result = await users_collection.insert_one(user_doc)
    
    return {
        "id": str(result.inserted_id),
        "full_name": request.full_name,
        "email": request.email,
        "education_level": request.education_level,
        "created_at": user_doc["created_at"]
    }

@router.post("/login")
async def login(request: LoginRequest):
    user = await users_collection.find_one({"email": request.email})
    
    if not user or not verify_password(request.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid email or password."
        )

    access_token = create_access_token(data={"user_id": str(user["_id"])})

    await users_collection.update_one(
        {"_id": user["_id"]}, 
        {"$set": {"last_login": datetime.utcnow()}}
    )

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user["_id"]),
        "full_name": user["full_name"],
        "message": f"Welcome back, {user['full_name']}!"
    }

@router.get("/me", response_model=UserResponse)
async def get_user_profile(current_user_id: str = Depends(verify_token)):
    user = await users_collection.find_one({"_id": ObjectId(current_user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user["id"] = str(user["_id"])
    return user

@router.put("/update-profile")
async def update_profile(request: ProfileUpdate, current_user_id: str = Depends(verify_token)):
    try:
        update_data = {}
        
        if request.full_name:
            update_data["full_name"] = request.full_name
        if request.education_level:
            update_data["education_level"] = request.education_level

        if request.profile_image_b64:
            try:
                upload_result = cloudinary.uploader.upload(
                    f"data:image/jpeg;base64,{request.profile_image_b64}",
                    folder="user_profiles",
                    transformation=[
                        {"width": 400, "height": 400, "crop": "fill", "gravity": "face"}
                    ]
                )
                update_data["profile_pic"] = upload_result.get("secure_url")
            except Exception as cloud_err:
                print(f"Cloudinary Error: {cloud_err}")
                raise HTTPException(status_code=500, detail="Failed to upload profile image.")

        if update_data:
            await users_collection.update_one(
                {"_id": ObjectId(current_user_id)},
                {"$set": update_data}
            )

        updated_user = await users_collection.find_one({"_id": ObjectId(current_user_id)})
        updated_user["id"] = str(updated_user["_id"])
        
        return {
            "status": "success",
            "full_name": updated_user.get("full_name"),
            "education_level": updated_user.get("education_level"),
            "profile_pic": updated_user.get("profile_pic"),
            "message": "Profile updated successfully."
        }

    except Exception as e:
        print(f"Update Route Error: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong. Please try again.")