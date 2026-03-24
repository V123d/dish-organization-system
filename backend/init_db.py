import asyncio
from app.database import engine, Base
from app.models.user import User
from app.models.history import MenuHistory
from app.models.chat_session import ChatSession

async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized successfully.")

if __name__ == "__main__":
    asyncio.run(init())
