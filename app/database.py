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

SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")  # or hardcode if needed

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
