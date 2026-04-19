import sqlite3
import os
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "shop.db")
USER_DEFAULTS = {
    "balance": 0.0,
    "ref_code": None,
    "referred_by": None,
    "is_banned": 0,
}
ORDER_DEFAULTS = {
    "status": "pending",
    "key_issued": None,
    "review": 0,
}


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_row(row, defaults=None):
    if row is None:
        return None
    data = dict(row)
    if defaults:
        for key, value in defaults.items():
            data.setdefault(key, value)
    return data


def _get_columns(conn, table_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_column(conn, table_name, column_sql):
    column_name = column_sql.split()[0]
    if column_name not in _get_columns(conn, table_name):
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}")


def _generate_ref_code(conn):
    while True:
        code = secrets.token_hex(4).upper()
        exists = conn.execute("SELECT 1 FROM users WHERE ref_code = ?", (code,)).fetchone()
        if not exists:
            return code


def _migrate_users_table(conn):
    _ensure_column(conn, "users", "ref_code TEXT")
    _ensure_column(conn, "users", "referred_by INTEGER")
    _ensure_column(conn, "users", "is_banned INTEGER DEFAULT 0")

    conn.execute("UPDATE users SET is_banned = COALESCE(is_banned, 0)")

    missing_ref_codes = conn.execute(
        "SELECT user_id FROM users WHERE ref_code IS NULL OR TRIM(ref_code) = ''"
    ).fetchall()
    for row in missing_ref_codes:
        conn.execute(
            "UPDATE users SET ref_code = ? WHERE user_id = ?",
            (_generate_ref_code(conn), row["user_id"]),
        )

    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_ref_code ON users(ref_code)")


def _migrate_orders_table(conn):
    _ensure_column(conn, "orders", "review INTEGER DEFAULT 0")
    conn.execute("UPDATE orders SET review = COALESCE(review, 0)")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        full_name   TEXT,
        balance     REAL DEFAULT 0,
        ref_code    TEXT UNIQUE,
        referred_by INTEGER,
        is_banned   INTEGER DEFAULT 0,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        type        TEXT,
        amount      REAL,
        description TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        product_id  TEXT,
        price       REAL,
        status      TEXT DEFAULT 'pending',
        key_issued  TEXT,
        review      INTEGER,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS keys (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id  TEXT,
        key_value   TEXT,
        used        INTEGER DEFAULT 0,
        used_by     INTEGER,
        used_at     TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS promocodes (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT UNIQUE,
        discount    INTEGER,
        type        TEXT DEFAULT 'percent',
        uses_left   INTEGER DEFAULT 1,
        uses_total  INTEGER DEFAULT 0,
        active      INTEGER DEFAULT 1,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        order_id    INTEGER,
        product_id  TEXT,
        rating      INTEGER,
        text        TEXT,
        created_at  TEXT DEFAULT (datetime('now'))
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS product_settings (
        product_id  TEXT PRIMARY KEY,
        active      INTEGER DEFAULT 1
    )""")

    _migrate_users_table(conn)
    _migrate_orders_table(conn)

    conn.commit()
    conn.close()


# ─── USERS ────────────────────────────────────────────────────────────────────

def get_or_create_user(user_id, username=None, full_name=None, ref_code=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        my_ref = _generate_ref_code(conn)
        referrer_id = None
        if ref_code:
            c.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
            referrer = c.fetchone()
            if referrer and referrer["user_id"] != user_id:
                referrer_id = referrer["user_id"]
        c.execute(
            "INSERT INTO users (user_id, username, full_name, ref_code, referred_by) VALUES (?,?,?,?,?)",
            (user_id, username, full_name, my_ref, referrer_id)
        )
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
    conn.close()
    return _normalize_row(user, USER_DEFAULTS)


def get_user(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return _normalize_row(row, USER_DEFAULTS)


def get_user_by_ref(ref_code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE ref_code = ?", (ref_code,))
    row = c.fetchone()
    conn.close()
    return _normalize_row(row, USER_DEFAULTS)


def get_user_by_username(username):
    username = username.lstrip("@")
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return _normalize_row(row, USER_DEFAULTS)


def get_balance(user_id):
    user = get_user(user_id)
    return user["balance"] if user else 0.0


def add_balance(user_id, amount, description="Пополнение"):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    c.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?,?,?,?)",
              (user_id, "deposit", amount, description))
    conn.commit()
    conn.close()


def deduct_balance(user_id, amount, description="Покупка"):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    c.execute("INSERT INTO transactions (user_id, type, amount, description) VALUES (?,?,?,?)",
              (user_id, "purchase", amount, description))
    conn.commit()
    conn.close()


def ban_user(user_id, banned=True):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (1 if banned else 0, user_id))
    conn.commit()
    conn.close()


def is_banned(user_id):
    user = get_user(user_id)
    return bool(user and user.get("is_banned", 0))


def get_all_users():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM users ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [_normalize_row(r, USER_DEFAULTS) for r in rows]


def count_referrals(user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


def get_tx_history(user_id, limit=15):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
              (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── ORDERS ───────────────────────────────────────────────────────────────────

def create_order(user_id, product_id, price):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, product_id, price) VALUES (?,?,?)",
              (user_id, product_id, price))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id


def complete_order(order_id, key_issued=None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE orders SET status='completed', key_issued=? WHERE id=?", (key_issued, order_id))
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = c.fetchone()
    conn.close()
    return _normalize_row(row, ORDER_DEFAULTS)


def get_user_orders(user_id, limit=20):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user_id, limit))
    rows = c.fetchall()
    conn.close()
    return [_normalize_row(r, ORDER_DEFAULTS) for r in rows]


def get_all_orders(limit=50):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    return [_normalize_row(r, ORDER_DEFAULTS) for r in rows]


# ─── KEYS ─────────────────────────────────────────────────────────────────────

def add_keys(product_id, keys):
    conn = get_conn()
    c = conn.cursor()
    for k in keys:
        k = k.strip()
        if k:
            c.execute("INSERT INTO keys (product_id, key_value) VALUES (?,?)", (product_id, k))
    conn.commit()
    conn.close()


def get_available_key(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM keys WHERE product_id=? AND used=0 LIMIT 1", (product_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def mark_key_used(key_id, user_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE keys SET used=1, used_by=?, used_at=datetime('now') WHERE id=?", (user_id, key_id))
    conn.commit()
    conn.close()


def count_keys(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM keys WHERE product_id=? AND used=0", (product_id,))
    avail = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM keys WHERE product_id=? AND used=1", (product_id,))
    used = c.fetchone()[0]
    conn.close()
    return {"available": avail, "used": used}


# ─── PROMOCODES ───────────────────────────────────────────────────────────────

def create_promo(code, discount, promo_type="percent", uses=1):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO promocodes (code, discount, type, uses_left) VALUES (?,?,?,?)",
                  (code.upper(), discount, promo_type, uses))
        conn.commit()
        result = True
    except:
        result = False
    conn.close()
    return result


def use_promo(code):
    """Returns promo dict if valid, else None"""
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM promocodes WHERE code=? AND active=1 AND uses_left > 0", (code.upper(),))
    row = c.fetchone()
    if row:
        c.execute("UPDATE promocodes SET uses_left=uses_left-1, uses_total=uses_total+1 WHERE code=?",
                  (code.upper(),))
        c.execute("UPDATE promocodes SET active=0 WHERE code=? AND uses_left <= 0", (code.upper(),))
        conn.commit()
        conn.close()
        return dict(row)
    conn.close()
    return None


def get_all_promos():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM promocodes ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_promo(code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM promocodes WHERE code=?", (code.upper(),))
    conn.commit()
    conn.close()


# ─── REVIEWS ──────────────────────────────────────────────────────────────────

def add_review(user_id, order_id, product_id, rating, text=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO reviews (user_id, order_id, product_id, rating, text) VALUES (?,?,?,?,?)",
              (user_id, order_id, product_id, rating, text))
    c.execute("UPDATE orders SET review=1 WHERE id=?", (order_id,))
    conn.commit()
    conn.close()


def get_product_reviews(product_id, limit=10):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM reviews WHERE product_id=? ORDER BY created_at DESC LIMIT ?",
              (product_id, limit))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_rating(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT AVG(rating), COUNT(*) FROM reviews WHERE product_id=?", (product_id,))
    row = c.fetchone()
    conn.close()
    avg = round(row[0] or 0, 1)
    count = row[1]
    return avg, count


# ─── PRODUCT SETTINGS ─────────────────────────────────────────────────────────

def toggle_product(product_id, active):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO product_settings (product_id, active) VALUES (?,?)",
              (product_id, 1 if active else 0))
    conn.commit()
    conn.close()


def get_product_active(product_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT active FROM product_settings WHERE product_id=?", (product_id,))
    row = c.fetchone()
    conn.close()
    if row is None:
        return True  # default active
    return bool(row[0])


# ─── STATS ────────────────────────────────────────────────────────────────────

def get_stats():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
    new_today = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='completed'")
    total_orders = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM orders WHERE status='completed' AND date(created_at)=date('now')")
    orders_today = c.fetchone()[0]
    c.execute("SELECT SUM(amount) FROM transactions WHERE type='deposit'")
    total_deposits = c.fetchone()[0] or 0
    c.execute("SELECT SUM(price) FROM orders WHERE status='completed'")
    total_revenue = c.fetchone()[0] or 0
    c.execute("SELECT SUM(price) FROM orders WHERE status='completed' AND date(created_at)=date('now')")
    revenue_today = c.fetchone()[0] or 0
    conn.close()
    return {
        "total_users": total_users, "new_today": new_today,
        "total_orders": total_orders, "orders_today": orders_today,
        "total_deposits": total_deposits,
        "total_revenue": total_revenue, "revenue_today": revenue_today,
    }
