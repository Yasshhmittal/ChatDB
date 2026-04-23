from datetime import datetime, timedelta, timezone
import jwt
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt

from app.auth_db import create_user, get_user_by_username, update_last_active

# -------------------------------------------------------------
# Security & Config
# -------------------------------------------------------------

SECRET_KEY = "super-secret-key-for-chatdb-dev"  # Note: move to env in prod
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 1 week

security = HTTPBearer(auto_error=False)

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def get_password_hash(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user_or_none(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extracts user from JWT token if present, else returns None."""
    if not credentials:
        return None
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            return None
        return {"id": user_id, "name": payload.get("name"), "username": payload.get("username")}
    except jwt.PyJWTError:
        return None

# -------------------------------------------------------------
# Schemas
# -------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str
    username: str
    password: str

class SigninRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    avatar: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

# -------------------------------------------------------------
# Router Implementation
# -------------------------------------------------------------

router = APIRouter()

@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    # Check if user exists
    existing_user = get_user_by_username(request.username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Hash password and create user
    hashed_pass = get_password_hash(request.password)
    try:
        new_user = create_user(request.name, request.username, hashed_pass)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create token
    access_token = create_access_token(data={"sub": str(new_user["id"]), "name": new_user["name"], "username": new_user["username"]})
    
    avatar = new_user["name"][0].upper()
    user_resp = UserResponse(id=new_user["id"], name=new_user["name"], username=new_user["username"], avatar=avatar)
    
    return {"access_token": access_token, "user": user_resp}

@router.post("/signin", response_model=AuthResponse)
async def signin(request: SigninRequest, background_tasks: BackgroundTasks):
    user = get_user_by_username(request.username)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Create token
    access_token = create_access_token(data={"sub": str(user["id"]), "name": user["name"], "username": user["username"]})
    
    # Track last activity in background to avoid blocking the sign-in response
    background_tasks.add_task(update_last_active, user["id"])
    
    avatar = user["name"][0].upper()
    user_resp = UserResponse(id=user["id"], name=user["name"], username=user["username"], avatar=avatar)
    
    return {"access_token": access_token, "user": user_resp}
