from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_ID, PRODUCTS
from database.db import (
    get_stats, get_all_users, get_all_orders,
    add_keys, count_keys, add_balance, get_user,
    get_user_by_username, ban_user, is_banned,
    create_promo, get_all_promos, delete_promo,
    toggle_product, get_product_active
)
from keyboards.kb import (
    admin_panel_kb, admin_products_kb, admin_back_kb,
    admin_promos_kb, admin_toggle_products_kb, ban_user_kb
)

router = Router()


def admin_only(func):
    from functools import wraps
    @wraps(func)
    async def wrapper(obj, *args, **kwargs):
        uid = obj.from_user.id if hasattr(obj, 'from_user') else None
        if uid != ADMIN_ID:
            if isinstance(obj, CallbackQuery):
                await obj.answer("❌ Нет доступа", show_alert=True)
            else:
                await obj.answer("❌ Нет доступа")
            return
        return await func(obj, *args, **kwargs)
    return wrapper


class AdminState(StatesGroup):
    keys_product    = State()
    keys_input      = State()
    bal_user        = State()
    bal_amount      = State()
    bal_user_id     = State()   # прямое пополнение по ID из инлайн
    broadcast       = State()
    find_user       = State()
    ban_input       = State()
    promo_code      = State()
    promo_discount  = State()
    promo_uses      = State()
    promo_delete    = State()


# ─── ВХОД В ПАНЕЛЬ ────────────────────────────────────────────────────────────

@router.message(Command("admin"))
@admin_only
async def admin_cmd(message: Message):
    await message.answer(
        "🔐 <b>Панель администратора</b>\n━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_panel_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data == "admin")
@admin_only
async def admin_panel(call: CallbackQuery):
    await call.message.edit_text(
        "🔐 <b>Панель администратора</b>\n━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_panel_kb(), parse_mode="HTML"
    )


# ─── СТАТИСТИКА ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_stats")
@admin_only
async def adm_stats(call: CallbackQuery):
    s = get_stats()
    text = (
        f"📊 <b>Статистика магазина</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Всего пользователей: <b>{s['total_users']}</b> (+{s['new_today']} сегодня)\n"
        f"📦 Выполнено заказов: <b>{s['total_orders']}</b> (+{s['orders_today']} сегодня)\n"
        f"💰 Всего пополнений: <b>{s['total_deposits']:.2f}₽</b>\n"
        f"💵 Выручка всего: <b>{s['total_revenue']:.2f}₽</b>\n"
        f"📅 Выручка сегодня: <b>{s['revenue_today']:.2f}₽</b>"
    )
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")


# ─── ПОЛЬЗОВАТЕЛИ ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_users")
@admin_only
async def adm_users(call: CallbackQuery):
    users = get_all_users()
    text = f"👥 <b>Пользователи ({len(users)})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for u in users[:25]:
        uname = f"@{u['username']}" if u["username"] else f"ID:{u['user_id']}"
        ban_icon = " 🚫" if u["is_banned"] else ""
        text += f"• {uname} — 💰{u['balance']:.0f}₽{ban_icon} ({u['created_at'][:10]})\n"
    if len(users) > 25:
        text += f"\n... и ещё {len(users) - 25}"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")


# ─── НАЙТИ ПОЛЬЗОВАТЕЛЯ ───────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_find_user")
@admin_only
async def adm_find_user_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.find_user)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]])
    await call.message.edit_text(
        "🔍 <b>Найти пользователя</b>\n━━━━━━━━━━━━━━━━━━━━\nВведи ID или @username:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.find_user)
async def adm_find_user_exec(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    query = message.text.strip()
    user = None
    if query.startswith("@"):
        user = get_user_by_username(query)
    else:
        try:
            user = get_user(int(query))
        except ValueError:
            user = get_user_by_username(query)

    if not user:
        await message.answer("❌ Пользователь не найден", reply_markup=admin_back_kb())
        return

    banned = bool(user["is_banned"])
    text = (
        f"👤 <b>Пользователь</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 ID: <code>{user['user_id']}</code>\n"
        f"👤 Имя: {user['full_name'] or '—'}\n"
        f"📱 Username: @{user['username'] or '—'}\n"
        f"💰 Баланс: <b>{user['balance']:.2f}₽</b>\n"
        f"🔗 Реф. код: <code>{user['ref_code']}</code>\n"
        f"📅 Регистрация: {user['created_at'][:10]}\n"
        f"🚫 Забанен: {'Да' if banned else 'Нет'}"
    )
    await message.answer(text, reply_markup=ban_user_kb(user["user_id"], banned), parse_mode="HTML")


# ─── БАН/РАЗБАН ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_bans")
@admin_only
async def adm_bans(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.ban_input)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]])
    await call.message.edit_text(
        "🚫 <b>Управление банами</b>\n━━━━━━━━━━━━━━━━━━━━\nВведи ID пользователя для бана/разбана:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.ban_input)
async def adm_ban_exec(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    try:
        uid = int(message.text.strip())
        user = get_user(uid)
        if not user:
            await message.answer("❌ Пользователь не найден"); return
        banned = bool(user["is_banned"])
        await message.answer(
            f"👤 {user['full_name'] or uid}\n💰 {user['balance']:.2f}₽\n🚫 Забанен: {'Да' if banned else 'Нет'}",
            reply_markup=ban_user_kb(uid, banned), parse_mode="HTML"
        )
    except ValueError:
        await message.answer("❌ Введи числовой ID")


@router.callback_query(F.data.startswith("adm_ban_"))
@admin_only
async def do_ban(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    ban_user(uid, True)
    try:
        await call.bot.send_message(uid, "🚫 Ваш аккаунт заблокирован. Обратитесь в поддержку.")
    except: pass
    await call.answer("✅ Пользователь забанен", show_alert=True)
    await call.message.edit_text("🚫 Пользователь заблокирован.", reply_markup=admin_back_kb())


@router.callback_query(F.data.startswith("adm_unban_"))
@admin_only
async def do_unban(call: CallbackQuery):
    uid = int(call.data.split("_")[2])
    ban_user(uid, False)
    try:
        await call.bot.send_message(uid, "✅ Ваш аккаунт разблокирован. Добро пожаловать обратно!")
    except: pass
    await call.answer("✅ Пользователь разбанен", show_alert=True)
    await call.message.edit_text("✅ Пользователь разблокирован.", reply_markup=admin_back_kb())


# ─── ДОБАВИТЬ КЛЮЧИ ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_add_keys")
@admin_only
async def adm_add_keys(call: CallbackQuery):
    await call.message.edit_text(
        "🔑 <b>Добавить ключи</b>\n━━━━━━━━━━━━━━━━━━━━\nВыбери продукт:",
        reply_markup=admin_products_kb(for_keys=True), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_keys_"))
@admin_only
async def adm_keys_product(call: CallbackQuery, state: FSMContext):
    pid = call.data.split("adm_keys_")[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        await call.answer("Продукт не найден", show_alert=True); return

    stock = count_keys(pid)
    await state.update_data(target_product=pid)
    await state.set_state(AdminState.keys_input)

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_add_keys")]])
    await call.message.edit_text(
        f"🔑 <b>Добавить ключи: {prod['name']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"В наличии: {stock['available']} шт. | Использовано: {stock['used']} шт.\n\n"
        f"Отправь ключи — каждый с новой строки:\n"
        f"<code>login1:pass1\nlogin2:pass2</code>",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.keys_input)
async def receive_keys(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    pid = data.get("target_product")
    await state.clear()

    keys_list = [k.strip() for k in message.text.strip().split("\n") if k.strip()]
    if not keys_list:
        await message.answer("❌ Не нашёл ни одного ключа"); return

    add_keys(pid, keys_list)
    prod = PRODUCTS.get(pid, {})
    stock = count_keys(pid)
    await message.answer(
        f"✅ <b>Добавлено!</b>\n{prod.get('name', pid)}\n"
        f"➕ Добавлено: {len(keys_list)} шт.\n📊 В наличии: {stock['available']} шт.",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )


# ─── ОСТАТКИ КЛЮЧЕЙ ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_keys_stock")
@admin_only
async def adm_keys_stock(call: CallbackQuery):
    text = "📦 <b>Остатки ключей</b>\n━━━━━━━━━━━━━━━━━━━━\n"
    for pid, prod in PRODUCTS.items():
        if prod["manual"]:
            text += f"📬 {prod['emoji']} {prod['name']}: ручная выдача\n"
            continue
        stock = count_keys(pid)
        avail = stock["available"]
        icon = "✅" if avail > 5 else ("⚠️" if avail > 0 else "❌")
        text += f"{icon} {prod['emoji']} {prod['name']}: {avail} шт.\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")


# ─── ПОСЛЕДНИЕ ЗАКАЗЫ ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_orders")
@admin_only
async def adm_orders(call: CallbackQuery):
    orders = get_all_orders(25)
    if not orders:
        text = "📋 <b>Заказы</b>\n━━━━━━━━━━━━━━━━━━━━\nЗаказов пока нет"
    else:
        text = f"📋 <b>Последние заказы ({len(orders)})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for o in orders:
            prod = PRODUCTS.get(o["product_id"], {})
            st = {"completed": "✅", "pending": "⏳", "cancelled": "❌"}.get(o["status"], "❓")
            text += f"{st} #{o['id']} | {prod.get('name', o['product_id'])} | {o['price']:.0f}₽ | user:{o['user_id']} | {o['created_at'][:10]}\n"
    await call.message.edit_text(text, reply_markup=admin_back_kb(), parse_mode="HTML")


# ─── ПОПОЛНИТЬ БАЛАНС ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_add_balance")
@admin_only
async def adm_add_balance_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.bal_user)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]])
    await call.message.edit_text(
        "💰 <b>Пополнить баланс</b>\n━━━━━━━━━━━━━━━━━━━━\nВведи ID пользователя:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_bal_"))
@admin_only
async def adm_bal_from_user(call: CallbackQuery, state: FSMContext):
    uid = int(call.data.split("_")[2])
    await state.update_data(target_user=uid)
    await state.set_state(AdminState.bal_amount)
    user = get_user(uid)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]])
    await call.message.edit_text(
        f"💰 Пополнить баланс {user['full_name'] or uid}\nСейчас: {user['balance']:.2f}₽\n\nВведи сумму:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.bal_user)
async def adm_balance_user(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        uid = int(message.text.strip())
        user = get_user(uid)
        if not user:
            await message.answer("❌ Пользователь не найден"); return
        await state.update_data(target_user=uid)
        await state.set_state(AdminState.bal_amount)
        await message.answer(
            f"✅ {user['full_name'] or uid}\nБаланс: {user['balance']:.2f}₽\n\nВведи сумму пополнения:"
        )
    except ValueError:
        await message.answer("❌ Введи числовой ID")


@router.message(AdminState.bal_amount)
async def adm_balance_amount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        amount = float(message.text.strip())
        data = await state.get_data()
        uid = data["target_user"]
        await state.clear()
        add_balance(uid, amount, "Пополнение администратором")
        user = get_user(uid)
        await message.answer(
            f"✅ Баланс пополнен!\n👤 {uid}\n➕ {amount:.2f}₽\n💰 Новый баланс: {user['balance']:.2f}₽",
            reply_markup=admin_back_kb(), parse_mode="HTML"
        )
        try:
            await message.bot.send_message(
                uid,
                f"💰 <b>Баланс пополнен администратором</b>\n➕ {amount:.2f}₽\n💵 Баланс: {user['balance']:.2f}₽",
                parse_mode="HTML"
            )
        except: pass
    except ValueError:
        await message.answer("❌ Введи число")


# ─── ТОВАРЫ ВКЛ/ВЫКЛ ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_toggle_products")
@admin_only
async def adm_toggle_products(call: CallbackQuery):
    await call.message.edit_text(
        "🔧 <b>Включить / выключить товары</b>\n━━━━━━━━━━━━━━━━━━━━\nНажми на товар чтобы переключить:",
        reply_markup=admin_toggle_products_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("adm_tgl_"))
@admin_only
async def adm_toggle_product(call: CallbackQuery):
    pid = call.data.split("adm_tgl_")[1]
    prod = PRODUCTS.get(pid)
    if not prod:
        await call.answer("Продукт не найден", show_alert=True); return
    current = get_product_active(pid)
    toggle_product(pid, not current)
    status = "включён ✅" if not current else "выключен 🔴"
    await call.answer(f"{prod['name']} {status}", show_alert=True)
    await call.message.edit_text(
        "🔧 <b>Включить / выключить товары</b>\n━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_toggle_products_kb(), parse_mode="HTML"
    )


# ─── ПРОМОКОДЫ ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_promos")
@admin_only
async def adm_promos(call: CallbackQuery):
    await call.message.edit_text(
        "🏷 <b>Управление промокодами</b>\n━━━━━━━━━━━━━━━━━━━━",
        reply_markup=admin_promos_kb(), parse_mode="HTML"
    )


@router.callback_query(F.data == "adm_promo_list")
@admin_only
async def adm_promo_list(call: CallbackQuery):
    promos = get_all_promos()
    if not promos:
        text = "🏷 <b>Промокоды</b>\n━━━━━━━━━━━━━━━━━━━━\nПромокодов нет"
    else:
        text = f"🏷 <b>Промокоды ({len(promos)})</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        for p in promos:
            active = "✅" if p["active"] else "🔴"
            type_str = "%" if p["type"] == "percent" else "₽"
            text += (
                f"{active} <code>{p['code']}</code> — {p['discount']}{type_str}\n"
                f"   Осталось: {p['uses_left']} | Использовано: {p['uses_total']}\n\n"
            )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="adm_promos")]])
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "adm_promo_create")
@admin_only
async def adm_promo_create_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.promo_code)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_promos")]])
    await call.message.edit_text(
        "🏷 <b>Создать промокод</b>\n━━━━━━━━━━━━━━━━━━━━\nВведи код (например: SALE20):",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.promo_code)
async def adm_promo_code(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(new_promo_code=message.text.strip().upper())
    await state.set_state(AdminState.promo_discount)
    await message.answer(
        "Введи скидку:\n• Число = проценты (например: 20 = скидка 20%)\n• Число₽ = рубли (например: 500₽ = скидка 500₽)"
    )


@router.message(AdminState.promo_discount)
async def adm_promo_discount(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.strip()
    promo_type = "fixed" if text.endswith("₽") else "percent"
    try:
        discount = int(text.rstrip("₽"))
        await state.update_data(new_discount=discount, new_type=promo_type)
        await state.set_state(AdminState.promo_uses)
        await message.answer("Сколько раз можно использовать? (введи число, например: 1 или 100)")
    except ValueError:
        await message.answer("❌ Введи число (например: 20 или 500₽)")


@router.message(AdminState.promo_uses)
async def adm_promo_uses(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    try:
        uses = int(message.text.strip())
        data = await state.get_data()
        await state.clear()
        ok = create_promo(data["new_promo_code"], data["new_discount"], data["new_type"], uses)
        if ok:
            type_str = "%" if data["new_type"] == "percent" else "₽"
            await message.answer(
                f"✅ <b>Промокод создан!</b>\n"
                f"Код: <code>{data['new_promo_code']}</code>\n"
                f"Скидка: {data['new_discount']}{type_str}\n"
                f"Использований: {uses}",
                reply_markup=admin_back_kb(), parse_mode="HTML"
            )
        else:
            await message.answer("❌ Такой промокод уже существует", reply_markup=admin_back_kb())
    except ValueError:
        await message.answer("❌ Введи число")


@router.callback_query(F.data == "adm_promo_delete")
@admin_only
async def adm_promo_delete_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.promo_delete)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="adm_promos")]])
    await call.message.edit_text(
        "🗑 <b>Удалить промокод</b>\n━━━━━━━━━━━━━━━━━━━━\nВведи код для удаления:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.promo_delete)
async def adm_promo_delete_exec(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    code = message.text.strip().upper()
    delete_promo(code)
    await message.answer(f"✅ Промокод <code>{code}</code> удалён", reply_markup=admin_back_kb(), parse_mode="HTML")


# ─── РАССЫЛКА ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
@admin_only
async def adm_broadcast_start(call: CallbackQuery, state: FSMContext):
    await state.set_state(AdminState.broadcast)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin")]])
    await call.message.edit_text(
        "📢 <b>Рассылка</b>\n━━━━━━━━━━━━━━━━━━━━\nНапиши сообщение для всех пользователей:",
        reply_markup=kb, parse_mode="HTML"
    )


@router.message(AdminState.broadcast)
async def adm_broadcast_send(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    users = get_all_users()
    sent = failed = 0
    for user in users:
        try:
            await message.bot.send_message(
                user["user_id"],
                f"📢 <b>ASTRAVIK SHOP</b>\n━━━━━━━━━━━━━━━━━━━━\n{message.text}",
                parse_mode="HTML"
            )
            sent += 1
        except:
            failed += 1
    await message.answer(
        f"✅ Рассылка завершена!\n📤 Отправлено: {sent}\n❌ Не доставлено: {failed}",
        reply_markup=admin_back_kb(), parse_mode="HTML"
    )