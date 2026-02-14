from dotenv import load_dotenv
import os
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
if not MONGO_URL:
    raise RuntimeError("MONGO_URL not set in environment variables")

print("Connecting to MongoDB...")

client = MongoClient(MONGO_URL, server_api=ServerApi('1'))

try:
   
    client.admin.command("ping")

    db = client["autoai"]  

    print("Connected successfully to cluster.")
    print("Database ready:", db.name)

except Exception as e:
    print("MongoDB connection failed.")
    print("Error:", e)
    raise  
