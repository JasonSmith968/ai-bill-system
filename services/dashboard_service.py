from collections import defaultdict

from database.db import get_connection


# =========================
# 获取账单列表
# =========================
def build_bill_list(
    user_id,
    keyword="",
    category="",
    page=1,
    per_page=5
):

    conn = get_connection()

    cursor = conn.cursor()

    sql = """
        SELECT *
        FROM bills
        WHERE user_id = ?
    """

    params = [user_id]

    # 搜索
    if keyword:

        sql += " AND title LIKE ? "

        params.append(f"%{keyword}%")

    # 分类
    if category:

        sql += " AND category = ? "

        params.append(category)

    sql += " ORDER BY date DESC "

    # 分页
    offset = (page - 1) * per_page

    sql += " LIMIT ? OFFSET ? "

    params.extend([per_page, offset])

    cursor.execute(sql, params)

    bills = cursor.fetchall()

    conn.close()

    return bills


# =========================
# 获取总数量
# =========================
def get_bill_count(
    user_id,
    keyword="",
    category=""
):

    conn = get_connection()

    cursor = conn.cursor()

    sql = """
        SELECT COUNT(*)
        FROM bills
        WHERE user_id = ?
    """

    params = [user_id]

    if keyword:

        sql += " AND title LIKE ? "

        params.append(f"%{keyword}%")

    if category:

        sql += " AND category = ? "

        params.append(category)

    cursor.execute(sql, params)

    total_count = cursor.fetchone()[0]

    conn.close()

    return total_count


# =========================
# 计算总金额
# =========================
def calculate_total(bills):

    total = 0

    for bill in bills:

        total += bill["money"]

    return total


# =========================
# 分类统计
# =========================
def calculate_category_total(bills):

    category_map = defaultdict(float)

    for bill in bills:

        category_map[bill["category"]] += bill["money"]

    return list(category_map.items())


# =========================
# 图表数据
# =========================
def build_chart_data(category_data):

    labels = []

    values = []

    for item in category_data:

        labels.append(item[0])

        values.append(item[1])

    return labels, values


# =========================
# 趋势图数据
# =========================
def build_trend_data(bills):

    trend_map = defaultdict(float)

    for bill in bills:

        trend_map[bill["date"]] += bill["money"]

    labels = list(trend_map.keys())

    values = list(trend_map.values())

    return labels, values


# =========================
# AI分析
# =========================
def build_ai_analysis(bills, total):

    ai_analysis = []

    if len(bills) == 0:

        ai_analysis.append("暂无消费记录")

        return ai_analysis

    ai_analysis.append(
        f"本月共记录 {len(bills)} 笔消费"
    )

    if total > 3000:

        ai_analysis.append(
            "本月消费较高，请注意预算控制"
        )

    food_total = 0

    for bill in bills:

        if bill["category"] == "餐饮":

            food_total += bill["money"]

    if food_total > total * 0.4:

        ai_analysis.append(
            "餐饮消费占比较高"
        )

    study_total = 0

    for bill in bills:

        if bill["category"] == "学习":

            study_total += bill["money"]

    if study_total > 0:

        ai_analysis.append(
            "你很重视自我提升"
        )

    return ai_analysis