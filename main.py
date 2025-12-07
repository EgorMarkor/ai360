# main.py
# AI-МАРКЕТОЛОГ 360° — Telegram-бот в одном файле, продакшн-ready
# Зависимости:
#   pip install python-telegram-bot==20.8 openai python-dotenv pandas openpyxl reportlab

import os
import io
import re
import asyncio
import json
import math
import traceback
import contextlib
from datetime import datetime, timedelta
from typing import Any, Awaitable, Dict, List, Optional

import pandas as pd

from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InputFile,
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

from ai_marketer import config
from ai_marketer.gpt_client import ask_gpt_with_typing, chatgpt_answer
from ai_marketer.keyboards import (
    AI_MARKETER_MENU,
    CONTENT_MENU,
    INLINE_COMP_MENU,
    INLINE_CONTACT,
    INLINE_GROWTH_MENU,
    INLINE_START_DIAG,
    MAIN_MENU,
    SERVICES_MENU,
    aux_menu,
    back_main_buttons,
    report_menu,
    tariff_buttons,
    tariff_details_buttons,
)
from ai_marketer.logging_utils import log_event
from ai_marketer.payments import build_service_payment
from ai_marketer.state import UserState, get_state, reset_state
from ai_marketer.user_db import (
    activate_tariff,
    active_tariff_label,
    add_prompt_history,
    check_access,
    get_user,
    has_active_subscription,
    subscription_days_left,
    register_usage,
)

# ------------------------------
# 🔧 ИНИЦИАЛИЗАЦИЯ
# ------------------------------
TELEGRAM_TOKEN = config.TELEGRAM_TOKEN
BOT_NAME = config.BOT_NAME
OPENAI_MODEL = config.OPENAI_MODEL
TEMPERATURE = config.TEMPERATURE
OPENAI_RETRIES = config.OPENAI_RETRIES
SERVICES_TEXT = config.SERVICES_TEXT
TARIFFS = config.TARIFFS

# ------------------------------
# 🧩 КОНСТАНТЫ И ВСПОМОГАТЕЛЬНОЕ
# ------------------------------


def sanitize(text: str, max_len: int = 3500) -> str:
    if not text:
        return ""
    text = text.replace("\x00", " ").strip()
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def split_for_telegram(text: str, chunk_size: int = 3500) -> List[str]:
    cleaned = (text or "").replace("\x00", " ").strip()
    if not cleaned:
        return ["(пустой ответ)"]
    parts: List[str] = []
    remaining = cleaned
    while remaining:
        if len(remaining) <= chunk_size:
            parts.append(remaining)
            break
        split_idx = remaining.rfind("\n", 0, chunk_size)
        if split_idx == -1 or split_idx < chunk_size * 0.5:
            split_idx = remaining.rfind(" ", 0, chunk_size)
        if split_idx == -1 or split_idx < chunk_size * 0.5:
            split_idx = chunk_size
        parts.append(remaining[:split_idx].strip())
        remaining = remaining[split_idx:].lstrip()
    return [p for p in parts if p]


def strip_md_symbols(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[\*#]+", "", text)


def format_gpt_answer_for_telegram(text: str) -> str:
    """Делает структурированную выдачу для Telegram без Markdown/HTML и символов * или #."""
    if not text:
        return ""

    normalized = strip_md_symbols(text.replace("\r\n", "\n").replace("\r", "\n").strip())
    if not normalized:
        return ""

    blocks = [b.strip() for b in re.split(r"\n{2,}", normalized) if b.strip()]
    formatted_blocks: List[str] = []

    for block in blocks:
        lines = [strip_md_symbols(ln.strip()) for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue

        original_header = lines[0]
        header_line = strip_md_symbols(re.sub(r"^[\-•—\*]+\s*", "", original_header).strip())
        header_line = strip_md_symbols(re.sub(r"^\d+[)\.\-–]\s*", "", header_line).strip())
        if not header_line:
            header_line = strip_md_symbols(original_header.strip())

        inline_body = ""
        if ":" in header_line:
            potential_header, potential_body = header_line.split(":", 1)
            if potential_body.strip():
                inline_body = strip_md_symbols(potential_body.strip())
            header_line = strip_md_symbols(potential_header.strip())

        body_candidates = []
        if inline_body:
            body_candidates.append(inline_body)
        body_candidates.extend(lines[1:])

        formatted_body = []
        for raw_line in body_candidates:
            clean = strip_md_symbols(re.sub(r"^[\-•—\*]+\s*", "", raw_line).strip())
            clean = strip_md_symbols(re.sub(r"^\d+[)\.\-–]\s*", "", clean).strip())
            if clean:
                formatted_body.append(f"• {clean}")

        header_text = f"🔹 {header_line}" if header_line else ""
        if formatted_body:
            formatted_blocks.append(strip_md_symbols(header_text + "\n" + "\n".join(formatted_body)))
        else:
            formatted_blocks.append(strip_md_symbols(header_text))

    result = "\n\n".join(formatted_blocks) if formatted_blocks else normalized
    return strip_md_symbols(result)


async def send_split_text(message_obj, text: str, *, parse_mode=None, disable_preview: bool = True, reply_markup=None):
    chunks = split_for_telegram(text)
    for idx, chunk in enumerate(chunks):
        kwargs = {
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_preview,
        }
        if idx == len(chunks) - 1 and reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        await message_obj.reply_text(chunk, **kwargs)
        await asyncio.sleep(0.4)


def tariff_text_intro() -> str:
    return "Выберите тариф AI маркетолога 360."


def tariff_description(code: str) -> str:
    data = TARIFFS[code]
    header = f"Тариф «{data['name']}» — {data['display_price']}"
    if code == "start":
        bullets = [
            "Только текстовый ИИ-маркетолог 24/7",
            "Стратегии, контент-планы, офферы, воронки, тексты постов и рекламы",
        ]
    elif code == "marketing_pro":
        bullets = [
            "Всё из тарифа \"Старт\"",
            "До 50 генераций изображений (креативы, обложки, баннеры)",
        ]
    elif code == "content_studio":
        bullets = [
            "Всё из «Маркетинг-про»",
            "До 80 генераций изображений",
            "До 15 видео-сценариев (Reels, Shorts, реклама)",
            "До 3 презентаций (структура + тексты)",
        ]
    else:
        bullets = [
            "Всё из «Контент-студия»",
            "До 200 генераций изображений",
            "До 60 видео-сценариев",
            "До 10 презентаций",
            "Приоритетная поддержка",
        ]
    return header + "\n" + "\n".join([f"• {b}" for b in bullets])


def tariffs_more_info() -> str:
    return (
        "Как работают тарифы и лимиты\n"
        "• Каждый тариф действует 30 дней с момента оплаты.\n"
        "• Внутри тарифа есть лимиты на текстовые запросы и генерации (изображения, видео-сценарии, презентации).\n"
        "• Если вы израсходовали лимиты раньше 30 дней — просто покупаете новый пакет того же тарифа и получаете новые лимиты, а срок продлевается ещё на 30 дней с даты оплаты.\n"
        "• Если вы не израсходовали лимиты за 30 дней — остатки сгорают. Новый месяц оплачивается по полной стоимости тарифа.\n"
        "• Прикрепленный файл кнопкой для просмотра к сообщению: Подробнее о тарифах"
    )


def format_success_payment(code: str, user_data: Optional[Dict] = None) -> str:
    data = TARIFFS[code]
    limits = data["limits"]
    text_limit = limits.get("text", "по тарифу")
    images_limit = limits.get("images", 0)
    video_limit = limits.get("video", 0)
    pres_limit = limits.get("presentations", 0)

    expires_text = "до активации"
    if user_data:
        days_left = subscription_days_left(user_data)
        expires_raw = user_data.get("subscription_expires_at")
        if expires_raw:
            try:
                expires_dt = datetime.strptime(expires_raw, "%Y-%m-%dT%H:%M:%S")
                expires_text = expires_dt.strftime("%d.%m.%Y")
            except Exception:
                expires_text = "уточняется"
        else:
            expires_text = f"{days_left} дней"
    else:
        expires = datetime.now() + timedelta(days=30)
        expires_text = expires.strftime("%d.%m.%Y")

    return (
        "Оплата прошла успешно ✅\n"
        f"Тариф: {data['name']}\n"
        f"Срок действия до: {expires_text}\n\n"
        "Доступно:\n"
        f"• Текстовые запросы: {text_limit}\n"
        f"• Генерации изображений: {images_limit}\n"
        f"• Видео-сценарии: {video_limit}\n"
        f"• Презентации: {pres_limit}\n\n"
        "Можно начинать работу. Выберите раздел в меню и задайте первую задачу ИИ-маркетологу."
    )


async def ensure_paid_access(message_obj, user_profile: Dict, category: str):
    allowed, reason, updated_profile = check_access(
        user_profile.get("id", 0), category, user_profile.get("username")
    )
    if not allowed:
        await message_obj.reply_text(
            f"{reason}\n\nТекущий статус: {active_tariff_label(updated_profile)}",
            reply_markup=tariff_buttons(),
        )
    return allowed, updated_profile

# ------------------------------
# 🗂️ СОСТОЯНИЕ ПОЛЬЗОВАТЕЛЯ
# ------------------------------


BOLTALKA_HINT_TEXT = (
    "Можешь задавать уточняющие вопросы в свободной форме.\n"
    "Чтобы выйти, нажми «⬅️ В главное меню»."
)


def reset_boltalka_context(st: UserState, last_user_text: Optional[str], assistant_text: str):
    st.chat_mode = True
    st.chat_history = []
    if last_user_text:
        st.chat_history.append({"role": "user", "content": last_user_text})
    if assistant_text:
        st.chat_history.append({"role": "assistant", "content": assistant_text})


async def send_boltalka_hint(message_obj):
    await message_obj.reply_text(BOLTALKA_HINT_TEXT, reply_markup=back_main_buttons())


async def send_gpt_reply(message_obj, st: UserState, answer: str, *, last_user_text: Optional[str] = None, parse_mode=None):
    formatted_answer = format_gpt_answer_for_telegram(answer)
    await send_split_text(message_obj, formatted_answer, parse_mode=parse_mode)
    reset_boltalka_context(st, last_user_text, answer)
    try:
        user = getattr(message_obj, "from_user", None)
        if user:
            add_prompt_history(user.id, last_user_text or "", answer, username=user.username)
    except Exception:
        pass
    await send_boltalka_hint(message_obj)

# ------------------------------
# 📋 ВОПРОСЫ ДИАГНОСТИКИ (СОКР. + РАСШ.)
# ------------------------------
DIAG_QUESTIONS = [
    # О компании
    ("company_name", "Как называется твоя компания или бренд?"),
    ("company_niche", "В какой нише развивается компания?"),
    ("company_age", "Сколько лет бизнесу?"),

    # Продукт
    ("main_product", "Что является основным продуктом или услугой?\nОпиши простыми словами, что вы продаёте и какую задачу это решает."),
    ("product_value", "В чём ключевая ценность продукта? Какая главная выгода или результат для клиента?"),
    ("product_strengths", "Какие три сильные стороны продукта?"),
    ("product_weaknesses", "Какие слабые стороны или ограничения продукта?"),
    ("product_diff", "Чем ваш продукт отличается от конкурентов?\n(1–2 объективных отличия)"),
    ("product_improve", "Что вы хотите улучшить или изменить в продукте в ближайшие 3 месяца?"),

    # Целевая аудитория
    ("target_main", "Кто ваш основной клиент?\n(кто покупает и зачем)"),
    ("target_need", "Какую задачу или потребность клиент закрывает вашим продуктом?"),
    ("target_why_you", "Почему клиент выбирает вас?\n(1–2 ключевые причины)"),
    ("target_factors", "Какие три фактора сильнее всего влияют на решение купить?"),

    # Каналы привлечения
    ("traffic_channels", "Какие каналы привлечения клиентов вы используете?"),
    ("traffic_analytics", "Вы ведёте аналитику?"),
    ("traffic_budget", "Какой рекламный бюджет в месяц?"),
    ("traffic_team", "Есть ли команда для продвижения?"),
]

# ------------------------------
# ▶️ СТАРТ ДИАГНОСТИКИ
# ------------------------------
async def start_diagnostic_session(message_obj, st: UserState):
    """Запускает диагностику без дополнительных подтверждений."""
    st.stage = "diag_running"
    st.diagnostic_step = 1
    st.answers = {}
    st.competitors = []
    st.last_report_text = None
    st.last_report_sections = {}
    st.chat_mode = False


    first_question = DIAG_QUESTIONS[0][1]
    await message_obj.reply_text(
        "Начинаем.\n\n" + first_question,
        reply_markup=back_main_buttons()
    )

# ------------------------------
# 🖨️ PDF-ОТЧЁТ (ReportLab)
# ------------------------------
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

def make_pdf_report(username: str, summary_text: str, sections: Dict[str, str]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    left = 18 * mm
    top = height - 20 * mm

    def write_wrapped(text: str, x: float, y: float, max_width: float, leading=14):
        from reportlab.pdfbase.pdfmetrics import stringWidth
        lines = []
        for paragraph in text.split("\n"):
            words = paragraph.split(" ")
            line = ""
            for w in words:
                test = (line + " " + w).strip()
                if stringWidth(test, "Helvetica", 11) <= max_width:
                    line = test
                else:
                    lines.append(line)
                    line = w
            lines.append(line)
            lines.append("")  # blank between paragraphs
        cur_y = y
        for ln in lines:
            if cur_y < 20 * mm:
                c.showPage()
                cur_y = height - 20 * mm
                c.setFont("Helvetica", 11)
            c.drawString(x, cur_y, ln)
            cur_y -= leading
        return cur_y

    c.setTitle(f"Отчёт {BOT_NAME}")
    c.setAuthor(BOT_NAME)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(left, top, f"Итоговый отчёт — {BOT_NAME}")
    c.setFont("Helvetica", 11)
    c.drawString(left, top - 14, f"Пользователь: {username}")

    y = top - 30
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, y, "Краткое резюме")
    y -= 18
    c.setFont("Helvetica", 11)
    y = write_wrapped(sanitize(summary_text, 8000), left, y, width - 2*left)

    for title, body in sections.items():
        if y < 40 * mm:
            c.showPage()
            y = height - 20 * mm
        c.setFont("Helvetica-Bold", 13)
        c.drawString(left, y, title)
        y -= 18
        c.setFont("Helvetica", 11)
        y = write_wrapped(sanitize(body, 8000), left, y, width - 2*left)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()

# ------------------------------
# 🏁 СТАРТ / HELP / CANCEL
# ------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_state(user.id)
    text = (
        f"👋 Привет! Я — {BOT_NAME}\n"
        "Твой личный интеллект для роста бизнеса.\n"
        "Я анализирую, считаю, создаю и стратегирую.\n"
        "Помогаю расти быстрее, дешевле и умнее — на основе данных, технологий и системного мышления.\n\n"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU)

    await update.message.reply_text("Предлагаю провести диагностику бизнеса\nФормат — стратегический брифинг на 10-15 минут: после ответов ты получишь: \n- реальную картину текущего состояния\n- потенциал роста\n- приоритеты развития", reply_markup=INLINE_START_DIAG)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды:\n"
        "/start — начало\n"
        "/help — помощь\n"
        "/cancel — сброс диалога",
        reply_markup=MAIN_MENU
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    reset_state(user.id)
    await update.message.reply_text("Окей, всё сбросил. Что дальше?", reply_markup=MAIN_MENU)

# ------------------------------
# 💳 ОПЛАТА И ТАРИФЫ
# ------------------------------


async def show_tariffs(message_obj):
    await message_obj.reply_text(tariff_text_intro(), reply_markup=tariff_buttons())

# ------------------------------
# 🧭 ОБРАБОТКА ГЛАВНОГО МЕНЮ (ТЕКСТ)
# ------------------------------
async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = get_state(user.id)
    txt = (update.message.text or "").strip()
    chat_id = update.effective_chat.id if update.effective_chat else None
    user_profile = get_user(user.id, user.username)

    user_id = user.id
    log_event(
        user_id=user_id,
        user_message=txt,
        bot_answer="", 
        stage=st.stage
    )


    if txt in ("⬅️ В главное меню", "В главное меню", "/menu"):
        reset_state(user.id)
        await update.message.reply_text("Главное меню:", reply_markup=MAIN_MENU)
        st.chat_mode = False
        st.chat_history = []
        return

    if txt in ("🛠 Услуги", "Услуги"):
        await update.message.reply_text(SERVICES_TEXT, reply_markup=SERVICES_MENU)
        return

    if txt in ("Оплата", "Оплата и тарифы", "💳 Оплата и тарифы"):
        await show_tariffs(update.message)
        return

    # 1️⃣ Протестировать AI-маркетолога
    if "Протестировать AI-маркетолога" in txt:
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        msg = (
            "Демо-режим 🧠\n"
            "Покажу, как нахожу точки роста и формирую гипотезы.\n\n"
            "Готов пройти мини-тест (3 вопроса) и получить идеи?"
            " Напиши «да», когда будешь готов или скажи «позже»."
        )
        st.stage = "demo"
        await update.message.reply_text(msg, reply_markup=back_main_buttons())
        return

    # 2️⃣ Диагностика бизнеса
    if "Диагностика бизнеса" in txt or txt == "Пройти диагностику 🚀" or txt == "Начать диагностику 🚀":
        await start_diagnostic_session(update.message, st)
        return

    # 3️⃣ Что я умею
    if "Что я умею" in txt:
        msg = (
            "Я — не просто бот. Я маркетолог, который видит бизнес на 360°:\n\n"
            "📊 Анализ бизнеса\n🎯 Стратегия продвижения\n📣 Контент\n🚀 Трафик и воронки\n🤖 Внедрение AI\n📈 Прогноз роста\n\n"
            "Выбери, что показать:"
        )
        await update.message.reply_text(msg, reply_markup=aux_menu())
        return

    # 4️⃣ Примеры и кейсы
    if "Примеры и кейсы" in txt:
        msg = (
            "Реальные результаты:\n\n"
            "👕 Бренд одежды — +220% за 3 месяца\n"
            "💪 Спорпит — рост на 180%\n"
            "🎓 Онлайн-курс — −40% CPL\n\n"
            "Хочешь так же? Пройди диагностику."
        )
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardMarkup([["Пройти диагностику 🚀"], ["⬅️ В главное меню"]], resize_keyboard=True))
        return

    # 5️⃣ Связаться с командой
    if "Связаться с командой" in txt or "Связаться с командой 360°" in txt:
        msg = (
            "Хочешь индивидуальную стратегию или AI-внедрение под ключ?\n"
            "Выбери действие:"
        )
        await update.message.reply_text(msg, reply_markup=back_main_buttons())
        await update.message.reply_text("Контакты:", reply_markup=back_main_buttons())
        await update.message.reply_text("Нажми кнопку ниже, чтобы написать менеджеру:", reply_markup=INLINE_CONTACT)
        return

    # Подменю: AI-Маркетолог
    if txt == "AI-Маркетолог" or txt == "🧬AI-Маркетолог":
        await update.message.reply_text("Выбери действие:", reply_markup=AI_MARKETER_MENU)
        return

    if txt == "📊 Провести анализ компании":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "quick_analyze"
        await update.message.reply_text("Напиши в одной фразе: что продаёте, кому и через какие каналы сейчас?", reply_markup=back_main_buttons())
        return

    if st.stage == "quick_analyze" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Сделай экспресс-анализ компании и 5 точек роста."
            " Формат: 1) Краткое резюме 2) Точки роста 3) Быстрые действия на 7 дней 4) Метрики.\n"
            f"Ввод: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "💡 Составить стратегию":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "quick_strategy"
        await update.message.reply_text("Опиши цель на 30–90 дней и бюджет (диапазон).", reply_markup=back_main_buttons())
        return

    if st.stage == "quick_strategy" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Составь конспект стратегии на 90 дней: цели, каналы, гипотезы, вехи по неделям, риски, метрики."
            f" Дано: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "🧩 Создать контент-план":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "quick_cplan"
        await update.message.reply_text("Ниша и ключевой продукт? Укажи площадку (TG/IG/ВК/YouTube).", reply_markup=back_main_buttons())
        return

    if st.stage == "quick_cplan" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Составь контент-план на 2 недели: 14 постов/роликов с идеей, тезисами, CTA и метрикой."
            f" Дано: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "📈 Подобрать каналы трафика":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "quick_channels"
        await update.message.reply_text("Кто ЦА и какой средний чек?", reply_markup=back_main_buttons())
        return

    if st.stage == "quick_channels" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Подбери 5 каналов трафика с обоснованием, старт-бюджетом, первыми шагами и основными рисками."
            f" Дано: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "⚙️ Внедрить AI для автоматизации":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Дай дорожную карту внедрения AI в SMB: контент, продажи, поддержка, аналитика, алерты, интеграции."
            " Формат: этапы (2 недели, 30 дней, 60 дней), инструменты, метрики, риски."
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        return

    # Подменю: Генерация контента
    if txt == "Генерация контента" or txt == "☄️Генерация контента":
        await update.message.reply_text("Что сгенерировать?", reply_markup=CONTENT_MENU)
        return

    if txt == "Создать изображение 🖼️":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "images")
        if not allowed:
            return
        st.stage = "gen_image"
        await update.message.reply_text(
            "Опиши задачу: продукт/услуга, ЦА, эмоция и стиль. Сгенерирую готовые описания для нейросетей изображений и подписи.",
            reply_markup=back_main_buttons(),
        )
        return
    if st.stage == "gen_image" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "images")
        if not allowed:
            return
        prompt = (
            "Сгенерируй 4 подробных описания для генерации изображений (Midjourney/DALL·E):"
            " каждая сцена должна включать ключевые объекты, настроение и композицию, а также подпись с CTA."
            f" Ввод: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        register_usage(user.id, "images", username=user.username)
        st.stage = "idle"
        return

    if txt == "Создать Reels/Shorts 🎬":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "video")
        if not allowed:
            return
        st.stage = "gen_reels"
        await update.message.reply_text(
            "Укажи нишу/продукт и площадку. Дам 5 сценариев Reels/Shorts с хук-строкой и раскадровкой.",
            reply_markup=back_main_buttons(),
        )
        return
    if st.stage == "gen_reels" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "video")
        if not allowed:
            return
        prompt = (
            "Сгенерируй 5 сценариев Reels/Shorts: хук, 3-4 шага сюжета, финальный CTA, длительность до 35 сек."
            f" Дано: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt, model_type="video")
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        register_usage(user.id, "video", username=user.username)
        st.stage = "idle"
        return

    if txt == "Создать видео до 3 минут 🎥":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "video")
        if not allowed:
            return
        st.stage = "gen_video"
        await update.message.reply_text(
            "Что за продукт и цель ролика? Сценарий будет до 3 минут с репликами и планом съёмок.",
            reply_markup=back_main_buttons(),
        )
        return
    if st.stage == "gen_video" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "video")
        if not allowed:
            return
        prompt = (
            "Напиши сценарий видео до 3 минут: интро, основной блок в 4-5 сценах, финальный оффер."
            " Добавь таймкоды, визуальные подсказки и текст ведущего."
            f" Дано: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt, model_type="video")
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        register_usage(user.id, "video", username=user.username)
        st.stage = "idle"
        return

    if txt == "Создать презентацию 📑":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "presentations")
        if not allowed:
            return
        st.stage = "gen_presentation"
        await update.message.reply_text(
            "Про что презентация и кто аудитория? Дам структуру до 20 слайдов с тезисами.",
            reply_markup=back_main_buttons(),
        )
        return
    if st.stage == "gen_presentation" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "presentations")
        if not allowed:
            return
        prompt = (
            "Сделай план презентации до 20 слайдов: заголовок, цель, тезисы, CTA."
            " Укажи ключевые цифры/офер, предложи визуальные подсказки и спикер-ноты."
            f" Ввод: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt, model_type="presentations")
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        register_usage(user.id, "presentations", username=user.username)
        st.stage = "idle"
        return

    if txt == "Идеи Reels 🎬":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "video")
        if not allowed:
            return
        st.stage = "reels"
        await update.message.reply_text("Опиши продукт/услугу и площадку. Дам 10 идей с хук-строками.", reply_markup=back_main_buttons())
        return
    if st.stage == "reels" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "video")
        if not allowed:
            return
        prompt = (
            "Сгенерируй 10 идей Reels/Shorts: хук, сюжет в 3 шага, финальный CTA, хронометраж до 30 сек."
            f" Ввод: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt, model_type="video")
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        register_usage(user.id, "video", username=user.username)
        st.stage = "idle"
        return

    if txt == "Заголовки 🔥":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "titles"
        await update.message.reply_text("Какая тема? Дам 20 заголовков в 4 стилях.", reply_markup=back_main_buttons())
        return
    if st.stage == "titles" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Сгенерируй 20 заголовков: 5 инфо, 5 выгода, 5 триггер, 5 проблематика."
            f" Тема: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "Посты/описания ✍️":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "posts"
        await update.message.reply_text("Тема/оффер и площадка (TG/IG/ВК/маркетплейс)?", reply_markup=back_main_buttons())
        return
    if st.stage == "posts" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Напиши 3 варианта поста/описания: краткий, подробный, продающий. Добавь CTA и эмодзи."
            f" Тема: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "Контент-план на 14 дней 🗓️":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "cplan14"
        await update.message.reply_text("Ниша, задача (продажи/охваты/экспертность) и платформа?", reply_markup=back_main_buttons())
        return
    if st.stage == "cplan14" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Сформируй таблицей план на 14 дней: формат, идея, тезисы, CTA, цель метрики."
            f" Ввод: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    if txt == "Тексты для баннеров 📣":
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        st.stage = "banners"
        await update.message.reply_text("Продукт + спецпредложение + ЦА. Дам 8 вариантов УТП в 4 форматах.", reply_markup=back_main_buttons())
        return
    if st.stage == "banners" and txt not in ("⬅️ В главное меню",):
        allowed, user_profile = await ensure_paid_access(update.message, user_profile, "text")
        if not allowed:
            return
        prompt = (
            "Сгенерируй 8 баннерных текстов: короткие (до 6 слов), оффер+боль, срочность, соц.доказательства."
            f" Дано: {txt}"
        )
        ans = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(update.message, st, ans, last_user_text=txt)
        st.stage = "idle"
        return

    # Доп. ветки
    if "Как я могу помочь твоему бизнесу" in txt:
        await update.message.reply_text(
            "Я анализирую текущие показатели, выявляю точки потерь и даю пошаговый план: стратегия, контент, трафик, автоматизация. Обычно видимые улучшения — в первые 30 дней.",
            reply_markup=aux_menu()
        )
        return

    if "Показать стратегию роста" in txt:
        await update.message.reply_text(
            "Чтобы показать реальную стратегию, пройдём диагностику — это займёт 3–5 минут.",
            reply_markup=ReplyKeyboardMarkup([["Начать диагностику 🚀"], ["⬅️ В главное меню"]], resize_keyboard=True)
        )
        return

    if "AI-инструменты для компании" in txt:
        ideas = (
            "🧠 Где внедрить AI:\n"
            "• Автогенерация контента (посты, Reels, баннеры)\n"
            "• Сценарии лид-менеджмента и триггеры\n"
            "• Скрипты продаж и Q&A по базе знаний\n"
            "• Прогноз спроса/бюджетов, алерты по метрикам\n"
            "• Аналитика воронки и когорт"
        )
        await update.message.reply_text(ideas, reply_markup=aux_menu())
        return

    if "Мои цифры и анализ" in txt:
        st.stage = "await_sales_file"
        await update.message.reply_text(
            "Отправь файл с продажами (CSV или XLSX). Я выделю закономерности и слабые места.",
            reply_markup=ReplyKeyboardMarkup([["Пропустить"], ["⬅️ В главное меню"]], resize_keyboard=True)
        )
        return

    # Кнопки отчёта
    if txt in ("Продукт 📦", "Целевая аудитория 🎯", "Продажи 💰", "Маркетинг 📣", "Команда 👥", "Конкуренты ⚔️", "Цифры и аналитика 📊", "Приоритеты ⚡️"):
        await show_report_section(update, context, txt)
        return

    if txt == "Сохранить отчёт PDF 📁":
        await export_pdf(update, context)
        return
    
    if txt == "💬 Поддержка":
        await update.message.reply_text(
            "Нажми на кнопку ниже, чтобы написать в поддержку:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Написать в поддержку", url="https://t.me/maglena_a")]
            ])
        )
        return


    # «Да/Позже» в разных ветках
    if st.stage == "demo":
        await handle_demo_flow(update, context, txt)
        return

    if st.stage in ("diag", "diag_running"):
        await handle_diagnostic_flow(update, context, txt)
        return
    
    # === Болталка после диагностики ===
    if st.chat_mode:
        return await handle_chat_mode(update, context)


    # Приклеиваем «умный ответ» если ничего не подошло
    await update.message.reply_text(
            "Я тебя услышал. Чтобы получить максимальную пользу — выбери действие в меню ниже:",
            reply_markup=MAIN_MENU
    )
    
    
async def handle_chat_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = get_state(user.id)
    txt = update.message.text.strip()
    chat_id = update.effective_chat.id if update.effective_chat else None

    # добавляем сообщение в историю
    st.chat_history.append({"role": "user", "content": txt})

    # ограничиваем историю
    MAX_HISTORY = 12
    if len(st.chat_history) > MAX_HISTORY:
        st.chat_history = st.chat_history[-MAX_HISTORY:]

    # формируем сообщения
    messages = [
        {"role": "system", "content": "Ты — AI-маркетолог 360°. Отвечай коротко, по делу, учитывай контекст диагностики."},

        # контекст диагностики
        {"role": "system", "content": f"Контекст диагностики: {json.dumps(st.answers, ensure_ascii=False)}"},
    ]

    # сама история
    messages.extend(st.chat_history)

    # вызываем OpenAI
    resp = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=TEMPERATURE,
    )
    answer = resp.choices[0].message.content.strip()

    # сохраняем ответ
    st.chat_history.append({"role": "assistant", "content": answer})

    formatted_answer = format_gpt_answer_for_telegram(answer)
    await send_split_text(update.message, formatted_answer)
    await send_boltalka_hint(update.message)


# ------------------------------
# 📎 ДОКУМЕНТЫ (CSV/XLSX)
# ------------------------------
async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = get_state(user.id)
    doc = update.message.document
    if not doc:
        return
    fname = (doc.file_name or "").lower()
    if st.stage != "await_sales_file":
        await update.message.reply_text("Файл принят, но сейчас он не нужен. Нажми «Мои цифры и анализ», чтобы загрузить отчёт по продажам.", reply_markup=aux_menu())
        return
    if not (fname.endswith(".csv") or fname.endswith(".xlsx") or fname.endswith(".xls")):
        await update.message.reply_text("Поддерживаю CSV и XLSX. Отправь, пожалуйста, один из этих форматов.")
        return

    try:
        file = await doc.get_file()
        bio = io.BytesIO()
        await file.download_to_memory(bio)
        bio.seek(0)
        if fname.endswith(".csv"):
            df = pd.read_csv(bio)
        else:
            df = pd.read_excel(bio)
        summary = summarize_sales_df(df)
        st.sales_df_summary = summary
        await update.message.reply_text("Принял файл ✅\nПредварительный разбор:", reply_markup=aux_menu())
        await update.message.reply_text(f"```\n{summary}\n```", parse_mode=ParseMode.MARKDOWN)
        st.stage = "idle"
    except Exception as e:
        await update.message.reply_text("Не удалось обработать файл. Проверь формат/кодировку и попробуй снова.")
        print("File parse error:", e)

def summarize_sales_df(df: pd.DataFrame) -> str:
    info = []
    try:
        info.append(f"Строк: {len(df):,}".replace(",", " "))
        info.append(f"Колонок: {len(df.columns)}")
        num_cols = df.select_dtypes(include="number").columns.tolist()
        if num_cols:
            info.append(f"Числовые колонки: {', '.join(num_cols[:6])}{' …' if len(num_cols)>6 else ''}")
            # Проба сумм/средних
            for col in num_cols[:3]:
                s = float(df[col].sum())
                m = float(df[col].mean())
                info.append(f"Σ {col}: {s:,.2f} | μ {col}: {m:,.2f}".replace(",", " "))
        # Возможная дата
        dt_cols = [c for c in df.columns if re.search(r"date|дата|time|время", str(c), re.I)]
        if dt_cols:
            info.append(f"Дата-колонки: {', '.join(dt_cols[:3])}")
    except Exception:
        pass
    return "\n".join(info)

# ------------------------------
# 🧪 ДЕМО-РЕЖИМ
# ------------------------------
async def handle_demo_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, txt: str):
    user = update.effective_user
    st = get_state(user.id)
    chat_id = update.effective_chat.id if update.effective_chat else None

    if txt.lower().startswith("да"):
        if "demo_q" not in st.answers:
            st.answers["demo_q"] = 1
            await update.message.reply_text("1/3: В двух фразах — что продаёшь и кому?", reply_markup=back_main_buttons())
            return
        if st.answers["demo_q"] == 1:
            st.answers["demo_prod"] = txt
            st.answers["demo_q"] = 2
            await update.message.reply_text("2/3: Где сейчас берёшь трафик? (каналы)", reply_markup=back_main_buttons())
            return
        if st.answers["demo_q"] == 2:
            st.answers["demo_channels"] = txt
            st.answers["demo_q"] = 3
            await update.message.reply_text("3/3: Какая цель на 30–60 дней? (выручка/лидов/запуск)", reply_markup=back_main_buttons())
            return
        if st.answers["demo_q"] == 3:
            st.answers["demo_goal"] = txt
            # Генерация идей
            allowed, _ = await ensure_paid_access(update.message, get_user(user.id, user.username), "text")
            if not allowed:
                st.stage = "idle"
                return
            prompt = (
                "Сгенерируй 6 быстрых гипотез роста для бизнеса на 30–60 дней, с приоритетами и ожидаемым эффектом.\n"
                f"Бизнес: {st.answers.get('demo_prod')}\n"
                f"Каналы сейчас: {st.answers.get('demo_channels')}\n"
                f"Цель: {st.answers.get('demo_goal')}\n"
                "Формат: нумерованный список, по каждой — идея, зачем, метрика, первый шаг."
            )
            ideas = await ask_gpt_with_typing(context.bot, chat_id, prompt)
            await send_gpt_reply(
                update.message,
                st,
                "Готово! Вот идеи, с которых можно стартовать:\n\n" + ideas,
                last_user_text=txt
            )
            st.stage = "idle"
            st.answers.pop("demo_q", None)
            return

    if txt.lower().startswith("позже"):
        st.stage = "idle"
        await update.message.reply_text("Окей, вернёмся позже. Чем ещё помочь?", reply_markup=MAIN_MENU)
        return

    # Любой другой текст в демо — считаем ответом на текущий вопрос
    await handle_demo_flow(update, context, "да")

# ------------------------------
# 🧭 ДИАГНОСТИКА: ЛОГИКА
# ------------------------------
async def handle_diagnostic_flow(update: Update, context: ContextTypes.DEFAULT_TYPE, txt: str):
    user = update.effective_user
    st = get_state(user.id)

    lower_txt = txt.lower().strip()

    if lower_txt.startswith("позже"):
        st.stage = "idle"
        st.diagnostic_step = 0
        await update.message.reply_text("Окей, вернёмся позже. Чем ещё помочь?", reply_markup=MAIN_MENU)
        return

    if st.diagnostic_step <= 0:
        await update.message.reply_text("Чтобы начать диагностику, нажми «Диагностика бизнеса» в главном меню.", reply_markup=MAIN_MENU)
        st.stage = "idle"
        return

    # Сохранение ответа на предыдущий вопрос
    if 1 <= st.diagnostic_step <= len(DIAG_QUESTIONS):
        key_prev, _ = DIAG_QUESTIONS[st.diagnostic_step - 1]
        st.answers[key_prev] = txt

    # Переход к следующему
    if st.diagnostic_step < len(DIAG_QUESTIONS):
        key, q = DIAG_QUESTIONS[st.diagnostic_step]
        st.diagnostic_step += 1
        await update.message.reply_text(q, reply_markup=back_main_buttons())
        return

    # После основного блока — конкуренты
    if st.diagnostic_step == len(DIAG_QUESTIONS):
        st.diagnostic_step += 1
        await update.message.reply_text(
            "🕵️ Теперь пришли 2–5 ссылок на конкурентов (сайты, соцсети, маркетплейсы, Telegram-каналы).\n"
            "Если не знаешь — напиши «Нет», и я сам подберу аналоги."
        )
        return

    # Получение ссылок конкурентов
    if st.diagnostic_step == len(DIAG_QUESTIONS) + 1:
        links = re.findall(r'(https?://\S+)', txt)
        if links:
            st.competitors = links[:5]
            await update.message.reply_text("Принял ссылки конкурентов 🔍", reply_markup=None)
        else:
            await update.message.reply_text("Хорошо, подберу аналоги сам.")
        st.diagnostic_step += 1
        # Предложить анализ конкурентов
        await finalize_diagnostic(update, context)
        return


async def finalize_diagnostic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Собирает отчёт, включает болталку и показывает дальнейшие шаги."""
    user = update.effective_user
    st = get_state(user.id)
    chat_id = update.effective_chat.id if update.effective_chat else None

    if st.stage not in ("diag", "diag_running"):
        return

    st.stage = "diag_complete"
    st.diagnostic_step = 0

    await update.message.reply_text("Формирую итоговый отчёт и план…")
    report_text = await make_final_report(user, st, bot=context.bot, chat_id=chat_id)

    await send_gpt_reply(update.message, st, report_text)
    await update.message.reply_text(
        "Нужно углубиться в конкретный блок? Выбери раздел отчёта или просто продолжай диалог.",
        reply_markup=report_menu()
    )

# ------------------------------
# 🔎 КНОПКИ АНАЛИЗА КОНКУРЕНТОВ И ОТЧЁТ
# ------------------------------
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = get_state(user.id)
    q = update.callback_query
    data = q.data
    await q.answer()
    chat_id = update.effective_chat.id if update.effective_chat else None

    if data in ("tariff_back",):
        await q.message.reply_text(tariff_text_intro(), reply_markup=tariff_buttons())
        return

    if data == "tariff_main_menu":
        await q.message.reply_text("Главное меню:", reply_markup=MAIN_MENU)
        return

    if data == "tariff_more":
        await send_split_text(q.message, tariffs_more_info(), reply_markup=tariff_buttons())
        return

    if data.startswith("tariff_") and not data.startswith(("tariff_pay_", "tariff_success_")):
        code = data.replace("tariff_", "", 1)
        if code in TARIFFS:
            await send_split_text(q.message, tariff_description(code), reply_markup=tariff_details_buttons(code))
            return

    if data.startswith("tariff_pay_"):
        service_code = data.replace("tariff_pay_", "", 1)
        try:
            payment_result = build_service_payment(service_code)
        except Exception as exc:  # noqa: BLE001
            await q.message.reply_text(
                "Не получилось создать счёт в ЮKassa. Напиши менеджеру, мы поможем оформить оплату.",
                reply_markup=INLINE_CONTACT,
            )
            log_event(user.id, f"buy:{service_code}", f"yookassa_error:{exc}", stage="payment")
            return

        if not payment_result:
            await q.message.reply_text(
                "Оплата пока не активирована. Напиши менеджеру, чтобы получить счёт или оформить заказ вручную.",
                reply_markup=INLINE_CONTACT,
            )
            return

        payment_url, payment_payload = payment_result
        payment_keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Оплатить через ЮKassa", url=payment_url)],
                [InlineKeyboardButton("✅ Я оплатил", callback_data=f"tariff_success_{service_code}")],
                [InlineKeyboardButton("Написать менеджеру", url="https://t.me/maglena_a")],
            ]
        )
        await q.message.reply_text(
            "Готово! Ниже ссылка на оплату через ЮKassa. После оплаты лимиты обновятся автоматически.",
            reply_markup=payment_keyboard,
        )
        log_event(user.id, f"buy:{service_code}", json.dumps(payment_payload, ensure_ascii=False), stage="payment")
        return

    if data.startswith("tariff_success_"):
        code = data.replace("tariff_success_", "", 1)
        if code in TARIFFS:
            profile = activate_tariff(user.id, code, username=user.username)
            success_text = format_success_payment(code, profile)
            success_keyboard = ReplyKeyboardMarkup(
                [
                    ["🧬AI-Маркетолог", "☄️Генерация контента"],
                    ["⬅️ В главное меню"],
                ],
                resize_keyboard=True,
            )
            await send_split_text(q.message, success_text, reply_markup=success_keyboard, disable_preview=True)
            return

    if data.startswith("buy_service_"):
        service_code = data.replace("buy_service_", "", 1)
        try:
            payment_result = build_service_payment(service_code)
        except Exception as exc:  # noqa: BLE001
            await q.message.reply_text(
                "Не получилось создать счёт в ЮKassa. Напиши менеджеру, мы поможем оформить оплату.",
                reply_markup=INLINE_CONTACT,
            )
            log_event(user.id, f"buy:{service_code}", f"yookassa_error:{exc}", stage="payment")
            return

        if not payment_result:
            await q.message.reply_text(
                "Оплата пока не активирована. Напиши менеджеру, чтобы получить счёт или оформить заказ вручную.",
                reply_markup=INLINE_CONTACT,
            )
            return

        payment_url, payment_payload = payment_result
        payment_keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Оплатить через ЮKassa", url=payment_url)],
                [InlineKeyboardButton("Написать менеджеру", url="https://t.me/maglena_a")],
            ]
        )
        await q.message.reply_text(
            "Готово! Ниже ссылка на оплату через ЮKassa. После оплаты лимиты обновятся автоматически.",
            reply_markup=payment_keyboard,
        )
        log_event(user.id, f"buy:{service_code}", json.dumps(payment_payload, ensure_ascii=False), stage="payment")
        return

    if data == "start_diag":
        await start_diagnostic_session(q.message, st)
        return

    if data == "get_presentation":
        await q.message.reply_text("Отправил запрос на презентацию. Менеджер свяжется с тобой в ближайшее время ✅")
        return

    if data == "get_report":
        # Сформировать итоговый отчёт и показать меню секций
        txt = await make_final_report(user, st, bot=context.bot, chat_id=chat_id)
        await q.message.reply_text("Готово ✅\nНиже — краткий отчёт и рекомендации.")
        await send_gpt_reply(q.message, st, txt)
        st.stage = "idle"
        return

    if data == "plan_30d":
        # 30-дневный пошаговый план
        prompt = (
            "Составь пошаговый 30-дневный план внедрения приоритетов: неделя за неделей,"
            " задачи, ответственные роли, метрики успеха, ожидаемый эффект, чек-лист.\n"
            f"Вводные (кратко): {json.dumps(st.answers, ensure_ascii=False)[:1200]}"
        )
        allowed, _ = await ensure_paid_access(q.message, get_user(user.id, user.username), "text")
        if not allowed:
            return
        plan = await ask_gpt_with_typing(context.bot, chat_id, prompt)
        await send_gpt_reply(q.message, st, plan)
        st.stage = "idle"
        return

    # Анализ конкурентов — выбор раздела
    if data in ("comp_prices", "comp_content", "comp_product", "comp_all", "comp_back"):
        if data == "comp_back":
            await q.message.reply_text("Ок, продолжаем.", reply_markup=None)
        else:
            section_map = {
                "comp_prices": "Цены и позиционирование",
                "comp_content": "Контент и продвижение",
                "comp_product": "Продукт и предложения",
                "comp_all": "Все разделы вместе"
            }
            section = section_map[data]
            allowed, _ = await ensure_paid_access(q.message, get_user(user.id, user.username), "text")
            if not allowed:
                return
            comp_text = await generate_competitor_review(st, section, bot=context.bot, chat_id=chat_id)
            await send_gpt_reply(q.message, st, comp_text)
        return

# Генерация обзора конкурентов
async def generate_competitor_review(st: UserState, focus: str, *, bot=None, chat_id: Optional[int] = None) -> str:
    comps = "\n".join(st.competitors) if st.competitors else "Нет ссылок; подбери аналоги по нише."
    prompt = (
        "Сделай краткий обзор конкурентов по нише пользователя.\n"
        f"Ссылки/подсказки:\n{comps}\n\n"
        f"Фокус: {focus}\n"
        "Формат: 1) Наблюдения 2) Отличия 3) Риски 4) Возможности 5) 3 шага обойти конкурентов."
    )
    return await ask_gpt_with_typing(bot, chat_id, prompt)

# ------------------------------
# 📄 ИТОГОВЫЙ ОТЧЁТ
# ------------------------------
async def make_final_report(user: Any, st: UserState, *, bot=None, chat_id: Optional[int] = None) -> str:
    sales_block = st.sales_df_summary or "Нет файла продаж. Рекомендую выгрузку для поиска потерь."
    prompt = (
        "Сформируй итоговый отчёт AI-маркетолога 360° по 7 направлениям (кратко, по делу):\n"
        "Направления: Продукт, Клиенты (ЦА), Продажи, Маркетинг, Команда, Конкуренты, Цифры.\n"
        "В конце — приоритеты на 30 дней (5 пунктов).\n\n"
        f"Исходные ответы пользователя (JSON): {json.dumps(st.answers, ensure_ascii=False)}\n"
        f"Аналитика по файлу продаж (если есть): {sales_block}\n"
        f"Ссылки конкурентов: {', '.join(st.competitors) if st.competitors else 'нет'}\n"
        "Стиль: чётко, без Markdown, не используй символы * и #."
    )
    full = await ask_gpt_with_typing(bot, chat_id, prompt)
    st.last_report_text = full

    # Выделим секции для быстрого меню
    parts = {
        "Продукт 📦": r"(?si)продукт.*?(?=\n#|\Z)",
        "Целевая аудитория 🎯": r"(?si)(целев(ая|ая аудитория)|клиент).*?(?=\n#|\Z)",
        "Продажи 💰": r"(?si)продаж[аи].*?(?=\n#|\Z)",
        "Маркетинг 📣": r"(?si)маркетинг.*?(?=\n#|\Z)",
        "Команда 👥": r"(?si)команд[аи].*?(?=\n#|\Z)",
        "Конкуренты ⚔️": r"(?si)конкурент[ы|ы].*?(?=\n#|\Z)",
        "Цифры и аналитика 📊": r"(?si)(цифр|аналитик).*?(?=\n#|\Z)",
        "Приоритеты ⚡️": r"(?si)(приоритет|30 дней|шаг[аи]).*?(?=\n#|\Z)",
    }
    st.last_report_sections = {}
    for title, regex in parts.items():
        m = re.search(regex, full)
        if m:
            st.last_report_sections[title] = m.group(0).strip()
    return full

async def show_report_section(update: Update, context: ContextTypes.DEFAULT_TYPE, title: str):
    user = update.effective_user
    st = get_state(user.id)
    if not st.last_report_text:
        await update.message.reply_text("Сначала нужно завершить диагностику, чтобы сформировать отчёт.", reply_markup=MAIN_MENU)
        return
    body = st.last_report_sections.get(title) or "Эта секция не выделена отдельно. См. общий отчёт."
    formatted_body = format_gpt_answer_for_telegram(f"{title}\n\n{body}")
    await send_split_text(update.message, formatted_body, reply_markup=report_menu())

async def export_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    st = get_state(user.id)
    if not st.last_report_text:
        await update.message.reply_text("Сначала сформируй отчёт, а затем можно экспортировать в PDF.", reply_markup=MAIN_MENU)
        return
    pdf_bytes = make_pdf_report(
        username=user.full_name or user.username or f"id:{user.id}",
        summary_text=st.last_report_text,
        sections=st.last_report_sections or {}
    )
    await update.message.reply_document(document=InputFile(io.BytesIO(pdf_bytes), filename="ai_marketer_360_report.pdf"), caption="Отчёт готов 📁")

# ------------------------------
# 🧵 ЗАВЕРШЕНИЕ ДИАГНОСТИКИ (ТРИГГЕР)
# ------------------------------
async def maybe_finish_diag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Когда пользователь закончил конкурентов/файл — предложим итоговый отчёт."""
    user = update.effective_user
    st = get_state(user.id)
    if st.stage in ("await_sales_file", "diag_running"):
        # Ничего не делаем автоматически — ждём команды пользователя.
        return

# ------------------------------
# 🛡️ ОБЩИЙ ОБРАБОТЧИК ОШИБОК
# ------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Exception while handling an update:", file=os.sys.stderr)
    traceback.print_exception(None, context.error, context.error.__traceback__)
    try:
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text("Ой! Сервисная ошибка. Уже чищу хвосты — попробуй ещё раз 🙌")
    except Exception:
        pass

# ------------------------------
# 🌐 РОУТИНГ CALLBACK И ТЕКСТА
# ------------------------------
async def any_message_postprocess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Хук на будущее. Сейчас ничего.
    return

# ------------------------------
# ▶️ MAIN
# ------------------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("cancel", cancel))

    # Callback-кнопки
    app.add_handler(CallbackQueryHandler(cb_handler))

    # Документы (CSV/XLSX)
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))

    # Текстовый роутер
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # Постобработка (необязательно)
    app.add_handler(MessageHandler(filters.ALL, any_message_postprocess))

    # Ошибки
    app.add_error_handler(error_handler)

    print("🤖 Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
