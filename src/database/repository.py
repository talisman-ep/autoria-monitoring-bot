from typing import List, Optional, Any
from asyncpg import Connection
from dataclasses import dataclass

@dataclass
class SearchRecord:
    id: int
    user_id: int
    brand: str
    brand_id: int
    model_name: Optional[str]
    model_id: int
    year_from: int
    year_to: int
    price_from: int
    price_to: int
    region_id: int
    fuel_id: int
    gearbox_id: int
    status: str

class DatabaseRepo:
    """
    Repository pattern implementation for database operations.
    Abstracts raw SQL queries from business logic.
    """
    def __init__(self, conn: Connection):
        self.conn = conn

    # --- Users ---
    async def add_user(self, user_id: int, username: str, full_name: str):
        """Creates or updates a user record."""
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, full_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id) DO UPDATE 
            SET username = EXCLUDED.username, full_name = EXCLUDED.full_name
            """,
            user_id, username, full_name
        )

    # --- Searches (Subscriptions) ---
    async def add_search(self, user_id: int, data: dict):
        """
        Creates a new search subscription.
        Args:
            user_id: Telegram user ID.
            data: Dictionary containing FSM state data.
        """
        await self.conn.execute(
            """
            INSERT INTO searches
            (user_id, brand, brand_id, model_name, model_id, year_from, year_to, 
             price_from, price_to, region_id, fuel_id, gearbox_id, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'active')
            """,
            user_id,
            data["brand_name"],
            int(data.get("brand_id", 0)),
            data.get("model_name"),
            int(data.get("model_id", 0)),
            int(data.get("year_from", 0)),
            int(data.get("year_to", 0)),
            int(data.get("price_from", 0)),
            int(data.get("price_to", 0)),
            int(data.get("region_id", 0)),
            int(data.get("fuel_id", 0)),
            int(data.get("gearbox_id", 0)),
        )

    async def get_active_searches(self) -> List[dict]:
        """Fetches all active subscriptions for the scheduler."""
        rows = await self.conn.fetch("SELECT * FROM searches WHERE status = 'active'")
        return rows

    async def get_user_searches(self, user_id: int) -> List[dict]:
        """Fetches active subscriptions for a specific user."""
        return await self.conn.fetch(
            "SELECT id, brand, model_name, year_from, status FROM searches WHERE user_id=$1 AND status='active' ORDER BY id DESC",
            user_id
        )

    async def delete_search(self, search_id: int, user_id: int):
        """Deletes (or deactivates) a subscription."""
        await self.conn.execute("DELETE FROM searches WHERE id=$1 AND user_id=$2", search_id, user_id)

    # --- Seen Cars ---
    async def is_car_seen(self, user_id: int, car_id: int) -> bool:
        """
        Checks if a user has already received a specific car.
        Returns:
            True if car was already seen.
            False if it's new (and inserts it as seen).
        """
        res = await self.conn.execute(
            """
            INSERT INTO seen_cars (user_id, car_id)
            VALUES ($1, $2)
            ON CONFLICT (user_id, car_id) DO NOTHING
            """,
            user_id, int(car_id)
        )
        # 'INSERT 0 1' means row was inserted (New car) -> Return False
        # 'INSERT 0 0' means conflict/duplicate (Seen car) -> Return True
        return res != "INSERT 0 1"