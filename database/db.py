import sqlite3

# =========================
# 连接数据库
# =========================
def get_connection():

    conn = sqlite3.connect("bills.db")

    conn.row_factory = sqlite3.Row

    return conn


# =========================
# 初始化数据库
# =========================
def init_db():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bills (

            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            title TEXT,
            money REAL,
            category TEXT

        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (

            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT

        )
        """
    )

    conn.commit()
    conn.close()