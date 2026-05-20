import json

from openai import OpenAI


# =========================
# deepseek API
# =========================
client = OpenAI(
    api_key="sk-bfb27c7e9ac047b09736099c41e8e4fc",
    base_url="https://api.deepseek.com"
)


# =========================
# AI消费分析
# =========================
def generate_ai_report(bills):

    # 无数据
    if len(bills) == 0:

        return "暂无消费数据"

    # 拼接账单文本
    bill_text = ""

    for bill in bills:

        bill_text += (
            f"日期:{bill['date']}, "
            f"标题:{bill['title']}, "
            f"金额:{bill['money']}, "
            f"分类:{bill['category']}\n"
        )

    prompt = f"""
你是一名专业财务分析助手。

以下是用户近期消费记录：

{bill_text}

请从以下几个角度分析：

1. 消费习惯
2. 高消费风险
3. 节省建议
4. 消费结构是否合理

要求：
1. 使用中文
2. 控制在150字以内
3. 使用简洁条目形式
"""

    try:

        completion = client.chat.completions.create(

            model="deepseek-chat",

            messages=[
                {
                    "role": "system",
                    "content": "你是一名专业财务分析助手"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.7,
            max_tokens=512
        )

        ai_text = completion.choices[0].message.content

        return ai_text

    except Exception as e:

        return f"AI分析失败: {str(e)}"


# =========================
# AI自然语言记账
# =========================
def parse_bill_text(user_input):

    prompt = f"""
你是一个智能记账助手。

请从下面文本中提取：

1. title
2. money
3. category
4. date

用户输入：
{user_input}

返回 JSON 格式：

{{
    "title": "",
    "money": 0,
    "category": "",
    "date": ""
}}

不要返回其他内容。
"""

    try:

        completion = client.chat.completions.create(
            model="deepseek-chat",

            messages=[
                {
                    "role": "system",
                    "content": "你是智能记账助手"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],

            temperature=0.3,
            max_completion_tokens=512
        )

        content = completion.choices[0].message.content

        return json.loads(content)

    except Exception as e:

        return {
            "error": str(e)
        }