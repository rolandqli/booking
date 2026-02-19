"""Supabase database client for the booking system."""
import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


def get_supabase() -> Client:
    """Get Supabase client. Uses service role key for backend operations."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment"
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
