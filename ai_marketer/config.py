import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_API_KEY = os.getenv("YOOKASSA_API_KEY", "")
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "") or "https://t.me/ai_marketer_360_bot"

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Не заданы TELEGRAM_TOKEN / OPENAI_API_KEY в .env")

BOT_NAME = "AI-маркетолог 360°"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.1")
SORA_MODEL = os.getenv("SORA_MODEL", OPENAI_MODEL)
PRESENTATION_MODEL = os.getenv("PRESENTATION_MODEL", OPENAI_MODEL)
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
OPENAI_RETRIES = 3
LOG_FILE = "logs.jsonl"

TARIFFS = {
    "start": {
        "name": "Старт",
        "price": 2990,
        "display_price": "2 990 ₽ / мес",
        "limits": {"text": "24/7 текстовый ИИ", "images": 0, "video": 0, "presentations": 0},
        "description": (
            "Маркетолог 24/7 (только текст): стратегии, планы, офферы, воронки. "
            "Контент-планы и тексты постов/объявлений, базовые сценарии, стратегия на 7/30 дней, "
            "доступ к базовым обучающим материалам."
        ),
    },
    "marketing_pro": {
        "name": "Маркетинг-про",
        "price": 5990,
        "display_price": "5 990 ₽ / мес",
        "limits": {"text": "всё из Старт", "images": 50, "video": 0, "presentations": 0},
        "description": (
            "Всё из «Старт» плюс расширенные сценарии, детализированные стратегии и воронки. "
            "Добавлена генерация изображений (креативы, обложки, баннеры), лимиты: до 300 текстовых запросов и 50 изображений."
        ),
    },
    "content_studio": {
        "name": "Контент-студия",
        "price": 13990,
        "display_price": "13 990 ₽ / мес",
        "limits": {"text": "всё из Маркетинг-про", "images": 80, "video": 15, "presentations": 3},
        "description": (
            "Всё из «Маркетинг-про» плюс генерация видео (Reels/Shorts/VK-клипы, ролики до 3 минут) "
            "и презентаций (питч-деки, КП, вебинары, тексты слайдов + рекомендации). "
            "Лимиты: 600 текстов, 80 изображений, 15 видео-сценариев, 3 презентации."
        ),
    },
    "agency": {
        "name": "Агентство 360",
        "price": 59990,
        "display_price": "59 990 ₽ / мес",
        "limits": {"text": "всё из Контент-студия", "images": 200, "video": 60, "presentations": 10},
        "description": (
            "Всё из «Контент-студия» плюс повышенные лимиты и массовая генерация под несколько проектов. "
            "Лимиты: 1 200 текстов, 200 изображений, 60 видео-сценариев, 10 презентаций. "
            "Приоритетная поддержка и онбординг."
        ),
    },
}

PROMOCODES = {
    "стеблев": 0.5,
    "шимин": 0.5,
}

SERVICES = [
    (f"{data['name']} — {data['display_price']}", data["display_price"], code)
    for code, data in TARIFFS.items()
]

SERVICES_TEXT = (
    "Выбери тариф AI маркетолога 360.\n"
    + "\n".join([f"• {data['name']} — {data['display_price']}" for data in TARIFFS.values()])
    + "\n\nОплата доступна через ЮKassa по кнопкам ниже."
)
