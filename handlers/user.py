from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import PRODUCTS, CATEGORIES, ADMIN_ID, MANAGER_USERNAME, MIN_DEPOSIT, REFERRAL_BONUS, REFERRAL_BONUS_NEW
from database.db import (
    get_or_create_user, get_user, get_balance, deduct_balance,
    create_order, complete_order, get_user_orders, get_order,
    get_available_key, mark_key_used, count_keys, add_balance,
    count_referrals, get_tx_history, get_product_active,
    use_promo, get_product_rating, get_product_reviews, add_review,
    is_banned, get_user_by_ref
)
from keyboards.kb import (
    main_menu_kb, catalog_categories_kb, category_products_kb,
    product_kb, confirm_purchase_kb, wallet_kb, deposit_amounts_kb,
    profile_kb, back_to_menu_kb, orders_kb, payment_kb,
    referral_kb, reviews_back_kb, promo_cancel_kb,
    order_detail_kb, review_rating_kb
)

router = Router()


class States(StatesGroup):
    dep_custom      = State()
    promo_input     = State()
    review_text     = State()
    review_data     = State()   # хранит order_id_product_id_rating


# ─── БАН ФИЛЬТР ───────────────────────────────────────────────────────────────

async def check_ban(user_id, obj):
    if is_banned(user_id):
        text = "🚫 Ваш аккаунт заблокирован. Обратитесь в поддержку."
        if isinstance(obj, Message):
            await obj.answer(text)
        else:
            await obj.answer(text, show_alert=True)
        return True
    return False


# ─── СТАРТ ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    user = message.from_user
    args = message.text.split()
    ref_code = args[1] if len(args) > 1 else None

    existing = get_user(user.id)
    new_user = existing is None

    db_user = get_or_create_user(user.id, user.username, user.full_name, ref_code)

    # Реферальные бонусы
    if new_user and ref_code:
        referrer = get_user_by_ref(ref_code)
        if referrer and referrer["user_id"] != user.id:
            add_balance(referrer["user_id"], REFERRAL_BONUS, f"Реферальный бонус (пользователь {user.id})")
            add_balance(user.id, REFERRAL_BONUS_NEW, "Бонус за регистрацию по реферальной ссылке")
            try:
                await message.bot.send_message(
                    referrer["user_id"],
                    f"🎉 По вашей реферальной ссылке зарегистрировался новый пользователь!\n"
                    f"➕ Вам начислено <b>{REFERRAL_BONUS}₽</b>",
                    parse_mode="HTML"
                )
            except:
                pass

    if await check_ban(user.id, message):
        return

    text = (
        f"👋 Привет, <b>{user.first_name}</b>!\n\n"
        f"🏪 Добро пожаловать в <b>ASTRAVIK SHOP</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Продаём подписки на лучшие AI-сервисы:\n\n"
        f"🤖 Claude Pro / Max5 / Max20\n"
        f"💬 ChatGPT Plus / Team\n"
        f"🌟 Gemini Advanced\n"
        f"💻 Cursor Pro / Business\n"
        f"🎨 Midjourney Basic / Standard / Pro\n"
        f"🔍 Perplexity Pro и другие\n\n"
        f"⚡ Автовыдача сразу после оплаты\n"
        f"🔐 Безопасная оплата через ЮКассу\n"
        f"💬 Поддержка 24/7\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )
    if new_user and ref_code:
        text += f"🎁 Вам начислен приветственный бонус <b>{REFERRAL_BONUS_NEW}₽</b>!\n"

    text += "Выбери раздел 👇"
    await message.answer(text, reply_markup=main_menu_kb(user.id), parse_mode="HTML")


@router.callback_query(F.data == "main_menu")
async def main_menu(call: CallbackQuery):
    if await check_ban(call.from_user.id, call): return
    await call.message.edit_text(
        "🏪 <b>ASTRAVIK SHOP</b> — магазин AI-подписок\n━━━━━━━━━━━━━━━━━━━━\nВыбери раздел 👇",
        reply_markup=main_menu_kb(call.from_user.id),
        parse_mode="HTML"
    )


# ─── КАТАЛОГ ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "catalog")
async def show_catalog(call: CallbackQuery):
    if await check_ban(call.from_user.id, call): return
    await call.message.edit_text(
        "🛍 <b>Каталог подписок</b>\n━━━━━━━━━━━━━━━━━━━━\nВыбери категорию 👇",
        reply_markup=catalog_categories_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("cat_"))
async def show_category(call: CallbackQuery):
    cat = call.data.split("_", 1)[1]
    cat_name = CATEGORIES.get(cat, "Категория")
    await call.message.edit_text(
        f"{cat_name}\n━━━━━━━━━━━━━━━━━━━━\nВыбери подписку 👇",
        reply_markup=category_products_kb(cat), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("product_"))
async def show_product(call: CallbackQuery):
    pid = call.data.split("_", 1)[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        await call.answer("Товар не найден", show_alert=True); return

    active = get_product_active(pid)
    stock = count_keys(pid)
    avg, cnt = get_product_rating(pid)

    if prod["manual"]:
        stock_text = "📬 Выдача через менеджера"
    else:
        avail = stock["available"]
        if avail > 5:    stock_text = f"✅ В наличии: {avail} шт."
        elif avail > 0:  stock_text = f"⚠️ Осталось: {avail} шт."
        else:            stock_text = "❌ Нет в наличии"

    if not active:
        stock_text = "🔴 Временно недоступен"

    rating_text = f"⭐ {avg} ({cnt} отзывов)" if cnt > 0 else "⭐ Нет отзывов"
    has_stock = prod["manual"] or (stock["available"] > 0 and active)

    text = (
        f"{prod['description']}\n\n"
        f"💵 Цена: <b>{prod['price']}₽</b>\n"
        f"{stock_text}\n"
        f"{rating_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{'📬 После покупки напиши менеджеру для активации' if prod['manual'] else '⚡ Аккаунт выдаётся автоматически'}"
    )
    await call.message.edit_text(text, reply_markup=product_kb(pid, has_stock, active), parse_mode="HTML")


@router.callback_query(F.data == "no_stock")
async def no_stock(call: CallbackQuery):
    await call.answer("❌ Товар временно недоступен. Загляни позже!", show_alert=True)


# ─── ПОКУПКА ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("buy_"))
async def buy_product(call: CallbackQuery, state: FSMContext):
    pid = call.data.split("_", 1)[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        await call.answer("Товар не найден", show_alert=True); return

    balance = get_balance(call.from_user.id)
    # Сбрасываем промокод из предыдущей сессии
    await state.update_data(promo_discount=0, promo_code=None)

    await _show_confirm(call, pid, prod, balance, 0, None)


async def _show_confirm(call, pid, prod, balance, discount, promo_code):
    final_price = max(0, prod["price"] - discount)
    text = (
        f"🛒 <b>Подтверждение покупки</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{prod['emoji']} {prod['name']}\n"
        f"💵 Цена: {prod['price']}₽\n"
    )
    if discount:
        text += f"🏷 Скидка по промокоду <b>{promo_code}</b>: -{discount}₽\n"
        text += f"✅ Итого: <b>{final_price}₽</b>\n"
    text += f"💰 Ваш баланс: <b>{balance:.2f}₽</b>\n"

    if balance < final_price:
        diff = final_price - balance
        text += (
            f"\n❌ <b>Недостаточно средств</b>\n"
            f"Не хватает: <b>{diff:.2f}₽</b>\n\n"
            f"Пополни кошелёк 👇"
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Пополнить кошелёк", callback_data="deposit")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data=f"product_{pid}")],
        ])
    else:
        text += "\n✅ Средств достаточно. Подтвердить покупку?"
        kb = confirm_purchase_kb(pid)

    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("promo_"))
async def enter_promo(call: CallbackQuery, state: FSMContext):
    pid = call.data.split("_", 1)[1]
    await state.update_data(promo_product=pid)
    await state.set_state(States.promo_input)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = promo_cancel_kb(pid)
    await call.message.edit_text(
        "🏷 <b>Введи промокод</b>\n━━━━━━━━━━━━━━━━━━━━\nНапиши промокод в чат:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(States.promo_input)
async def receive_promo(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("promo_product")
    prod = PRODUCTS.get(pid)
    code = message.text.strip().upper()

    promo = use_promo(code)
    if not promo:
        await message.answer(f"❌ Промокод <b>{code}</b> недействителен или уже использован.",
                             parse_mode="HTML")
        return

    discount = promo["discount"]
    if promo["type"] == "percent":
        discount = int(prod["price"] * discount / 100)

    await state.update_data(promo_discount=discount, promo_code=code)
    await state.clear()

    balance = get_balance(message.from_user.id)
    # Эмулируем CallbackQuery для переиспользования функции
    final = max(0, prod["price"] - discount)
    text = (
        f"🛒 <b>Подтверждение покупки</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{prod['emoji']} {prod['name']}\n"
        f"💵 Цена: {prod['price']}₽\n"
        f"🏷 Скидка по промокоду <b>{code}</b>: -{discount}₽\n"
        f"✅ Итого: <b>{final}₽</b>\n"
        f"💰 Ваш баланс: <b>{balance:.2f}₽</b>\n\n"
    )
    if balance < final:
        text += f"❌ Не хватает: {final - balance:.2f}₽"
    else:
        text += "✅ Подтвердить покупку?"

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✅ Купить за {final}₽", callback_data=f"confirm_{pid}_{discount}"),
         InlineKeyboardButton(text="❌ Отмена", callback_data=f"product_{pid}")],
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("confirm_"))
async def confirm_purchase(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    pid = parts[1]
    discount = int(parts[2]) if len(parts) > 2 else 0

    prod = PRODUCTS.get(pid)
    if not prod:
        await call.answer("Товар не найден", show_alert=True); return

    user_id = call.from_user.id
    final_price = max(0, prod["price"] - discount)
    balance = get_balance(user_id)

    if balance < final_price:
        await call.answer("❌ Недостаточно средств!", show_alert=True); return

    key_data = None
    if not prod["manual"]:
        key_data = get_available_key(pid)
        if not key_data:
            await call.answer("❌ Товар закончился! Попробуй позже.", show_alert=True); return

    deduct_balance(user_id, final_price, f"Покупка: {prod['name']}")
    order_id = create_order(user_id, pid, final_price)

    if prod["manual"]:
        complete_order(order_id, "manual_delivery")
        text = (
            f"✅ <b>Покупка оформлена!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{prod['emoji']} <b>{prod['name']}</b>\n"
            f"💵 Оплачено: {final_price}₽\n"
            f"📦 Заказ: <b>#{order_id}</b>\n\n"
            f"📬 <b>Как получить подписку:</b>\n"
            f"1. Напиши менеджеру: <b>{MANAGER_USERNAME}</b>\n"
            f"2. Укажи номер заказа: <b>#{order_id}</b>\n"
            f"3. Менеджер активирует в течение 15 минут\n\n"
            f"⏰ Время работы: 09:00 — 23:00 МСК"
        )
        try:
            await call.bot.send_message(
                ADMIN_ID,
                f"🔔 <b>Новый заказ #{order_id}</b>\n"
                f"👤 @{call.from_user.username or call.from_user.id}\n"
                f"🛍 {prod['name']} — {final_price}₽\n"
                f"📌 Требуется ручная выдача",
                parse_mode="HTML"
            )
        except: pass
    else:
        mark_key_used(key_data["id"], user_id)
        complete_order(order_id, key_data["key_value"])
        text = (
            f"✅ <b>Покупка успешна!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{prod['emoji']} <b>{prod['name']}</b>\n"
            f"💵 Оплачено: {final_price}₽\n"
            f"📦 Заказ: <b>#{order_id}</b>\n\n"
            f"🔑 <b>Ваш аккаунт:</b>\n"
            f"<code>{key_data['key_value']}</code>\n\n"
            f"⚠️ Сохрани данные в надёжном месте!\n"
            f"❓ Проблемы? Напиши в поддержку"
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Мои заказы", callback_data="my_orders")],
        [InlineKeyboardButton(text="🛍 Продолжить покупки", callback_data="catalog")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")],
    ])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ─── КОШЕЛЁК ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "wallet")
async def show_wallet(call: CallbackQuery):
    if await check_ban(call.from_user.id, call): return
    balance = get_balance(call.from_user.id)
    text = (
        f"💰 <b>Мой кошелёк</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Текущий баланс: <b>{balance:.2f}₽</b>\n\n"
        f"Минимальное пополнение: {MIN_DEPOSIT}₽\n"
        f"Оплата: карта, СБП"
    )
    await call.message.edit_text(text, reply_markup=wallet_kb(), parse_mode="HTML")


@router.callback_query(F.data == "deposit")
async def show_deposit(call: CallbackQuery):
    await call.message.edit_text(
        f"➕ <b>Пополнение баланса</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Выбери сумму или введи свою:\n\n"
        f"💳 Оплата: карта, СБП, QIWI\n"
        f"⚡ Зачисление: мгновенно",
        reply_markup=deposit_amounts_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("dep_"))
async def process_deposit(call: CallbackQuery, state: FSMContext):
    val = call.data.split("_", 1)[1]
    if val == "custom":
        await state.set_state(States.dep_custom)
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="deposit")]
        ])
        await call.message.edit_text(
            f"✏️ <b>Введи сумму пополнения</b>\n━━━━━━━━━━━━━━━━━━━━\nМинимум: {MIN_DEPOSIT}₽",
            reply_markup=kb, parse_mode="HTML"
        )
        return
    await _show_payment(call, int(val))


@router.message(States.dep_custom)
async def custom_amount(message: Message, state: FSMContext):
    try:
        amount = int(message.text.strip())
        if amount < MIN_DEPOSIT:
            await message.answer(f"❌ Минимум: {MIN_DEPOSIT}₽"); return
        await state.clear()
        payment_url = "https://yookassa.ru/demo"
        await message.answer(
            f"💳 <b>Пополнение на {amount}₽</b>\n━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <i>ЮКасса в режиме настройки</i>",
            reply_markup=payment_kb(payment_url), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введи число (например: 500)")


async def _show_payment(call: CallbackQuery, amount: int):
    payment_url = "https://yookassa.ru/demo"
    text = (
        f"💳 <b>Пополнение на {amount}₽</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"1. Нажми «Перейти к оплате»\n"
        f"2. Оплати удобным способом\n"
        f"3. Нажми «Я оплатил» — баланс пополнится\n\n"
        f"⚠️ <i>ЮКасса в режиме настройки</i>"
    )
    await call.message.edit_text(text, reply_markup=payment_kb(payment_url), parse_mode="HTML")


@router.callback_query(F.data == "check_payment")
async def check_payment(call: CallbackQuery):
    await call.answer("⏳ Проверяем оплату. Баланс пополнится автоматически.", show_alert=True)


@router.callback_query(F.data == "tx_history")
async def tx_history(call: CallbackQuery):
    txs = get_tx_history(call.from_user.id)
    if not txs:
        text = "📋 <b>История транзакций</b>\n━━━━━━━━━━━━━━━━━━━━\nПока нет транзакций"
    else:
        text = "📋 <b>История транзакций</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for tx in txs:
            icon = "➕" if tx["type"] == "deposit" else "➖"
            sign = "+" if tx["type"] == "deposit" else "-"
            text += f"{icon} {sign}{tx['amount']:.0f}₽ — {tx['description']}\n🕐 {tx['created_at'][:16]}\n\n"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Кошелёк", callback_data="wallet")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ─── ПРОФИЛЬ ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "profile")
async def show_profile(call: CallbackQuery):
    user = get_user(call.from_user.id)
    balance = user["balance"] if user else 0
    orders = get_user_orders(call.from_user.id)
    completed = sum(1 for o in orders if o["status"] == "completed")
    refs = count_referrals(call.from_user.id)

    text = (
        f"👤 <b>Мой профиль</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{call.from_user.id}</code>\n"
        f"👤 Имя: {call.from_user.full_name}\n"
        f"📅 Регистрация: {user['created_at'][:10] if user else '—'}\n\n"
        f"💰 Баланс: <b>{balance:.2f}₽</b>\n"
        f"📦 Заказов: <b>{completed}</b>\n"
        f"🔗 Рефералов: <b>{refs}</b>"
    )
    await call.message.edit_text(text, reply_markup=profile_kb(), parse_mode="HTML")


# ─── ЗАКАЗЫ ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_orders")
async def my_orders(call: CallbackQuery):
    orders = get_user_orders(call.from_user.id)
    if not orders:
        text = "📦 <b>Мои заказы</b>\n━━━━━━━━━━━━━━━━━━━━\nЗаказов пока нет. Загляни в каталог!"
        await call.message.edit_text(text, reply_markup=orders_kb(), parse_mode="HTML")
        return

    text = "📦 <b>Мои заказы</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    buttons = []
    for order in orders[:10]:
        prod = PRODUCTS.get(order["product_id"], {})
        prod_name = prod.get("name", order["product_id"])
        emoji = prod.get("emoji", "📦")
        status_map = {"completed": "✅", "pending": "⏳", "cancelled": "❌"}
        status = status_map.get(order["status"], "❓")
        text += f"{status} #{order['id']} {emoji} {prod_name} — {order['price']:.0f}₽ ({order['created_at'][:10]})\n"
        buttons.append([])
        from aiogram.types import InlineKeyboardButton
        buttons[-1].append(InlineKeyboardButton(
            text=f"{status} #{order['id']} {prod_name}",
            callback_data=f"order_{order['id']}"
        ))

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons.append([InlineKeyboardButton(text="🛍 В каталог", callback_data="catalog")])
    buttons.append([InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("order_"))
async def order_detail(call: CallbackQuery):
    order_id = int(call.data.split("_")[1])
    order = get_order(order_id)
    if not order or order["user_id"] != call.from_user.id:
        await call.answer("Заказ не найден", show_alert=True); return

    prod = PRODUCTS.get(order["product_id"], {})
    status_map = {"completed": "✅ Выполнен", "pending": "⏳ В обработке", "cancelled": "❌ Отменён"}
    status = status_map.get(order["status"], "❓")

    text = (
        f"📦 <b>Заказ #{order_id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{prod.get('emoji', '📦')} {prod.get('name', order['product_id'])}\n"
        f"💵 Оплачено: {order['price']:.0f}₽\n"
        f"📊 Статус: {status}\n"
        f"🕐 Дата: {order['created_at'][:16]}\n"
    )
    if order["key_issued"] and order["key_issued"] != "manual_delivery":
        text += f"\n🔑 <b>Ваш аккаунт:</b>\n<code>{order['key_issued']}</code>\n"
    elif order["key_issued"] == "manual_delivery":
        text += f"\n📬 Выдача через менеджера: <b>{MANAGER_USERNAME}</b>\nУкажи заказ <b>#{order_id}</b>\n"

    reviewed = bool(order.get("review"))
    await call.message.edit_text(
        text,
        reply_markup=order_detail_kb(order_id, order["product_id"], reviewed),
        parse_mode="HTML"
    )


# ─── ОТЗЫВЫ ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("reviews_"))
async def show_reviews(call: CallbackQuery):
    pid = call.data.split("_", 1)[1]
    prod = PRODUCTS.get(pid, {})
    reviews = get_product_reviews(pid)
    avg, cnt = get_product_rating(pid)

    if not reviews:
        text = f"⭐ <b>Отзывы: {prod.get('name', pid)}</b>\n━━━━━━━━━━━━━━━━━━━━\nОтзывов пока нет. Будь первым!"
    else:
        text = f"⭐ <b>Отзывы: {prod.get('name', pid)}</b>\nРейтинг: {avg} ⭐ ({cnt} отзывов)\n━━━━━━━━━━━━━━━━━━━━\n"
        for r in reviews:
            stars = "⭐" * r["rating"]
            text += f"{stars}\n{r['text'] or '—'}\n🕐 {r['created_at'][:10]}\n\n"

    await call.message.edit_text(text, reply_markup=reviews_back_kb(pid), parse_mode="HTML")


@router.callback_query(F.data.startswith("leave_review_"))
async def leave_review_start(call: CallbackQuery):
    parts = call.data.split("_")
    order_id = parts[2]
    pid = parts[3]
    prod = PRODUCTS.get(pid, {})
    await call.message.edit_text(
        f"⭐ <b>Оценка: {prod.get('name', pid)}</b>\n━━━━━━━━━━━━━━━━━━━━\nПоставь оценку 👇",
        reply_markup=review_rating_kb(order_id, pid), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rate_"))
async def review_rating(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    order_id, pid, rating = parts[1], parts[2], int(parts[3])
    await state.update_data(review_order=order_id, review_pid=pid, review_rating=rating)
    await state.set_state(States.review_text)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data=f"review_skip_{order_id}_{pid}_{rating}")]
    ])
    await call.message.edit_text(
        f"{'⭐' * rating}\n\n✍️ Напиши текст отзыва (или пропусти):",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(States.review_text)
async def review_text_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    add_review(message.from_user.id, int(data["review_order"]), data["review_pid"],
               data["review_rating"], message.text.strip())
    await message.answer("✅ Спасибо за отзыв!", reply_markup=back_to_menu_kb())


@router.callback_query(F.data.startswith("review_skip_"))
async def review_skip(call: CallbackQuery, state: FSMContext):
    await state.clear()
    parts = call.data.split("_")
    order_id, pid, rating = int(parts[2]), parts[3], int(parts[4])
    add_review(call.from_user.id, order_id, pid, rating, "")
    await call.message.edit_text("✅ Спасибо за оценку!", reply_markup=back_to_menu_kb())


# ─── РЕФЕРАЛЬНАЯ ПРОГРАММА ────────────────────────────────────────────────────

@router.callback_query(F.data == "referral")
async def referral(call: CallbackQuery):
    user = get_user(call.from_user.id)
    refs = count_referrals(call.from_user.id)
    ref_link = f"https://t.me/ASTRAVIKshopBot?start={user['ref_code']}"

    text = (
        f"🔗 <b>Реферальная программа</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Приглашай друзей и получай бонусы!\n\n"
        f"💰 Тебе за каждого друга: <b>{REFERRAL_BONUS}₽</b>\n"
        f"🎁 Другу при регистрации: <b>{REFERRAL_BONUS_NEW}₽</b>\n\n"
        f"👥 Приглашено друзей: <b>{refs}</b>\n"
        f"💵 Заработано: <b>{refs * REFERRAL_BONUS}₽</b>\n\n"
        f"🔗 Твоя ссылка:\n"
        f"<code>{ref_link}</code>"
    )
    await call.message.edit_text(text, reply_markup=referral_kb(ref_link), parse_mode="HTML")


# ─── FAQ ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "faq")
async def faq(call: CallbackQuery):
    text = (
        "❓ <b>Часто задаваемые вопросы</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>❓ Как оплатить?</b>\n"
        "Пополни внутренний кошелёк через ЮКассу (карта, СБП) и купи нужную подписку.\n\n"
        "<b>❓ Как получить подписку?</b>\n"
        "После оплаты — аккаунт выдаётся автоматически (кроме Claude, там через менеджера).\n\n"
        "<b>❓ Что делать если аккаунт не работает?</b>\n"
        f"Напиши в поддержку: {MANAGER_USERNAME} с номером заказа.\n\n"
        "<b>❓ Безопасно ли?</b>\n"
        "Да. Оплата через ЮКассу — официальный платёжный сервис.\n\n"
        "<b>❓ Есть ли скидки?</b>\n"
        "Да! Используй промокоды при покупке. Также есть реферальная программа — приглашай друзей и получай бонусы.\n\n"
        "<b>❓ Какой срок действия подписок?</b>\n"
        "Указан в описании каждого товара. Обычно 1 месяц, Gemini — 12 месяцев."
    )
    await call.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")


# ─── ПОДДЕРЖКА / О НАС ────────────────────────────────────────────────────────

@router.callback_query(F.data == "support")
async def support(call: CallbackQuery):
    text = (
        f"💬 <b>Поддержка</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Менеджер: <b>{MANAGER_USERNAME}</b>\n"
        f"⏰ Время работы: 09:00 — 23:00 МСК\n\n"
        f"При обращении укажи:\n"
        f"• Номер заказа\n"
        f"• Описание проблемы"
    )
    await call.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "about")
async def about(call: CallbackQuery):
    text = (
        "ℹ️ <b>ASTRAVIK SHOP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Официальный магазин AI-подписок\n\n"
        "✅ Только проверенные аккаунты\n"
        "⚡ Автовыдача сразу после оплаты\n"
        "🔒 Безопасная оплата через ЮКассу\n"
        "🏷 Промокоды и скидки\n"
        "🔗 Реферальная программа\n"
        "💬 Поддержка 24/7\n\n"
        "🌐 <i>ASTRAVIK — технологии будущего</i>"
    )
    await call.message.edit_text(text, reply_markup=back_to_menu_kb(), parse_mode="HTML")