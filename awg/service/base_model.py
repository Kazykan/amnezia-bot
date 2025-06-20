from pydantic import BaseModel
from typing import Optional


class YoomoneyModel(BaseModel):
    currency: str
    total_amount: int
    invoice_payload: str
    telegram_payment_charge_id: str
    provider_payment_charge_id: str
    subscription_expiration_date: str | None
    is_recurring: str | None
    is_first_recurring: str | None
    shipping_option_id: str | None
    order_info: str | None


class UserData(BaseModel):
    user_id: int
    telegram_id: str
    name: Optional[str]
    end_date: Optional[str]
    is_unlimited: int
    has_used_trial: int


class Config(BaseModel):
    config_id: int
    user_id: int
    private_key: str
    address: str
    dns: Optional[str]

    # Дополнительные параметры интерфейса
    jc: Optional[int]
    jmin: Optional[int]
    jmax: Optional[int]
    s1: Optional[int]
    s2: Optional[int]
    h1: Optional[int]
    h2: Optional[int]
    h3: Optional[int]
    h4: Optional[int]

    # Параметры peer'а
    public_key: str
    preshared_key: Optional[str]
    allowed_ips: Optional[str]
    endpoint: Optional[str]
    persistent_keepalive: Optional[int]

    deactivate_presharekey: Optional[str]


class Payment(BaseModel):
    payment_id: Optional[int]  # PRIMARY KEY AUTOINCREMENT, может быть None при создании
    user_id: int  # Внешний ключ на users(user_id)
    amount: int
    months: int
    provider_payment_id: Optional[str] = None
    payment_time: Optional[str] = (
        None  # DEFAULT CURRENT_TIMESTAMP, может быть установлено БД
    )
    raw_payload: Optional[str] = None
    status: Optional[str] = "pending"  # DEFAULT 'pending'
    unique_payload: Optional[str] = None


class PeerData(BaseModel):
    public_key: Optional[str] = None
    endpoint: Optional[str] = "Нет данных"
    latest_handshake: Optional[str] = "Нет данных"
    transfer: Optional[str] = "Нет данных"

    def is_active(self) -> bool:
        handshake = (self.latest_handshake or "").lower()
        return handshake not in {"never", "нет данных", "-"}


class ActiveClient(BaseModel):
    last_time: str
    transfer: str
    endpoint: str
    server: Optional[str] = None
