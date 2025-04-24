from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from uuid import UUID, uuid4
from database.database import connect_to_db, get_user_by_id
from auth.endpoints import get_current_user, TokenData

router = APIRouter()

# ------------------------
# Schemas
# ------------------------

class BattleCreateRequest(BaseModel):
    opponent_id: UUID

class BattleResult(BaseModel):
    battle_id: UUID
    user_1: str
    user_2: str
    winner: str
    report: str

# ------------------------
# Routes
# ------------------------

@router.post("/create_battle", response_model=BattleResult)
def create_battle(battle_data: BattleCreateRequest, current_user: TokenData = Depends(get_current_user)):
    print(f"⚔️ Battle initiation: {current_user.username} vs {battle_data.opponent_id}")

    conn = connect_to_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        with conn.cursor() as cursor:
            # Fetch user 1 and opponent
            user1 = get_user_by_id(current_user.id)
            user2 = get_user_by_id(str(battle_data.opponent_id))

            if not user2:
                raise HTTPException(status_code=404, detail="Opponent not found")
            if str(battle_data.opponent_id) == current_user.id:
                raise HTTPException(status_code=400, detail="Cannot battle yourself")

            # Generate dummy fleet sizes
            cursor.execute("SELECT FLOOR(RANDOM() * 100 + 1)::int AS fleet_size")
            fleet1 = cursor.fetchone()[0]
            cursor.execute("SELECT FLOOR(RANDOM() * 100 + 1)::int AS fleet_size")
            fleet2 = cursor.fetchone()[0]

            # Determine winner
            if fleet1 > fleet2:
                winner_id = user1[0]
                winner_name = user1[1]
            elif fleet2 > fleet1:
                winner_id = user2[0]
                winner_name = user2[1]
            else:
                winner_id = None
                winner_name = "Draw"

            battle_id = uuid4()
            report = (
                f"{user1[1]} (Fleet: {fleet1}) vs {user2[1]} (Fleet: {fleet2}) — "
                f"{'Winner: ' + winner_name if winner_id else 'It was a draw!'}"
            )

            # Save battle
            cursor.execute("""
                INSERT INTO battles (id, user_1_id, user_2_id, winner_id, report)
                VALUES (%s, %s, %s, %s, %s)
            """, (battle_id, user1[0], user2[0], winner_id, report))
            conn.commit()

            print(f"✅ Battle {battle_id} created. {report}")

            return {
                "battle_id": battle_id,
                "user_1": user1[1],
                "user_2": user2[1],
                "winner": winner_name,
                "report": report
            }

    except Exception as e:
        print(f"❌ Error during battle: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Battle error: {str(e)}")
    finally:
        conn.close()
