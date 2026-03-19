import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from src.routes.chat import router as chat_router 
from src.routes.user import router as user_router
from src.routes.library import router as library_router
from src.routes.learning_chat import router as learning_router

load_dotenv()

app = FastAPI(title="Groq AI Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(user_router)
app.include_router(library_router)
app.include_router(learning_router)

class ChatInput(BaseModel):
    message: str

@app.get("/")
async def root():
    return {"status": "online", "model": "llama-3.3-70b"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="0.0.0.0", port=8000, reload=True)