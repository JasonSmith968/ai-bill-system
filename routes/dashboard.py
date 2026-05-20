from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    request
)

from services.dashboard_service import (
    build_bill_list,
    get_bill_count,
    calculate_total,
    calculate_category_total,
    build_chart_data,
    build_trend_data,
    build_ai_analysis
)
from services.ai_service import generate_ai_report


dashboard_bp = Blueprint(
    "dashboard",
    __name__
)


PER_PAGE = 5


@dashboard_bp.route("/dashboard")
def dashboard():

    if "user_id" not in session:

        return redirect("/login")

    # 搜索
    keyword = request.args.get(
        "keyword",
        ""
    )

    # 分类筛选
    category = request.args.get(
        "category",
        ""
    )

    # 分页
    page = request.args.get(
        "page",
        1,
        type=int
    )

    bills = build_bill_list(
        session["user_id"],
        keyword,
        category,
        page,
        PER_PAGE
    )

    total_count = get_bill_count(
        session["user_id"],
        keyword,
        category
    )

    total_pages = (
        total_count + PER_PAGE - 1
    ) // PER_PAGE

    total = calculate_total(bills)

    category_data = calculate_category_total(bills)

    category_labels, category_values = build_chart_data(
        category_data
    )

    trend_labels, trend_values = build_trend_data(
        bills
    )

    ai_analysis = build_ai_analysis(
        bills,
        total
    )

    ai_report = generate_ai_report(
        bills
    )

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

        page=page,

        total_pages=total_pages,

        ai_report=ai_report
    )