import json
import re
import logging
from flask import current_app

logger = logging.getLogger(__name__)


class AIService:
    """AI service for parsing natural language transactions.

    Uses LLMClient for all API calls (circuit breaker, token budget, tracing).
    Falls back to local parser only when LLMClient raises LLMClientError.
    """

    @staticmethod
    def parse_transaction(text):
        """Parse user text to extract transaction info via LLM."""
        from services.llm_client import get_llm_client, LLMClientError

        try:
            llm = get_llm_client()
            messages = [
                {'role': 'system', 'content': '你是一个专业的记账助手，擅长从用户的自然语言描述中提取交易信息。'},
                {'role': 'user', 'content': f"""你是一个智能记账助手。请分析用户的输入，提取交易信息。

用户输入："{text}"

请以JSON格式返回以下信息：
{{
    "type": "income" 或 "expense",
    "amount": 数字（金额），
    "category": "分类名称"（如：餐饮、交通、购物、工资、娱乐、医疗、教育、住房等），
    "description": "简短描述",
    "note": "备注说明",
    "confidence": 0-1之间的置信度
}}

注意：
1. 如果是收入，type为"income"；如果是支出，type为"expense"
2. 金额必须是数字
3. 分类要准确
4. 如果信息不完整，请根据上下文合理推断
5. 只返回JSON，不要有其他内容"""}
            ]

            result = llm.chat(
                messages,
                temperature=0.1,
                max_tokens=500,
                agent_name='ai_service_parse',
            )

            content = result.get('content', '').strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()

            parsed = json.loads(content)
            usage = result.get('usage', {})
            logger.info(
                f"LLM parse success: type={parsed.get('type')} amount={parsed.get('amount')} "
                f"tokens={usage.get('prompt_tokens', 0)}+{usage.get('completion_tokens', 0)} "
                f"model={result.get('model', 'unknown')}"
            )
            return {'success': True, 'data': parsed, 'source': 'llm'}

        except LLMClientError as e:
            logger.warning(f"LLM parse failed ({e}), falling back to local parser")
            result = AIService._local_parse(text)
            result['source'] = 'local'
            return result
        except json.JSONDecodeError as e:
            logger.error(f"LLM parse JSON error: {e}")
            result = AIService._local_parse(text)
            result['source'] = 'local'
            return result
        except Exception as e:
            logger.error(f"LLM parse unexpected error: {e}", exc_info=True)
            result = AIService._local_parse(text)
            result['source'] = 'local'
            return result

    @staticmethod
    def _local_parse(text):
        """Local keyword-based parser (fallback)."""
        text = text.lower().strip()

        income_keywords = ['工资', '薪水', '收入', '奖金', '红包', '转账收', '借入', '还款收']
        expense_keywords = ['花了', '买了', '消费', '支出', '付了', '花费', '借出', '还款付']

        is_income = any(kw in text for kw in income_keywords)
        is_expense = any(kw in text for kw in expense_keywords)

        amount_match = re.search(r'(\d+\.?\d*)', text)
        amount = float(amount_match.group(1)) if amount_match else 0

        if is_income:
            trans_type = 'income'
        elif is_expense:
            trans_type = 'expense'
        else:
            trans_type = 'expense'

        category_map = {
            'expense': {
                '餐饮': ['吃饭', '外卖', '餐厅', '饭店', '火锅', '烧烤', '奶茶', '咖啡', '午餐', '晚餐', '早餐', '食堂'],
                '交通': ['打车', '地铁', '公交', '加油', '停车', '高铁', '飞机', '火车', '滴滴', '出租'],
                '购物': ['买了', '购物', '超市', '商场', '淘宝', '京东', '拼多多', '衣服', '鞋'],
                '娱乐': ['电影', '游戏', 'KTV', '旅游', '门票', '演出', '健身'],
                '住房': ['房租', '水电', '物业', '维修', '家具', '装修'],
                '医疗': ['医院', '药店', '看病', '体检', '药品'],
                '教育': ['课程', '培训', '书籍', '学费', '考试'],
                '通讯': ['话费', '流量', '宽带', '会员'],
            },
            'income': {
                '工资': ['工资', '薪水', '月薪', '底薪'],
                '奖金': ['奖金', '年终奖', '绩效', '提成'],
                '投资': ['股票', '基金', '利息', '分红', '理财'],
                '兼职': ['兼职', '副业', '外包', '稿费'],
                '红包': ['红包', '转账'],
            }
        }

        category = '其他'
        categories = category_map.get(trans_type, {})
        for cat, keywords in categories.items():
            if any(kw in text for kw in keywords):
                category = cat
                break

        description = text[:50] if len(text) > 50 else text
        note = f'AI识别: {text}'

        logger.info(f"Local parse result: type={trans_type} amount={amount} category={category}")

        return {
            'success': True,
            'data': {
                'type': trans_type,
                'amount': amount,
                'category': category,
                'description': description,
                'note': note,
                'confidence': 0.7
            }
        }

    @staticmethod
    def analyze_spending(transactions_data, summary_data):
        """Generate AI financial analysis from user's transaction data."""
        from services.llm_client import get_llm_client, LLMClientError

        prompt = f"""你是一位专业的个人财务顾问。请根据以下用户的财务数据，生成一份详细的中文财务分析报告。

## 用户财务数据概览
- 本月收入：¥{summary_data.get('month_income', 0):.2f}
- 本月支出：¥{summary_data.get('month_expense', 0):.2f}
- 本月结余：¥{summary_data.get('month_balance', 0):.2f}
- 本月记录数：{summary_data.get('month_count', 0)}笔
- 本周支出：¥{summary_data.get('week_expense', 0):.2f}
- 今日支出：¥{summary_data.get('today_expense', 0):.2f}

## 分类支出详情
{chr(10).join(f"- {c['name']}：¥{c['amount']:.2f}（{c['percentage']}%，{c['count']}笔）" for c in summary_data.get('categories', []))}

## 最近交易记录（最新10笔）
{chr(10).join(f"- [{t['date']}] {t['type'] == 'income' and '收入' or '支出'} ¥{t['amount']:.2f} {t.get('category_name', '未分类')} {t.get('merchant', '')} {t.get('description', '')}" for t in transactions_data)}

请用 Markdown 格式输出以下内容：

### 📊 月度财务总结
用2-3句话总结本月整体财务状况，包括收支比、消费趋势等。

### 💰 消费结构分析
分析各分类支出占比，指出主要消费方向，评价消费结构是否合理。

### ⚠️ 超支提醒
如果某个分类支出过高或总支出超过收入，给出具体警告和数据支撑。

### 💡 节省建议
根据消费模式，给出3-5条具体可执行的节省建议，每条建议要具体、可操作。

### 🎯 理财建议
给出短期（本月）和中期（3个月）的理财规划建议。

请直接输出分析内容，不要加多余的前缀。"""

        try:
            llm = get_llm_client()
            messages = [
                {'role': 'system', 'content': '你是一位专业的个人财务顾问，擅长分析消费数据并给出实用的理财建议。请用中文回答，使用 Markdown 格式，语言亲切专业。'},
                {'role': 'user', 'content': prompt}
            ]

            result = llm.chat(
                messages,
                temperature=0.7,
                max_tokens=2000,
                agent_name='ai_service_analyze',
            )

            content = result.get('content', '')
            usage = result.get('usage', {})
            logger.info(
                f"LLM analysis success: length={len(content)} "
                f"tokens={usage.get('prompt_tokens', 0)}+{usage.get('completion_tokens', 0)} "
                f"model={result.get('model', 'unknown')}"
            )
            return {'success': True, 'content': content, 'source': 'llm'}

        except LLMClientError as e:
            logger.warning(f"LLM analysis failed ({e}), falling back to local analysis")
            result = AIService._local_analyze(transactions_data, summary_data)
            result['source'] = 'local'
            return result
        except Exception as e:
            logger.error(f"LLM analysis unexpected error: {e}", exc_info=True)
            result = AIService._local_analyze(transactions_data, summary_data)
            result['source'] = 'local'
            return result

    @staticmethod
    def _local_analyze(transactions_data, summary_data):
        """Local rule-based financial analysis (fallback)."""
        month_expense = summary_data.get('month_expense', 0)
        month_income = summary_data.get('month_income', 0)
        month_balance = summary_data.get('month_balance', 0)
        categories = summary_data.get('categories', [])

        lines = ['### 📊 月度财务总结\n']
        if month_income > 0:
            savings_rate = (month_balance / month_income * 100)
            if savings_rate > 30:
                lines.append(f'本月财务状况**良好**。收入 ¥{month_income:.2f}，支出 ¥{month_expense:.2f}，结余 ¥{month_balance:.2f}，储蓄率 **{savings_rate:.1f}%**，继续保持！')
            elif savings_rate > 0:
                lines.append(f'本月收支基本平衡。收入 ¥{month_income:.2f}，支出 ¥{month_expense:.2f}，结余 ¥{month_balance:.2f}，储蓄率 {savings_rate:.1f}%，还有提升空间。')
            else:
                lines.append(f'⚠️ 本月**入不敷出**。收入 ¥{month_income:.2f}，支出 ¥{month_expense:.2f}，超支 ¥{abs(month_balance):.2f}，需要控制消费。')
        else:
            lines.append(f'本月支出 ¥{month_expense:.2f}，暂无收入记录。')

        lines.append('\n### 💰 消费结构分析\n')
        if categories:
            top3 = categories[:3]
            for c in top3:
                pct = c['percentage']
                bar = '█' * int(pct / 5) + '░' * (20 - int(pct / 5))
                lines.append(f"- **{c['name']}**：¥{c['amount']:.2f}（{pct}%）{bar}")
            if top3[0]['percentage'] > 40:
                lines.append(f"\n> {top3[0]['name']}占比过高（{top3[0]['percentage']}%），建议关注该分类的消费频率。")
        else:
            lines.append('暂无分类数据。')

        lines.append('\n### ⚠️ 超支提醒\n')
        if month_balance < 0:
            lines.append(f'**本月已超支 ¥{abs(month_balance):.2f}**，请注意控制后续消费。')
        for c in categories[:3]:
            if c['percentage'] > 50:
                lines.append(f"- **{c['name']}** 占比达到 {c['percentage']}%，建议适当减少该分类支出。")
        if month_balance >= 0 and not any(c['percentage'] > 50 for c in categories[:3]):
            lines.append('本月暂无明显超支情况，消费结构较合理。')

        lines.append('\n### 💡 节省建议\n')
        if categories:
            top = categories[0]['name']
            tips = {
                '餐饮': ['尝试自己做饭，每周减少2-3次外卖', '使用优惠券和满减活动', '带饭上班，健康又省钱'],
                '交通': ['优先选择公共交通', '拼车出行，分摊油费', '短途步行或骑车，锻炼又省钱'],
                '购物': ['列购物清单，避免冲动消费', '等待大促活动再购买大件', '比较多个平台价格后再下单'],
                '娱乐': ['选择免费或低成本的娱乐方式', '利用团购和会员优惠', '控制娱乐频次，设定月度预算'],
            }
            suggestions = tips.get(top, [f'关注{top}类支出，设定月度预算上限', '记录每笔消费，养成记账习惯', '区分"想要"和"需要"，减少非必要支出'])
            for i, tip in enumerate(suggestions, 1):
                lines.append(f'{i}. {tip}')
        else:
            lines.append('1. 养成每日记账习惯')
            lines.append('2. 设定月度消费预算')
            lines.append('3. 区分"想要"和"需要"')

        lines.append('\n### 🎯 理财建议\n')
        lines.append('**短期（本月）：**')
        if month_balance > 0:
            lines.append(f'- 将结余 ¥{month_balance:.2f} 的 50% 存入储蓄账户')
            lines.append('- 检查是否有可取消的订阅服务')
        else:
            lines.append('- 制定每日消费上限，严格执行')
            lines.append('- 暂停非必要消费，优先填补超支缺口')
        lines.append('\n**中期（3个月）：**')
        lines.append('- 建立应急基金（建议3-6个月生活费）')
        lines.append('- 每月复盘消费数据，持续优化消费结构')
        lines.append('- 设定明确的储蓄目标并跟踪进度')

        content = '\n'.join(lines)
        return {'success': True, 'content': content}

    @staticmethod
    def get_category_id(category_name, trans_type):
        """Find category ID by name and type."""
        from models.transaction import Category

        category = Category.query.filter_by(
            name=category_name, type=trans_type
        ).first()
        if category:
            return category.id

        category = Category.query.filter(
            Category.name.contains(category_name),
            Category.type == trans_type
        ).first()
        if category:
            return category.id

        default = Category.query.filter_by(
            type=trans_type, is_default=True
        ).first()
        return default.id if default else None
