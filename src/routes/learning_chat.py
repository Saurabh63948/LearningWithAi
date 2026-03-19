import os
import jwt
import datetime
import chromadb
from fastapi import APIRouter, HTTPException, Depends, Header
from chromadb.utils import embedding_functions
from openai import OpenAI
from typing import Optional
from pydantic import BaseModel

class LearningRequest(BaseModel):
    message: str
    language: str
    level: str   

router = APIRouter(prefix="/learning", tags=["Learning AI"])

chroma_client = chromadb.PersistentClient(path="./learning_mem")
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
collection = chroma_client.get_or_create_collection(name="user_learning", embedding_function=ef)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1", 
    api_key=os.getenv("GROQ_API_KEY1")
)

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-donot-share")
ALGORITHM = "HS256"

async def verify_token(authorization: Optional[str] = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required. Please log in again.")
    token = authorization.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("user_id")
    except:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials.")

@router.post("/chat")
async def learning_chat(request: LearningRequest, user_id: str = Depends(verify_token)):
    try:
        past_memory = collection.query(
            query_texts=[request.message],
            n_results=3,
            where={"user_id": user_id}
        )
        
        context = ""
        if past_memory['documents'] and len(past_memory['documents'][0]) > 0:
            context = "\n".join(past_memory['documents'][0])

        system_prompt = f"""
        You are a personalized {request.language} tutor for a {request.level} student.
        Use the following past interaction context to maintain continuity:
        {context}
        Keep explanations simple and include a small coding task at the end.
        """

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ]
        )
        ai_reply = response.choices[0].message.content

        collection.add(
            documents=[f"Topic: {request.language} | User: {request.message} | AI: {ai_reply}"],
            metadatas=[{"user_id": user_id, "lang": request.language, "date": str(datetime.date.today())}],
            ids=[f"{user_id}_{datetime.datetime.now().timestamp()}"]
        )

        return {"reply": ai_reply}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/test")
async def generate_test(user_id: str = Depends(verify_token)):
    try:
        results = collection.get(where={"user_id": user_id})
        
        if not results['documents']:
            return {"error": "Please study some topics first before attempting the test."}

        history = " ".join(results['documents'])
        
        test_prompt = f"Based on this learning history: {history}. Create a 5-question MCQ test in JSON."
        
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": test_prompt}],
            response_format={"type": "json_object"}
        )
        
        return {"test_paper": completion.choices[0].message.content}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/history/{language}")
async def get_learning_history(language: str, user_id: str = Depends(verify_token)):
    try:
        results = collection.get(
            where={
                "$and": [
                    {"user_id": user_id},
                    {"lang": language}
                ]
            }
        )
        
        history = []
        if results['documents']:
            for doc in results['documents']:
                parts = doc.split(" | ")
                user_part = parts[1].replace("User: ", "")
                ai_part = parts[2].replace("AI: ", "")
                history.append({"role": "user", "content": user_part})
                history.append({"role": "assistant", "content": ai_part})
        
        return {"history": history}
    except Exception as e:
        return {"history": []}