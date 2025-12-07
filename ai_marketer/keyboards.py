from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from ai_marketer.config import SERVICES

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🧭 Диагностика бизнеса"],
        ["🧬AI-Маркетолог", "☄️Генерация контента"],
        ["🛠 Услуги"],
        ["📞 Связаться с командой", "💬 Поддержка"],
    ],
    resize_keyboard=True,
)


def aux_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["💡 Как я могу помочь твоему бизнесу"],
            ["📊 Показать стратегию роста", "🧠 AI-инструменты для компании"],
            ["🧾 Мои цифры и анализ"],
            ["⬅️ В главное меню"],
        ],
        resize_keyboard=True,
    )


def back_main_buttons() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["⬅️ В главное меню"]], resize_keyboard=True)


def report_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["Продукт 📦", "Целевая аудитория 🎯"],
            ["Продажи 💰", "Маркетинг 📣"],
            ["Команда 👥", "Конкуренты ⚔️"],
            ["Цифры и аналитика 📊", "Приоритеты ⚡️"],
            ["Сохранить отчёт PDF 📁", "⬅️ В главное меню"],
        ],
        resize_keyboard=True,
    )


AI_MARKETER_MENU = ReplyKeyboardMarkup(
    [
        ["📊 Провести анализ компании", "💡 Составить стратегию"],
        ["🧩 Создать контент-план", "📈 Подобрать каналы трафика"],
        ["⚙️ Внедрить AI для автоматизации"],
        ["⬅️ В главное меню"],
    ],
    resize_keyboard=True,
)


CONTENT_MENU = ReplyKeyboardMarkup(
    [
        ["Создать изображение 🔒️"],
        ["Создать Reels/Shorts 🔒️", "Создать Видео до 3 минут 🔒️"],
        ["Создать презентацию 🔒️"],
        ["⬅️ В главное меню"],
    ],
    resize_keyboard=True,
)


SERVICES_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(f"Купить: {name}", callback_data=f"buy_service_{code}")]
        for name, _, code in SERVICES
    ]
)


INLINE_CONTACT = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Написать в Telegram менеджеру", url="https://t.me/maglena_a")]]
)

INLINE_START_DIAG = InlineKeyboardMarkup(
    [[InlineKeyboardButton("НАЧАТЬ ДИАГНОСТИКУ 🚀", callback_data="start_diag")]]
)

INLINE_COMP_MENU = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Цены и позиционирование 💰", callback_data="comp_prices"),
            InlineKeyboardButton("Контент и продвижение 📣", callback_data="comp_content"),
        ],
        [
            InlineKeyboardButton("Продукт и предложения ⚙️", callback_data="comp_product"),
            InlineKeyboardButton("Всё вместе 🧠", callback_data="comp_all"),
        ],
        [InlineKeyboardButton("⏪ Назад", callback_data="comp_back")],
    ]
)

INLINE_GROWTH_MENU = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("Получить отчёт 📊", callback_data="get_report")],
        [InlineKeyboardButton("Да, шаг за шагом 🚀", callback_data="plan_30d")],
        [InlineKeyboardButton("Получить аудит конкурентов 🕵️", callback_data="comp_all")],
    ]
)
