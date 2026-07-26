from aiogram.fsm.state import State, StatesGroup


class ExchangeStates(StatesGroup):
    waiting_currency_from = State()
    waiting_currency_to = State()
    waiting_amount_mode = State()
    waiting_amount = State()
    waiting_address = State()
    confirm = State()