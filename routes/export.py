from flask import (
    Blueprint,
    redirect,
    session,
    send_file
)

from openpyxl import Workbook

from database.db import get_connection

import io


export_bp = Blueprint(
    "export",
    __name__
)


# =========================
# 导出 Excel
# =========================
@export_bp.route("/export_excel")
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