import os
from typing import Optional
from utils import get_instructions_text
from service.notifier import notify_admins
from service.user_vpn_check import update_vpn_state
from service.vpn_service import create_vpn_config
import db
import uuid
import logging

from aiogram import Router, F
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.enums import ContentType
from aiogram.types import CallbackQuery

from keyboard.menu import get_extend_subscription_keyboard, get_instruction_type
from service.generate_vpn_key import generate_vpn_key
from service.db_instance import user_db
from aiogram.types import Message, FSInputFile
from settings import BOT, YOOKASSA_PROVIDER_TOKEN


logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "buy_vpn")
async def buy_vpn(callback: CallbackQuery):
    logger.info(f"🔔 buy_vpn triggered by {callback.from_user.id}")
    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    await callback.message.answer(
        "💰 Выберите срок подписки:", reply_markup=get_extend_subscription_keyboard()
    )
    await callback.answer()


# 👉 Обработка кнопок "Купить VPN"
@router.callback_query(F.data.endswith("_extend"))
async def handle_extend_subscription(callback: CallbackQuery):
    if (
        callback.bot is None
        or callback.data is None
        or callback.message is None
        or callback.message.bot is None
    ):
        await callback.answer("Ошибка: бот недоступен.")
        return

    telegram_id = callback.from_user.id

    try:
        month = int(callback.data.split("_")[0])
    except (IndexError, ValueError):
        await callback.answer("Неверный формат выбора")
        return

    prices_by_month = {
        1: 80,
        2: 150,
        3: 210,
    }

    price_per_month = prices_by_month.get(month)
    if not price_per_month:
        await callback.answer("Выбранный срок недоступен.")
        return

    amount = price_per_month * 100  # копейки
    logger.info(f"{telegram_id} - {month} mec. - {price_per_month}₽")
    unique_payload = str(uuid.uuid4())

    await callback.message.bot.send_invoice(
        chat_id=telegram_id,
        title=f"Безопасное соединение на {month} mec.",
        description="Мы предоставляем безопасное соединение",
        payload=f"{unique_payload}-{telegram_id}-{month}-{price_per_month}",
        provider_token=YOOKASSA_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="RUB", amount=amount)],
        start_parameter="vpn-subscription",
    )

    user_db.add_payment(
        user_id=telegram_id,
        amount=amount / 100,
        months=month,
        provider_payment_id=None,
        raw_payload=f"{unique_payload}-{telegram_id}-{month}-{price_per_month}",
        status="pending",
        unique_payload=f"{unique_payload}-{telegram_id}-{month}-{price_per_month}",
    )
    await callback.answer()


# 👉 Pre-checkout обработка
@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    logger.info(f"💳 PreCheckout: {pre_checkout_query.id}")
    await pre_checkout_query.answer(ok=True)


async def process_successful_payment(
    user_id: str, raw_payload: str, provider_payment_charge_id: str
) -> Optional[int]:
    """Обновление статуса платежа и продление подписки"""
    try:
        updated_payment = user_db.update_payment_status(
            raw_payload, provider_payment_charge_id, new_status="success"
        )
        if not updated_payment:
            return None

        user_db.update_user_end_date(user_id, months_to_add=updated_payment.months)
        return updated_payment.months
    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа: {e}", exc_info=True)
        return None


def validate_payment(message: Message) -> Optional[tuple[str, str, str]]:
    """Валидация входных данных"""
    payment = message.successful_payment
    if payment is None or payment.invoice_payload is None or message.from_user is None:
        return None
    return (
        str(message.from_user.id),
        payment.invoice_payload,
        payment.provider_payment_charge_id,
    )


# 👉 Успешная оплата
@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    try:
        result = validate_payment(message)
        if result is None:
            await message.answer("Ошибка оплаты")
            return
        telegram_id, payload, provider_payment_charge_id = result

        logger.info(f"💰 Успешная оплата {payload}")

        months = await process_successful_payment(
            telegram_id, payload, provider_payment_charge_id
        )
        if months is None:
            await message.answer("Не удалось обновить статус оплаты.")
            return

        logger.info(f"🔁 Подписка продлена на {months} мес. для {telegram_id}")

        # Проверяем есть конфигурация или нет
        clients = db.get_client_list()
        client_entry = next((c for c in clients if c[0] == str(telegram_id)), None)
        if client_entry is None:  # Если нет создаем
            # Проверяем есть она у нас в БД
            config = user_db.get_config_by_telegram_id(str(telegram_id))
            if not config:
                await message.answer("⚙️ Генерируем VPN-конфигурацию...")
                await create_vpn_config(telegram_id, message)
                await message.answer(
                    text=get_instructions_text(),
                    disable_web_page_preview=True,
                    reply_markup=get_instruction_type()
                )
        else:
            await message.answer("🛡 У вас уже есть активная конфигурация.")
        update_vpn_state()
        await notify_admins(
            text=f"🔁 Подписка продлена на {months} мес. для {telegram_id} \n {message.from_user.username} \n {payload}"
        )
        await message.answer("✅ Спасибо за покупку! Подписка активирована.")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке успешной оплаты: {e}")
        await message.answer(
            "Произошла ошибка при активации подписки. Свяжитесь с поддержкой."
        )
