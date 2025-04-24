from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from uuid import uuid4, UUID
import json

from users.endpoints import get_user_by_username, get_user_by_id
from auth.endpoints import get_current_user
from database.database import connect_to_db


class Planet(BaseModel):
    name: str
    resources: dict
    discovered_at: str
    claimed_at: str


router = APIRouter()


def validate_uuid(uuid_str: str) -> UUID:
    print(f"Validating UUID: {uuid_str}")
    try:
        return UUID(uuid_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {uuid_str}")


@router.post("/")
def create_planet(planet: Planet, current_user: dict = Depends(get_current_user)):
    print("🌍 Create Planet endpoint hit")
    print(f"🔐 Current user: {current_user}")

    conn = connect_to_db()
    if not conn:
        print("❌ Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        print("✅ Database connection successful")

    user = get_user_by_username(current_user.username)
    if not user:
        print("❌ User not found in DB")
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user[0])
    print(f"User found. ID: {user_id}")
    planet_id = uuid4()
    print(f"Generated new planet ID: {planet_id}")
    resources_json = json.dumps(planet.resources)
    print(f"Resources as JSON: {resources_json}")

    try:
        with conn.cursor() as cursor:
            print("📝 Inserting planet data into the database")
            cursor.execute("""
                INSERT INTO planets (id, name, user_id, resources, discovered_at, claimed_at) 
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (planet_id, planet.name, user_id, resources_json, planet.discovered_at, planet.claimed_at))
            conn.commit()
            print("✅ Planet created successfully")
    except Exception as e:
        print(f"❌ Error during DB insert: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating planet: {str(e)}")
    finally:
        conn.close()
        print("🔒 Database connection closed.")

    return {"id": str(planet_id), "name": planet.name, "owner_id": user_id}


@router.get("/{planet_id}")
def read_planet(planet_id: str, current_user: dict = Depends(get_current_user)):
    print(f"🌍 Reading planet with ID: {planet_id}")
    validate_uuid(planet_id)

    conn = connect_to_db()
    if not conn:
        print("❌ Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        print("✅ Database connection successful")

    try:
        with conn.cursor() as cursor:
            print(f"📝 Fetching planet data from the database for planet ID {planet_id}")
            cursor.execute("""
                SELECT id, name, user_id, resources, discovered_at, claimed_at 
                FROM planets WHERE id = %s
            """, (planet_id,))
            planet = cursor.fetchone()
            print(f"Fetched planet data: {planet}")
    finally:
        conn.close()
        print("🔒 Database connection closed.")

    if not planet:
        print(f"❌ Planet with ID {planet_id} not found")
        raise HTTPException(status_code=404, detail="Planet not found")

    resources = planet[3] if isinstance(planet[3], dict) else json.loads(planet[3])
    print(f"Resources for planet {planet_id}: {resources}")

    planet_data = {
        "id": planet[0],
        "name": planet[1],
        "owner_id": planet[2],
        "resources": resources,
        "discovered_at": planet[4],
        "claimed_at": planet[5]
    }
    print(f"Formatted planet data: {planet_data}")

    owner = get_user_by_id(planet_data["owner_id"])
    if not owner:
        print(f"❌ Owner with ID {planet_data['owner_id']} not found")
        raise HTTPException(status_code=404, detail="Owner user not found")

    print(f"Owner found: {owner}")
    if current_user.username == owner[1] or current_user.is_admin:
        print("✅ User has permission to view the planet")
        return planet_data

    print(f"❌ User does not have permission to view this planet")
    raise HTTPException(status_code=403, detail="Unauthorized to view this planet")


@router.get("/")
def read_all_planets(current_user: dict = Depends(get_current_user)):
    print("🌍 Fetching all planets for current user")

    user = get_user_by_username(current_user.username)
    if not user:
        print(f"❌ User {current_user.username} not found in DB")
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user[0])
    print(f"User found. ID: {user_id}")
    conn = connect_to_db()
    if not conn:
        print("❌ Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        print("✅ Database connection successful")

    try:
        with conn.cursor() as cursor:
            print(f"📝 Fetching all planets for user ID {user_id}")
            cursor.execute("""
                SELECT id, name, resources, discovered_at, claimed_at 
                FROM planets WHERE user_id = %s
            """, (user_id,))
            planets = cursor.fetchall()
            print(f"Fetched planets: {planets}")
    finally:
        conn.close()
        print("🔒 Database connection closed.")

    return [
        {
            "id": p[0],
            "name": p[1],
            "resources": p[2] if isinstance(p[2], dict) else json.loads(p[2]),
            "discovered_at": p[3],
            "claimed_at": p[4]
        } for p in planets
    ]


@router.put("/{planet_id}")
def update_planet(planet_id: str, planet: Planet, current_user: dict = Depends(get_current_user)):
    print(f"🌍 Updating planet with ID: {planet_id}")
    validate_uuid(planet_id)

    user = get_user_by_username(current_user.username)
    if not user:
        print(f"❌ User {current_user.username} not found in DB")
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user[0])
    print(f"User found. ID: {user_id}")
    resources_json = json.dumps(planet.resources)
    print(f"Resources as JSON: {resources_json}")
    conn = connect_to_db()
    if not conn:
        print("❌ Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        print("✅ Database connection successful")

    try:
        with conn.cursor() as cursor:
            print(f"📝 Fetching planet data for update with planet ID {planet_id}")
            cursor.execute("SELECT user_id FROM planets WHERE id = %s", (planet_id,))
            existing_planet = cursor.fetchone()
            print(f"Fetched existing planet data: {existing_planet}")
            if not existing_planet:
                print(f"❌ Planet with ID {planet_id} not found")
                raise HTTPException(status_code=404, detail="Planet not found")
            if str(existing_planet[0]) != user_id:
                print(f"❌ User with ID {user_id} is not the owner of this planet")
                raise HTTPException(status_code=403, detail="Unauthorized to update this planet")

            print(f"📝 Updating planet data with new values for planet ID {planet_id}")
            cursor.execute("""
                UPDATE planets 
                SET name = %s, resources = %s, discovered_at = %s, claimed_at = %s 
                WHERE id = %s
            """, (planet.name, resources_json, planet.discovered_at, planet.claimed_at, planet_id))
            conn.commit()
            print(f"✅ Planet with ID {planet_id} updated successfully")
    except Exception as e:
        print(f"❌ Error during DB update: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating planet: {str(e)}")
    finally:
        conn.close()
        print("🔒 Database connection closed.")

    return {"message": "Planet updated successfully"}


@router.delete("/{planet_id}")
def delete_planet(planet_id: str, current_user: dict = Depends(get_current_user)):
    print(f"🌍 Deleting planet with ID: {planet_id}")
    validate_uuid(planet_id)

    user = get_user_by_username(current_user.username)
    if not user:
        print(f"❌ User {current_user.username} not found in DB")
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user[0])
    print(f"User found. ID: {user_id}")
    conn = connect_to_db()
    if not conn:
        print("❌ Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        print("✅ Database connection successful")

    try:
        with conn.cursor() as cursor:
            print(f"📝 Fetching planet data for deletion with planet ID {planet_id}")
            cursor.execute("SELECT user_id FROM planets WHERE id = %s", (planet_id,))
            existing_planet = cursor.fetchone()
            print(f"Fetched existing planet data: {existing_planet}")
            if not existing_planet:
                print(f"❌ Planet with ID {planet_id} not found")
                raise HTTPException(status_code=404, detail="Planet not found")
            if str(existing_planet[0]) != user_id:
                print(f"❌ User with ID {user_id} is not the owner of this planet")
                raise HTTPException(status_code=403, detail="Unauthorized to delete this planet")

            print(f"📝 Deleting planet with ID {planet_id}")
            cursor.execute("DELETE FROM planets WHERE id = %s", (planet_id,))
            conn.commit()
            print(f"✅ Planet with ID {planet_id} deleted successfully")
    except Exception as e:
        print(f"❌ Error during DB delete: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting planet: {str(e)}")
    finally:
        conn.close()
        print("🔒 Database connection closed.")

    return {"message": "Planet deleted successfully"}


@router.put("/{planet_id}/claim")
def claim_planet(planet_id: str, current_user: dict = Depends(get_current_user)):
    print(f"🌍 Claiming planet with ID: {planet_id}")
    validate_uuid(planet_id)

    conn = connect_to_db()
    if not conn:
        print("❌ Database connection failed")
        raise HTTPException(status_code=500, detail="Database connection failed")
    else:
        print("✅ Database connection successful")

    user = get_user_by_username(current_user.username)
    if not user:
        print(f"❌ User {current_user.username} not found in DB")
        raise HTTPException(status_code=404, detail="User not found")

    user_id = str(user[0])
    print(f"User found. ID: {user_id}")

    try:
        with conn.cursor() as cursor:
            print(f"📝 Fetching planet data for claiming with planet ID {planet_id}")
            cursor.execute("SELECT user_id, claimed_at FROM planets WHERE id = %s", (planet_id,))
            planet = cursor.fetchone()
            print(f"Fetched planet data: {planet}")
            if not planet:
                print(f"❌ Planet with ID {planet_id} not found")
                raise HTTPException(status_code=404, detail="Planet not found")
            if str(planet[0]) == user_id:
                print(f"❌ Planet with ID {planet_id} is already claimed by user {user_id}")
                raise HTTPException(status_code=400, detail="Planet already claimed by you")

            print(f"📝 Updating planet claim data with planet ID {planet_id}")
            cursor.execute("""
                UPDATE planets 
                SET claimed_at = NOW(), user_id = %s
                WHERE id = %s
            """, (user_id, planet_id))
            conn.commit()
            print(f"✅ Planet with ID {planet_id} claimed successfully")
    except Exception as e:
        print(f"❌ Error during DB claim: {e}")
        raise HTTPException(status_code=500, detail=f"Error claiming planet: {str(e)}")
    finally:
        conn.close()
        print("🔒 Database connection closed.")

    return {"message": "Planet claimed successfully"}