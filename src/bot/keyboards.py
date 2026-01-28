from __future__ import annotations

from typing import List, Dict, Optional

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# -----------------------------
# Reply keyboards
# -----------------------------

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Створити підписку")],
        [KeyboardButton(text="📋 Мої підписки")],
    ],
    resize_keyboard=True,
    persistent=True,
)

def get_skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➡️ Пропустити")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

# -----------------------------
# Inline keyboards helpers
# -----------------------------

def _grid_buttons(
    items: List[Dict],
    prefix: str,
    *,
    cols: int = 2,
) -> List[List[InlineKeyboardButton]]:
    """Helper to arrange buttons in a grid."""
    rows: List[List[InlineKeyboardButton]] = []
    row: List[InlineKeyboardButton] = []
    for it in items:
        row.append(InlineKeyboardButton(text=str(it["name"]), callback_data=f"{prefix}:{it['id']}"))
        if len(row) == cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return rows


def build_paged_inline_keyboard(
    items: List[Dict],
    prefix: str,
    *,
    page: int = 0,
    per_page: int = 20,
    cols: int = 2,
    include_skip: bool = False,
    skip_text: str = "➡️ Пропустити (Всі)",
    skip_callback: Optional[str] = None,
    extra_row: Optional[List[InlineKeyboardButton]] = None,
) -> InlineKeyboardMarkup:
    """
    Generic builder for paginated inline keyboards.
    Used for Brands, Models, Regions, etc.
    """
    if page < 0:
        page = 0

    start = page * per_page
    chunk = items[start : start + per_page]

    keyboard: List[List[InlineKeyboardButton]] = []
    keyboard.extend(_grid_buttons(chunk, prefix, cols=cols))

    # Add extra functional row (e.g. Search button)
    if extra_row:
        keyboard.append(extra_row)

    # Navigation row (Prev/Next)
    nav_row: List[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_page:{page-1}"))
    if start + per_page < len(items):
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_page:{page+1}"))
    if nav_row:
        keyboard.append(nav_row)

    # Skip button
    if include_skip:
        keyboard.append(
            [
                InlineKeyboardButton(
                    text=skip_text,
                    callback_data=skip_callback or f"{prefix}:0",
                )
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# -----------------------------
# Concrete keyboards
# -----------------------------

def build_brands_keyboard(brands: List[Dict], *, page: int = 0) -> InlineKeyboardMarkup:
    return build_paged_inline_keyboard(brands, "brand", page=page, per_page=20, cols=2)

def build_regions_keyboard(regions: List[Dict], *, page: int = 0) -> InlineKeyboardMarkup:
    """Dynamically builds regions keyboard with pagination."""
    return build_paged_inline_keyboard(
        regions,
        "region",
        page=page,
        per_page=20,
        cols=2,
        include_skip=True,
        skip_text="➡️ Вся Україна",
        skip_callback="region:0",
    )

def get_fuel_keyboard() -> InlineKeyboardMarkup:
    fuels = [
        {"name": "Бензин", "id": 1},
        {"name": "Дизель", "id": 2},
        {"name": "Газ", "id": 3},
        {"name": "Газ/Бензин", "id": 4},
        {"name": "Гібрид", "id": 5},
        {"name": "Електро", "id": 6},
    ]
    return build_paged_inline_keyboard(
        fuels,
        "fuel",
        page=0,
        per_page=50,
        cols=2,
        include_skip=True,
        skip_text="➡️ Пропустити (Будь-яке)",
        skip_callback="fuel:0",
    )


def get_gearbox_keyboard() -> InlineKeyboardMarkup:
    gearboxes = [
        {"name": "Ручна", "id": 1},
        {"name": "Автомат", "id": 2},
        {"name": "Робот", "id": 4},
        {"name": "Варіатор", "id": 5},
    ]
    return build_paged_inline_keyboard(
        gearboxes,
        "gear",
        page=0,
        per_page=50,
        cols=2,
        include_skip=True,
        skip_text="➡️ Пропустити (Будь-яка)",
        skip_callback="gear:0",
    )