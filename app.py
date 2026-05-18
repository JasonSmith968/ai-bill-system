from datetime import datetime

from openpyxl import Workbook

from flask import send_file

import io

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    session
)
from collections import defaultdict

from database.db import (
    init_db,
    get_connection
)

from services.bill_service import get_category

import bcrypt
import json


app = Flask(__name__)

@app.route("/")
def index():

    # 已登录直接进dashboard
    if "user_id" in session:
        return redirect("/dashboard")

    return render_template("index.html")

app.secret_key = "ai_bill_secret"

# 初始化数据库
init_db()

# 每页数量
PER_PAGE = 5


# =========================
# AI分析
# =========================
def get_ai_analysis(category_data, total_money):

    analysis = []

    # 无数据
    if total_money == 0:

        analysis.append("暂无消费数据")

        return analysis

    # 转字典
    data = {}

    for item in category_data:

        data[item[0]] = item[1]

    # 餐饮
    food_money = data.get("餐饮", 0)

    if food_money > total_money * 0.4:

        analysis.append(
            "餐饮消费占比过高，建议减少外卖频率"
        )

    # 娱乐
    entertainment_money = data.get("娱乐", 0)

    if entertainment_money > total_money * 0.3:

        analysis.append(
            "娱乐消费较高，请注意预算"
        )

    # 购物
    shopping_money = data.get("购物", 0)

    if shopping_money > total_money * 0.5:

        analysis.append(
            "购物支出偏高，建议理性消费"
        )

    # 学习
    study_money = data.get("学习", 0)

    if study_money > 0:

        analysis.append(
            "你很重视自我提升，继续保持"
        )

    # 默认
    if len(analysis) == 0:

        analysis.append(
            "你的消费结构较为合理"
        )

    return analysis

# =========================
# 注册
# =========================
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()

        if user:

            conn.close()

            return "用户名已存在"

        cursor.execute(
            """
            INSERT INTO users
            (username, password)
            VALUES (?, ?)
            """,
            (
                username,
                hashed_password
            )
        )

        conn.commit()

        conn.close()

        return redirect("/login")

    return render_template("register.html")


# =========================
# 登录
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]

        password = request.form["password"]

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM users
            WHERE username = ?
            """,
            (username,)
        )

        user = cursor.fetchone()

        conn.close()

        if user:

            stored_password = user[2].encode("utf-8")

            if bcrypt.checkpw(
                password.encode("utf-8"),
                stored_password
            ):

                session["user_id"] = user[0]

                session["username"] = user[1]

                return redirect("/dashboard")

        return "用户名或密码错误"

    return render_template("login.html")


# =========================
# 仪表盘
# =========================
from collections import defaultdict

@app.route("/dashboard")
def dashboard():

    # 未登录跳转
    if "user_id" not in session:
        return redirect("/login")

    # 连接数据库
    conn = get_connection()

    cursor = conn.cursor()

    # 查询当前用户账单
    # 获取搜索关键词
    keyword = request.args.get("keyword", "")

    # 获取分类
    category = request.args.get("category", "")

    # 分页
    page = request.args.get("page", 1, type=int)

    per_page = 5

    offset = (page - 1) * per_page

    # 有关键词 + 有分类
    if keyword and category:

        cursor.execute(
            """
            SELECT *
            FROM bills
            WHERE user_id = ?
            AND title LIKE ?
            AND category = ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
            """,
            (
                session["user_id"],
                f"%{keyword}%",
                category,
                per_page,
                offset
            )
        )

    # 只有关键词
    elif keyword:

        cursor.execute(
            """
            SELECT *
            FROM bills
            WHERE user_id = ?
            AND title LIKE ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
            """,
            (
                session["user_id"],
                f"%{keyword}%",
                per_page,
                offset
            )
        )

    # 只有分类
    elif category:

        cursor.execute(
            """
            SELECT *
            FROM bills
            WHERE user_id = ?
            AND category = ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
            """,
            (
                session["user_id"],
                category,
                per_page,
                offset
            )
        )

    # 无筛选
    else:

        cursor.execute(
            """
            SELECT *
            FROM bills
            WHERE user_id = ?
            ORDER BY date DESC
            LIMIT ? OFFSET ?
            """,
            (
                session["user_id"],
                per_page,
                offset
            )
        )

    rows = cursor.fetchall()

    # 查询总数量
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM bills
        WHERE user_id = ?
        """,
        (session["user_id"],)
    )

    total_count = cursor.fetchone()[0]

    total_pages = (
                          total_count + per_page - 1
                  ) // per_page

    conn.close()

    # 转换成列表
    bills = []

    for row in rows:

        bills.append({
            "id": row["id"],
            "date": row["date"],
            "title": row["title"],
            "money": row["money"],
            "category": row["category"]
        })

    # 总消费
    total = sum(bill["money"] for bill in bills)

    # AI分析
    ai_analysis = []

    if len(bills) == 0:

        ai_analysis.append("暂无消费记录")

    else:

        ai_analysis.append(f"本月共记录 {len(bills)} 笔消费")

        if total > 500:
            ai_analysis.append("本月消费偏高，请注意预算")

        food_total = 0

        for bill in bills:

            if bill["category"] == "餐饮":
                food_total += bill["money"]

        if total > 0 and food_total / total > 0.4:
            ai_analysis.append("餐饮消费占比较高")

        if len(bills) >= 5:
            ai_analysis.append("近期消费频率较高")

    # 分类统计
    category_data = defaultdict(float)

    for bill in bills:

        category_data[bill["category"]] += bill["money"]

    category_labels = list(category_data.keys())

    category_values = list(category_data.values())

    # 月度趋势
    trend_data = defaultdict(float)

    for bill in bills:

        month = bill["date"][:7]

        trend_data[month] += bill["money"]

    trend_labels = list(trend_data.keys())

    trend_values = list(trend_data.values())

    # 页面渲染
    return render_template(
        "dashboard.html",

        username=session["username"],

        bills=bills,

        total=total,

        ai_analysis=ai_analysis,

        keyword=keyword,
        category=category,

        category_labels=category_labels,
        category_values=category_values,

        trend_labels=trend_labels,
        trend_values=trend_values,

        page = page,
        total_pages = total_pages
    )


# =========================
# 添加账单
# =========================
@app.route("/add_bill", methods=["GET", "POST"])
def add_bill():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        date = request.form["date"]

        title = request.form["title"]

        money = float(request.form["money"])

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
                session["user_id"]
            )
        )

        conn.commit()

        conn.close()

        return redirect("/dashboard")

    return render_template(
        "add_bill.html",
        today=datetime.now().strftime("%Y-%m-%d")
    )

# =========================
# 删除账单
# =========================

@app.route("/delete_bill/<int:bill_id>")
def delete_bill(bill_id):

    # 未登录禁止操作
    if "user_id" not in session:
        return redirect("/login")

    conn = get_connection()

    cursor = conn.cursor()

    # 只能删除当前用户自己的账单
    cursor.execute(
        """
        DELETE FROM bills
        WHERE id = ?
        AND user_id = ?
        """,
        (
            bill_id,
            session["user_id"]
        )
    )

    conn.commit()

    conn.close()

    return redirect("/dashboard")

# =========================
# 编辑账单
# =========================
@app.route("/edit_bill/<int:bill_id>", methods=["GET", "POST"])
def edit_bill(bill_id):

    # 未登录
    if "user_id" not in session:
        return redirect("/login")

    conn = get_connection()

    cursor = conn.cursor()

    # POST：保存修改
    if request.method == "POST":

        date = request.form["date"]

        title = request.form["title"]

        money = float(request.form["money"])

        category = request.form["category"]

        cursor.execute(
            """
            UPDATE bills
            SET
                date = ?,
                title = ?,
                money = ?,
                category = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (
                date,
                title,
                money,
                category,
                bill_id,
                session["user_id"]
            )
        )

        conn.commit()

        conn.close()

        return redirect("/dashboard")

    # GET：读取旧数据
    cursor.execute(
        """
        SELECT *
        FROM bills
        WHERE id = ?
        AND user_id = ?
        """,
        (
            bill_id,
            session["user_id"]
        )
    )

    bill = cursor.fetchone()

    conn.close()

    return render_template(
        "edit_bill.html",
        bill=bill
    )

@app.route("/export_excel")
def export_excel():

    # 未登录
    if "user_id" not in session:
        return redirect("/login")

    conn = get_connection()

    cursor = conn.cursor()

    # 查询当前用户账单
    cursor.execute(
        """
        SELECT *
        FROM bills
        WHERE user_id = ?
        ORDER BY date DESC
        """,
        (session["user_id"],)
    )

    bills = cursor.fetchall()

    conn.close()

    # 创建 Excel
    wb = Workbook()

    ws = wb.active

    ws.title = "账单数据"

    # 表头
    ws.append([
        "ID",
        "日期",
        "标题",
        "金额",
        "分类"
    ])

    # 数据
    for bill in bills:

        ws.append([
            bill["id"],
            bill["date"],
            bill["title"],
            bill["money"],
            bill["category"]
        ])

    # 保存到内存
    output = io.BytesIO()

    wb.save(output)

    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="bills.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# =========================
# 退出登录
# =========================
@app.route("/logout")
def logout():
    session.clear()

    return redirect("/login")
# =========================
# 启动
# =========================
if __name__ == "__main__":

    app.run(debug=True)
