from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_client_profile_keyboard(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="ℹ️ IP info", callback_data=f"ip_info_{username}"),
                InlineKeyboardButton(text="🔗 Подключения", callback_data=f"connections_{username}")
            ],
            [
                InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"delete_user_{username}")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="list_users"),
                InlineKeyboardButton(text="🏠 Домой", callback_data="home")
            ]
        ]
    )