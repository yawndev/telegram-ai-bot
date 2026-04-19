import os


BASE_DIR = os.path.dirname(__file__)
ENV_PATH = os.path.join(BASE_DIR, ".env")


def _load_env_file():
    if not os.path.exists(ENV_PATH):
        return

    with open(ENV_PATH, encoding="utf-8") as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def _get_env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(
            f"Missing required setting: {name}. "
            "Create a .env file or set the environment variable before starting the bot."
        )
    return value


def _get_env_int(name, default=0):
    value = os.getenv(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"Environment variable {name} must be an integer.") from exc


_load_env_file()

BOT_TOKEN = _get_env("BOT_TOKEN", required=True)
ADMIN_ID = _get_env_int("ADMIN_ID", 0)

YUKASSA_SHOP_ID = _get_env("YUKASSA_SHOP_ID", "YOUR_SHOP_ID")
YUKASSA_SECRET_KEY = _get_env("YUKASSA_SECRET_KEY", "YOUR_SECRET_KEY")

MIN_DEPOSIT = _get_env_int("MIN_DEPOSIT", 150)
CURRENCY = _get_env("CURRENCY", "RUB")
MANAGER_USERNAME = _get_env("MANAGER_USERNAME", "@yaroslav_blog1")
CHANNEL_USERNAME = _get_env("CHANNEL_USERNAME") or None
REFERRAL_BONUS = _get_env_int("REFERRAL_BONUS", 100)
REFERRAL_BONUS_NEW = _get_env_int("REFERRAL_BONUS_NEW", 50)

PRODUCTS = {
    "claude_pro": {
        "name": "Claude Pro",
        "description": "✨ <b>Claude Pro</b>\n\n• Модель: Claude 3.5 Sonnet / Haiku\n• ~45 сообщений / 5 часов\n• Приоритетная очередь\n• Срок: 1 месяц",
        "price": 1990, "category": "claude", "emoji": "🤖", "manual": True, "active": True,
    },
    "claude_max5": {
        "name": "Claude Max 5x",
        "description": "🚀 <b>Claude Max 5x</b>\n\n• В 5 раз больше сообщений чем Pro\n• Доступ к Claude Opus 4\n• Расширенные Projects\n• Срок: 1 месяц",
        "price": 4990, "category": "claude", "emoji": "🚀", "manual": True, "active": True,
    },
    "claude_max20": {
        "name": "Claude Max 20x",
        "description": "⚡ <b>Claude Max 20x</b>\n\n• В 20 раз больше сообщений чем Pro\n• Claude Opus 4 без ограничений\n• Максимальные лимиты\n• Срок: 1 месяц",
        "price": 9990, "category": "claude", "emoji": "⚡", "manual": True, "active": True,
    },
    "chatgpt_plus": {
        "name": "ChatGPT Plus",
        "description": "💬 <b>ChatGPT Plus</b>\n\n• GPT-4o / GPT-4\n• DALL·E 3 генерация изображений\n• Плагины и Advanced Data Analysis\n• Срок: 1 месяц",
        "price": 1990, "category": "chatgpt", "emoji": "💬", "manual": False, "active": True,
    },
    "chatgpt_team": {
        "name": "ChatGPT Team",
        "description": "👥 <b>ChatGPT Team</b>\n\n• Всё из Plus\n• Командное пространство\n• Данные не используются для обучения\n• Срок: 1 месяц",
        "price": 3490, "category": "chatgpt", "emoji": "👥", "manual": False, "active": True,
    },
    "gemini_advanced": {
        "name": "Gemini Advanced (12 мес)",
        "description": "🌟 <b>Gemini Advanced</b>\n\n• Gemini Ultra 1.0\n• Интеграция с Google Workspace\n• 2 ТБ хранилища Google One\n• Срок: 12 месяцев",
        "price": 7990, "category": "gemini", "emoji": "🌟", "manual": False, "active": True,
    },
    "cursor_pro": {
        "name": "Cursor Pro",
        "description": "💻 <b>Cursor Pro</b>\n\n• AI-редактор кода (GPT-4 + Claude)\n• 500 быстрых запросов в месяц\n• Автодополнение кода\n• Срок: 1 месяц",
        "price": 1990, "category": "cursor", "emoji": "💻", "manual": False, "active": True,
    },
    "cursor_business": {
        "name": "Cursor Business",
        "description": "🏢 <b>Cursor Business</b>\n\n• Всё из Pro\n• Приватность кода\n• Командное управление + SSO\n• Срок: 1 месяц",
        "price": 3990, "category": "cursor", "emoji": "🏢", "manual": False, "active": True,
    },
    "midjourney_basic": {
        "name": "Midjourney Basic",
        "description": "🎨 <b>Midjourney Basic</b>\n\n• 200 изображений в месяц\n• Коммерческое использование\n• Все версии моделей\n• Срок: 1 месяц",
        "price": 990, "category": "midjourney", "emoji": "🎨", "manual": False, "active": True,
    },
    "midjourney_standard": {
        "name": "Midjourney Standard",
        "description": "🖼 <b>Midjourney Standard</b>\n\n• Безлимит (медленный режим)\n• 15 часов GPU быстрого режима\n• Stealth-режим (приватные фото)\n• Срок: 1 месяц",
        "price": 2490, "category": "midjourney", "emoji": "🖼", "manual": False, "active": True,
    },
    "midjourney_pro": {
        "name": "Midjourney Pro",
        "description": "🖌 <b>Midjourney Pro</b>\n\n• Безлимит (медленный режим)\n• 30 часов GPU быстрого режима\n• 12 параллельных генераций\n• Срок: 1 месяц",
        "price": 4490, "category": "midjourney", "emoji": "🖌", "manual": False, "active": True,
    },
    "perplexity_pro": {
        "name": "Perplexity Pro",
        "description": "🔍 <b>Perplexity Pro</b>\n\n• 600 Pro-поисков в день\n• GPT-4, Claude, Gemini для ответов\n• Загрузка файлов и изображений\n• Срок: 1 месяц",
        "price": 1490, "category": "other", "emoji": "🔍", "manual": False, "active": True,
    },
    "elevenlabs_starter": {
        "name": "ElevenLabs Starter",
        "description": "🎙 <b>ElevenLabs Starter</b>\n\n• 30 000 символов в месяц\n• 10 кастомных голосов\n• Клонирование голоса\n• Срок: 1 месяц",
        "price": 890, "category": "other", "emoji": "🎙", "manual": False, "active": True,
    },
    "runway_standard": {
        "name": "Runway Standard",
        "description": "🎬 <b>Runway Standard</b>\n\n• 625 кредитов в месяц\n• Генерация видео Gen-2\n• Удаление фона, инпейнтинг\n• Срок: 1 месяц",
        "price": 1290, "category": "other", "emoji": "🎬", "manual": False, "active": True,
    },
    "notion_plus": {
        "name": "Notion Plus",
        "description": "📝 <b>Notion Plus</b>\n\n• Безлимит блоков\n• Безлимит загрузок файлов\n• 30-дневная история версий\n• Notion AI включён\n• Срок: 1 месяц",
        "price": 790, "category": "other", "emoji": "📝", "manual": False, "active": True,
    },
}

CATEGORIES = {
    "claude":     "🤖 Claude",
    "chatgpt":    "💬 ChatGPT",
    "gemini":     "🌟 Gemini",
    "cursor":     "💻 Cursor",
    "midjourney": "🎨 Midjourney",
    "other":      "🎯 Другие сервисы",
}
