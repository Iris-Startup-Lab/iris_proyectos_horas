import os
from dotenv import load_dotenv

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(base_dir, ".env"))
load_dotenv(os.path.join(base_dir, "src", ".env"))

API_KEY = os.getenv("TRELLO_API_KEY", "").strip("'\" ")
TOKEN = os.getenv("TRELLO_TOKEN", "").strip("'\" ")
BOARD_IDS = [b.strip("'\" ") for b in os.getenv("TRELLO_BOARD_IDS", "").split(",") if b.strip()]
PROYECTOS_BOARD_ID = os.getenv("TRELLO_PROYECTOS_BOARD_ID", "q0VwmXfl").strip("'\" ")
SUPABASE_HOST = os.getenv("SUPABASE_HOST", "").strip("'\" ")
SUPABASE_DB = os.getenv("SUPABASE_DB", "").strip("'\" ")
SUPABASE_USER = os.getenv("SUPABASE_USER", "").strip("'\" ")
SUPABASE_PASSWORD = os.getenv("SUPABASE_PASSWORD", "").strip("'\" ")
SUPABASE_PORT = os.getenv("SUPABASE_PORT", "5432").strip("'\" ")
FULL_RELOAD = os.getenv("FULL_RELOAD", "false").strip("'\" ").lower() == "true"