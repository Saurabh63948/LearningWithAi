from pydantic import BaseModel,Field
from datetime import datetime
from typing import Optional

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    doc_id: Optional[str] = None
    image_b64: Optional[str] = None
    
class ChatMessage(BaseModel):
   role:str
   content:str
   timestamp:datetime=Field(default_factory=datetime.utcnow)

class StudyDocument(BaseModel):
   title:str
   content:str
   timestamp:datetime= Field(default_factory=datetime.utcnow)  
   