from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

# Import routers
from auth.endpoints import router as auth_router
from users.endpoints import router as users_router
from buildings.endpoints import router as buildings_router
from user_buildings.endpoints import router as user_buildings_router
from user_fleets.endpoints import router as user_fleets_router
from user_battles.endpoints import router as battle_router
from planets.endpoints import router as planets_router

# -----------------------
# Logging Setup
# -----------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    filename="app_logs.log",
    filemode='a'
)

logger = logging.getLogger("crimson_dominion")

# -----------------------
# FastAPI App Setup
# -----------------------
app = FastAPI(
    title="🚀 CRIMSON DOMINION API",
    description="""
Welcome to the **Crimson Dominion API** — the backend powering your intergalactic empire!
Use this API to manage players, battles, planets, buildings, and fleets.
""",
    version="1.0.0",
    contact={
        "name": "CrimsonDominion Dev",
        "url": "https://TheCrimsonDominion.com",
        "email": "Moe.Yassir@gmail.com",
    },
    license_info={"name": "OpenSource / MIT"},
    debug=True
)

# -----------------------
# Include All Routers
# -----------------------
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/users", tags=["Users"])
app.include_router(buildings_router, prefix="/buildings", tags=["Buildings"])
app.include_router(user_buildings_router, prefix="/user-buildings", tags=["User Buildings"])
app.include_router(user_fleets_router, prefix="/user-fleets", tags=["User Fleets"])
app.include_router(battle_router, prefix="/user-battles", tags=["User Battles"])  # Corrected prefix
app.include_router(planets_router, prefix="/planets", tags=["Planets"])

# -----------------------
# Startup Event
# -----------------------
@app.on_event("startup")
def on_startup():
    logger.info("🚀 Crimson Dominion API has launched.")
    try:
        from database.database import connect_to_db
        conn = connect_to_db()
        if conn:
            logger.info("✅ Database connection successful at startup.")
            conn.close()
    except Exception as e:
        logger.error(f"❌ Failed DB check at startup: {str(e)}")

# -----------------------
# Root Endpoint
# -----------------------
@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Welcome to the Crimson Dominion API — Rule the stars!"}

# -----------------------
# Run with Uvicorn
# -----------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000)  # reload=True for dev
