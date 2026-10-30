import os
import time
import logging
import firebase_admin
from firebase_admin import credentials, firestore

logger = logging.getLogger("alertx.firebase")

_db = None
_last_failed_init_time = 0.0
_FAILED_INIT_COOLDOWN = 300.0

def init_firebase():
    """Initialize Firebase Admin SDK."""
    global _db, _last_failed_init_time
    try:
        if not firebase_admin._apps:
            cred = None
            
            # 1. Try environment variable (JSON string)
            env_cred = os.getenv("FIREBASE_SERVICE_ACCOUNT")
            if env_cred:
                import json
                try:
                    cred_dict = json.loads(env_cred)
                    cred = credentials.Certificate(cred_dict)
                    logger.info("Firebase initialized via FIREBASE_SERVICE_ACCOUNT env var")
                except Exception as e:
                    logger.error(f"Failed to parse FIREBASE_SERVICE_ACCOUNT env var: {e}")

            # 2. Try serviceAccountKey.json
            if not cred:
                cred_path = os.path.join(os.getcwd(), "serviceAccountKey.json")
                if os.path.exists(cred_path):
                    cred = credentials.Certificate(cred_path)
                    logger.info("Firebase initialized with serviceAccountKey.json")

            # 3. Try credentials.json (Legacy/Common name)
            if not cred:
                legacy_path = os.path.join(os.getcwd(), "credentials.json")
                if os.path.exists(legacy_path):
                    cred = credentials.Certificate(legacy_path)
                    logger.info("Firebase initialized with credentials.json")

            # Initialize with cred or default
            if cred:
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()
                logger.info("Firebase initialized with default credentials")
        
        _db = firestore.client()
        _last_failed_init_time = 0.0
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Firebase: {e}")
        _db = None
        _last_failed_init_time = time.time()
        return False

def get_firestore():
    """Return the Firestore client with negative caching on init failure."""
    global _db, _last_failed_init_time
    if _db is not None:
        return _db
    now = time.time()
    if (now - _last_failed_init_time) < _FAILED_INIT_COOLDOWN:
        return None
    init_firebase()
    return _db
