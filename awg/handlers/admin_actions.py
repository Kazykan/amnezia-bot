import asyncio
import datetime
from io import BytesIO
import json
import logging
import os
import re
import aiofiles
import aiohttp
import humanize
from typing import cast, Optional
from zoneinfo import ZoneInfo
import db
from service.system_stats import get_vnstati_image_to_buffer
from service.amnezia_server import check_wg_show_remote, deploy_to_all_servers
from aiogram import Bot
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from admin_service.admin import is_privileged
from service.send_backup_admin import create_db_backup
from utils import (
    generate_config_text,
    get_isp_info,
    parse_relative_time,
    parse_transfer,
)
from fsm.callback_data import ClientCallbackFactory, UserConfCallbackFactory
from keyboard.admin_menu import get_client_profile_keyboard
from keyboard.menu import get_home_keyboard
from fsm.admin_state import AdminState
from service.vpn_service import create_vpn_config
from service.db_instance import user_db
from settings import ADMINS, DB_FILE, MODERATORS

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "add_user")
async def adimin_add_user_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Добавить пользователя' и переводит в состояние ожидания данных."""
    user_id = callback.from_user.id
    if not is_privileged(user_id):
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    await callback.answer()  # Отвечаем на callback, чтобы кнопка не оставалась "нажатой"

    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return

    await callback.message.answer("Пожалуйста, введите данные для нового пользоваля:")
    await state.set_state(AdminState.waiting_for_user_name)
    logger.info(f"Admin {user_id} entered state waiting_for_user_name")


@router.callback_query(F.data == "add_admin")
async def add_admin_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Добавить админа' и переводит в состояние ожидания ID."""
    user_id = callback.from_user.id
    if not is_privileged(user_id):
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    await callback.answer()

    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return

    await callback.message.answer(
        "Пожалуйста, введите Telegram ID нового администратора:"
    )
    await state.set_state(AdminState.waiting_for_admin_id)
    logger.info(f"Admin {user_id} entered state waiting_for_admin_id")


@router.message(AdminState.waiting_for_user_name)
async def admin_create_user(message: Message, state: FSMContext):
    """Обрабатывает ввод имени нового пользователя."""
    if message.from_user is None or message.text is None:
        await message.answer("Ошибка: пользователь не определен.", show_alert=True)
        return
    admin_id = message.from_user.id

    # Проверка прав
    if not is_privileged(admin_id):
        await message.answer("❌ У вас нет прав для этого действия.")
        await state.clear()
        return

    user_name = message.text.strip()
    await message.answer(
        f"✅ Создаю конфигурацию для пользователя: *{user_name}*", parse_mode="HTML"
    )

    # Генерируем конфиг и отправляем его
    await create_vpn_config(user_name, message, True)

    await state.clear()


@router.callback_query(F.data == "list_users")
async def admin_list_users_callback(callback: CallbackQuery):
    """Обрабатывает нажатие кнопки 'Список клиентов' и показывает список."""
    user_id = callback.from_user.id
    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    logger.info(f"User {user_id} requested client list.")

    if not is_privileged(user_id):
        logger.warning(
            f"User {user_id} attempted to access client list without permissions."
        )
        await callback.answer("Нет прав.", show_alert=True)
        return

    try:
        logger.info("Fetching client list...")
        clients = db.get_client_list()
        logger.info(f"Found {len(clients)} clients.")

        if not clients:
            logger.info("Client list is empty.")
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    text="Список слиентов пуст",
                    reply_markup=get_home_keyboard(),
                )
            await callback.answer()
            return

        activ_clients = db.get_active_list()
        logger.info(f"Fetched active clients data.")

        keyboard_buttons: list = []

        for client_data in clients:
            username = client_data[0]
            print(f"Processing client: {username}")

            activ_client = activ_clients.get(username)
            logger.debug(
                f"Processing client: {username}, last_handshke: {activ_client}"
            )

            print(f"Processing client: {username}, last_handshke: {activ_client}")

            status = "❌"  # По умолчанию неактивен

            if (
                activ_client
                and activ_client.last_time
                and activ_client.last_time.lower() not in ["never", "нет данных", "-"]
            ):
                status = "🟢"  # Упрощенно ставим 🟢 если строка рукопожатия не пуста и не Never/Нет данных/
                server = activ_client.server if activ_client.server else ""

            telegram_name = user_db.get_user_by_telegram_id(username)

            if telegram_name is not False:
                button_text = f"{status} {telegram_name.name} {server[:5]}"
            else:
                button_text = f"{status} {username}"

            keyboard_buttons.append(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=ClientCallbackFactory(username=username).pack(),
                )
            )

        # Сборка клавиатуры
        keyboard_buttons_pairs = []

        # Формируем клавишу по парам, если кнопок нечетное количество, последняя будет одиночной
        for i in range(0, len(keyboard_buttons), 2):
            pair = [keyboard_buttons[i]]
            if i + 1 < len(keyboard_buttons):  # Если есть вторая кнопка для пары
                pair.append(keyboard_buttons[i + 1])
            keyboard_buttons_pairs.append(pair)

        # Добавляем кнопку "🏠 Домой" внизу
        keyboard_buttons_pairs.append(
            [InlineKeyboardButton(text="🏠 Домой", callback_data="home")]
        )

        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons_pairs)

        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text="Выберите пользователя:",
                reply_markup=keyboard,
            )
        logger.info(f"Displayed client list to user {user_id}")
        await callback.answer()

    except Exception as e:
        logger.error(
            f"Error in admin_list_users_callback for user {user_id}: {str(e)}",
            exc_info=True,
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text=f"Произошла ошибка при получении списка клиентов:\n{str(e)}",
                reply_markup=get_home_keyboard(),
            )
        # Отвечаем на callback с оповещением
        await callback.answer(
            "Ошибка на сервере при получении списка.", show_alert=True
        )


async def validate_callback_data(callback: CallbackQuery) -> bool:
    """Проверяет валидность callback данных и права пользователя."""
    user_id = callback.from_user.id

    if (
        callback.from_user is None
        or callback.message is None
        or not isinstance(callback.message, Message)
    ):
        await callback.answer(
            "Ошибка: пользователь или сообщение не определены.", show_alert=True
        )
        return False

    if not is_privileged(user_id):
        await callback.answer("Нет прав.", show_allert=True)
        return False

    return True


async def get_client_info(username: str) -> Optional[tuple]:
    """Получает базовую информацию о клиенте."""
    clients = db.get_client_list()
    return next((c for c in clients if c[0] == username), None)


def get_client_network_info(client_info: tuple) -> tuple[str, str, str, str]:
    """Извлекает сетевую информацию клиента."""
    status = "🔴 Офлайн"
    incoming_traffic = "↓—"
    outgoing_traffic = "↑—"
    ipv4_address = "—"

    if (
        isinstance(client_info, (tuple, list))
        and len(client_info) > 2
        and client_info[2]
    ):
        ip_match = re.search(r"(\d{1,3}\.){3}\d{1,3}/\d+", str(client_info[2]))
        ipv4_address = ip_match.group(0) if ip_match else "—"

    return status, incoming_traffic, outgoing_traffic, ipv4_address


async def update_client_activity_status(
    username: str, status: str, incoming_traffic: str, outgoing_traffic: str
) -> tuple[str, str, str]:
    """Обновляет статус активности клиента."""
    active_clients = db.get_active_list()
    active_info = active_clients.get(username)

    if active_info and active_info.last_time.lower() not in [
        "never",
        "нет данных",
        "-",
    ]:
        try:
            last_handshake = parse_relative_time(active_info.last_time)
            if (
                last_handshake
                and (
                    datetime.datetime.now(ZoneInfo("Europe/Moscow")) - last_handshake
                ).total_seconds()
                <= 60
            ):
                status = "🟢 Онлайн"
            else:
                status = "❌ Офлайн"

            transfer_result = parse_transfer(active_info.transfer)
            if transfer_result:
                incoming_bytes, outgoing_bytes = transfer_result
                incoming_traffic = f"↓{humanize.naturalsize(incoming_bytes)}"
                outgoing_traffic = f"↑{humanize.naturalsize(outgoing_bytes)}"

        except Exception as e:
            logger.error(f"Ошибка при анализе активности клиента: {e}", exc_info=True)

    return status, incoming_traffic, outgoing_traffic


def format_profile_text(
    username: str,
    ipv4_address: str,
    status: str,
    outgoing_traffic: str,
    incoming_traffic: str,
) -> str:
    """Форматирует текст профиля пользователя."""
    telegram_name = user_db.get_user_by_telegram_id(username)
    telegram_name_text = telegram_name.name if telegram_name is not False else ""
    is_unlimited = telegram_name.is_unlimited if telegram_name is not False else 0
    telegram_end_date_text = (
        "безлимит"
        if is_unlimited
        else (telegram_name.end_date if telegram_name is not False else "")
    )

    return (
        f"📧 <b>Имя:</b> {username} {telegram_name_text}\n"
        f"🌐 <b>IPv4:</b> {ipv4_address}\n"
        f"🌐 <b>Статус:</b> {status}\n"
        f"🔼 <b>Исходящий:</b> {outgoing_traffic}\n"
        f"🔽 <b>Входящий:</b> {incoming_traffic}\n"
        f"🗓️ <b>Дата окончания:</b> {telegram_end_date_text}"
    )


@router.callback_query(ClientCallbackFactory.filter())
async def client_selected_callback(
    callback: CallbackQuery, callback_data: ClientCallbackFactory
):
    """Обработчик выбора клиента."""
    if not await validate_callback_data(callback):
        return

    username = callback_data.username
    logger.info(f"Выбран клиент: {username}")

    try:
        client_info = await get_client_info(username)
        if not client_info:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        status, incoming_traffic, outgoing_traffic, ipv4_address = (
            get_client_network_info(client_info)
        )

        status, incoming_traffic, outgoing_traffic = (
            await update_client_activity_status(
                username, status, incoming_traffic, outgoing_traffic
            )
        )

        text = format_profile_text(
            username, ipv4_address, status, outgoing_traffic, incoming_traffic
        )

        await callback.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=get_client_profile_keyboard(username),
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в client_selected_callback: {e}", exc_info=True)
        await callback.message.edit_text(
            text=f"Ошибка при загрузке профиля: {str(e)}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="list_users")],
                    [InlineKeyboardButton(text="🏠 Домой", callback_data="home")],
                ]
            ),
        )
        await callback.answer("Ошибка на сервере.", show_alert=True)


@router.callback_query(F.data == "create_backup")
async def create_backup_callback(callback: CallbackQuery):
    """Отправка бекапа админу"""
    user_id = callback.from_user.id
    if callback.message is None and callback.bot is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    logger.info(f"Create backup for {user_id}")

    if not is_privileged(user_id):
        logger.warning(
            f"User {user_id} attempted to access client list without permissions."
        )
        await callback.answer("Нет прав.", show_alert=True)
        return

    await callback.answer("Создаю бэкап...")

    try:
        bot = cast(Bot, callback.bot)
        async with ChatActionSender.upload_document(bot=bot, chat_id=user_id):
            backup_bytes = create_db_backup(DB_FILE)
            await bot.send_document(
                chat_id=user_id,
                document=BufferedInputFile(file=backup_bytes, filename="backup.zip"),
                caption="Бэкап успешно создан и отправлен.",
                parse_mode=ParseMode.HTML,
            )
        logging.info(f"Бэкап отправлен администратору: {user_id}")
    except Exception as e:
        logging.error(f"Ошибка при создании/отправке бэкапа: {e}")
        await callback.answer("Ошибка при создании бэкапа.", show_alert=True)


@router.callback_query(F.data.startswith("connections_"))
async def client_connections_callback(callback: CallbackQuery):
    if callback.data is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    user_id = callback.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback.answer("Нет прав.", show_alert=True)
        return

    username = callback.data.split("connections_")[1]
    file_path = os.path.join("files", "connections", f"{username}_ip.json")
    if not os.path.exists(file_path):
        await callback.answer("Нет данных о подключениях.", show_alert=True)
        return

    async with aiofiles.open(file_path, "r") as f:
        data = json.loads(await f.read())

    last_connections = sorted(
        data.items(),
        key=lambda x: datetime.datetime.strptime(x[1], "%d.%m.%Y %H:%M"),
        reverse=True,
    )[:5]

    isp_results = await asyncio.gather(
        *(get_isp_info(ip) for ip, _ in last_connections)
    )

    text = f"*Последние подключения {username}:*\n" + "\n".join(
        f"{ip} ({isp}) - {time}"
        for (ip, time), isp in zip(last_connections, isp_results)
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=ClientCallbackFactory(username=username).pack(),
                ),
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ]
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )

    await callback.answer()


@router.callback_query(F.data.startswith("ip_info_"))
async def ip_info_callback(callback: CallbackQuery):
    if callback.data is None:
        await callback.answer("Ошибка: бот недоступен.")
        return

    user_id = callback.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback.answer("Нет прав.", show_alert=True)
        return

    username = callback.data.split("ip_info_")[1]
    active_clients = db.get_active_list()
    active_info = active_clients.get(username)

    if not active_info:
        await callback.answer("Нет данных о подключении.", show_alert=True)
        return

    ip_address = active_info.endpoint.split(":")[0]

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://ip-api.com/json/{ip_address}") as resp:
            data = await resp.json() if resp.status == 200 else {}

    text = f"*IP info {username}:*\n" + "\n".join(
        f"{k.capitalize()}: {v}" for k, v in data.items()
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=ClientCallbackFactory(username=username).pack(),
                ),
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ]
        ]
    )

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            text=text, parse_mode=ParseMode.MARKDOWN, reply_markup=keyboard
        )

    await callback.answer()


@router.message(Command("traffic"))
async def send_traffic_graph(message: Message):
    image_buf = get_vnstati_image_to_buffer()
    if not image_buf:
        await message.answer("❌ Не удалось получить данные о трафике.")
        return
    photo = BufferedInputFile(file=image_buf.read(), filename="traffic.png")
    await message.answer_photo(photo, caption="📊 Почасовой график сетевой нагрузки")


@router.message(Command("data"))
async def send_traffic_graph(message: Message):
    data = check_wg_show_remote("files/servers.json")
    if not data:
        await message.answer("❌ Не удалось получить данные о серверах.")
        return
    await message.answer(
        f"```{data}```",
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )


@router.callback_query(UserConfCallbackFactory.filter())
async def client_selected_callback(
    callback: CallbackQuery, callback_data: UserConfCallbackFactory
):
    """Получение конфигурации пользователя по username"""
    user_id = callback.from_user.id
    if callback.message is None:
        await callback.answer("Невозможно получить сообщение для отправки документа.")
        return

    if not is_privileged(user_id):
        await callback.message.answer("У вас нет прав для этого действия.", show_alert=True)
        return


    username = callback_data.username

    config = user_db.get_config_by_telegram_id(username)
    if not config:
        await callback.message.answer("Конфигурация не найдена")
        return

    config_text = generate_config_text(config)

    file_bytes = BytesIO(config_text.encode())
    file = BufferedInputFile(file=file_bytes.getvalue(), filename=f"{username}.conf")
    await callback.message.answer_document(
        document=file,
        caption=f"Конфигурация для пользователя {username}",
        parse_mode=ParseMode.HTML,
    )
    return
