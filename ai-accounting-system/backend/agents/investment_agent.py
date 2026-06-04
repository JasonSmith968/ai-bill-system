"""Investment Agent — Investment analysis, portfolio review, risk assessment."""

import time
import logging
from agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)

INVESTMENT_SYSTEM_PROMPT = (
    '你是投资分析Agent，基于用户的财务状况提供投资建议和风险评估。\n'
    '用中文回答，注意风险提示，不做具体投资推荐。\n'
    '分析维度：资产配置、风险承受能力、流动性需求、投资期限。'
)


class InvestmentAgent(BaseAgent):
    """Agent for investment analysis and portfolio review."""

    @property
    def name(self):
        return 'investment'

    @property
    def description(self):
        return 'Investment analysis, portfolio review, and risk assessment'

    @property
    def capabilities(self):
        return ['analysis', 'portfolio_review', 'risk_assess']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'analysis')

        try:
            if task == 'analysis':
                return self._analysis(context, start, **kwargs)
            elif task == 'portfolio_review':
                return self._portfolio_review(context, start, **kwargs)
            elif task == 'risk_assess':
                return self._risk_assess(context, start, **kwargs)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"InvestmentAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _analysis(self, context, start, **kwargs):
        """Provide investment analysis based on financial data."""
        summary_data = context.get('summary_data', {})
        analysis_data = context.get('analysis_data', {})

        context_parts = []
        if summary_data:
            income = summary_data.get('month_income', 0)
            expense = summary_data.get('month_expense', 0)
            balance = income - expense
            context_parts.append(f"月收入: ¥{income:,.0f}")
            context_parts.append(f"月支出: ¥{expense:,.0f}")
            context_parts.append(f"月结余: ¥{balance:,.0f}")
            if expense > 0:
                context_parts.append(f"储蓄率: {balance/income*100:.1f}%" if income > 0 else "")

        if analysis_data:
            subs = analysis_data.get('subscriptions', [])
            if subs:
                annual = sum(s.get('annual_cost', 0) for s in subs)
                context_parts.append(f"年度订阅: ¥{annual:,.0f}")

        user_profile = context.recall('investment_profile', {})
        if user_profile:
            context_parts.append(f"投资偏好: {user_profile}")

        prompt = "基于以下财务数据，提供投资分析建议：\n\n"
        if context_parts:
            prompt += "\n".join(context_parts) + "\n\n"
        prompt += "请评估：1)风险承受能力 2)建议资产配置 3)流动性建议 4)注意事项"

        messages = [
            {'role': 'system', 'content': INVESTMENT_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ]

        llm = context.llm
        result = llm.chat(messages, max_tokens=1500)
        content = result.get('content', '')

        context.set('investment_advice', content, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['investment_advice'])

        return AgentResult(
            success=True,
            data={'investment_advice': content, 'source': 'llm'},
            agent_name=self.name,
            duration_ms=duration
        )

    def _portfolio_review(self, context, start, **kwargs):
        """Review investment portfolio and provide suggestions."""
        # Placeholder — would integrate with real portfolio data
        message = kwargs.get('message', '请提供投资组合审查建议')

        messages = [
            {'role': 'system', 'content': INVESTMENT_SYSTEM_PROMPT},
            {'role': 'user', 'content': message}
        ]

        llm = context.llm
        result = llm.chat(messages, max_tokens=1500)
        content = result.get('content', '')

        context.set('portfolio_review', content, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['portfolio_review'])

        return AgentResult(
            success=True,
            data={'portfolio_review': content},
            agent_name=self.name,
            duration_ms=duration
        )

    def _risk_assess(self, context, start, **kwargs):
        """Assess investment risk tolerance."""
        summary_data = context.get('summary_data', {})
        income = summary_data.get('month_income', 0)
        expense = summary_data.get('month_expense', 0)
        balance = income - expense

        # Simple risk scoring
        risk_score = 0
        factors = []

        if income > 0:
            savings_rate = balance / income
            if savings_rate > 0.3:
                risk_score += 30
                factors.append(f'储蓄率高({savings_rate:.0%})')
            elif savings_rate > 0.1:
                risk_score += 15
                factors.append(f'储蓄率中等({savings_rate:.0%})')
            else:
                factors.append(f'储蓄率低({savings_rate:.0%})')

        if balance > 10000:
            risk_score += 20
            factors.append('月结余充足')
        elif balance > 3000:
            risk_score += 10
            factors.append('月结余一般')

        age = context.recall('age', 30)
        if age < 35:
            risk_score += 25
            factors.append('年龄较轻，风险承受力强')
        elif age < 50:
            risk_score += 15
            factors.append('中年，风险适中')
        else:
            factors.append('年龄偏大，建议保守')

        risk_level = '激进' if risk_score >= 60 else '稳健' if risk_score >= 35 else '保守'

        result_data = {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'factors': factors,
            'suggestion': f'建议以{risk_level}型投资为主'
        }

        context.set('risk_assessment', result_data, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['risk_assessment'])

        return AgentResult(
            success=True,
            data={'risk_assessment': result_data},
            agent_name=self.name,
            duration_ms=duration
        )
