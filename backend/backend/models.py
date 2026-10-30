import os
import sqlite3
from datetime import datetime
from utils.firebase_service import get_firestore

# ── Local user store (fallback when Firebase credentials are unavailable) ──
_LOCAL_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "local_users.db"
)


def _local_conn():
    conn = sqlite3.connect(_LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            email TEXT,
            hashed_password TEXT NOT NULL,
            role TEXT,
            badge_id TEXT,
            created_at TEXT
        )"""
    )
    return conn


def _local_save_user(username, email, hashed_password, role, badge_id):
    try:
        with _local_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO users VALUES (?, ?, ?, ?, ?, ?)",
                (username, email, hashed_password, role, badge_id,
                 datetime.utcnow().isoformat()),
            )
        return True
    except Exception:
        return False


def _local_get_user(username):
    try:
        with _local_conn() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
        return dict(row) if row else None
    except Exception:
        return None

# Firebase-based Models
class DBStore:
    """Helper to handle Firestore collections."""
    @staticmethod
    def save_event(data: dict):
        db = get_firestore()
        if db:
            db.collection("events").add({
                **data,
                "timestamp": datetime.utcnow()
            })
            return True
        return False

    @staticmethod
    def get_events(limit=50):
        db = get_firestore()
        if not db: return []
        docs = db.collection("events").order_by("timestamp", direction="DESCENDING").limit(limit).stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def save_user(username, email, hashed_password, role="civilian", badge_id=""):
        db = get_firestore()
        if db:
            db.collection("users").document(username).set({
                "username": username,
                "email": email,
                "hashed_password": hashed_password,
                "role": role,
                "badge_id": badge_id,
                "created_at": datetime.utcnow()
            })
            return True
        # Fallback: local SQLite store when Firebase is not configured
        return _local_save_user(username, email, hashed_password, role, badge_id)

    @staticmethod
    def get_user(username):
        db = get_firestore()
        if not db:
            return _local_get_user(username)
        doc = db.collection("users").document(username).get()
        return doc.to_dict() if doc.exists else None

# Compatibility classes for main.py
class User:
    """Mock class for Auth compatibility."""
    pass

class Event:
    """Mock class for DB compatibility."""
    pass

# Compatibility constants for main.py
SQLALCHEMY_DATABASE_URL = "firebase"

def get_db():
    """Returns the Firestore store."""
    return DBStore()
