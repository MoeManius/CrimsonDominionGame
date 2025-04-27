from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from uuid import UUID
from auth.endpoints import get_current_user, get_user_by_username
from database.database import connect_to_db

router = APIRouter()


class UserUpdate(BaseModel):
    username: str
    email: EmailStr
    is_admin: bool


@router.get("/me")
def read_users_me(current_user: dict = Depends(get_current_user)):
    print("👤 /me endpoint hit")
    user = get_user_by_username(current_user.username)

    if user:
        print(f"✅ Found user: {user}")
        return {
            "id": str(user[0]),
            "username": user[1],
            "email": user[2],
            "is_admin": user[4]  # Fixed index from 4 to 3
        }

    print("❌ User not found")
    raise HTTPException(status_code=404, detail="User not found")


def get_user_by_id(user_id: str):
    print(f"🔍 Fetching user by ID: {user_id}")
    try:
        user_uuid = user_id if isinstance(user_id, UUID) else UUID(user_id)
    except ValueError:
        print("❌ Invalid UUID format")
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    conn = connect_to_db()
    if not conn:
        print("❌ DB connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, is_admin FROM users WHERE id = %s",
                (user_uuid,)
            )
            user = cursor.fetchone()
            print(f"👤 User found: {user}")
    except Exception as e:
        print(f"❌ DB error while fetching user: {e}")
        user = None
    finally:
        conn.close()

    return user


@router.get("/")
def read_all_users(current_user: dict = Depends(get_current_user)):
    print("📋 Fetching all users")

    if not current_user.is_admin:
        print("🚫 Unauthorized access attempt")
        raise HTTPException(status_code=403, detail="Unauthorized to fetch all users")

    conn = connect_to_db()
    if not conn:
        print("❌ DB connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, username, email, is_admin FROM users"
            )
            users = cursor.fetchall()
            print(f"✅ Users fetched: {len(users)}")
    except Exception as e:
        print(f"❌ Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching users: {str(e)}")
    finally:
        conn.close()

    return [
        {
            "id": str(user[0]),
            "username": user[1],
            "email": user[2],
            "is_admin": user[3],
        }
        for user in users
    ]


@router.get("/{user_id}")
def read_user(user_id: str, current_user: dict = Depends(get_current_user)):
    print(f"👤 Fetching user with ID: {user_id}")
    user = get_user_by_id(user_id)

    if user:
        if current_user.username == user[1] or current_user.is_admin:
            print(f"✅ Found user: {user}")
            return {
                "id": str(user[0]),
                "username": user[1],
                "email": user[2],
                "is_admin": user[3]
            }

        print("🚫 Unauthorized access to user data")
        raise HTTPException(status_code=403, detail="Unauthorized to view this user")

    print("❌ User not found")
    raise HTTPException(status_code=404, detail="User not found")


@router.put("/{user_id}")
def update_user(user_id: UUID, user_data: UserUpdate, current_user: dict = Depends(get_current_user)):
    print(f"✏️ Update request for user ID: {user_id}")

    if not current_user.is_admin:
        print("🚫 Only admins can update users")
        raise HTTPException(status_code=403, detail="Only admins can update users")

    conn = connect_to_db()
    if not conn:
        print("❌ DB connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                print("❌ User not found")
                raise HTTPException(status_code=404, detail="User not found")

            cursor.execute("""
                UPDATE users 
                SET username = %s, email = %s, is_admin = %s
                WHERE id = %s
            """, (user_data.username, user_data.email, user_data.is_admin, user_id))
            conn.commit()
            print("✅ User updated successfully")

    except Exception as e:
        print(f"❌ Error updating user: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")
    finally:
        conn.close()

    return {"message": "User updated successfully"}


@router.delete("/{user_id}")
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    print(f"🗑️ Deletion request for user ID: {user_id}")

    if not current_user.is_admin:
        print("🚫 Only admins can delete users")
        raise HTTPException(status_code=403, detail="Only admins can delete users")

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        print("❌ Invalid UUID format")
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    conn = connect_to_db()
    if not conn:
        print("❌ DB connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_uuid,))
            if not cursor.fetchone():
                print("❌ User not found")
                raise HTTPException(status_code=404, detail="User not found")

            cursor.execute("DELETE FROM users WHERE id = %s", (user_uuid,))
            conn.commit()
            print("✅ User deleted successfully")

    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")
    finally:
        conn.close()

    return {"message": "User deleted successfully"}
