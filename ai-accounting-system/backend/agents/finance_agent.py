"""Finance Agent - Transaction parsing, spending analysis, chat context."""

import time
import logging
from datetime import date, timedelta
from sqlalchemy import func
from flask import current_app
from agents.base import BaseAgent, AgentResult
from services.ai_service import AIService
from extensions import db
from models.transaction import Transaction, Category

logger = logging.getLogger(__name__)


class FinanceAgent(BaseAgent):
    """Agent for financial analysis and transaction parsing."""

    @property
    def name(self):
        return 'finance'

    @property
    def description(self):
        return 'Transaction parsing, spending analysis, and chat context building'

    @property
    def capabilities(self):
        return ['parse_transaction', 'analyze_spending', 'build_chat_context']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'parse')

        try:
            if task == 'parse':
                return self._parse_transaction(context, start, **kwargs)
            elif task == 'analyze':
                return self._analyze_spending(context, start, **kwargs)
            elif task == 'chat_context':
                return self._build_chat_context(context, start, **kwargs)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"FinanceAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _parse_transaction(self, context, start, **kwargs):
        input_keys = []
        output_keys = []

        # Read OCR text from context if available
        text = kwargs.get('text', '') or context.get('ocr_text', '')
        if context.get('ocr_text'):
            input_keys.append('ocr_text')

        if not text:
            return AgentResult(success=False, error='No text provided',
                               agent_name=self.name)

        result = AIService.parse_transaction(text)
        if not result.get('success'):
            return AgentResult(success=False, error='Transaction parsing failed',
                               agent_name=self.name)

        parsed = result['data']
        context.set('parsed_transaction', parsed, self.name)
        output_keys.append('parsed_transaction')

        # Resolve category ID
        category_id = AIService.get_category_id(
            parsed.get('category', '其他'),
            parsed.get('type', 'expense')
        )
        context.set('category_id', category_id, self.name)
        output_keys.append('category_id')

        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, input_keys, output_keys)

        return AgentResult(
            success=True,
            data={'parsed_transaction': parsed, 'category_id': category_id},
            agent_name=self.name,
            duration_ms=duration
        )

    def _analyze_spending(self, context, start, **kwargs):
        user_id = context.user_id
        output_keys = []

        today = date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        # Gather summary data
        month_income = float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income',
            Transaction.date >= month_start, Transaction.date <= month_end
        ).scalar() or 0)

        month_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense',
            Transaction.date >= month_start, Transaction.date <= month_end
        ).scalar() or 0)

        categories = db.session.query(
            Category.name, Category.icon, Category.color,
            func.sum(Transaction.amount).label('amount'),
            func.count(Transaction.id).label('count')
        ).join(Transaction, Transaction.category_id == Category.id).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense',
            Transaction.date >= month_start, Transaction.date <= month_end
        ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

        total_cat = sum(float(c.amount) for c in categories) or 1
        cat_list = [{
            'name': c.name, 'amount': float(c.amount),
            'count': c.count, 'percentage': round(float(c.amount) / total_cat * 100, 1)
        } for c in categories]

        recent = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.date.desc()
        ).limit(10).all()
        recent_list = [{
            'date': t.date.isoformat(), 'type': t.type,
            'amount': float(t.amount), 'category_name': t.category.name if t.category else '未分类',
            'description': t.description or '', 'merchant': t.merchant or ''
        } for t in recent]

        summary_data = {
            'month_income': month_income, 'month_expense': month_expense,
            'month_balance': month_income - month_expense,
            'month_count': sum(c.count for c in categories),
            'categories': cat_list
        }

        result = AIService.analyze_spending(recent_list, summary_data)
        content = result.get('content', '') if result.get('success') else ''

        context.set('analysis_content', content, self.name)
        context.set('summary_data', summary_data, self.name)
        output_keys.extend(['analysis_content', 'summary_data'])

        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], output_keys)

        return AgentResult(
            success=True,
            data={'analysis_content': content, 'summary_data': summary_data},
            agent_name=self.name,
            duration_ms=duration
        )

    def _build_chat_context(self, context, start, **kwargs):
        user_id = context.user_id
        output_keys = []

        today = date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)

        month_income = float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'income',
            Transaction.date >= month_start, Transaction.date <= month_end
        ).scalar() or 0)

        month_expense = float(db.session.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense',
            Transaction.date >= month_start, Transaction.date <= month_end
        ).scalar() or 0)

        cat_stats = db.session.query(
            Category.name, func.sum(Transaction.amount).label('total'),
            func.count(Transaction.id).label('count')
        ).join(Transaction, Transaction.category_id == Category.id).filter(
            Transaction.user_id == user_id, Transaction.type == 'expense',
            Transaction.date >= month_start, Transaction.date <= month_end
        ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).limit(8).all()

        recent = Transaction.query.filter_by(user_id=user_id).order_by(
            Transaction.date.desc(), Transaction.created_at.desc()
        ).limit(5).all()

        trend_data = []
        for i in range(3):
            m = today.month - i
            y = today.year
            if m <= 0:
                m += 12
                y -= 1
            ms = date(y, m, 1)
            if m == 12:
                me = date(y + 1, 1, 1) - timedelta(days=1)
            else:
                me = date(y, m + 1, 1) - timedelta(days=1)
            exp = float(db.session.query(func.sum(Transaction.amount)).filter(
                Transaction.user_id == user_id, Transaction.type == 'expense',
                Transaction.date >= ms, Transaction.date <= me
            ).scalar() or 0)
            trend_data.append(f'{y}年{m}月支出¥{exp:,.0f}')

        lines = [f'【用户财务数据 - {today.isoformat()}】']
        lines.append(f'本月收入: ¥{month_income:,.2f}, 本月支出: ¥{month_expense:,.2f}, 结余: ¥{month_income - month_expense:,.2f}')

        if cat_stats and month_expense > 0:
            cats = ', '.join(f'{c.name}¥{float(c.total):,.0f}({float(c.total)/month_expense*100:.0f}%)' for c in cat_stats)
            lines.append(f'本月支出分类: {cats}')

        if trend_data:
            lines.append(f'近3月趋势: {" → ".join(reversed(trend_data))}')

        if recent:
            txns = [f'{t.date} {"收入" if t.type == "income" else "支出"}¥{t.amount:,.0f}({t.category.name if t.category else "未分类"})' for t in recent]
            lines.append(f'最近交易: {"; ".join(txns)}')

        user_context = '\n'.join(lines)
        context.set('user_context_text', user_context, self.name)
        output_keys.append('user_context_text')

        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], output_keys)

        return AgentResult(
            success=True,
            data={'user_context_text': user_context},
            agent_name=self.name,
            duration_ms=duration
        )
