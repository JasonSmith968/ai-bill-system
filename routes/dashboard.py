from flask import (
    Blueprint,
    render_template,
    session,
    redirect
)

from services.dashboard_service import (
    get_total_expense,
    get_bill_count,
    get_recent_bills,
    get_category_statistics
)

from services.ai_service import generate_ai_report


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


# =========================
# Dashboard
# =========================
@dashboard_bp.route("/dashboard")
def dashboard():

    # 未登录
    if "user_id" not in session:

        return redirect("/login")

    user_id = session["user_id"]

    # 总消费
    total = get_total_expense(user_id)

    # 账单数量
    bill_count = get_bill_count(user_id)

    # 最近账单
    recent_bills = get_recent_bills(user_id)

    # 分类统计
    category_data = get_category_statistics(user_id)

    # AI分析
    ai_report = generate_ai_report(
        recent_bills,
        total
    )

    return render_template(
        "dashboard.html",
        total=total,
        bill_count=bill_count,
        recent_bills=recent_bills,
        category_data=category_data,
        ai_report=ai_report
    )