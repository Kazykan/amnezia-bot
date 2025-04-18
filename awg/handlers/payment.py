import os
import db
import uuid
import logging

from aiogram import Router, F
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.enums import ContentType
from aiogram.types import CallbackQuery

from keyboard.menu import get_extend_subscription_keyboard
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
        await callback.answer("Неверный формат выбораю")
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
        title=f"Покупка VPN на {month} mec.",
        description="Мы предоставляем удобные VPN услуги",
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
        unique_payload=unique_payload,
    )
    await callback.answer()


# 👉 Pre-checkout обработка
@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    logger.info(f"💳 PreCheckout: {pre_checkout_query.id}")
    await pre_checkout_query.answer(ok=True)


# 👉 Успешная оплата
@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payment = message.successful_payment
    if payment is None or payment.invoice_payload is None or message.from_user is None:
        await message.answer("Ошибка оплаты")
        return
    unique_payload = payment.invoice_payload
    telegram_id = message.from_user.id

    logger.info(f"💰 Успешная оплата {payment.invoice_payload}")

    try:
        # Обновляем статус платежа
        updated_payment = user_db.update_payment_status(unique_payload, new_status="success")
        if not updated_payment:
            await message.answer("Не удалось обновить статус оплаты.")
            return
        
        # Продлеваем подписку
        months = updated_payment.months
        updated_user = user_db.update_user_end_date(telegram_id, months_to_add=months)

        await message.answer("✅ Спасибо за покупку! Подписка активирована.")
        logger.info(f"🔁 Подписка продлена на {months} мес. для {telegram_id}")

        # Проверка конфигурации
        config = user_db.get_config_by_telegram_id(str(telegram_id))
        if not config:
            await message.answer("⚙️ Генерируем VPN-конфигурацию...")

            success = db.root_add(str(telegram_id), ipv6=False)
            if success:
                conf_path = os.path.join("users", str(telegram_id), f"{telegram_id}.conf")
                if os.path.exists(conf_path):
                    vpn_key = await generate_vpn_key(conf_path)
                    caption = (
                        f"Конфигурация для {telegram_id}:\n"
                        f"AmneziaVPN:\n"
                        f"[Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n"
                        f"[GitHub](https://github.com/amnezia-vpn/amnezia-client)\n"
                        f"```\n{vpn_key}\n```"
                    )
                    config_file = FSInputFile(conf_path)
                    config_message = await BOT.send_document(
                        telegram_id, config_file, caption=caption, parse_mode="Markdown"
                    )
                    await BOT.pin_chat_message(
                        telegram_id, config_message.message_id, disable_notification=True
                    )
                else:
                    await message.answer("❌ Не удалось найти сгенерированный конфиг-файл.")
            else:
                await message.answer("❌ Не удалось создать конфигурацию. Обратитесь в поддержку.")
        else:
            await message.answer("🛡 У вас уже есть активная конфигурация.")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке успешной оплаты: {e}")
        await message.answer("Произошла ошибка при активации подписки. Свяжитесь с поддержкой.")
