import datetime
import json
from ai_marketer import config


def log_event(user_id: int, user_message: str, bot_answer: str, stage: str = ""):
    """Записывает событие в JSONL файл."""
    try:
        record = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "user_id": user_id,
            "stage": stage,
            "user_message": user_message,
            "bot_answer": bot_answer,
        }
        with open(config.LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("LOGGING ERROR:", exc)
