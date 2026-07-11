from fastapi import Request
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from app.config import settings
from app.models import User

serializer = URLSafeSerializer(settings.app_secret, salt="enterprise7")
hasher = PasswordHasher()

def hash_password(password: str) -> str:
    return hasher.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (VerifyMismatchError, Exception):
        return False

def ensure_admin_user(db):
    if not db.query(User).filter(User.username == settings.admin_user).first():
        db.add(User(username=settings.admin_user, password_hash=hash_password(settings.admin_password), role="admin", active=True))
        db.commit()

def create_session_token(username: str) -> str:
    return serializer.dumps({"user": username})

def current_user(request: Request, db):
    token = request.cookies.get("session")
    if not token:
        return None
    try:
        data = serializer.loads(token)
    except BadSignature:
        return None
    return db.query(User).filter(User.username == data.get("user"), User.active == True).first()

def require_login(request: Request, db):
    if not current_user(request, db):
        return RedirectResponse("/login", status_code=303)
    return None
