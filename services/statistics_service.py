from database.db import get_connection


# =====================
# 消费统计
# =====================
def statistics_bills(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT money, category
        FROM bills
        WHERE user_id = ?
        """,
        (user_id,)
    )

    bills = cursor.fetchall()

    conn.close()

    if len(bills) == 0:

        print("暂无账单数据")
        return

    total_expense = 0

    category_data = {}

    for bill in bills:

        money = bill[0]
        category = bill[1]

        total_expense += money

        if category in category_data:

            category_data[category] += money

        else:

            category_data[category] = money

    print("\n===== 消费统计 =====")

    print(f"总消费: {total_expense:.2f} 元")

    print("\n===== 分类统计 =====")

    for category, money in category_data.items():

        percent = (money / total_expense) * 100

        print(
            f"{category}: "
            f"{money:.2f} 元 "
            f"占比 {percent:.2f}%"
        )


# =====================
# 金额排序
# =====================
def sort_bills_by_money(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT date, title, money, category
        FROM bills
        WHERE user_id = ?
        ORDER BY money DESC
        """,
        (user_id,)
    )

    bills = cursor.fetchall()

    conn.close()

    if len(bills) == 0:

        print("暂无账单")
        return

    print("\n===== 金额排序 =====")

    for bill in bills:

        print(
            bill[0],
            bill[1],
            f"{bill[2]:.2f}",
            bill[3]
        )


# =====================
# 最高消费
# =====================
def max_expense_bill(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT date, title, money, category
        FROM bills
        WHERE user_id = ?
        ORDER BY money DESC
        LIMIT 1
        """,
        (user_id,)
    )

    bill = cursor.fetchone()

    conn.close()

    if not bill:

        print("暂无账单")
        return

    print("\n===== 最高消费 =====")

    print("日期：", bill[0])
    print("消费项目：", bill[1])
    print("金额：", f"{bill[2]:.2f}")
    print("分类：", bill[3])


# =====================
# 月度统计
# =====================
def month_statistics(user_id):

    month = input("请输入月份(例如2026-05)：")

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT date, title, money, category
        FROM bills
        WHERE user_id = ?
        AND date LIKE ?
        """,
        (
            user_id,
            f"{month}%"
        )
    )

    bills = cursor.fetchall()

    conn.close()

    if len(bills) == 0:

        print("该月份暂无账单")
        return

    total = 0

    print(f"\n===== {month} 月账单 =====")

    for bill in bills:

        total += bill[2]

        print(
            bill[0],
            bill[1],
            f"{bill[2]:.2f}",
            bill[3]
        )

    print(f"\n{month} 总消费: {total:.2f}")