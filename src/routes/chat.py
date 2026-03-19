import fitz
import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, HTTPException, Depends, Header
from src.config.database import chats_collection, users_collection
from src.models.documents import ChatRequest
from openai import OpenAI
import os
import jwt
from bson import ObjectId
from datetime import datetime
from typing import Optional

cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

router = APIRouter(prefix="/chat", tags=["Study Chat"])

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key")
ALGORITHM = "HS256"

async def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required. Please log in again.")
    
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: User ID not found.")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials.")

@router.post("/")
async def study_chat(request: ChatRequest, current_user_id: str = Depends(verify_token)):
    try:
        user_id = current_user_id
        image_url = None

        if request.image_b64:
            try:
                upload_result = cloudinary.uploader.upload(
                    f"data:image/jpeg;base64,{request.image_b64}",
                    folder="study_ai_chats"
                )
                image_url = upload_result.get("secure_url")
            except Exception as cloud_err:
                print(f"Cloudinary Error: {cloud_err}")

        messages = [{"role": "system", "content": "You are a helpful Study Assistant. Analyze text and images provided to give concise academic answers."}]

        if request.doc_id:
            user_data = await users_collection.find_one({"_id": ObjectId(user_id)})
            if user_data:
                library = user_data.get("library", [])
                doc = next((d for d in library if d["id"] == request.doc_id), None)
                if doc and os.path.exists(doc["path"]):
                    try:
                        pdf_text = ""
                        with fitz.open(doc["path"]) as pdf:
                            for page_num in range(min(len(pdf), 5)):
                                pdf_text += pdf.load_page(page_num).get_text()
                        messages.append({
                            "role": "system",
                            "content": f"Use the following PDF content to assist the user:\n{pdf_text[:3000]}"
                        })
                    except Exception as pdf_err:
                        print(f"PDF Reading Error: {pdf_err}")

        cursor = chats_collection.find({"user_id": user_id}).sort("timestamp", -1).limit(5)
        history = await cursor.to_list(length=5)
        for chat in reversed(history):
            messages.append({"role": chat["role"], "content": chat["content"]})

        user_content = [{"type": "text", "text": request.message}]
        if image_url:
            user_content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })

        messages.append({"role": "user", "content": user_content})
        selected_model = "pixtral-12b-2409" if image_url else "llama-3.3-70b-versatile"

        response = client.chat.completions.create(
            model=selected_model,
            messages=messages
        )
        ai_reply = response.choices[0].message.content

        await chats_collection.insert_one({
            "user_id": user_id,
            "role": "user",
            "content": request.message,
            "image_url": image_url,
            "timestamp": datetime.utcnow()
        })
        await chats_collection.insert_one({
            "user_id": user_id,
            "role": "assistant",
            "content": ai_reply,
            "timestamp": datetime.utcnow()
        })

        return {"reply": ai_reply, "image_url": image_url}

    except Exception as e:
        print(f"Chat Error Trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_chat_history(current_user_id: str = Depends(verify_token)):
    try:
        cursor = chats_collection.find({"user_id": current_user_id}).sort("timestamp", 1)
        history = await cursor.to_list(length=50)
        return [
            {
                "role": chat["role"],
                "content": chat["content"],
                "image_url": chat.get("image_url"),
                "timestamp": chat["timestamp"]
            }
            for chat in history
        ]
    except Exception as e:
        print(f"History Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch chat history.")