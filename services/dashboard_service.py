from database.db import get_connection


# =========================
# 获取总消费
# =========================
def get_total_expense(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT SUM(money)
        FROM bills
        WHERE user_id = ?
        """,
        (user_id,)
    )

    total = cursor.fetchone()[0]

    conn.close()

    return total or 0


# =========================
# 获取账单数量
# =========================
def get_bill_count(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM bills
        WHERE user_id = ?
        """,
        (user_id,)
    )

    count = cursor.fetchone()[0]

    conn.close()

    return count


# =========================
# 获取最近账单
# =========================
def get_recent_bills(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM bills
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 5
        """,
        (user_id,)
    )

    bills = cursor.fetchall()

    conn.close()

    return bills


# =========================
# 分类统计
# =========================
def get_category_statistics(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT category, SUM(money)
        FROM bills
        WHERE user_id = ?
        GROUP BY category
        """,
        (user_id,)
    )

    data = cursor.fetchall()

    conn.close()

    return data