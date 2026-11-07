import os
import secrets
from datetime import datetime, timedelta, timezone
import jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from .database import get_db
from .models import User, Audit

passwords = PasswordHash.recommended()
SECRET = os.getenv('JWT_SECRET')
if not SECRET:
    if os.getenv('APP_ENV') == 'production' or os.getenv('VERCEL'):
        raise RuntimeError('JWT_SECRET is required in production')
    SECRET = secrets.token_urlsafe(48)
bearer = HTTPBearer()

def token(user):
    return jwt.encode({'sub': str(user.id), 'exp': datetime.now(timezone.utc) + timedelta(hours=8)}, SECRET, algorithm='HS256')

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)):
    try:
        claims = jwt.decode(credentials.credentials, SECRET, algorithms=['HS256'])
        user = db.get(User, int(claims['sub']))
        if not user:
            raise ValueError()
        return user
    except (jwt.InvalidTokenError, ValueError, KeyError):
        raise HTTPException(401, 'Invalid or expired session')

def require(user, roles=('admin', 'approver')):
    if user.role not in roles:
        raise HTTPException(403, 'This action requires an authorized approver')

def audit(db, user, action, data):
    db.add(Audit(user_id=user.id, action=action, data=data))
