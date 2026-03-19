import chromadb
from chromadb.utils import embedding_functions
import datetime

chroma_client = chromadb.PersistentClient(path="./study_ai_memory")

ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")

learning_collection = chroma_client.get_or_create_collection(
    name="learning_memory",
    embedding_function=ef
)