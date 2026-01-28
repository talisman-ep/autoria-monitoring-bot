from __future__ import annotations

from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from src.bot.keyboards import (
    main_menu,
    get_skip_keyboard,
    build_regions_keyboard,
    get_fuel_keyboard,
    get_gearbox_keyboard,
    build_brands_keyboard,
    build_paged_inline_keyboard,
)
from src.bot.states import SubscriptionForm
from src.parser.scraper import AutoRiaScraper
from src.database.repository import DatabaseRepo

user_router = Router()

# -----------------------------
# Constant Maps
# -----------------------------

FUEL_MAP = {
    0: "Будь-яке",
    1: "Бензин",
    2: "Дизель",
    3: "Газ",
    4: "Газ/Бензин",
    5: "Гібрид",
    6: "Електро",
}

GEARBOX_MAP = {
    0: "Будь-яка",
    1: "Ручна",
    2: "Автомат",
    4: "Робот",
    5: "Варіатор",
}

# -----------------------------
# Helpers
# -----------------------------
def _find_name_by_id(items: list[dict], item_id: int, fallback: str = "") -> str:
    """Helper to find the human-readable name of an item by its ID."""
    for it in items:
        if int(it.get("id")) == int(item_id):
            return str(it.get("name"))
    return fallback


def _build_models_keyboard(models: list[dict], *, page: int = 0, mode: str = "all"):
    """
    Constructs the keyboard for car models.
    Supports two modes: 'all' (list) and 'search' (filtered results).
    """
    extra_row = []

    if mode == "search":
        extra_row.append(types.InlineKeyboardButton(text="⬅️ Всі моделі", callback_data="model_back"))
        extra_row.append(types.InlineKeyboardButton(text="🔎 Новий пошук", callback_data="model_search"))
    else:
        extra_row.append(types.InlineKeyboardButton(text="🔎 Пошук моделі", callback_data="model_search"))

    # "Any model" option is always available
    extra_row.append(types.InlineKeyboardButton(text="➡️ Будь-яка модель", callback_data="model:0"))

    prefix = "modelS" if mode == "search" else "model"
    return build_paged_inline_keyboard(
        models,
        prefix,
        page=page,
        per_page=20,
        cols=2,
        extra_row=extra_row,
    )

# -----------------------------
# Handlers
# -----------------------------
@user_router.message(CommandStart())
async def cmd_start(message: types.Message, repo: DatabaseRepo):
    """Entry point. Registers the user in the database."""
    await repo.add_user(
        message.from_user.id,
        message.from_user.username or "",
        message.from_user.full_name,
    )
    await message.answer("👋 Привіт! Тисни кнопку для пошуку 👇", reply_markup=main_menu)


@user_router.message(F.text == "🔍 Створити підписку")
async def start_sub(message: types.Message, state: FSMContext):
    """Starts the subscription creation flow. Fetches brands."""
    scraper = AutoRiaScraper()
    brands = await scraper.get_brands()
    if not brands:
        return await message.answer("⚠️ Не вдалося завантажити список марок. Спробуй пізніше.")

    await state.update_data(brands=brands, brand_page=0)
    await message.answer("🚗 Обери марку:", reply_markup=build_brands_keyboard(brands, page=0))
    await state.set_state(SubscriptionForm.choosing_brand)


@user_router.callback_query(F.data.startswith("brand_page:"), SubscriptionForm.choosing_brand)
async def process_brand_page(callback: types.CallbackQuery, state: FSMContext):
    """Pagination handler for Brands."""
    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    brands = data.get("brands") or []
    
    # Refetch if state data is lost
    if not brands:
        scraper = AutoRiaScraper()
        brands = await scraper.get_brands()
        await state.update_data(brands=brands)

    await state.update_data(brand_page=page)
    await callback.message.edit_reply_markup(reply_markup=build_brands_keyboard(brands, page=page))
    await callback.answer()


@user_router.callback_query(F.data.startswith("brand:"), SubscriptionForm.choosing_brand)
async def process_brand(callback: types.CallbackQuery, state: FSMContext):
    """Handles Brand selection. Triggers Model fetching."""
    brand_id = int(callback.data.split(":")[1])

    data = await state.get_data()
    brands = data.get("brands") or []
    brand_name = _find_name_by_id(brands, brand_id, fallback=str(brand_id))

    await state.update_data(brand_id=brand_id, brand_name=brand_name)

    await callback.message.edit_text(f"⏳ Завантажую моделі {brand_name}...")
    scraper = AutoRiaScraper()
    models = await scraper.get_models(brand_id)

    # If no models found (or empty), allow user to skip to Year selection
    if not models:
        await state.update_data(model_id=0, model_name="Будь-яка")
        await callback.message.answer("📅 Рік ВІД (наприклад 2010):", reply_markup=get_skip_keyboard())
        await state.set_state(SubscriptionForm.choosing_year_from)
        return

    await state.update_data(models_all=models, model_page=0, model_mode="all")

    kb = _build_models_keyboard(models, page=0, mode="all")
    await callback.message.delete()
    await callback.message.answer(f"🚗 Обери модель **{brand_name}**:", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(SubscriptionForm.choosing_model)


@user_router.callback_query(F.data.startswith("model_page:"), SubscriptionForm.choosing_model)
async def process_model_page(callback: types.CallbackQuery, state: FSMContext):
    """Pagination for Models (All mode)."""
    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    models = data.get("models_all") or []
    await state.update_data(model_page=page, model_mode="all")
    await callback.message.edit_reply_markup(reply_markup=_build_models_keyboard(models, page=page, mode="all"))
    await callback.answer()


@user_router.callback_query(F.data == "model_search", SubscriptionForm.choosing_model)
async def start_model_search(callback: types.CallbackQuery, state: FSMContext):
    """Switches model selection to Search mode."""
    await callback.message.answer("🔎 Введи назву моделі (наприклад: Camry, Octavia, X5):")
    await state.set_state(SubscriptionForm.choosing_model_search)
    await callback.answer()


@user_router.message(SubscriptionForm.choosing_model_search)
async def process_model_search_text(message: types.Message, state: FSMContext):
    """Filters the model list based on user text input."""
    query = (message.text or "").strip()
    if len(query) < 2:
        return await message.answer("❌ Введи хоча б 2 символи для пошуку.")

    data = await state.get_data()
    models_all = data.get("models_all") or []
    q = query.lower()

    filtered = [m for m in models_all if q in str(m.get("name", "")).lower()]
    if not filtered:
        return await message.answer("😕 Нічого не знайшов. Спробуй інший запит або коротше/довше слово.")

    await state.update_data(models_search=filtered, model_mode="search", model_page=0, model_search_query=query)

    kb = _build_models_keyboard(filtered, page=0, mode="search")
    await message.answer(f"🔎 Результати для: <b>{query}</b> (знайдено {len(filtered)})", reply_markup=kb, parse_mode="HTML")
    await state.set_state(SubscriptionForm.choosing_model)


@user_router.callback_query(F.data == "model_back", SubscriptionForm.choosing_model)
async def back_to_all_models(callback: types.CallbackQuery, state: FSMContext):
    """Returns to the full list of models."""
    data = await state.get_data()
    models_all = data.get("models_all") or []
    await state.update_data(model_mode="all", model_page=0)
    await callback.message.edit_reply_markup(reply_markup=_build_models_keyboard(models_all, page=0, mode="all"))
    await callback.answer()


@user_router.callback_query(F.data.startswith("modelS_page:"), SubscriptionForm.choosing_model)
async def process_model_search_page(callback: types.CallbackQuery, state: FSMContext):
    """Pagination for Models (Search mode)."""
    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    models = data.get("models_search") or []
    await state.update_data(model_page=page, model_mode="search")
    await callback.message.edit_reply_markup(reply_markup=_build_models_keyboard(models, page=page, mode="search"))
    await callback.answer()


@user_router.callback_query(F.data.startswith("model:"), SubscriptionForm.choosing_model)
@user_router.callback_query(F.data.startswith("modelS:"), SubscriptionForm.choosing_model)
async def process_model(callback: types.CallbackQuery, state: FSMContext):
    """Handles Model selection."""
    model_id = int(callback.data.split(":")[1])

    if model_id == 0:
        model_name = "Будь-яка"
    else:
        data = await state.get_data()
        mode = data.get("model_mode", "all")
        models = data.get("models_search") if mode == "search" else data.get("models_all")
        models = models or []
        model_name = _find_name_by_id(models, model_id, fallback=str(model_id))

    await state.update_data(model_id=model_id, model_name=model_name)

    await callback.message.edit_text(f"✅ Модель: <b>{model_name}</b>", parse_mode="HTML")
    await callback.message.answer("📅 Рік ВІД (наприклад 2010):", reply_markup=get_skip_keyboard())
    await state.set_state(SubscriptionForm.choosing_year_from)
    await callback.answer()


@user_router.message(SubscriptionForm.choosing_year_from)
async def process_year_from(message: types.Message, state: FSMContext):
    text = message.text or ""
    if text in ["➡️ Пропустити", "Пропустити"]:
        year = 0
    elif text.isdigit():
        year = int(text)
    else:
        return await message.answer("❌ Введи число або натисни '➡️ Пропустити'.")

    await state.update_data(year_from=year)
    await message.answer("📅 Рік ДО (або 'Пропустити'):", reply_markup=get_skip_keyboard())
    await state.set_state(SubscriptionForm.choosing_year_to)


@user_router.message(SubscriptionForm.choosing_year_to)
async def process_year_to(message: types.Message, state: FSMContext):
    yt = int(message.text) if (message.text or "").isdigit() else 0
    await state.update_data(year_to=yt)
    await message.answer("💰 Ціна ВІД $ (або 'Пропустити'):", reply_markup=get_skip_keyboard())
    await state.set_state(SubscriptionForm.choosing_price_from)


@user_router.message(SubscriptionForm.choosing_price_from)
async def process_price_from(message: types.Message, state: FSMContext):
    pf = int(message.text) if (message.text or "").isdigit() else 0
    await state.update_data(price_from=pf)
    await message.answer("💰 Ціна ДО $ (або 'Пропустити'):", reply_markup=get_skip_keyboard())
    await state.set_state(SubscriptionForm.choosing_price_to)


# -----------------------------
# DYNAMIC REGIONS LOGIC
# -----------------------------
@user_router.message(SubscriptionForm.choosing_price_to)
async def process_price_to(message: types.Message, state: FSMContext):
    pt = int(message.text) if (message.text or "").isdigit() else 0
    await state.update_data(price_to=pt)

    # 1. Fetch regions from AutoRia dynamically
    await message.answer("⏳ Завантажую список областей...")
    scraper = AutoRiaScraper()
    regions = await scraper.get_states()

    if not regions:
        # Fallback if API is down
        await message.answer("⚠️ Не вдалося отримати список областей. Буде 'Вся Україна'.")
        await state.update_data(region_id=0, region_name="Вся Україна")
        await message.answer("⛽ Тип палива:", reply_markup=get_fuel_keyboard())
        await state.set_state(SubscriptionForm.choosing_fuel)
        return

    # 2. Save regions to state (to look up names later)
    await state.update_data(regions=regions, region_page=0)

    # 3. Show keyboard
    await message.answer("📍 Обери область:", reply_markup=build_regions_keyboard(regions, page=0))
    await state.set_state(SubscriptionForm.choosing_region)


@user_router.callback_query(F.data.startswith("region_page:"), SubscriptionForm.choosing_region)
async def process_region_page(callback: types.CallbackQuery, state: FSMContext):
    """Pagination for Regions."""
    page = int(callback.data.split(":")[1])
    data = await state.get_data()
    regions = data.get("regions") or []
    
    if not regions:
        scraper = AutoRiaScraper()
        regions = await scraper.get_states()
        await state.update_data(regions=regions)

    await state.update_data(region_page=page)
    await callback.message.edit_reply_markup(reply_markup=build_regions_keyboard(regions, page=page))
    await callback.answer()


@user_router.callback_query(F.data.startswith("region:"), SubscriptionForm.choosing_region)
async def process_region(callback: types.CallbackQuery, state: FSMContext):
    """Handles Region selection."""
    region_id = int(callback.data.split(":")[1])
    
    if region_id == 0:
        region_name = "Вся Україна"
    else:
        data = await state.get_data()
        regions = data.get("regions") or []
        region_name = _find_name_by_id(regions, region_id, fallback=str(region_id))

    await state.update_data(region_id=region_id, region_name=region_name)

    await callback.message.edit_text(f"✅ Область: <b>{region_name}</b>", parse_mode="HTML")
    await callback.message.answer("⛽ Тип палива:", reply_markup=get_fuel_keyboard())
    await state.set_state(SubscriptionForm.choosing_fuel)
    await callback.answer()


@user_router.callback_query(F.data.startswith("fuel:"), SubscriptionForm.choosing_fuel)
async def process_fuel(callback: types.CallbackQuery, state: FSMContext):
    fuel_id = int(callback.data.split(":")[1])
    fuel_name = FUEL_MAP.get(fuel_id, str(fuel_id))
    await state.update_data(fuel_id=fuel_id, fuel_name=fuel_name)

    await callback.message.edit_text(f"✅ Паливо: <b>{fuel_name}</b>", parse_mode="HTML")
    await callback.message.answer("⚙️ Коробка передач:", reply_markup=get_gearbox_keyboard())
    await state.set_state(SubscriptionForm.choosing_gearbox)
    await callback.answer()


@user_router.callback_query(F.data.startswith("gear:"), SubscriptionForm.choosing_gearbox)
async def process_save(callback: types.CallbackQuery, state: FSMContext, repo: DatabaseRepo):
    """
    Final step. Saves the subscription to the database via Repository.
    """
    gearbox_id = int(callback.data.split(":")[1])
    gearbox_name = GEARBOX_MAP.get(gearbox_id, str(gearbox_id))
    await state.update_data(gearbox_id=gearbox_id, gearbox_name=gearbox_name)

    data = await state.get_data()

    await callback.message.edit_text(f"✅ Коробка: <b>{gearbox_name}</b>", parse_mode="HTML")

    try:
        await repo.add_search(callback.from_user.id, data)

        model_part = f" {data.get('model_name')}" if data.get("model_id", 0) else ""
        year_to = data.get("year_to") or ""
        price_to = data.get("price_to") or "..."
        summary = (
            f"🚘 <b>{data['brand_name']}{model_part}</b>\n"
            f"📅 {data['year_from']}-{year_to}\n"
            f"💰 {data.get('price_from', 0)}$-{price_to}\n"
            f"📍 {data.get('region_name', '...')} | ⛽ {data.get('fuel_name', '...')} | ⚙️ {gearbox_name}"
        )

        await callback.message.answer(f"🎉 <b>Підписку збережено!</b>\n\n{summary}", reply_markup=main_menu, parse_mode="HTML")
    except Exception as e:
        await callback.message.answer(f"❌ Помилка БД: {e}")

    await state.clear()
    await callback.answer()


@user_router.message(F.text == "📋 Мої підписки")
async def show_subs(message: types.Message, repo: DatabaseRepo):
    """Fetches and displays active subscriptions for the user."""
    rows = await repo.get_user_searches(message.from_user.id)
    if not rows:
        return await message.answer("📭 Пусто.")

    txt = "<b>📋 Твої пошуки:</b>\n\n"
    for r in rows:
        model_part = f" {r['model_name']}" if r.get("model_name") else ""
        txt += f"🔹 <b>{r['brand']}{model_part}</b> ({r.get('year_from') or ''}+)\n"
        txt += f"❌ /del_{r['id']}\n\n"

    await message.answer(txt, parse_mode="HTML")


@user_router.message(F.text.startswith("/del_"))
async def del_sub(m: types.Message, repo: DatabaseRepo):
    """Deletes a subscription by ID."""
    try:
        sid = int(m.text.split("_")[1])
        await repo.delete_search(sid, m.from_user.id)
        await m.answer("✅ Видалено.")
    except Exception:
        pass