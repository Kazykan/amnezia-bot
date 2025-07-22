import base64
import json
import os
import re
from typing import Dict
import aiohttp
import logging
import aiofiles
import ipaddress
from datetime import datetime, timedelta, timezone

from aiogram.types import User
from service.base_model import ActiveClient, Config, PeerData, UserData
from settings import CACHE_TTL, ISP_CACHE_FILE, WG_CONFIG_FILE

logger = logging.getLogger(__name__)


def parse_relative_time(relative_str: str) -> datetime:
    if not isinstance(relative_str, str) or not relative_str.strip():
        logger.error(f"Некорректный relative_str: {relative_str}")
        return datetime.now(timezone.utc)  # Значение по умолчанию
    try:
        relative_str = relative_str.lower().replace(" ago", "")
        delta = 0
        for part in relative_str.split(", "):
            num, unit = part.split()
            num = int(num)
            if "minute" in unit:
                delta += num * 60
            elif "hour" in unit:
                delta += num * 3600
            elif "day" in unit:
                delta += num * 86400
            elif "week" in unit:
                delta += num * 604800
            elif "month" in unit:
                delta += num * 2592000
        return datetime.now(timezone.utc) - timedelta(seconds=delta)
    except Exception as e:
        logger.error(f"Ошибка в parse_relative_time: {str(e)}")
        return datetime.now(timezone.utc)  # Значение по умолчанию


def parse_transfer(transfer_str):
    if not isinstance(transfer_str, str) or not transfer_str.strip():
        logger.error(f"Некорректный transfer_str: {transfer_str}")
        return 0, 0  # Значения по умолчанию
    try:
        incoming, outgoing = re.split(r"[/,]", transfer_str)[:2]
        size_map = {
            "B": 1,
            "KB": 10**3,
            "KiB": 1024,
            "MB": 10**6,
            "MiB": 1024**2,
            "GB": 10**9,
            "GiB": 1024**3,
        }
        incoming_bytes = outgoing_bytes = 0
        for unit, multiplier in size_map.items():
            if unit in incoming:
                match = re.match(r"([\d.]+)", incoming)
                if match:
                    incoming_bytes = float(match.group(0)) * multiplier
            if unit in outgoing:
                match = re.match(r"([\d.]+)", outgoing)
                if match:
                    outgoing_bytes = float(match.group(0)) * multiplier
        return incoming_bytes, outgoing_bytes
    except Exception as e:
        logger.error(f"Ошибка в parse_transfer: {str(e)}")
        return 0, 0  # Значения по умолчанию


isp_cache = {}


def get_interface_name():
    return os.path.basename(WG_CONFIG_FILE).split(".")[0]


async def load_isp_cache():
    global isp_cache
    if os.path.exists(ISP_CACHE_FILE):
        async with aiofiles.open(ISP_CACHE_FILE, "r") as f:
            isp_cache = json.loads(await f.read())


async def save_isp_cache():
    async with aiofiles.open(ISP_CACHE_FILE, "w") as f:
        await f.write(json.dumps(isp_cache))


async def get_isp_info(ip: str) -> str:
    now = datetime.now(timezone.utc).timestamp()
    if ip in isp_cache and (now - isp_cache[ip]["timestamp"]) < CACHE_TTL:
        return isp_cache[ip]["isp"]

    try:
        if ipaddress.ip_address(ip).is_private:
            return "Private Range"
    except:
        return "Invalid IP"

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://ip-api.com/json/{ip}?fields=isp") as resp:
            if resp.status == 200:
                data = await resp.json()
                isp = data.get("isp", "Unknown ISP")
                isp_cache[ip] = {"isp": isp, "timestamp": now}
                await save_isp_cache()
                return isp
    return "Unknown ISP"


def get_short_name(user: User) -> str:
    """Формирует имя пользователя: username или имя + фамилия (обрезается до 30 символов)."""
    if user.username:
        name = f"@{user.username}"
    else:
        name_parts = filter(None, [user.first_name, user.last_name])
        name = " ".join(name_parts)
    return name[:10]


def generate_deactivate_presharekey():
    """ "Получаем мусорную строку"""
    fixed_prefix = b"Deactivate"  # 10 байт
    total_bytes = 32  # WireGuard требует ровно 32 байта
    random_part_length = total_bytes - len(fixed_prefix)

    if random_part_length < 0:
        raise ValueError("Prefix is too long for a 32-byte key")

    random_part = os.urandom(random_part_length)
    full_bytes = fixed_prefix + random_part

    # Закодировать в Base64 и убрать паддинги "="
    base64_key = base64.b64encode(full_bytes).decode()

    if len(base64_key) != 44:
        raise ValueError(
            f"Resulting Base64 key is not 44 characters long: {len(base64_key)}"
        )

    return base64_key


def get_profile_text(user: UserData):
    """
    Возвращает текст профиля пользователя с учётом статуса подписки и пробного периода.
    """
    trial_text = ""

    # Проверка подписки
    if user.is_unlimited:
        subscription_text = "♾️ Безлимитная"

    elif user.end_date:
        try:
            end_date_obj = datetime.strptime(user.end_date, "%Y-%m-%d")
            end_date_str = end_date_obj.strftime("%d.%m.%Y")
        except Exception:
            end_date_obj = None
            end_date_str = user.end_date  # если не удалось распарсить

        if end_date_obj and end_date_obj < datetime.now():
            subscription_text = f"❌ Подписка закончилась {end_date_str}"
        else:
            subscription_text = f"📅 Активна до {end_date_str}"

    else:
        subscription_text = "❌ Нет активной подписки"
        trial_text = (
            f"🧪 Пробный период: {'использован' if user.has_used_trial else 'доступен'}"
        )

    # Сборка текста профиля
    profile_text = (
        f"👤 *Ваш профиль*\n\n"
        f"🆔 ID: `{user.telegram_id}`\n"
        f"👥 Имя: *{user.name}*\n"
        f"{subscription_text}\n"
    )

    if trial_text:
        profile_text += f"{trial_text}"

    return profile_text


def generate_config_text(config: Config) -> str:
    """Формирует текст VPN-конфигурации WireGuard."""
    lines = ["[Interface]"]
    lines.append(f"Address = {config.address}")
    if config.dns:
        lines.append(f"DNS = {config.dns}")
    lines.append(f"PrivateKey = {config.private_key}")

    # Дополнительные параметры интерфейса
    for field in ["jc", "jmin", "jmax", "s1", "s2", "h1", "h2", "h3", "h4"]:
        value = getattr(config, field)
        if value is not None:
            lines.append(f"{field.upper()} = {value}")

    lines.append("[Peer]")
    lines.append(f"PublicKey = {config.public_key}")
    if config.preshared_key:
        lines.append(f"PresharedKey = {config.preshared_key}")
    if config.allowed_ips:
        lines.append(f"AllowedIPs = {config.allowed_ips}")
    if config.endpoint:
        lines.append(f"Endpoint = {config.endpoint}")
    if config.persistent_keepalive:
        lines.append(f"PersistentKeepalive = {config.persistent_keepalive}")

    return "\n".join(lines)


def get_vpn_caption(user_id: int) -> str:
    return (
        f"Конфигурация для {user_id}:\n"
        f"AmneziaVPN:\n"
        f"📱 [App Store](https://apps.apple.com/ru/app/amneziawg/id6478942365)\n"
        f"🤖 [Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n"
        f"💻 [GitHub](https://github.com/amnezia-vpn/amnezia-client)\n"
    )


def get_welcome_caption() -> str:
    return (
        "👋 Добро пожаловать в *Rufat Бот!*\n\n"
        "⚡ **Оптимизированное соединение.** 🔐 **Полная безопасность.** 💸 **Всего за 80₽ в месяц.**\n\n"
        "Это доступнее чашки кофе, но несравнимо полезнее.\n"
        'Нажми **"Подключить"** и наслаждайся быстрым и защищённым интернетом уже сейчас! 🚀\n\n'
        "Выберите действие:"
    )


def get_instructions_text() -> str:
    return (
        "Чтобы начать, сначала скачайте приложение, затем установите его. После установки выберите тип вашего устройства, чтобы получить подробные инструкции.\n\n"
        "Ссылки для скачивания AmneziaVPN:\n"
        "📱 Если у вас iPhone или iPad – скачайте приложение здесь: [App Store](https://apps.apple.com/ru/app/amneziawg/id6478942365)\n\n"
        "🤖 Если у вас Android – скачайте приложение здесь: [Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n\n"
        "После установки выберите свое устройство, чтобы узнать, как настроить приложение.\n\n"
        "ℹ️ Если у вас возникли сложности или остались вопросы — напишите мне: [@Kazykan] (https://t.me/Kazykan)"
    )
