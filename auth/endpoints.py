import os
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta
from database.database import connect_to_db
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from dotenv import load_dotenv
from uuid import UUID

load_dotenv()

# ------------------------
# Configurations
# ------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
REFRESH_SECRET_KEY = os.getenv("REFRESH_SECRET_KEY", "your-refresh-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()

# ------------------------
# Schemas
# ------------------------

class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    username: str
    email: str
    password: str

class UserUpdate(BaseModel):
    username: str
    email: str
    is_admin: bool

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class TokenData(BaseModel):
    id: str
    username: str
    is_admin: bool

# ------------------------
# Utility Functions
# ------------------------

def hash_password(password):
    return pwd_context.hash(password)

def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)

def get_user_by_username(username: str):
    print(f"🔍 Fetching user: {username}")
    conn = connect_to_db()
    if not conn:
        print("❌ DB connection failed")
        return None
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, username, email, password, is_admin FROM users WHERE username = %s", (username,))
            return cursor.fetchone()
    finally:
        conn.close()

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    print("🔐 Validating token...")
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("id")
        username: str = payload.get("sub")
        is_admin: bool = payload.get("is_admin")
        if not all([user_id, username, is_admin is not None]):
            raise credentials_exception
        return TokenData(id=user_id, username=username, is_admin=is_admin)
    except JWTError as e:
        print(f"❌ Token decode error: {e}")
        raise credentials_exception

# ------------------------
# Auth Routes
# ------------------------

@router.post("/login", response_model=Token)
def login(form_data: UserLogin):
    print(f"🔐 Login attempt: {form_data.username}")
    user = get_user_by_username(form_data.username)
    if user is None or not verify_password(form_data.password, user[3]):
        print("❌ Invalid credentials")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    payload = {"id": str(user[0]), "sub": user[1], "is_admin": user[4]}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    print("✅ Login successful")
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }

@router.post("/refresh", response_model=Token)
def refresh_token(refresh_token: str):
    print("🔄 Refreshing token...")
    try:
        payload = jwt.decode(refresh_token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("id")
        username = payload.get("sub")
        is_admin = payload.get("is_admin")
        if not username or not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        new_access_token = create_access_token({"id": user_id, "sub": username, "is_admin": is_admin})
        new_refresh_token = create_refresh_token({"id": user_id, "sub": username, "is_admin": is_admin})

        print("✅ Token refreshed")
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    except JWTError as e:
        print(f"❌ Refresh token error: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/register")
def register_user(user_data: UserRegister):
    print(f"📝 Registering user: {user_data.username}")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (user_data.username,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username already taken")

            cursor.execute("SELECT id FROM users WHERE email = %s", (user_data.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already in use")

            hashed_pw = hash_password(user_data.password)

            cursor.execute("""
                INSERT INTO users (username, email, password, is_admin)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (user_data.username, user_data.email, hashed_pw, False))

            new_user_id = cursor.fetchone()[0]
            conn.commit()

            print(f"✅ User registered: {new_user_id}")
            return {"message": "User created successfully", "user_id": new_user_id}

    except Exception as e:
        print(f"❌ Error creating user: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")
    finally:
        conn.close()

@router.post("/register-admin")
def register_admin(admin_data: UserRegister):
    print(f"🛡️ Registering admin: {admin_data.username}")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE username = %s", (admin_data.username,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username already taken")

            cursor.execute("SELECT id FROM users WHERE email = %s", (admin_data.email,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Email already in use")

            hashed_pw = hash_password(admin_data.password)

            cursor.execute("""
                INSERT INTO users (username, email, password, is_admin)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (admin_data.username, admin_data.email, hashed_pw, True))

            new_user_id = cursor.fetchone()[0]
            conn.commit()

            print(f"✅ Admin registered: {new_user_id}")
            return {"message": "Admin user created successfully", "user_id": new_user_id}

    except Exception as e:
        print(f"❌ Error creating admin: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating admin: {str(e)}")
    finally:
        conn.close()

@router.put("/update_user/{user_id}")
def update_user(user_id: str, user_data: UserUpdate, current_user: TokenData = Depends(get_current_user)):
    print(f"✏️ Update request for user {user_id}")
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can update user data")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_uuid,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            cursor.execute("""
                UPDATE users 
                SET username = %s, email = %s, is_admin = %s 
                WHERE id = %s
            """, (user_data.username, user_data.email, user_data.is_admin, user_uuid))
            conn.commit()
            print("✅ User updated")

    except Exception as e:
        print(f"❌ Error updating user: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")
    finally:
        conn.close()

    return {"message": "User updated successfully"}

@router.delete("/delete_user/{user_id}")
def delete_user(user_id: str, current_user: TokenData = Depends(get_current_user)):
    print(f"🗑️ Delete request for user: {user_id}")
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_uuid,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            cursor.execute("DELETE FROM users WHERE id = %s", (user_uuid,))
            conn.commit()
            print("✅ User deleted")

    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")
    finally:
        conn.close()

    return {"message": "User deleted successfully"}
