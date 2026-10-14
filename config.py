
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-this-key")
    SQLALCHEMY_DATABASE_URI = (
        f"sqlite:///{(BASE_DIR / 'instance' / 'hospital.db').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
