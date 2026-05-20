from services.ai_service import parse_bill_text
from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash
)

from database.db import get_connection

from services.bill_service import get_category


bill_bp = Blueprint(
    "bill",
    __name__
)


# =========================
# AI自然语言记账
# =========================
@bill_bp.route("/ai_add_bill", methods=["GET", "POST"])
def ai_add_bill():

    if "user_id" not in session:

        return redirect("/login")

    # 提交文本
    if request.method == "POST":

        user_input = request.form["bill_text"]

        result = parse_bill_text(user_input)

        # AI失败
        if "error" in result:

            flash("AI解析失败")

            return redirect("/ai_add_bill")

        # 保存到 session
        session["ai_bill"] = result

        return render_template(
            "ai_confirm.html",
            bill=result
        )

    return render_template(
        "ai_add_bill.html"
    )
# =========================
# AI确认入账
# =========================
@bill_bp.route("/confirm_ai_bill", methods=["POST"])
def confirm_ai_bill():

    if "user_id" not in session:

        return redirect("/login")

    # 读取 session
    bill = session.get("ai_bill")

    if not bill:

        flash("没有待确认账单")

        return redirect("/ai_add_bill")

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO bills
        (date, title, money, category, user_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            bill["date"],
            bill["title"],
            bill["money"],
            bill["category"],
            session["user_id"]
        )
    )

    conn.commit()

    conn.close()

    # 清空 session
    session.pop("ai_bill", None)

    flash("AI智能记账成功")

    return redirect("/dashboard")

# =========================
# 添加账单
# =========================
@bill_bp.route("/add_bill", methods=["GET", "POST"])
def add_bill():

    # 未登录
    if "user_id" not in session:

        return redirect("/login")

    # 提交表单
    if request.method == "POST":

        date = request.form["date"]

        title = request.form["title"]

        money = float(request.form["money"])

        # AI分类
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

        flash("账单添加成功")

        return redirect("/dashboard")

    return render_template(
        "add_bill.html",
        today=datetime.now().strftime("%Y-%m-%d")
    )
# =========================
# 删除账单
# =========================
@bill_bp.route("/delete_bill/<int:bill_id>")
def delete_bill(bill_id):

    if "user_id" not in session:

        return redirect("/login")

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
            session["user_id"]
        )
    )

    conn.commit()

    conn.close()

    flash("账单删除成功")

    return redirect("/dashboard")


# =========================
# 编辑账单
# =========================
@bill_bp.route("/edit_bill/<int:bill_id>", methods=["GET", "POST"])
def edit_bill(bill_id):

    if "user_id" not in session:

        return redirect("/login")

    conn = get_connection()

    cursor = conn.cursor()

    # POST 保存
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

        flash("账单修改成功")

        return redirect("/dashboard")

    # GET 读取旧数据
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