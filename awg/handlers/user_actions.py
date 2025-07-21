from datetime import datetime
from io import BytesIO
import logging
import os
import shutil
from utils import generate_config_text, get_profile_text, get_vpn_caption
import db
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, BufferedInputFile

from service.db_instance import user_db
from keyboard.menu import get_user_profile_menu, get_user_profile_menu_expired
from settings import BOT, VPN_NAME

logger = logging.getLogger(__name__)
router = Router()


async def send_user_profile(message: Message | CallbackQuery):

    if isinstance(message, Message) and message.from_user is not None:
        telegram_id = str(message.from_user.id)
    elif isinstance(message, CallbackQuery):
        telegram_id = str(message.from_user.id)
    else:
        telegram_id = "unknown"

    logger.info(f"Пользователь {telegram_id} открыл профиль")

    user = user_db.get_user_by_telegram_id(telegram_id)

    if not user:
        await message.answer(
            "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь или свяжитесь с поддержкой."
        )
        return

    profile_text = get_profile_text(user)

    if not user.is_unlimited:
        try:
            end_date_obj = (
                datetime.strptime(user.end_date, "%Y-%m-%d") if user.end_date else None
            )
        except Exception:
            end_date_obj = None

        if not user.end_date or (end_date_obj and end_date_obj < datetime.now()):
            reply_markup = get_user_profile_menu_expired()
        else:
            reply_markup = get_user_profile_menu()
    else:
        reply_markup = get_user_profile_menu()

    # Безопасная отправка
    if isinstance(message, CallbackQuery):
        msg = message.message
        if isinstance(msg, Message):
            if msg.text:
                await msg.edit_text(
                    profile_text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup,
                )
            else:
                await msg.delete()
                await msg.answer(
                    profile_text,
                    parse_mode="Markdown",
                    reply_markup=reply_markup,
                )
            await message.answer()
    else:
        await message.answer(
            profile_text,
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )


@router.message(Command("profile"))
async def show_profile_command(message: Message):
    await send_user_profile(message)


@router.callback_query(F.data == "user_account")
async def user_profile(callback: CallbackQuery):
    await send_user_profile(callback)


@router.callback_query(F.data == "get_config")
async def get_vpn_config(callback: CallbackQuery):
    """Получение конфига перед получение проверка есть у пользователя активаная подписка"""
    if callback.message is None:
        await callback.answer("Невозможно получить сообщение для отправки документа.")
        return

    user_id = callback.from_user.id
    config = user_db.get_config_by_telegram_id(str(user_id))
    if not config:
        await callback.answer("Конфигурация не найдена")
        return

    # Формируем содержимое конфигурации
    config_text = generate_config_text(config)

    # Готовим файл в памяти
    file_bytes = BytesIO(config_text.encode())
    file = BufferedInputFile(
        file=file_bytes.getvalue(), filename=f"{VPN_NAME}_{user_id}.conf"
    )

    await BOT.send_document(
        chat_id=callback.message.chat.id,
        document=file,
        caption=get_vpn_caption(user_id),
    )


@router.message(Command("delete"))
async def delete_user_handler(message: Message):
    if message.from_user is None:
        await message.answer("Ошибка: бот недоступен.")
        return
    username = str(message.from_user.id)

    if db.deactive_user_db(username):
        shutil.rmtree(os.path.join("users", username), ignore_errors=True)
        await message.answer(f"Пользователь **{username}** удален.")
    else:
        await message.answer("Ошибка при удалении пользователя.")
