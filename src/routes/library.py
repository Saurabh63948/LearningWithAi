import fitz
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from src.config.database import users_collection
from src.routes.chat import verify_token
from bson import ObjectId
import os
import shutil
from datetime import datetime

router = APIRouter(prefix="/library", tags=["Library"])

UPLOAD_DIR = "uploads/pdfs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...), 
    current_user_id: str = Depends(verify_token)
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")
    
    file_id = str(ObjectId())
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    new_doc = {
        "id": file_id,
        "name": file.filename,
        "path": file_path,
        "uploaded_at": datetime.utcnow()
    }
    
    await users_collection.update_one(
        {"_id": ObjectId(current_user_id)},
        {"$push": {"library": new_doc}}
    )

    return {"message": "Upload successful.", "doc": new_doc}

@router.get("/documents")
async def get_documents(current_user_id: str = Depends(verify_token)):
    user = await users_collection.find_one({"_id": ObjectId(current_user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    return user.get("library", [])

@router.get("/content/{doc_id}")
async def get_document_content(doc_id: str, current_user_id: str = Depends(verify_token)):
    user = await users_collection.find_one({"_id": ObjectId(current_user_id)})
    
    library = user.get("library", [])
    doc = next((d for d in library if d["id"] == doc_id), None)
    
    if not doc:
        raise HTTPException(status_code=404, detail="This document is not available in your library.")

    text = ""
    try:
        if not os.path.exists(doc["path"]):
            raise HTTPException(status_code=404, detail="File not found on disk.")

        with fitz.open(doc["path"]) as pdf:
            for page in pdf:
                text += page.get_text()
        
        return {
            "name": doc["name"],
            "content": text[:50000]
        }
    except Exception as e:
        print(f"Extraction Error: {str(e)}")
        raise HTTPException(status_code=500, detail="An error occurred while reading the PDF.")

@router.delete("/delete/{doc_id}")
async def delete_document(doc_id: str, current_user_id: str = Depends(verify_token)):
    user = await users_collection.find_one({"_id": ObjectId(current_user_id)})
    library = user.get("library", [])
    
    doc = next((d for d in library if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if os.path.exists(doc["path"]):
        os.remove(doc["path"])

    await users_collection.update_one(
        {"_id": ObjectId(current_user_id)},
        {"$pull": {"library": {"id": doc_id}}}
    )
    
    return {"message": "Document deleted successfully."}