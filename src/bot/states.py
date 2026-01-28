from aiogram.fsm.state import State, StatesGroup

class SubscriptionForm(StatesGroup):
    """FSM States for creating a new subscription."""
    choosing_brand = State()           # 1. Select Brand
    choosing_model = State()           # 2. Select Model (List)
    choosing_model_search = State()    # 2a. Select Model (Text Search)

    choosing_year_from = State()       # 3. Year From
    choosing_year_to = State()         # 4. Year To
    choosing_price_from = State()      # 5. Price From
    choosing_price_to = State()        # 6. Price To

    choosing_region = State()          # 7. Region
    choosing_fuel = State()            # 8. Fuel Type
    choosing_gearbox = State()         # 9. Gearbox