import asyncio
import os
import sys

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


async def create_tables() -> None:
    """
    Initializes the database structure.
    Creates necessary tables (users, searches, seen_cars) and performs migrations
    to ensure the schema is up-to-date with the latest code changes.
    """
    max_retries = 10
    delay = 2

    conn = None
    for i in range(max_retries):
        try:
            print(f"Attempting to connect {i+1}/{max_retries} to {DB_HOST}...")
            conn = await asyncpg.connect(DATABASE_URL, ssl="disable")
            break
        except Exception as e:
            print(f"Database is unavailable. Waiting {delay} sec. Error: {e}")
            await asyncio.sleep(delay)

    if not conn:
        print("Failed to connect to the database after multiple attempts.")
        return

    try:
        print("Creating 'users' table...")
        await conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS users(
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW()
            );
            '''
        )

        print("Creating 'searches' table (if missing)...")
        await conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS searches(
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,

                brand TEXT NOT NULL,
                brand_id INT DEFAULT 0,

                model_name TEXT,
                model_id INT DEFAULT 0,

                year_from INT DEFAULT 0,
                year_to INT DEFAULT 0,
                price_from INT DEFAULT 0,
                price_to INT DEFAULT 0,

                region_id INT DEFAULT 0,
                fuel_id INT DEFAULT 0,
                gearbox_id INT DEFAULT 0,

                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW()
            );
            '''
        )

        print("Migrating 'searches' table (adding missing columns)...")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS brand_id INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS model_id INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS model_name TEXT;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS year_from INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS year_to INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS price_from INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS price_to INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS region_id INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS fuel_id INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS gearbox_id INT DEFAULT 0;")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';")
        await conn.execute("ALTER TABLE searches ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")

        # Data migration block
        await conn.execute(
            '''
            DO $$
            BEGIN
                -- Migrate Gearbox data from old text column if exists
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='searches' AND column_name='gearbox'
                ) THEN
                    UPDATE searches
                    SET gearbox_id = COALESCE(gearbox_id, gearbox, 0)
                    WHERE gearbox_id IS NULL OR gearbox_id = 0;
                END IF;

                -- Migrate Fuel data
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='searches' AND column_name='fuel_type'
                ) THEN
                    UPDATE searches
                    SET fuel_id = COALESCE(fuel_id, fuel_type, 0)
                    WHERE fuel_id IS NULL OR fuel_id = 0;
                END IF;

                -- Migrate Model names
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='searches' AND column_name='model'
                ) THEN
                    UPDATE searches
                    SET model_name = COALESCE(model_name, model)
                    WHERE model_name IS NULL;
                END IF;
            END $$;
            '''
        )

        print("Creating 'seen_cars' table...")
        await conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS seen_cars (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                car_id BIGINT NOT NULL,
                seen_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(user_id, car_id)
            );
            '''
        )

        print("Creating indexes...")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_searches_user_status ON searches(user_id, status);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_seen_cars_user ON seen_cars(user_id);")

        print("Tables created and migrated successfully.")
    except Exception as e:
        print(f"Error initializing database: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(create_tables())