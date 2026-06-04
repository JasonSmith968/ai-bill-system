from openai import OpenAI
import json

# =========================
# DeepSeek Client
# =========================
client = OpenAI(

    api_key="sk-bfb27c7e9ac047b09736099c41e8e4fc",

    base_url="https://api.deepseek.com"

)

# =========================
# 智能分类
# =========================
def smart_category(text):

    text = text.lower()

    food_keywords = [
        "奶茶",
        "咖啡",
        "火锅",
        "烧烤",
        "早餐",
        "午饭",
        "晚饭",
        "麦当劳",
        "肯德基",
        "星巴克",
        "吃饭",
        "饮料"
    ]

    traffic_keywords = [
        "滴滴",
        "打车",
        "公交",
        "地铁",
        "高铁",
        "机票",
        "加油"
    ]

    shopping_keywords = [
        "淘宝",
        "京东",
        "拼多多",
        "买衣服",
        "鞋子",
        "耳机",
        "手机"
    ]

    entertainment_keywords = [
        "电影",
        "ktv",
        "游戏",
        "网吧",
        "酒吧"
    ]

    for word in food_keywords:

        if word in text:
            return "餐饮"

    for word in traffic_keywords:

        if word in text:
            return "交通"

    for word in shopping_keywords:

        if word in text:
            return "购物"

    for word in entertainment_keywords:

        if word in text:
            return "娱乐"

    return "其他"


# =========================
# AI解析账单
# =========================
def parse_bill_text(bill_text):

    prompt = f"""
你是智能记账助手。

请提取所有消费记录。

只返回 JSON 数组。

格式：

[
    {{
        "money": 18,
        "title": "奶茶"
    }}
]

用户输入：

{bill_text}
"""

    try:

        response = client.chat.completions.create(

            model="deepseek-chat",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]

        )

        result = response.choices[0].message.content

        print("========== AI返回 ==========")

        print(result)

        result = result.replace("```json", "")
        result = result.replace("```", "")
        result = result.strip()

        data = json.loads(result)

        return data

    except Exception as e:

        print("AI解析失败：", e)

        return []


# =========================
# AI消费分析
# =========================
def generate_ai_report(bills, total):

    prompt = f"""
你是专业财务分析师。

请根据账单数据：

1. 分析消费习惯
2. 分析消费风险
3. 给出省钱建议

总消费：

{total}

账单：

{bills}

请简洁回答。
"""

    try:

        response = client.chat.completions.create(

            model="deepseek-chat",

            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]

        )

        return response.choices[0].message.content

    except Exception as e:

        print("AI分析失败：", e)

        return "AI分析失败"