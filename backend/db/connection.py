from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()
MONGO_URL = os.getenv("MONGO_URL")

print("Connecting to MongoDB...")

try:
    client = MongoClient(
        MONGO_URL,
        tls=True,
        tlsAllowInvalidCertificates=True
    )
    db = client["autoai"]  # database name decided by you
    print("Connected successfully to cluster.")
    print("Database ready:", db.name)

except Exception as e:
    print("MongoDB connection failed.")
    print("Error:", e)
