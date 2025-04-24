import os
import psycopg
from dotenv import load_dotenv
from fastapi import HTTPException
from uuid import UUID

# Load environment variables from .env file
load_dotenv()

# Database connection function
def connect_to_db():
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise HTTPException(status_code=500, detail="Database URL is not set in environment variables")

    try:
        print("🔌 Connecting to database...")
        return psycopg.connect(DATABASE_URL)
    except Exception as e:
        print(f"❌ Database connection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# Get a user by ID
def get_user_by_id(user_id: str):
    try:
        user_uuid = UUID(user_id)
        print(f"🔍 Fetching user by ID: {user_uuid}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id, username, email, is_admin FROM users WHERE id = %s", (user_uuid,))
                user = cursor.fetchone()
                if user:
                    print(f"✅ User found: {user}")
                else:
                    print(f"❌ User not found for ID: {user_uuid}")
        finally:
            conn.close()
        return user
    return None

# Function to get all users (for admin purposes)
def get_all_users():
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                print("📋 Fetching all users")
                cursor.execute("SELECT id, username, email, is_admin FROM users")
                users = cursor.fetchall()
                print(f"✅ Found {len(users)} users")
        finally:
            conn.close()
        return users
    return None

# Function to create a new user
def create_user(username: str, email: str, password: str, is_admin: bool = False):
    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                print(f"👤 Creating user: {username}, admin: {is_admin}")
                cursor.execute("""
                    INSERT INTO users (username, email, password, is_admin)
                    VALUES (%s, %s, %s, %s) RETURNING id;
                """, (username, email, password, is_admin))
                user_id = cursor.fetchone()[0]
                conn.commit()
                print(f"✅ User created with ID: {user_id}")
            conn.close()
            return user_id
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"❌ Error creating user: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")
    raise HTTPException(status_code=500, detail="Database connection error")

# Function to update user data
def update_user(user_id: str, username: str, email: str, is_admin: bool):
    try:
        user_uuid = UUID(user_id)
        print(f"✏️ Updating user {user_uuid}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE users
                    SET username = %s, email = %s, is_admin = %s
                    WHERE id = %s
                """, (username, email, is_admin, user_uuid))
                conn.commit()
                print(f"✅ User {user_uuid} updated successfully")
            conn.close()
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"❌ Error updating user: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error updating user: {str(e)}")
    raise HTTPException(status_code=500, detail="Database connection error")

# Function to delete a user by ID
def delete_user(user_id: str):
    try:
        user_uuid = UUID(user_id)
        print(f"🗑️ Deleting user {user_uuid}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format")

    conn = connect_to_db()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE id = %s", (user_uuid,))
                conn.commit()
                print(f"✅ User {user_uuid} deleted successfully")
            conn.close()
        except Exception as e:
            conn.rollback()
            conn.close()
            print(f"❌ Error deleting user: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")
    raise HTTPException(status_code=500, detail="Database connection error")
