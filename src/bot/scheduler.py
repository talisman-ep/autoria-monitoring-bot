import asyncio
import logging
from aiogram import Bot
from asyncpg import Pool

from src.parser.scraper import AutoRiaScraper
from src.database.repository import DatabaseRepo

logger = logging.getLogger(__name__)

# Limits simultaneous requests to AutoRia to avoid 429 Too Many Requests errors
MAX_CONCURRENCY = 5

async def process_search(search: dict, bot: Bot, db_pool: Pool, scraper: AutoRiaScraper, semaphore: asyncio.Semaphore):
    """
    Processes a single search subscription:
    1. Acquires a semaphore slot (rate limiting).
    2. Performs the HTTP request to AutoRia.
    3. Filters results (name check).
    4. Saves new items to DB and notifies the user.
    """
    user_id = search["user_id"]
    brand_name = search["brand"]
    
    # Rate limiting block
    async with semaphore:
        try:
            found_cars = await scraper.search_cars(
                brand_id=int(search.get("brand_id") or 0),
                model_id=int(search.get("model_id") or 0),
                year_from=int(search.get("year_from") or 0),
                year_to=int(search.get("year_to") or 0),
                price_from=int(search.get("price_from") or 0),
                price_to=int(search.get("price_to") or 0),
                region_id=int(search.get("region_id") or 0),
                fuel_id=int(search.get("fuel_id") or 0),
                gearbox_id=int(search.get("gearbox_id") or 0),
            )
        except Exception as e:
            logger.error(f"Error scraping for user {user_id}: {e}")
            return

    if not found_cars:
        return
    
    # --- SAFETY CATCH: Name-based Filtering ---
    # Sometimes API returns unrelated cars if ID is invalid.
    # We double-check if the model name exists in the car title.
    target_model = search.get("model_name")
    filtered_cars = []

    if target_model and target_model not in ["Будь-яка", "Всі моделі"]:
        for car in found_cars:
            if target_model.lower() in car.title.lower():
                filtered_cars.append(car)
            else:
                # Debug log: filtered out unrelated car
                pass
        
        found_cars = filtered_cars
        
        if not found_cars:
            return

    # Database operations and Notification logic
    # (No semaphore here, as DB is fast and has its own pool)
    new_cars_count = 0
    
    try:
        async with db_pool.acquire() as conn:
            repo = DatabaseRepo(conn)
            for car in found_cars:
                # Check if user has already seen this car
                is_seen = await repo.is_car_seen(user_id, car.id)
                if is_seen:
                    continue
                
                new_cars_count += 1
                
                # Construct message
                msg = (
                    f"🚗 <b>{car.title}</b>\n"
                    f"💰 <b>{car.price_usd} $</b>\n\n"
                    f"📏 {car.mileage} тис. км\n"
                    f"📍 {car.location}\n"
                    f"⚙️ {car.gearbox} | ⛽ {car.fuel}\n\n"
                    f"🔗 <a href='{car.url}'>Відкрити оголошення</a>"
                )

                try:
                    if car.image_url:
                        await bot.send_photo(user_id, photo=car.image_url, caption=msg, parse_mode="HTML")
                    else:
                        await bot.send_message(user_id, msg, parse_mode="HTML", disable_web_page_preview=False)
                    
                    # Small delay to avoid Telegram flood limits
                    await asyncio.sleep(0.5)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {e}")

        if new_cars_count > 0:
            logger.info(f"User {user_id}: sent {new_cars_count} new cars ({brand_name})")
            
    except Exception as e:
        logger.error(f"DB/Logic error for user {user_id}: {e}")


async def check_new_cars(bot: Bot, db_pool: Pool):
    """
    Main cycle function. Launches search tasks in parallel groups.
    """
    scraper = AutoRiaScraper()
    
    # 1. Fetch all active subscriptions
    async with db_pool.acquire() as conn:
        repo = DatabaseRepo(conn)
        searches = await repo.get_active_searches()

    if not searches:
        return

    logger.info(f"Scheduler: checking {len(searches)} active searches...")
    
    # 2. Create tasks with semaphore
    sem = asyncio.Semaphore(MAX_CONCURRENCY)
    tasks = []
    
    for search in searches:
        task = asyncio.create_task(
            process_search(search, bot, db_pool, scraper, sem)
        )
        tasks.append(task)
    
    # 3. Wait for all tasks to complete
    await asyncio.gather(*tasks)
    
    logger.info("Scheduler: cycle finished.")


async def start_scheduler(bot: Bot, db_pool: Pool):
    logger.info("Scheduler started (interval: 10 min)")
    
    # Warm-up delay
    await asyncio.sleep(10)
    
    while True:
        try:
            await check_new_cars(bot, db_pool)
        except Exception as e:
            logger.error(f"Critical scheduler error: {e}")

        logger.info("Sleeping for 10 min...")
        await asyncio.sleep(600)