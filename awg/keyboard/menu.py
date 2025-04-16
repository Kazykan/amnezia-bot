from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_markup(user_id, admins):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("➕ Добавить пользователя", callback_data="add_user"),
        InlineKeyboardButton("📋 Список клиентов", callback_data="list_users"),
    )
    markup.add(
        InlineKeyboardButton("🔑 Получить конфиг", callback_data="get_config"),
        InlineKeyboardButton("ℹ️ Инструкция", callback_data="instructions"),
    )
    if user_id in admins:
        markup.add(
            InlineKeyboardButton("👥 Список админов", callback_data="list_admins"),
            InlineKeyboardButton("👤 Добавить админа", callback_data="add_admin"),
        )
        markup.add(
            InlineKeyboardButton("💾 Создать бекап", callback_data="create_backup")
        )
    return markup


def get_client_profile_keyboard(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ℹ️ IP info", callback_data=f"ip_info_{username}"
                ),
                InlineKeyboardButton(
                    text="🔗 Подключения", callback_data=f"connections_{username}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить", callback_data=f"delete_user_{username}"
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="list_users"),
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ],
        ]
    )


def get_user_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Купить VPN", callback_data="buy_vpn")],
            [InlineKeyboardButton(text="💳 Профиль", callback_data="user_account")],
            [
                InlineKeyboardButton(
                    text="📲 Как установить", callback_data="install_guide"
                )
            ],
        ]
    )


def get_extend_subscription_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 месяц - 80₽", callback_data="1_extend"),
                InlineKeyboardButton(text="2 месяца - 150₽", callback_data="2_extend"),
            ],
            [
                InlineKeyboardButton(text="3 месяца - 210₽", callback_data="3_extend"),
                InlineKeyboardButton(text="◀️ Назад", callback_data="start"),
            ],
        ]
    )


def get_user_profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Получить конфиг", callback_data="get_config"
                ),
                InlineKeyboardButton(text="🔄 Продлить", callback_data="renew_vpn"),
            ],
            [
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ],
        ]
    )
