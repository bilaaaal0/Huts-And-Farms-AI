import os
import requests
from dotenv import load_dotenv

load_dotenv()
# NOCO_API_TOKEN = os.getenv("NOCO_API_TOKEN")  # directly load the token
# HEADERS = {
#     "xc-token": NOCO_API_TOKEN
# }
# NOCO_BASE_URL = os.getenv("NOCO_BASE_URL") 
# NOCO_EMAIL = os.getenv("NOCO_EMAIL")
# NOCO_PASSWORD = os.getenv("NOCO_PASSWORD")

# def get_token():
#     if NOCO_API_TOKEN:
#       return NOCO_API_TOKEN  # Use static token
   

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

SQLALCHEMY_DATABASE_URL = "postgresql://neondb_owner:npg_A1IX3lDCgNOY@ep-silent-leaf-a8ebszia-pooler.eastus2.azure.neon.tech/neondb?sslmode=require&channel_binding=require" # or hardcode if needed
print(SQLALCHEMY_DATABASE_URL)
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

from fastapi import Depends

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
