# awg/users/config_generator.py
import os
import configparser
from typing import Optional
from aiogram.types import Message, FSInputFile
from utils import generate_deactivate_presharekey
from service.generate_vpn_key import generate_vpn_key
from db import root_add
from service.db_instance import user_db
from bot_manager import BOT


async def create_vpn_config(user_id: int, message: Message):
    """Генерируем файл в докере копируем его в директорию создаем файл и отправляем клиенту"""
    success = root_add(str(user_id), ipv6=False)
    if not success:
        await message.answer(
            "❌ Не удалось создать конфигурацию. Обратитесь в поддержку."
        )
        return

    conf_path = os.path.join("users", str(user_id), f"{user_id}.conf")
    if not os.path.exists(conf_path):
        await message.answer("❌ Не удалось найти сгенерированный конфиг-файл.")
        return

    vpn_key = await generate_vpn_key(conf_path)
    process_and_add_config(conf_path, user_id)
    caption = (
        f"Конфигурация для {user_id}:\n"
        f"AmneziaVPN:\n"
        f"[Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n"
        f"[GitHub](https://github.com/amnezia-vpn/amnezia-client)\n"
        f"```\n{vpn_key}\n```"
    )
    config_file = FSInputFile(conf_path)
    config_message = await BOT.send_document(
        user_id, config_file, caption=caption, parse_mode="Markdown"
    )
    await BOT.pin_chat_message(
        user_id, config_message.message_id, disable_notification=True
    )


def process_and_add_config(file_path: str, telegram_id: str) -> int:
    config = configparser.ConfigParser()
    config.read(file_path)

    # Получаем данные из секции [Interface]
    interface = config["Interface"]
    private_key = interface.get("PrivateKey")
    address = interface.get("Address")
    dns = interface.get("DNS", fallback=None)

    jc = interface.getint("Jc", fallback=None)
    jmin = interface.getint("Jmin", fallback=None)
    jmax = interface.getint("Jmax", fallback=None)
    s1 = interface.getint("S1", fallback=None)
    s2 = interface.getint("S2", fallback=None)
    h1 = interface.getint("H1", fallback=None)
    h2 = interface.getint("H2", fallback=None)
    h3 = interface.getint("H3", fallback=None)
    h4 = interface.getint("H4", fallback=None)

    # Получаем данные из секции [Peer]
    peer = config["Peer"]
    public_key = peer.get("PublicKey")
    preshared_key = peer.get("PresharedKey", fallback=None)
    allowed_ips = peer.get("AllowedIPs", fallback=None)
    endpoint = peer.get("Endpoint", fallback=None)
    persistent_keepalive = peer.getint("PersistentKeepalive", fallback=None)

    # Генерируем заранее deactivate_presharekey на случай отключения пользователя
    deactivate_presharekey = generate_deactivate_presharekey()

    # Вызов метода добавления в БД
    return user_db.add_config(
        telegram_id=telegram_id,
        private_key=private_key,
        address=address,
        dns=dns,
        jc=jc,
        jmin=jmin,
        jmax=jmax,
        s1=s1,
        s2=s2,
        h1=h1,
        h2=h2,
        h3=h3,
        h4=h4,
        public_key=public_key,
        preshared_key=preshared_key,
        allowed_ips=allowed_ips,
        endpoint=endpoint,
        persistent_keepalive=persistent_keepalive,
        deactivate_presharekey=deactivate_presharekey,
    )
