from datetime import date

from database.db import get_connection


# =========================
# AI自动分类
# =========================
def get_category(title):

    # 分类关键词库
    category_map = {

        "餐饮": [
            "奶茶",
            "咖啡",
            "火锅",
            "米饭",
            "汉堡",
            "外卖",
            "烧烤",
            "早餐",
            "午餐",
            "晚餐"
        ],

        "交通": [
            "地铁",
            "公交",
            "打车",
            "滴滴",
            "高铁",
            "火车",
            "飞机",
            "加油"
        ],

        "购物": [
            "淘宝",
            "京东",
            "拼多多",
            "衣服",
            "鞋子",
            "手机",
            "电脑"
        ],

        "娱乐": [
            "电影",
            "游戏",
            "KTV",
            "旅游",
            "景区"
        ],

        "学习": [
            "书",
            "课程",
            "培训",
            "学费"
        ]
    }

    # 转小写
    title = title.lower()

    # 遍历分类
    for category, keywords in category_map.items():

        # 遍历关键词
        for keyword in keywords:

            if keyword.lower() in title:

                return category

    return "其他"


# =========================
# 添加账单
# =========================
def add_bill(user_id):

    date = input("请输入日期(2025-05-17)：")

    title = input("请输入账单标题：")

    money = float(input("请输入金额："))

    # AI自动分类
    category = get_category(title)

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO bills
        (date, title, money, category, user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            date,
            title,
            money,
            category,
            user_id
        )
    )

    conn.commit()

    conn.close()

    print("添加成功")
    print("自动分类：", category)


# =========================
# 查询账单
# =========================
def query_bills(user_id):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM bills WHERE user_id = ?",
        (user_id,)
    )

    bills = cursor.fetchall()

    conn.close()

    if len(bills) == 0:

        print("暂无账单")

        return

    print("\n===== 我的账单 =====")

    for bill in bills:

        print(bill)


# =========================
# 删除账单
# =========================
def delete_bill(user_id):

    bill_id = input("请输入要删除的账单ID：")

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM bills
        WHERE id = ?
        AND user_id = ?
        """,
        (
            bill_id,
            user_id
        )
    )

    conn.commit()

    conn.close()

    print("删除成功")


# =========================
# 搜索账单
# =========================
def search_bill(user_id):

    keyword = input("请输入搜索关键词：")

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM bills
        WHERE title LIKE ?
        AND user_id = ?
        """,
        (
            f"%{keyword}%",
            user_id
        )
    )

    bills = cursor.fetchall()

    conn.close()

    if len(bills) == 0:

        print("未找到相关账单")

        return

    for bill in bills:

        print(bill)


# =========================
# 修改账单
# =========================
def update_bill(user_id):

    bill_id = input("请输入要修改的账单ID：")

    new_title = input("请输入新标题：")

    new_money = float(input("请输入新金额："))

    # 自动重新分类
    new_category = get_category(new_title)

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE bills
        SET title = ?, money = ?, category = ?
        WHERE id = ?
        AND user_id = ?
        """,
        (
            new_title,
            new_money,
            new_category,
            bill_id,
            user_id
        )
    )

    conn.commit()

    conn.close()

    print("修改成功")


# =========================
# 清空账单
# =========================
def clear_bills(user_id):

    confirm = input("确定清空所有账单？(y/n)：")

    if confirm.lower() != "y":

        print("已取消")

        return

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM bills WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()

    conn.close()

    print("已清空所有账单")