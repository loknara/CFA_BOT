import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    GOOGLE_CREDENTIALS_JSON = os.getenv('GOOGLE_CREDENTIALS_JSON')
    GOOGLE_PROJECT_ID = os.getenv('GOOGLE_PROJECT_ID')
