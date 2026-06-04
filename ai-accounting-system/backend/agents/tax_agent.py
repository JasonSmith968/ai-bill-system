"""Tax Agent — Tax consultation, deduction checking, filing assistance."""

import time
import logging
from agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)

TAX_SYSTEM_PROMPT = (
    '你是税务顾问Agent，了解中国个人所得税政策，帮助用户合理节税。\n'
    '用中文回答，引用相关税法条文，建议要合规合法。\n'
    '分析维度：个税专项附加扣除、年终奖计税方式、社保公积金优化、投资收益税务处理。'
)


class TaxAgent(BaseAgent):
    """Agent for tax consultation and optimization."""

    @property
    def name(self):
        return 'tax'

    @property
    def description(self):
        return 'Tax consultation, deduction checking, and filing assistance'

    @property
    def capabilities(self):
        return ['consult', 'deduction_check', 'filing_help']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'consult')

        try:
            if task == 'consult':
                return self._consult(context, start, **kwargs)
            elif task == 'deduction_check':
                return self._deduction_check(context, start, **kwargs)
            elif task == 'filing_help':
                return self._filing_help(context, start, **kwargs)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"TaxAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _consult(self, context, start, **kwargs):
        """Tax consultation based on financial data."""
        user_message = kwargs.get('message', '')
        analysis_data = context.get('analysis_data', {})
        summary_data = context.get('summary_data', {})

        # Build context from available data
        context_parts = []
        if summary_data:
            context_parts.append(f"本月收入: ¥{summary_data.get('month_income', 0):,.0f}")
            context_parts.append(f"本月支出: ¥{summary_data.get('month_expense', 0):,.0f}")
        if analysis_data:
            if analysis_data.get('subscriptions'):
                annual = sum(s.get('annual_cost', 0) for s in analysis_data['subscriptions'])
                context_parts.append(f"年度订阅费用: ¥{annual:,.0f}")

        user_profile = context.recall('tax_profile', {})
        if user_profile:
            context_parts.append(f"用户税务画像: {user_profile}")

        prompt_content = f"用户问题: {user_message}\n\n"
        if context_parts:
            prompt_content += "财务数据:\n" + "\n".join(context_parts) + "\n\n"
        prompt_content += "请提供税务优化建议。"

        messages = [
            {'role': 'system', 'content': TAX_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt_content}
        ]

        llm = context.llm
        result = llm.chat(messages, max_tokens=1500)
        content = result.get('content', '')

        context.set('tax_advice', content, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['tax_advice'])

        return AgentResult(
            success=True,
            data={'tax_advice': content, 'source': 'llm'},
            agent_name=self.name,
            duration_ms=duration
        )

    def _deduction_check(self, context, start, **kwargs):
        """Check available tax deductions."""
        deductions = [
            {'name': '子女教育', 'monthly': 1000, 'condition': '有3岁以上子女'},
            {'name': '继续教育', 'monthly': 400, 'condition': '学历/职业资格教育'},
            {'name': '大病医疗', 'annual': 80000, 'condition': '自付超15000部分'},
            {'name': '住房贷款利息', 'monthly': 1000, 'condition': '首套房贷'},
            {'name': '住房租金', 'monthly': '800-1500', 'condition': '无自有住房'},
            {'name': '赡养老人', 'monthly': 3000, 'condition': '60岁以上父母'},
            {'name': '婴幼儿照护', 'monthly': 2000, 'condition': '3岁以下婴幼儿'},
        ]

        context.set('available_deductions', deductions, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['available_deductions'])

        return AgentResult(
            success=True,
            data={'available_deductions': deductions},
            agent_name=self.name,
            duration_ms=duration
        )

    def _filing_help(self, context, start, **kwargs):
        """Provide filing assistance guidance."""
        messages = [
            {'role': 'system', 'content': TAX_SYSTEM_PROMPT},
            {'role': 'user', 'content': '请提供个人所得税年度汇算清缴的步骤指南，包括申报时间、所需材料、操作流程。'}
        ]

        llm = context.llm
        result = llm.chat(messages, max_tokens=1500)
        content = result.get('content', '')

        context.set('filing_guide', content, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['filing_guide'])

        return AgentResult(
            success=True,
            data={'filing_guide': content},
            agent_name=self.name,
            duration_ms=duration
        )
