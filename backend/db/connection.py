from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URL = os.getenv("MONGO_URL")

print("Connecting to MongoDB...")

client = MongoClient(
    MONGO_URL,
    tls=True,
    tlsAllowInvalidCertificates=True
)

try:
    db_list = client.list_database_names()
    print("Connection Successful!")
    print("Databases:", db_list)

except Exception as e:
    print("Connection Failed!")
    print("Error:", e)
