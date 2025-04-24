from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from uuid import uuid4, UUID
from auth import TokenData
from auth.endpoints import get_current_user
from database.database import connect_to_db

router = APIRouter()

class UserBuildingRequest(BaseModel):
    name: str
    planet_id: str
    level: int = 1

class UserBuilding(BaseModel):
    id: str
    name: str
    planet_id: str
    level: int
    user_id: str

    class Config:
        json_encoders = {
            UUID: str
        }

@router.post("/")
def create_user_building(user_building_request: UserBuildingRequest, current_user: TokenData = Depends(get_current_user)):
    print(f"🔧 Creating user building for user {current_user.id} with payload: {user_building_request}")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    user_building_id = str(uuid4())
    print(f"🆔 Generated new user building ID: {user_building_id}")

    try:
        with conn.cursor() as cursor:
            print(f"🔍 Verifying planet ownership for planet_id={user_building_request.planet_id}")
            cursor.execute("SELECT id FROM planets WHERE id = %s AND user_id = %s",
                           (user_building_request.planet_id, current_user.id))
            planet = cursor.fetchone()
            print(f"🔍 Planet ownership check result: {planet}")
            if not planet:
                print(f"❌ Planet {user_building_request.planet_id} not found or not owned by user {current_user.id}")
                raise HTTPException(status_code=404, detail="Planet not found or not owned by the user")

            print("📥 Inserting new building into database...")
            cursor.execute("""
                INSERT INTO user_buildings (id, name, planet_id, level, user_id)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """, (
                user_building_id, user_building_request.name, user_building_request.planet_id, user_building_request.level,
                current_user.id))
            conn.commit()

            cursor.execute("SELECT * FROM user_buildings WHERE id = %s", (user_building_id,))
            inserted_building = cursor.fetchone()
            print(f"✅ Building inserted: {inserted_building}")

    except Exception as e:
        print(f"💥 Error during building creation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating user building: {str(e)}")
    finally:
        conn.close()

    return UserBuilding(id=user_building_id, name=user_building_request.name, planet_id=user_building_request.planet_id,
                        level=user_building_request.level, user_id=current_user.id)

@router.get("/{user_building_id}")
def get_user_building(user_building_id: str, current_user: TokenData = Depends(get_current_user)):
    print(f"📦 Fetching user building with ID {user_building_id}...")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, planet_id, level, user_id FROM user_buildings WHERE id = %s
            """, (user_building_id,))
            user_building = cursor.fetchone()
            print(f"🔍 Query result: {user_building}")
    finally:
        conn.close()

    if user_building:
        print(f"🔑 Checking access: current_user.id={current_user.id}, building_owner_id={user_building[4]}")
        if str(user_building[4]) == str(current_user.id):
            print("✅ User has permission to view this building.")
            return UserBuilding(id=str(user_building[0]), name=user_building[1], planet_id=str(user_building[2]),
                                level=user_building[3], user_id=str(user_building[4]))
        else:
            print("❌ User does not have permission to view this building.")
            raise HTTPException(status_code=403, detail="Unauthorized to view this building")

    print(f"❌ User building with ID {user_building_id} not found.")
    raise HTTPException(status_code=404, detail="User building not found")

@router.get("/")
def get_all_user_buildings(current_user: TokenData = Depends(get_current_user)):
    print(f"📋 Fetching all user buildings for user {current_user.id}...")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, name, planet_id, level, user_id FROM user_buildings WHERE user_id = %s
            """, (current_user.id,))
            user_buildings = cursor.fetchall()
            print(f"✅ Found {len(user_buildings)} user buildings.")
    finally:
        conn.close()

    return [
        UserBuilding(id=str(ub[0]), name=ub[1], planet_id=str(ub[2]), level=ub[3], user_id=str(ub[4]))
        for ub in user_buildings
    ]

@router.put("/{user_building_id}")
def update_user_building(user_building_id: str, user_building_request: UserBuildingRequest,
                         current_user: TokenData = Depends(get_current_user)):
    print(f"🔧 Updating user building with ID {user_building_id} for user {current_user.id}")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM user_buildings WHERE id = %s", (user_building_id,))
            user_building = cursor.fetchone()
            print(f"🔍 Retrieved building owner: {user_building}")

            if not user_building:
                raise HTTPException(status_code=404, detail="User building not found")

            if str(user_building[0]) != str(current_user.id):
                print(f"❌ User {current_user.id} is not authorized to update this building.")
                raise HTTPException(status_code=403, detail="Unauthorized to update this user building")

            print(f"✏️ Updating name to '{user_building_request.name}', level to {user_building_request.level}")
            cursor.execute("""
                UPDATE user_buildings SET name = %s, level = %s WHERE id = %s
            """, (user_building_request.name, user_building_request.level, user_building_id))
            conn.commit()
            print("✅ Update successful.")
    except Exception as e:
        print(f"💥 Error during building update: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating user building: {str(e)}")
    finally:
        conn.close()

    return {"message": "User building updated successfully"}

@router.delete("/{user_building_id}")
def delete_user_building(user_building_id: str, current_user: TokenData = Depends(get_current_user)):
    print(f"🗑️ Deleting user building with ID {user_building_id} for user {current_user.id}")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM user_buildings WHERE id = %s", (user_building_id,))
            user_building = cursor.fetchone()
            print(f"🔍 Retrieved building owner: {user_building}")

            if not user_building:
                raise HTTPException(status_code=404, detail="User building not found")

            if str(user_building[0]) != str(current_user.id):
                print(f"❌ User {current_user.id} is not authorized to delete this building.")
                raise HTTPException(status_code=403, detail="Unauthorized to delete this user building")

            print("🧨 Deleting building from database...")
            cursor.execute("DELETE FROM user_buildings WHERE id = %s", (user_building_id,))
            conn.commit()
            print("✅ Deletion successful.")
    except Exception as e:
        print(f"💥 Error during building deletion: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting user building: {str(e)}")
    finally:
        conn.close()

    return {"message": "User building deleted successfully"}
