import bcrypt
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import os
import hmac
import time
import hashlib
import logging
import secrets

_auth_logger = logging.getLogger("alertx.auth")

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    # No public default: generate an ephemeral key (sessions reset on restart)
    SECRET_KEY = secrets.token_hex(32)
    _auth_logger.warning(
        "SECRET_KEY env var not set - generated a random key. "
        "Login tokens will be invalidated on every restart."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 300 # 5 hours for monitoring session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_password(plain_password: str, hashed_password: str):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str):
    # bcrypt.hashpw returns bytes, we decode to string for database storage
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


# ── Signed, expiring dispatch tokens (used by emailed "Call Police/Security/Ambulance/Fire" links) ──
DISPATCH_SERVICES = {"police", "security", "ambulance", "fire"}
DISPATCH_TOKEN_TTL = 30 * 60  # 30 minutes


def _dispatch_sig(service: str, expiry: int) -> str:
    return hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{service}:{expiry}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def make_dispatch_token(service: str) -> str:
    """Return '<expiry>.<hmac>' valid for 30 minutes for the given service."""
    service = service.lower()
    expiry = int(time.time()) + DISPATCH_TOKEN_TTL
    return f"{expiry}.{_dispatch_sig(service, expiry)}"


def verify_dispatch_token(service: str, token: Optional[str]) -> bool:
    if not token or "." not in token:
        return False
    try:
        expiry_s, sig = token.split(".", 1)
        expiry = int(expiry_s)
    except ValueError:
        return False
    if expiry < time.time():
        return False
    return hmac.compare_digest(sig, _dispatch_sig(service.lower(), expiry))


def verify_bearer_header(authorization: Optional[str]) -> bool:
    """True if the Authorization header carries a valid JWT access token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return False
    try:
        payload = jwt.decode(authorization[7:].strip(), SECRET_KEY, algorithms=[ALGORITHM])
        return bool(payload.get("sub"))
    except JWTError:
        return False
