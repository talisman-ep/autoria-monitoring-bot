import asyncio
import aiohttp
import logging
import json
import re
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class CarDTO:
    """Data Transfer Object representing a single car advertisement."""
    id: int
    title: str
    price_usd: int
    url: str
    mileage: int = 0
    image_url: str = ""
    location: str = ""
    gearbox: str = ""
    fuel: str = ""


class AutoRiaScraper:
    """
    Scraper for Auto.ria.com using asynchronous requests.
    
    Features:
    - RAM Caching for static data (Brands, Models, States) to reduce API load.
    - Robust HTML parsing using Regex (fallback mechanism for Nuxt/Pinia states).
    - Concurrent enrichment of car details.
    """

    BASE_SEARCH_URL = "https://auto.ria.com/uk/search/"
    MODELS_URL = "https://auto.ria.com/api/categories/1/marks/{}/models"
    BRANDS_URL = "https://auto.ria.com/api/categories/1/marks"
    STATES_URL = "https://auto.ria.com/api/states"
    FINAL_PAGE_URL = "https://auto.ria.com/bff/final-page/public/{car_id}"

    # --- In-Memory Cache (Class Level) ---
    _brands_cache: List[Dict] = []
    _brands_last_update: float = 0
    
    _states_cache: List[Dict] = []
    _states_last_update: float = 0
    
    _models_cache: Dict[int, List[Dict]] = {}
    
    # Cache Time-To-Live in seconds (1 hour)
    CACHE_TTL = 3600

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/121.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        self._details_concurrency = 6
        self._details_timeout_sec = 20

    async def get_brands(self) -> List[Dict]:
        """
        Fetches the list of car brands. 
        Uses in-memory cache if available and fresh.
        """
        now = time.time()
        if self._brands_cache and (now - self._brands_last_update < self.CACHE_TTL):
            return self._brands_cache

        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(self.BRANDS_URL, timeout=15) as r:
                    if r.status != 200:
                        logger.warning(f"Failed to fetch brands. Status: {r.status}")
                        return []
                    data = await r.json(content_type=None)
                    
                    # Normalize data
                    out = []
                    for item in data:
                        name = item.get("name")
                        val = item.get("value", item.get("id"))
                        if name and val:
                            out.append({"name": name, "id": int(val)})
                    
                    # Update cache
                    AutoRiaScraper._brands_cache = out
                    AutoRiaScraper._brands_last_update = now
                    logger.info(f"Brands cache updated: {len(out)} items")
                    return out
            except Exception as e:
                logger.error(f"Error fetching brands: {e}")
                return []
            
    async def get_states(self) -> List[Dict]:
        """
        Fetches the list of regions (states).
        Uses params={'langId': 4} to get Ukrainian names.
        """
        now = time.time()
        if self._states_cache and (now - self._states_last_update < self.CACHE_TTL):
            return self._states_cache

        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(self.STATES_URL, params={"langId": 4}, timeout=15) as r:
                    if r.status != 200:
                        logger.warning(f"Failed to fetch states. Status: {r.status}")
                        return []
                    data = await r.json(content_type=None)
                    
                    out = [{"name": i.get("name"), "id": int(i.get("value", i.get("id")))} for i in data]

                    AutoRiaScraper._states_cache = out
                    AutoRiaScraper._states_last_update = now
                    logger.info(f"States cache updated: {len(out)} items")
                    return out
            except Exception as e:
                logger.error(f"Error fetching states: {e}")
                return []

    async def get_models(self, brand_id: int) -> List[Dict]:
        """Fetches models for a specific brand ID. Cached by brand_id."""
        if brand_id in self._models_cache:
            return self._models_cache[brand_id]

        url = self.MODELS_URL.format(brand_id)
        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                async with session.get(url, timeout=15) as r:
                    if r.status != 200:
                        return []
                    data = await r.json(content_type=None)
                    models = [{"name": item["name"], "id": item["value"]} for item in data]
                    self._models_cache[brand_id] = models
                    return models
            except Exception as e:
                logger.error(f"Error fetching models: {e}")
                return []

    async def search_cars(
        self,
        brand_id: int,
        model_id: int = 0,
        year_from: int = 0,
        year_to: int = 0,
        price_from: int = 0,
        price_to: int = 0,
        region_id: int = 0,
        gearbox_id: int = 0,
        fuel_id: int = 0,
    ) -> List[CarDTO]:
        """
        Main search method.
        1. Fetches the search results page (HTML).
        2. Extracts raw JSON data using Regex.
        3. Enriches missing details via separate API calls if necessary.
        """
        params = {
            "indexName": "auto,order_auto,newauto_search",
            "categories.main.id": 1,
            "brand.id[0]": brand_id,
            "page": 0,
            "size": 20,
        }

        # Conditionally add parameters
        if model_id and model_id > 0: params["model.id[0]"] = model_id
        if year_from: params["year[0].gte"] = year_from
        if year_to: params["year[0].lte"] = year_to
        if price_from: params["price.USD.gte"] = price_from
        if price_to: params["price.USD.lte"] = price_to
        if region_id: params["state[0]"] = region_id
        if gearbox_id: params["gearbox.id[0]"] = gearbox_id
        if fuel_id: params["fuel.id[0]"] = fuel_id

        async with aiohttp.ClientSession(headers=self.headers) as session:
            try:
                # Mimic browser headers
                html_headers = dict(self.headers)
                html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                html_headers["Upgrade-Insecure-Requests"] = "1"

                async with session.get(self.BASE_SEARCH_URL, params=params, headers=html_headers, timeout=25) as r:
                    if r.status != 200:
                        logger.warning(f"Search page returned status: {r.status}")
                        return []
                    html = await r.text()

                cars = self._extract_cars_from_pinia(html)
                if not cars:
                    # Often happens if AutoRia changes layout or blocks IP
                    logger.warning(f"Search returned 0 cars. URL: {r.url}")
                    return []

                # Enrich details (images, mileage, etc.)
                cars = await self._enrich_missing_details(session, cars)
                return cars

            except Exception as e:
                logger.error(f"Error during scraping: {e}")
                return []

    # ----------------------------
    # ROBUST PINIA PARSING
    # ----------------------------
    def _extract_cars_from_pinia(self, html: str) -> List[CarDTO]:
        """
        Extracts car data from the embedded JSON state in the HTML.
        Supports both 'PINIA' (new stack) and 'NUXT' (legacy stack) formats.
        """
        json_data = None
        
        # 1. Try finding PINIA state
        pinia_match = re.search(r'window\.__PINIA__\s*=\s*(\{.*?\})\s*(?:;<|;\n|<\/script>)', html, re.DOTALL)
        
        if pinia_match:
            try:
                json_data = json.loads(pinia_match.group(1))
            except json.JSONDecodeError:
                logger.warning("Failed to decode PINIA JSON")

        # 2. Fallback to NUXT state
        if not json_data:
            nuxt_match = re.search(r'window\.__NUXT__\s*=\s*(\{.*?\})\s*(?:;<|;\n|<\/script>)', html, re.DOTALL)
            if nuxt_match:
                try:
                    json_data = json.loads(nuxt_match.group(1))
                except json.JSONDecodeError:
                    pass

        if not json_data:
            logger.warning("Could not find PINIA or NUXT state in HTML")
            return []

        # 3. Recursively find car objects within the JSON
        found: List[Dict[str, Any]] = []

        def collect(obj: Any):
            if isinstance(obj, dict):
                # Heuristic: verify if object looks like a car ad
                if "id" in obj and "price" in obj and "USD" in str(obj["price"]):
                    if "basicInfo" in obj or "title" in obj:
                        found.append(obj)
                        return 
                for v in obj.values():
                    collect(v)
            elif isinstance(obj, list):
                for it in obj:
                    collect(it)

        collect(json_data)

        results: List[CarDTO] = []
        for d in found:
            try:
                car_id = d.get("id")
                if not car_id: continue
                
                # Extract Price
                price = 0
                price_obj = d.get("price")
                if isinstance(price_obj, dict):
                    price = int(price_obj.get("USD", 0) or 0)
                elif isinstance(price_obj, (int, float)):
                    price = int(price_obj)
                
                if not price: continue

                # Extract Title
                title_obj = d.get("title")
                title_txt = "Auto"
                if isinstance(title_obj, dict):
                    title_txt = title_obj.get("content") or title_obj.get("name") or "Auto"
                elif isinstance(title_obj, str):
                    title_txt = title_obj

                # Construct Link
                link = d.get("link", "") or f"https://auto.ria.com/uk/auto_{car_id}.html"
                if not link.startswith("http"):
                     link = f"https://auto.ria.com{link}"

                # Extract Image
                img = ""
                photos = d.get("photos", []) or d.get("photoData", {}).get("seo", [])
                if photos and isinstance(photos, list):
                    first = photos[0]
                    if isinstance(first, dict):
                         img = first.get("src") or first.get("formats", {}).get("middle", "")
                    elif isinstance(first, str):
                        img = first

                # Extract Details from basicInfo
                mileage_th = 0
                loc = ""
                gear = ""
                fuel = ""

                infos = d.get("basicInfo", [])
                if isinstance(infos, list):
                    for info in infos:
                        txt = str(info.get("content") or "").strip()
                        icon = str((info.get("icon") or {}).get("data") or "")
                        
                        if "speedometer" in icon or "тис. км" in txt:
                             m = re.search(r"(\d+)", txt.replace(" ", ""))
                             if m: mileage_th = int(m.group(1))
                        elif "location" in icon: loc = txt
                        elif "automat" in icon or "transmission" in icon: gear = txt
                        elif "fuel" in icon: fuel = txt

                results.append(CarDTO(
                    id=int(car_id),
                    title=str(title_txt),
                    price_usd=price,
                    url=link,
                    mileage=mileage_th,
                    image_url=img,
                    location=loc,
                    gearbox=gear,
                    fuel=fuel
                ))
            except Exception:
                continue

        # Deduplicate results by ID
        unique_results = {c.id: c for c in results}
        return list(unique_results.values())

    async def _enrich_missing_details(self, session: aiohttp.ClientSession, cars: List[CarDTO]) -> List[CarDTO]:
        """
        Fetches the 'final page' API for cars that are missing critical details 
        (like location or mileage) after the initial search scrape.
        """
        sem = asyncio.Semaphore(self._details_concurrency)

        async def enrich_one(car: CarDTO) -> CarDTO:
            if car.location and car.gearbox and car.fuel and car.mileage:
                return car
            
            async with sem:
                try:
                    details = await self._fetch_final_page(session, car.id, car.url)
                    if not details: return car
                    
                    # Update fields if missing
                    if not car.title: car.title = details.get("title") or car.title
                    if not car.image_url: car.image_url = details.get("image_url") or car.image_url
                    if not car.mileage and details.get("mileage_th"): car.mileage = int(details["mileage_th"])
                    if not car.location and details.get("location"): car.location = details["location"]
                    if not car.gearbox and details.get("gearbox"): car.gearbox = details["gearbox"]
                    if not car.fuel and details.get("fuel"): car.fuel = details["fuel"]
                    
                    return car
                except Exception:
                    return car

        enriched = await asyncio.gather(*(enrich_one(c) for c in cars))
        
        # Set defaults for still missing fields
        for c in enriched:
            if not c.location: c.location = "—"
            if not c.gearbox: c.gearbox = "—"
            if not c.fuel: c.fuel = "—"
            
        return list(enriched)

    async def _fetch_final_page(self, session: aiohttp.ClientSession, car_id: int, car_url: str) -> Optional[Dict[str, Any]]:
        route_path = self._route_path_from_url(car_url) or f"/uk/auto_{car_id}.html"
        url = self.FINAL_PAGE_URL.format(car_id=car_id)
        params = {"langId": "4", "device": "desktop-web", "ssr": "0", "routePath": route_path}
        headers = dict(self.headers)
        headers["Referer"] = car_url

        try:
            async with session.get(url, params=params, headers=headers, timeout=self._details_timeout_sec) as r:
                if r.status != 200: return None
                data = await r.json(content_type=None)

            # Deep search for key data in the response
            ld = self._find_key_recursive(data, "ldJSON") or {}
            title = (ld.get("name") or "").strip()
            
            price_usd = None
            if isinstance(ld.get("offers"), dict):
                 p = ld["offers"].get("price")
                 if str(p).isdigit(): price_usd = int(p)

            mileage_th = None
            if isinstance(ld.get("mileageFromOdometer"), dict):
                v = ld["mileageFromOdometer"].get("value")
                if isinstance(v, (int, float)): mileage_th = int(v) // 1000

            fuel = ld.get("fuelType") or (ld.get("vehicleEngine") or {}).get("fuelType")
            gearbox = ld.get("vehicleTransmission")
            location = self._extract_location_best_effort(data)
            image_url = self._extract_first_image_url(data)

            return {
                "title": title, "price_usd": price_usd, "mileage_th": mileage_th,
                "fuel": fuel, "gearbox": gearbox, "location": location, "image_url": image_url
            }
        except Exception:
            return None

    @staticmethod
    def _route_path_from_url(url: str) -> str:
        try:
            return urlparse(url).path or ""
        except Exception: return ""

    @staticmethod
    def _find_key_recursive(obj: Any, key: str) -> Optional[Any]:
        if isinstance(obj, dict):
            if key in obj: return obj[key]
            for v in obj.values():
                res = AutoRiaScraper._find_key_recursive(v, key)
                if res: return res
        elif isinstance(obj, list):
            for it in obj:
                res = AutoRiaScraper._find_key_recursive(it, key)
                if res: return res
        return None

    @staticmethod
    def _extract_location_best_effort(data: Any) -> Optional[str]:
        keys = {"city", "cityName", "locationCityName", "regionName", "stateName", "location", "locationName"}
        def walk(obj: Any) -> Optional[str]:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k) in keys and isinstance(v, str) and v.strip(): return v.strip()
                    res = walk(v)
                    if res: return res
            elif isinstance(obj, list):
                for it in obj:
                    res = walk(it)
                    if res: return res
            return None
        return walk(data)

    @staticmethod
    def _extract_first_image_url(data: Any) -> str:
        img_re = re.compile(r"^https?://.+\.(jpg|jpeg|png|webp)(\?.*)?$", re.IGNORECASE)
        def walk(obj: Any) -> Optional[str]:
            if isinstance(obj, str) and img_re.match(obj.strip()) and ("ria" in obj or "cdn" in obj):
                return obj.strip()
            if isinstance(obj, dict):
                for v in obj.values():
                    res = walk(v)
                    if res: return res
            if isinstance(obj, list):
                for it in obj:
                    res = walk(it)
                    if res: return res
            return None
        return walk(data) or ""