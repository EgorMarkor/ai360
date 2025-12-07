from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)

from ai_marketer.config import SERVICES, TARIFFS

MAIN_MENU = ReplyKeyboardMarkup(
    [
        ["🧭 Диагностика бизнеса"],
        ["🧬AI-Маркетолог", "☄️Генерация контента"],
        ["🛠 Услуги", "💳 Оплата и тарифы"],
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
        ["Создать изображение 🖼️"],
        ["Создать Reels/Shorts 🎬", "Создать видео до 3 минут 🎥"],
        ["Создать презентацию 📑"],
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


def tariff_buttons() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"Старт — {TARIFFS['start']['display_price']}", callback_data="tariff_start")],
            [
                InlineKeyboardButton(
                    f"Маркетинг-про — {TARIFFS['marketing_pro']['display_price']}",
                    callback_data="tariff_marketing_pro",
                )
            ],
            [InlineKeyboardButton(f"Контент-студия — {TARIFFS['content_studio']['display_price']}", callback_data="tariff_content_studio")],
            [InlineKeyboardButton(f"Агентство 360 — {TARIFFS['agency']['display_price']}", callback_data="tariff_agency")],
            [InlineKeyboardButton("ℹ Подробнее о тарифах", callback_data="tariff_more")],
            [InlineKeyboardButton("⬅ В главное меню", callback_data="tariff_main_menu")],
        ]
    )


def tariff_details_buttons(code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"Оплатить тариф \"{TARIFFS[code]['name']}\"", callback_data=f"tariff_pay_{code}")],
            [InlineKeyboardButton("⬅ Назад к тарифам", callback_data="tariff_back")],
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
