import uuid
from typing import Dict, Optional, Tuple

import requests

from ai_marketer import config

SERVICE_AMOUNTS: Dict[str, float] = {code: data["price"] for code, data in config.TARIFFS.items()}


def _apply_promocode(amount: float, promo_code: Optional[str]) -> Tuple[float, Optional[str]]:
    if not promo_code:
        return amount, None

    normalized = promo_code.strip().lower()
    multiplier = config.PROMOCODES.get(normalized)
    if not multiplier:
        return amount, None

    discounted_amount = max(amount * multiplier, 0)
    return discounted_amount, normalized


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


def build_service_payment(service_code: str, promo_code: Optional[str] = None) -> Optional[Tuple[str, Dict]]:
    amount = SERVICE_AMOUNTS.get(service_code)
    if amount is None:
        return None

    metadata: Dict[str, str] = {"service_code": service_code}

    discounted_amount, normalized_promo = _apply_promocode(amount, promo_code)
    if normalized_promo:
        metadata["promo_code"] = normalized_promo
        discount_percent = max(int(round((1 - discounted_amount / amount) * 100)), 0)
        metadata["discount"] = f"{discount_percent}%"

    description = f"Оплата услуги {service_code} в AI-Маркетологе 360"
    if normalized_promo:
        description += f" (промокод {normalized_promo})"

    return create_payment(amount=discounted_amount, description=description, metadata=metadata)
