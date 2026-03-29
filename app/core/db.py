import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
DB_NAME = os.getenv("MONGO_DB_NAME")


mongo_client = MongoClient(
    MONGO_URL,
    serverSelectionTimeoutMS=5000,  
)

db = mongo_client[DB_NAME]

week_collection = db["weekly_summaries"]
llm_reports_collection = db["llm_reports"]



week_collection.create_index(
    [("user_id", 1), ("week_id", 1)],
    unique=True
)

llm_reports_collection.create_index(
    [("user_id", 1), ("week_id", 1)],
    unique=True
)
