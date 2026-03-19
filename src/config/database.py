import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URL = os.getenv("MONGO_URI")

# create client
client = AsyncIOMotorClient(MONGO_URL)

# database
database = client.study_assistant_db

# collections
documents_collection = database.get_collection("documents")
chats_collection = database.get_collection("chats")
users_collection = database.get_collection("Users")