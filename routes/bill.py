from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    session,
    flash
)

from models import db, Bill

from services.ai_service import (
    parse_bill_text,
    smart_category
)

from datetime import datetime

bill_bp = Blueprint(
    "bill",
    __name__
)

# =========================
# 添加账单
# =========================
@bill_bp.route("/add_bill", methods=["GET", "POST"])
def add_bill():

    if "user_id" not in session:

        return redirect("/login")

    if request.method == "POST":

        title = request.form["title"]

        amount = float(
            request.form["amount"]
        )

        category = request.form["category"]

        new_bill = Bill(

            user_id=session["user_id"],

            title=title,

            amount=amount,

            category=category
        )

        db.session.add(new_bill)

        db.session.commit()

        flash("添加成功")

        return redirect("/dashboard")

    return render_template("add_bill.html")

# =========================
# AI 自动记账
# =========================
@bill_bp.route("/ai_add_bill", methods=["GET", "POST"])
def ai_add_bill():

    if "user_id" not in session:

        return redirect("/login")

    if request.method == "POST":

        text = request.form["text"]

        results = parse_bill_text(text)

        print(results)

        if not results:

            flash("AI解析失败")

            return redirect("/ai_add_bill")

        for item in results:

            category = smart_category(
                item["title"]
            )

            bill = Bill(

                user_id=session["user_id"],

                title=item["title"],

                amount=item["money"],

                category=category
            )

            db.session.add(bill)

        db.session.commit()

        flash("AI记账成功")

        return redirect("/dashboard")

    return render_template("ai_add.html")