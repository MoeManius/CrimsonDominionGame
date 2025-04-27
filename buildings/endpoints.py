import os
import psycopg
from dotenv import load_dotenv
from fastapi import HTTPException, APIRouter, Depends
from uuid import uuid4, UUID
from pydantic import BaseModel
from auth.endpoints import get_current_user, TokenData
from database.database import connect_to_db

# Load environment variables from .env file
load_dotenv()

# Create the router for building-related endpoints
router = APIRouter()

# Model to define the structure of the building request payload
class BuildingRequest(BaseModel):
    name: str
    type: str  # Added type for building
    planet_id: UUID  # Changed to UUID
    level: int = None  # This will be automatically determined

# Model to represent a building's information
class Building(BaseModel):
    id: UUID
    name: str
    type: str  # Added type for building
    planet_id: UUID  # Changed to UUID
    level: int

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

# Function to create a new building
@router.post("/")
def create_building(building_request: BuildingRequest, current_user: TokenData = Depends(get_current_user)):
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    building_id = str(uuid4())
    print(f"[CREATE] User: {current_user.id}, Planet: {building_request.planet_id}")

    try:
        with conn.cursor() as cursor:
            # Ensure the planet exists for the user
            print(f"[DB] Checking if planet {building_request.planet_id} exists for user {current_user.id}")
            cursor.execute("SELECT id FROM planets WHERE id = %s AND user_id = %s", (building_request.planet_id, current_user.id))
            planet = cursor.fetchone()
            print(f"[DB] Planet fetch result: {planet}")

            if not planet:
                raise HTTPException(status_code=404, detail="Planet not found or not owned by the user")

            # Get the current max level of any building on the planet (auto-increment logic)
            print(f"[DB] Fetching max level for planet {building_request.planet_id}")
            cursor.execute("""
                SELECT MAX(level) FROM buildings WHERE planet_id = %s
            """, (building_request.planet_id,))
            max_level = cursor.fetchone()[0]
            print(f"[DB] Max level for planet {building_request.planet_id}: {max_level}")

            # Set the level to max level + 1, or default to 1 if no buildings exist
            level = max_level + 1 if max_level else 1
            print(f"[CREATE] New building level: {level}")

            # Insert the new building record (added `type`)
            print(f"[DB] Inserting new building with ID {building_id}, Name: {building_request.name}, Level: {level}, Type: {building_request.type}")
            cursor.execute("""
                INSERT INTO buildings (id, name, planet_id, level, type)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """, (building_id, building_request.name, building_request.planet_id, level, building_request.type))
            conn.commit()
            print(f"[DB] New building created with ID: {building_id}")
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] Error creating building: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating building: {str(e)}")
    finally:
        conn.close()

    return Building(id=building_id, name=building_request.name, type=building_request.type, planet_id=building_request.planet_id, level=level)

# Endpoint to get a building by its ID
@router.get("/{building_id}")
def get_building(building_id: str, current_user: TokenData = Depends(get_current_user)):
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    print(f"[GET] Fetching building {building_id} for user {current_user.id}")

    try:
        with conn.cursor() as cursor:
            print(f"[DB] Checking if building {building_id} exists for user {current_user.id}")
            cursor.execute("""
                SELECT b.id, b.name, b.planet_id, b.level, b.type
                FROM buildings b
                JOIN planets p ON b.planet_id = p.id
                WHERE b.id = %s AND p.user_id = %s
            """, (building_id, current_user.id))
            building = cursor.fetchone()
            print(f"[DB] Building fetch result: {building}")
    finally:
        conn.close()

    if building:
        print(f"[GET] Building {building_id} fetched for user {current_user.id}")
        return Building(id=building[0], name=building[1], type=building[4], planet_id=building[2], level=building[3])

    raise HTTPException(status_code=404, detail="Building not found or not owned by user")

# Endpoint to get all buildings for the current user
@router.get("/")
def get_all_buildings(current_user: TokenData = Depends(get_current_user)):
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    print(f"[LIST] Fetching all buildings for user {current_user.id}")

    try:
        with conn.cursor() as cursor:
            print(f"[DB] Fetching all buildings for user {current_user.id}")
            cursor.execute("""
                SELECT b.id, b.name, b.planet_id, b.level, b.type
                FROM buildings b
                JOIN planets p ON b.planet_id = p.id
                WHERE p.user_id = %s
            """, (current_user.id,))
            buildings = cursor.fetchall()
            print(f"[DB] Buildings fetch result: {buildings}")
    finally:
        conn.close()

    print(f"[LIST] {len(buildings)} buildings found for user {current_user.id}")

    return [
        Building(id=b[0], name=b[1], type=b[4], planet_id=b[2], level=b[3])
        for b in buildings
    ]

# Endpoint to update a building's details (e.g., upgrade its level)
@router.put("/{building_id}")
def update_building(building_id: str, building_request: BuildingRequest, current_user: TokenData = Depends(get_current_user)):
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    print(f"[UPDATE] Attempting to update building {building_id} by user {current_user.id}")

    try:
        with conn.cursor() as cursor:
            print(f"[DB] Checking if building {building_id} exists for user {current_user.id}")
            cursor.execute("""
                SELECT b.id, b.level FROM buildings b
                JOIN planets p ON b.planet_id = p.id
                WHERE b.id = %s AND p.user_id = %s
            """, (building_id, current_user.id))
            building = cursor.fetchone()
            print(f"[DB] Building fetch result: {building}")

            if not building:
                raise HTTPException(status_code=404, detail="Building not found or not owned by user")

            current_level = building[1]
            print(f"[UPDATE] Current building level: {current_level}")

            # Increment the building's level
            new_level = current_level + 1
            print(f"[UPDATE] New building level: {new_level}")

            # Update the building's details
            cursor.execute("""
                UPDATE buildings SET level = %s WHERE id = %s
            """, (new_level, building_id))
            conn.commit()
            print(f"[DB] Building {building_id} updated to level {new_level}")
    except Exception as e:
        print(f"[ERROR] Error updating building: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating building: {str(e)}")
    finally:
        conn.close()

    return {"message": f"Building upgraded to level {new_level} successfully"}

# Endpoint to delete a building by its ID
@router.delete("/{building_id}")
def delete_building(building_id: str, current_user: TokenData = Depends(get_current_user)):
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    print(f"[DELETE] Attempting to delete building {building_id} by user {current_user.id}")

    try:
        with conn.cursor() as cursor:
            print(f"[DB] Checking if building {building_id} exists for user {current_user.id}")
            cursor.execute("""
                SELECT b.id FROM buildings b
                JOIN planets p ON b.planet_id = p.id
                WHERE b.id = %s AND p.user_id = %s
            """, (building_id, current_user.id))
            building = cursor.fetchone()
            print(f"[DB] Building fetch result: {building}")

            if not building:
                raise HTTPException(status_code=404, detail="Building not found or not owned by user")

            cursor.execute("DELETE FROM buildings WHERE id = %s", (building_id,))
            conn.commit()
            print(f"[DB] Building {building_id} deleted")
    except Exception as e:
        print(f"[ERROR] Error deleting building: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting building: {str(e)}")
    finally:
        conn.close()

    return {"message": "Building deleted successfully"}
