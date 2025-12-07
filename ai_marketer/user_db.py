import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from ai_marketer import config

DATE_FMT = "%Y-%m-%dT%H:%M:%S"
USER_DB_PATH = Path(os.getenv("USER_DB_PATH", "data/users.json"))

DEFAULT_USAGE = {"images": 0, "video": 0, "presentations": 0}


def _load_db() -> Dict[str, Dict]:
    if USER_DB_PATH.exists():
        with USER_DB_PATH.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def _save_db(data: Dict[str, Dict]):
    USER_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _default_user(user_id: int, username: Optional[str] = None) -> Dict:
    return {
        "id": user_id,
        "username": username or "",
        "tariff": "free",
        "subscription_expires_at": None,
        "usage": DEFAULT_USAGE.copy(),
        "history": [],
        "last_payment_at": None,
        "created_at": datetime.utcnow().strftime(DATE_FMT),
    }


def _sanitize_user_record(record: Dict) -> Dict:
    record.setdefault("usage", DEFAULT_USAGE.copy())
    for key in DEFAULT_USAGE:
        record["usage"].setdefault(key, 0)
    record.setdefault("history", [])
    record.setdefault("tariff", "free")
    record.setdefault("subscription_expires_at", None)
    record.setdefault("last_payment_at", None)
    record.setdefault("username", "")
    return record


def get_user(user_id: int, username: Optional[str] = None) -> Dict:
    data = _load_db()
    key = str(user_id)
    if key not in data:
        data[key] = _default_user(user_id, username)
    else:
        if username:
            data[key]["username"] = username
        data[key] = _sanitize_user_record(data[key])
    _save_db(data)
    return data[key]


def _tariff_limits(tariff_code: str) -> Dict[str, Optional[int]]:
    limits = config.TARIFFS.get(tariff_code, {}).get("limits", {})
    return {
        "text": None,
        "images": limits.get("images"),
        "video": limits.get("video"),
        "presentations": limits.get("presentations"),
    }


def _now() -> datetime:
    return datetime.utcnow()


def activate_tariff(user_id: int, tariff_code: str, days: int = 30, username: Optional[str] = None) -> Dict:
    data = _load_db()
    key = str(user_id)
    user = data.get(key, _default_user(user_id, username))
    user = _sanitize_user_record(user)
    expires_at = _now() + timedelta(days=days)
    user["tariff"] = tariff_code
    user["subscription_expires_at"] = expires_at.strftime(DATE_FMT)
    user["usage"] = DEFAULT_USAGE.copy()
    user["last_payment_at"] = _now().strftime(DATE_FMT)
    if username:
        user["username"] = username
    data[key] = user
    _save_db(data)
    return user


def subscription_days_left(user: Dict) -> int:
    expires_at = user.get("subscription_expires_at")
    if not expires_at:
        return 0
    try:
        expires_dt = datetime.strptime(expires_at, DATE_FMT)
    except Exception:  # noqa: BLE001
        return 0
    delta = expires_dt - _now()
    return max(delta.days, 0)


def has_active_subscription(user: Dict) -> bool:
    return subscription_days_left(user) > 0


def _limit_for_category(user: Dict, category: str) -> Optional[int]:
    limits = _tariff_limits(user.get("tariff", "free"))
    return limits.get(category)


def remaining_quota(user: Dict, category: str) -> Optional[int]:
    limit = _limit_for_category(user, category)
    if limit is None:
        return None
    used = user.get("usage", {}).get(category, 0)
    return max(limit - used, 0)


def check_access(user_id: int, category: str, username: Optional[str] = None) -> Tuple[bool, str, Dict]:
    user = get_user(user_id, username)
    if not has_active_subscription(user):
        return False, "У тебя нет активной подписки. Оформи тариф, чтобы пользоваться этим разделом.", user

    limit = _limit_for_category(user, category)
    used = user.get("usage", {}).get(category, 0)
    if limit is not None and used >= limit:
        return (
            False,
            "Лимит по твоему тарифу исчерпан. Обнови тариф или продли подписку, чтобы продолжить.",
            user,
        )

    return True, "", user


def register_usage(user_id: int, category: str, username: Optional[str] = None) -> Dict:
    data = _load_db()
    key = str(user_id)
    user = data.get(key, _default_user(user_id, username))
    user = _sanitize_user_record(user)
    user["usage"][category] = user["usage"].get(category, 0) + 1
    data[key] = user
    _save_db(data)
    return user


def add_prompt_history(user_id: int, prompt: str, answer: str, username: Optional[str] = None, max_items: int = 20) -> Dict:
    data = _load_db()
    key = str(user_id)
    user = data.get(key, _default_user(user_id, username))
    user = _sanitize_user_record(user)
    user["history"].append({
        "prompt": prompt,
        "answer": answer,
        "ts": _now().strftime(DATE_FMT),
    })
    if len(user["history"]) > max_items:
        user["history"] = user["history"][-max_items:]
    data[key] = user
    _save_db(data)
    return user


def active_tariff_label(user: Dict) -> str:
    tariff_code = user.get("tariff", "free")
    tariff = config.TARIFFS.get(tariff_code)
    if not tariff:
        return "Бесплатный режим"
    days = subscription_days_left(user)
    return f"{tariff['name']} (осталось дней: {days})"
