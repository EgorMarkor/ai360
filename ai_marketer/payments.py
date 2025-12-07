import uuid
from typing import Dict, Optional, Tuple

import requests

from ai_marketer import config

SERVICE_AMOUNTS: Dict[str, float] = {
    "ai_marketer": 2500.0,
    "img_25": 2500.0,
    "img_50": 5000.0,
    "reels_10": 2500.0,
    "video_avatar_10": 2500.0,
    "presentation": 1000.0,
}


def create_payment(amount: float, description: str, metadata: Optional[Dict[str, str]] = None) -> Optional[Tuple[str, Dict]]:
    """Создаёт платёж в ЮKassa и возвращает ссылку на оплату."""
    if not config.YOOKASSA_SHOP_ID or not config.YOOKASSA_API_KEY:
        return None

    payload: Dict[str, object] = {
        "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
        "capture": True,
        "description": description,
        "confirmation": {
            "type": "redirect",
            "return_url": config.YOOKASSA_RETURN_URL,
        },
    }
    if metadata:
        payload["metadata"] = metadata

    headers = {"Idempotence-Key": uuid.uuid4().hex}
    response = requests.post(
        "https://api.yookassa.ru/v3/payments",
        json=payload,
        auth=(config.YOOKASSA_SHOP_ID, config.YOOKASSA_API_KEY),
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    data: Dict = response.json()
    confirmation = data.get("confirmation", {})
    return confirmation.get("confirmation_url"), data


def build_service_payment(service_code: str) -> Optional[Tuple[str, Dict]]:
    amount = SERVICE_AMOUNTS.get(service_code)
    if amount is None:
        return None

    description = f"Оплата услуги {service_code} в AI-Маркетологе 360"
    metadata = {"service_code": service_code}
    return create_payment(amount=amount, description=description, metadata=metadata)
