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
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
OPENAI_RETRIES = 3
LOG_FILE = "logs.jsonl"

SERVICES = [
    ("AI маркетолог", "2500/мес", "ai_marketer"),
    ("Пакет на генерацию 25 изображений", "2500 руб", "img_25"),
    ("Пакет на генерацию 50 изображений", "5000 руб", "img_50"),
    ("Пакет на генерацию Reels/Shorts до 1 мин 10 шт", "2500 руб", "reels_10"),
    ("Пакет 10 шт. на генерацию видео до 3 мин с Аватаром", "2500 руб", "video_avatar_10"),
    ("Пакет на генерацию презентации (до 20 слайдов)", "1000 руб/преза", "presentation"),
]

SERVICES_TEXT = (
    "Выбери услугу:\n"
    + "\n".join([f"• {name} — {price}" for name, price, _ in SERVICES])
    + "\n\nОплата доступна через ЮKassa по кнопке ниже."
)
