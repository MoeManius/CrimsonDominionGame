from fastapi import APIRouter, HTTPException, Depends
from uuid import UUID, uuid4
import json
from auth.endpoints import get_current_user
from database.database import connect_to_db
from pydantic import BaseModel

router = APIRouter()


class BattleResult(BaseModel):
    battle_id: UUID
    attacker_id: UUID
    defender_id: UUID
    attacker_fleet_id: UUID
    defender_fleet_id: UUID
    winner_id: UUID
    loser_id: UUID
    attacker_total_ships: int
    defender_total_ships: int
    report: str


@router.post("/battle")
def start_battle(attacker_fleet_id: UUID, defender_fleet_id: UUID, current_user=Depends(get_current_user)):
    print(f"⚔️ Battle initiated: Attacker Fleet {attacker_fleet_id} vs Defender Fleet {defender_fleet_id}")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            # Get attacker fleet
            cursor.execute("SELECT id, user_id, ships FROM user_fleets WHERE id = %s", (str(attacker_fleet_id),))
            attacker_fleet = cursor.fetchone()
            if not attacker_fleet:
                raise HTTPException(status_code=404, detail="Attacker fleet not found")
            if str(attacker_fleet[1]) != str(current_user.id):
                raise HTTPException(status_code=403, detail="You do not own the attacker fleet")

            # Get defender fleet
            cursor.execute("SELECT id, user_id, ships FROM user_fleets WHERE id = %s", (str(defender_fleet_id),))
            defender_fleet = cursor.fetchone()
            if not defender_fleet:
                raise HTTPException(status_code=404, detail="Defender fleet not found")
            if str(defender_fleet[1]) == str(current_user.id):
                raise HTTPException(status_code=400, detail="Cannot attack your own fleet")

            # Parse ships
            attacker_ships = json.loads(attacker_fleet[2]) if isinstance(attacker_fleet[2], str) else attacker_fleet[2]
            defender_ships = json.loads(defender_fleet[2]) if isinstance(defender_fleet[2], str) else defender_fleet[2]

            # Calculate fleet size
            attacker_total = sum(attacker_ships.values())
            defender_total = sum(defender_ships.values())

            print(f"🛡️ Attacker total ships: {attacker_total}")
            print(f"🛡️ Defender total ships: {defender_total}")

            # Determine winner
            if attacker_total > defender_total:
                winner_id = attacker_fleet[1]
                loser_id = defender_fleet[1]
                outcome = "Attacker wins"
            elif defender_total > attacker_total:
                winner_id = defender_fleet[1]
                loser_id = attacker_fleet[1]
                outcome = "Defender wins"
            else:
                # Tie rule: attacker loses
                winner_id = defender_fleet[1]
                loser_id = attacker_fleet[1]
                outcome = "Tie - Defender wins by default"

            battle_id = uuid4()
            report = f"Battle ID: {battle_id}\n{outcome}!\nAttacker ships: {attacker_total}\nDefender ships: {defender_total}"
            print("📜 Battle Report:\n" + report)

            return BattleResult(
                battle_id=battle_id,
                attacker_id=attacker_fleet[1],
                defender_id=defender_fleet[1],
                attacker_fleet_id=attacker_fleet_id,
                defender_fleet_id=defender_fleet_id,
                winner_id=winner_id,
                loser_id=loser_id,
                attacker_total_ships=attacker_total,
                defender_total_ships=defender_total,
                report=report
            )

    except Exception as e:
        print(f"💥 Error during battle: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error during battle: {str(e)}")
    finally:
        conn.close()
