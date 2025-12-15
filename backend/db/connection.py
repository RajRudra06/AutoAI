from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")
if not MONGO_URL:
    raise RuntimeError("MONGO_URL not set in environment variables")

print("Connecting to MongoDB...")

try:
    client = MongoClient(
        MONGO_URL,
        tls=True,
        tlsAllowInvalidCertificates=True,
        serverSelectionTimeoutMS=5000  # fail fast if cluster unreachable
    )

    # Force a ping to verify connection immediately
    client.admin.command("ping")

    db = client["autoai"]  # database name decided by you

    print("Connected successfully to cluster.")
    print("Database ready:", db.name)

except Exception as e:
    print("MongoDB connection failed.")
    print("Error:", e)
    raise  # re-raise so app/agent fails fast
