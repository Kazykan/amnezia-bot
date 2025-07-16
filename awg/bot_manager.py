import logging
import asyncio
import os
import sys
from service.send_backup_admin import send_backup, send_peak_usage
from utils import load_isp_cache
import db
from zoneinfo import ZoneInfo
from aiogram import Router, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from service.user_vpn_check import update_vpn_state
from service.notifier import daily_check_end_date_and_notify
from handlers import payment, user_actions, start_help, admin_actions, instrustion
from middlewares.admin_delete import AdminMessageDeletionMiddleware
from settings import BOT, ADMINS, check_environment


# ⚙️ Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📦 Инициализация
dp = Dispatcher(storage=MemoryStorage())
router = Router()
scheduler = AsyncIOScheduler(timezone=ZoneInfo("UTC"))


# 🚀 Запуск
async def main():
    os.makedirs("files/connections", exist_ok=True)
    os.makedirs("users", exist_ok=True)
    await load_isp_cache()
    if not await check_environment():
        for admin_id in ADMINS:
            await BOT.send_message(admin_id, "Ошибка инициализации AmneziaVPN.")
        await BOT.close()
        sys.exit(1)

    dp.include_router(start_help.router)
    dp.include_router(payment.router)
    dp.include_router(user_actions.router)
    dp.include_router(admin_actions.router)
    dp.include_router(instrustion.router)

    dp.message.middleware(AdminMessageDeletionMiddleware(admins=ADMINS))

    scheduler.add_job(
        daily_check_end_date_and_notify,
        trigger="cron",
        hour=10,  # каждый день в 10:00 утра
        minute=0,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.add_job(
        update_vpn_state,
        trigger="cron",
        hour=9,  # каждый день в 9:00 утра
        minute=30,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.add_job(
        send_backup,
        trigger="cron",
        hour=0,  # каждый день в 9:00 утра
        minute=42,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.add_job(
        send_peak_usage,
        trigger="cron",
        hour=2,  # каждый день в 9:00 утра
        minute=39,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.add_job(db.ensure_peer_names, trigger="interval", minutes=1)

    scheduler.start()
    await dp.start_polling(BOT)


if __name__ == "__main__":
    asyncio.run(main())
