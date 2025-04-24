from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from uuid import UUID, uuid4
import json
from auth.endpoints import get_current_user
from database.database import connect_to_db

router = APIRouter()

class UserFleetRequest(BaseModel):
    planet_id: UUID
    ships: dict
    name: str

class UserFleet(BaseModel):
    id: UUID
    user_id: UUID
    planet_id: UUID
    ships: dict
    name: str

@router.post("/")
def create_user_fleet(user_fleet_request: UserFleetRequest, current_user=Depends(get_current_user)):
    print("Creating user fleet...")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    fleet_id = uuid4()
    ships_json = json.dumps(user_fleet_request.ships)

    try:
        with conn.cursor() as cursor:
            print(f"Checking if planet {user_fleet_request.planet_id} exists for user {current_user.id}")
            cursor.execute("SELECT id FROM planets WHERE id = %s AND user_id = %s",
                           (str(user_fleet_request.planet_id), str(current_user.id)))
            planet = cursor.fetchone()
            if not planet:
                raise HTTPException(status_code=404, detail="Planet not found or not owned by the user")

            print(f"Inserting user fleet with ID {fleet_id} into database")
            cursor.execute("""
                INSERT INTO user_fleets (id, user_id, planet_id, ships, name)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """, (str(fleet_id), str(current_user.id), str(user_fleet_request.planet_id),
                  ships_json, user_fleet_request.name))
            conn.commit()
    except Exception as e:
        print(f"Error creating user fleet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating user fleet: {str(e)}")
    finally:
        conn.close()

    print(f"User fleet with ID {fleet_id} created successfully")
    return UserFleet(
        id=fleet_id,
        user_id=current_user.id,
        planet_id=user_fleet_request.planet_id,
        ships=user_fleet_request.ships,
        name=user_fleet_request.name
    )


@router.get("/{user_fleet_id}")
def get_user_fleet(user_fleet_id: UUID, current_user=Depends(get_current_user)):
    print(f"Retrieving user fleet with ID {user_fleet_id}")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, user_id, planet_id, ships, name FROM user_fleets WHERE id = %s
            """, (str(user_fleet_id),))
            user_fleet = cursor.fetchone()
    finally:
        conn.close()

    if user_fleet:
        if str(user_fleet[1]) == str(current_user.id):
            print(f"User fleet with ID {user_fleet_id} found and belongs to the current user")

            # Check if ships is already a dictionary (no need to parse JSON)
            ships = user_fleet[3]
            if isinstance(ships, str):
                ships = json.loads(ships)

            return UserFleet(
                id=user_fleet[0],
                user_id=user_fleet[1],
                planet_id=user_fleet[2],
                ships=ships,
                name=user_fleet[4]
            )

        raise HTTPException(status_code=403, detail="Unauthorized to view this fleet")

    raise HTTPException(status_code=404, detail="User fleet not found")


@router.get("/")
def get_all_user_fleets(current_user=Depends(get_current_user)):
    print(f"Retrieving all fleets for user {current_user.id}")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, planet_id, ships, name FROM user_fleets WHERE user_id = %s
            """, (str(current_user.id),))
            user_fleets = cursor.fetchall()
    finally:
        conn.close()

    print(f"Found {len(user_fleets)} fleets for user {current_user.id}")
    return [
        UserFleet(
            id=f[0],
            user_id=current_user.id,
            planet_id=f[1],
            ships=json.loads(f[2]) if isinstance(f[2], str) else f[2],  # Ensure correct parsing
            name=f[3]
        )
        for f in user_fleets
    ]


@router.put("/{user_fleet_id}")
def update_user_fleet(user_fleet_id: UUID, user_fleet_request: UserFleetRequest,
                      current_user=Depends(get_current_user)):
    print(f"Updating user fleet with ID {user_fleet_id}")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    ships_json = json.dumps(user_fleet_request.ships)

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM user_fleets WHERE id = %s", (str(user_fleet_id),))
            user_fleet = cursor.fetchone()
            if not user_fleet:
                raise HTTPException(status_code=404, detail="User fleet not found")

            if str(user_fleet[0]) != str(current_user.id):
                raise HTTPException(status_code=403, detail="Unauthorized to update this fleet")

            print(f"Updating fleet ID {user_fleet_id} with new planet {user_fleet_request.planet_id} and ships")
            cursor.execute("""
                UPDATE user_fleets SET planet_id = %s, ships = %s, name = %s WHERE id = %s
            """, (str(user_fleet_request.planet_id), ships_json, user_fleet_request.name, str(user_fleet_id)))
            conn.commit()
    except Exception as e:
        print(f"Error updating user fleet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error updating user fleet: {str(e)}")
    finally:
        conn.close()

    print(f"User fleet with ID {user_fleet_id} updated successfully")
    return {"message": "User fleet updated successfully"}


@router.delete("/{user_fleet_id}")
def delete_user_fleet(user_fleet_id: UUID, current_user=Depends(get_current_user)):
    print(f"Deleting user fleet with ID {user_fleet_id}")
    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM user_fleets WHERE id = %s", (str(user_fleet_id),))
            user_fleet = cursor.fetchone()
            if not user_fleet:
                raise HTTPException(status_code=404, detail="User fleet not found")

            if str(user_fleet[0]) != str(current_user.id):
                raise HTTPException(status_code=403, detail="Unauthorized to delete this fleet")

            print(f"Deleting fleet with ID {user_fleet_id} from the database")
            cursor.execute("DELETE FROM user_fleets WHERE id = %s", (str(user_fleet_id),))
            conn.commit()
    except Exception as e:
        print(f"Error deleting user fleet: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting user fleet: {str(e)}")
    finally:
        conn.close()

    print(f"User fleet with ID {user_fleet_id} deleted successfully")
    return {"message": "User fleet deleted successfully"}
