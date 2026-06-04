from flask import (
    Blueprint,
    jsonify,
    request
)

from models import db, Bill, User

import requests
import json

api_bp = Blueprint(
    "api",
    __name__
)

# =========================
# 获取所有账单
# =========================
@api_bp.route("/api/bills")
def get_bills():

    bills = Bill.query.all()

    data = []

    for bill in bills:

        data.append({

            "id": bill.id,

            "title": bill.title,

            "amount": bill.amount,

            "category": bill.category,

            "created_at": str(bill.created_at)

        })

    return jsonify(data)


# =========================
# 添加普通账单
# =========================
@api_bp.route("/api/add_bill", methods=["POST"])
def api_add_bill():

    data = request.json

    title = data.get("title")

    amount = data.get("amount")

    category = data.get("category")

    new_bill = Bill(

        user_id=1,

        title=title,

        amount=amount,

        category=category
    )

    db.session.add(new_bill)

    db.session.commit()

    return jsonify({

        "message": "账单添加成功"

    })


# =========================
# 获取统计
# =========================
@api_bp.route("/api/statistics")
def statistics():

    bills = Bill.query.all()

    total = sum(
        bill.amount
        for bill in bills
    )

    count = len(bills)

    return jsonify({

        "total_amount": total,

        "bill_count": count
    })


# =========================
# AI 自动记账
# =========================
@api_bp.route("/api/ai_bill", methods=["POST"])
def ai_bill():

    try:

        # 前端数据
        data = request.json

        text = data.get("text")

        # DeepSeek API — read key from environment variable
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        if not api_key:
            return jsonify({"error": "AI service not configured"}), 503
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Prompt
        prompt = f"""
你是一个智能记账助手。

请从下面内容中提取消费记录。

用户输入：

{text}

请返回 JSON 数组格式：

[
    {{
        "title": "奶茶",
        "amount": 18,
        "category": "餐饮"
    }}
]

分类只能是：

餐饮
交通
购物
娱乐
住房
医疗
其他

不要返回解释。
不要返回 markdown。
不要返回 ```json。
只返回纯 JSON。
"""

        # 请求体
        body = {

            "model": "deepseek-chat",

            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            "temperature": 0.2
        }

        # 请求 DeepSeek
        response = requests.post(

            "https://api.deepseek.com/chat/completions",

            headers=headers,

            json=body
        )

        print("DeepSeek返回：")
        print(response.text)

        # 转 JSON
        result = response.json()

        # AI 内容
        ai_text = result["choices"][0]["message"]["content"]

        # 清理 markdown
        ai_text = ai_text.replace("```json", "")
        ai_text = ai_text.replace("```", "")
        ai_text = ai_text.strip()

        # JSON解析
        bills = json.loads(ai_text)

        # 保存数据库
        for item in bills:

            new_bill = Bill(

                user_id=1,

                title=item["title"],

                amount=float(item["amount"]),

                category=item["category"]
            )

            db.session.add(new_bill)

        db.session.commit()

        return jsonify({

            "message": "AI记账成功",

            "data": bills

        })

    except Exception as e:

        print("AI记账失败：")
        print(e)

        return jsonify({

            "error": str(e)

        }), 500
# =========================
# 删除账单
# =========================
@api_bp.route("/api/delete_bill/<int:bill_id>", methods=["DELETE"])
def delete_bill(bill_id):

    try:

        bill = Bill.query.get(bill_id)

        if not bill:

            return jsonify({

                "error": "账单不存在"

            }), 404

        db.session.delete(bill)

        db.session.commit()

        return jsonify({

            "message": "删除成功"

        })

    except Exception as e:

        return jsonify({

            "error": str(e)

        }), 500