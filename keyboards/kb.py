from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import PRODUCTS, CATEGORIES, ADMIN_ID


def is_admin(user_id): return user_id == ADMIN_ID


# ─── ГЛАВНОЕ МЕНЮ ─────────────────────────────────────────────────────────────

def main_menu_kb(user_id=None):
    rows = [
        [
            InlineKeyboardButton(text="🛍 Каталог", callback_data="catalog"),
            InlineKeyboardButton(text="💰 Кошелёк", callback_data="wallet"),
        ],
        [
            InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        ],
        [
            InlineKeyboardButton(text="🔗 Реферальная программа", callback_data="referral"),
        ],
        [
            InlineKeyboardButton(text="💬 Поддержка", callback_data="support"),
            InlineKeyboardButton(text="ℹ️ О магазине", callback_data="about"),
        ],
        [
            InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
        ],
    ]
    if user_id and is_admin(user_id):
        rows.append([InlineKeyboardButton(text="🔐 Админ панель", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ─── КАТАЛОГ ──────────────────────────────────────────────────────────────────

def catalog_categories_kb():
    buttons = [[InlineKeyboardButton(text=name, callback_data=f"cat_{cid}")]
               for cid, name in CATEGORIES.items()]
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def category_products_kb(category):
    from database.db import get_product_active, get_product_rating
    buttons = []
    for pid, prod in PRODUCTS.items():
        if prod["category"] != category:
            continue
        active = get_product_active(pid)
        avg, cnt = get_product_rating(pid)
        stars = f" ⭐{avg}" if cnt > 0 else ""
        status = "" if active else " 🔴"
        label = f"{prod['emoji']} {prod['name']} — {prod['price']}₽{stars}{status}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"product_{pid}")])
    buttons.append([InlineKeyboardButton(text="🔙 К категориям", callback_data="catalog")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def product_kb(product_id, has_key=True, active=True):
    buttons = []
    if active and has_key:
        buttons.append([InlineKeyboardButton(text="✅ Купить", callback_data=f"buy_{product_id}")])
    elif not active:
        buttons.append([InlineKeyboardButton(text="🔴 Временно недоступен", callback_data="no_stock")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Нет в наличии", callback_data="no_stock")])
    buttons.append([InlineKeyboardButton(text="⭐ Отзывы", callback_data=f"reviews_{product_id}")])
    cat = PRODUCTS[product_id]["category"]
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"cat_{cat}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_purchase_kb(product_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{product_id}"),
            InlineKeyboardButton(text="❌ Отмена", callback_data=f"product_{product_id}"),
        ],
        [InlineKeyboardButton(text="🏷 Промокод", callback_data=f"promo_{product_id}")],
    ])


# ─── КОШЕЛЁК ──────────────────────────────────────────────────────────────────

def wallet_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Пополнить баланс", callback_data="deposit")],
        [InlineKeyboardButton(text="📋 История транзакций", callback_data="tx_history")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


def deposit_amounts_kb():
    amounts = [150, 300, 500, 1000, 2000, 5000]
    buttons = []
    row = []
    for i, a in enumerate(amounts):
        row.append(InlineKeyboardButton(text=f"{a}₽", callback_data=f"dep_{a}"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row: buttons.append(row)
    buttons.append([InlineKeyboardButton(text="✏️ Своя сумма", callback_data="dep_custom")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="wallet")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_kb(payment_url):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Перейти к оплате", url=payment_url)],
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="check_payment")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="wallet")],
    ])


# ─── ПРОФИЛЬ / ЗАКАЗЫ ─────────────────────────────────────────────────────────

def profile_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Кошелёк", callback_data="wallet"),
         InlineKeyboardButton(text="📦 Заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="🔗 Реферальная программа", callback_data="referral")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


def back_to_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
    ])


def orders_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍 В каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


def order_detail_kb(order_id, product_id, reviewed):
    buttons = []
    if not reviewed:
        buttons.append([InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"leave_review_{order_id}_{product_id}")])
    buttons.append([InlineKeyboardButton(text="🔙 К заказам", callback_data="my_orders")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def review_rating_kb(order_id, product_id):
    stars = ["1⭐", "2⭐", "3⭐", "4⭐", "5⭐"]
    buttons = [[InlineKeyboardButton(text=s, callback_data=f"rate_{order_id}_{product_id}_{i+1}")]
               for i, s in enumerate(stars)]
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="my_orders")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ─── РЕФЕРАЛЬНАЯ ПРОГРАММА ────────────────────────────────────────────────────

def referral_kb(ref_link):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}&text=Лучший магазин AI-подписок!")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


# ─── ОТЗЫВЫ ───────────────────────────────────────────────────────────────────

def reviews_back_kb(product_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 К товару", callback_data=f"product_{product_id}")]
    ])


# ─── ПРОМОКОД ─────────────────────────────────────────────────────────────────

def promo_cancel_kb(product_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"buy_{product_id}")]
    ])


# ─── АДМИН ПАНЕЛЬ ─────────────────────────────────────────────────────────────

def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats"),
            InlineKeyboardButton(text="👥 Пользователи", callback_data="adm_users"),
        ],
        [
            InlineKeyboardButton(text="🔑 Добавить ключи", callback_data="adm_add_keys"),
            InlineKeyboardButton(text="📦 Остатки ключей", callback_data="adm_keys_stock"),
        ],
        [
            InlineKeyboardButton(text="📋 Последние заказы", callback_data="adm_orders"),
            InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="adm_add_balance"),
        ],
        [
            InlineKeyboardButton(text="🏷 Промокоды", callback_data="adm_promos"),
            InlineKeyboardButton(text="🔧 Товары вкл/выкл", callback_data="adm_toggle_products"),
        ],
        [
            InlineKeyboardButton(text="🔍 Найти пользователя", callback_data="adm_find_user"),
            InlineKeyboardButton(text="🚫 Баны", callback_data="adm_bans"),
        ],
        [
            InlineKeyboardButton(text="📢 Рассылка", callback_data="adm_broadcast"),
        ],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])


def admin_products_kb(for_keys=True):
    rows = []
    for pid, prod in PRODUCTS.items():
        label = f"{prod['emoji']} {prod['name']}"
        cb = f"adm_keys_{pid}" if for_keys else f"adm_tgl_{pid}"
        rows.append([InlineKeyboardButton(text=label, callback_data=cb)])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_toggle_products_kb():
    from database.db import get_product_active
    rows = []
    for pid, prod in PRODUCTS.items():
        active = get_product_active(pid)
        icon = "✅" if active else "🔴"
        label = f"{icon} {prod['emoji']} {prod['name']}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"adm_tgl_{pid}")])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_promos_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать промокод", callback_data="adm_promo_create")],
        [InlineKeyboardButton(text="📋 Список промокодов", callback_data="adm_promo_list")],
        [InlineKeyboardButton(text="🗑 Удалить промокод", callback_data="adm_promo_delete")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")],
    ])


def admin_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Админ панель", callback_data="admin")]
    ])


def ban_user_kb(user_id, is_banned):
    action = "adm_unban" if is_banned else "adm_ban"
    label = "✅ Разбанить" if is_banned else "🚫 Забанить"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data=f"{action}_{user_id}")],
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data=f"adm_bal_{user_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin")],
    ])