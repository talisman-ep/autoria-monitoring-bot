import asyncio
import logging
import os
import asyncpg
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
from aiogram import BaseMiddleware
from typing import Callable, Dict, Any, Awaitable
from aiogram.types import TelegramObject

from src.bot.handlers.user import user_router
from src.database.setup import create_tables
from src.bot.scheduler import start_scheduler
from src.database.repository import DatabaseRepo

class DbSessionMiddleware(BaseMiddleware):
    """
    Middleware that injects a Database Repository instance into every handler.
    Manages connection acquisition and release from the pool.
    """
    def __init__(self, pool):
        self.pool = pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with self.pool.acquire() as connection:
            data['repo'] = DatabaseRepo(connection)
            return await handler(event, data)

async def main():
    load_dotenv()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    )

    # 1. Configuration
    bot_token = os.getenv("BOT_TOKEN")
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    db_name = os.getenv("DB_NAME")
    
    # Docker friendly host resolution
    db_host = os.getenv("DB_HOST", "db") 
    db_port = os.getenv("DB_PORT", "5432")

    if not bot_token:
        print("Error: BOT_TOKEN is not set")
        return

    # 2. Database Connection
    dsn = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    pool = None
    # Retry logic for container startup race conditions
    for i in range(5):
        try:
            pool = await asyncpg.create_pool(dsn)
            print("Connected to database")
            await create_tables()
            break
        except Exception as e:
            print(f"Waiting for database... ({e})")
            await asyncio.sleep(2)
            
    if not pool:
        print("Failed to connect to database")
        return

    # 3. Bot Initialization
    bot = Bot(token=bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    
    dp.update.middleware(DbSessionMiddleware(pool))
    dp.include_router(user_router)

    print("Bot started")
    
    try:
        # Run scheduler in background
        asyncio.create_task(start_scheduler(bot, pool))
        await dp.start_polling(bot)
    finally:
        await pool.close()

if __name__ == "__main__":
    try:
        if os.name == 'nt':
             asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")