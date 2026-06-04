"""Report Agent — Financial report generation, export, and summary."""

import time
import logging
from datetime import date
from agents.base import BaseAgent, AgentResult

logger = logging.getLogger(__name__)

REPORT_SYSTEM_PROMPT = (
    '你是报告生成Agent，将财务数据整理成结构化的分析报告。\n'
    '用中文回答，报告格式清晰、数据准确、重点突出。\n'
    '使用Markdown格式，包含标题、摘要、详细分析、建议。'
)


class ReportAgent(BaseAgent):
    """Agent for financial report generation."""

    @property
    def name(self):
        return 'report'

    @property
    def description(self):
        return 'Financial report generation, export, and summary'

    @property
    def capabilities(self):
        return ['generate', 'export', 'summary']

    def execute(self, context, **kwargs):
        start = time.time()
        task = kwargs.get('task', 'generate')

        try:
            if task == 'generate':
                return self._generate(context, start, **kwargs)
            elif task == 'export':
                return self._export(context, start, **kwargs)
            elif task == 'summary':
                return self._summary(context, start, **kwargs)
            else:
                return AgentResult(success=False, error=f'Unknown task: {task}',
                                   agent_name=self.name)
        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, [], [])
            logger.error(f"ReportAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)

    def _generate(self, context, start, **kwargs):
        """Generate a comprehensive financial report."""
        # Gather all available data from context
        summary_data = context.get('summary_data', {})
        analysis_data = context.get('analysis_data', {})
        risk_data = {
            'subscriptions': context.get('subscriptions', []),
            'anomalies': context.get('anomalies', []),
            'high_frequency': context.get('high_frequency', []),
        }
        investment_advice = context.get('investment_advice', '')
        tax_advice = context.get('tax_advice', '')
        recommendations = context.get('recommendations', '')

        # Build report context
        context_parts = [f"报告日期: {date.today().isoformat()}"]

        if summary_data:
            context_parts.append(f"本月收入: ¥{summary_data.get('month_income', 0):,.0f}")
            context_parts.append(f"本月支出: ¥{summary_data.get('month_expense', 0):,.0f}")

        if risk_data.get('subscriptions'):
            context_parts.append(f"检测到 {len(risk_data['subscriptions'])} 个订阅服务")
        if risk_data.get('anomalies'):
            context_parts.append(f"发现 {len(risk_data['anomalies'])} 笔异常消费")

        if investment_advice:
            context_parts.append(f"投资建议: {investment_advice[:200]}...")
        if tax_advice:
            context_parts.append(f"税务建议: {tax_advice[:200]}...")

        prompt = "请基于以下数据生成一份完整的月度财务分析报告：\n\n"
        prompt += "\n".join(context_parts)
        prompt += "\n\n请包含：财务概览、消费分析、风险评估、投资建议、行动计划。"

        messages = [
            {'role': 'system', 'content': REPORT_SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt}
        ]

        llm = context.llm
        result = llm.chat(messages, max_tokens=2500)
        content = result.get('content', '')

        context.set('report', content, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['report'])

        return AgentResult(
            success=True,
            data={'report': content, 'source': 'llm'},
            agent_name=self.name,
            duration_ms=duration
        )

    def _export(self, context, start, **kwargs):
        """Export report data in specified format."""
        report_type = kwargs.get('report_type', 'markdown')
        report_content = context.get('report', '')

        if not report_type or report_type == 'markdown':
            export_data = {'format': 'markdown', 'content': report_content}
        elif report_type == 'json':
            export_data = {
                'format': 'json',
                'data': {
                    'summary': context.get('summary_data', {}),
                    'analysis': context.get('analysis_data', {}),
                    'report': report_content,
                }
            }
        else:
            export_data = {'format': report_type, 'content': report_content, 'note': 'Use frontend for PDF/XLSX export'}

        context.set('export_data', export_data, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['export_data'])

        return AgentResult(
            success=True,
            data={'export_data': export_data},
            agent_name=self.name,
            duration_ms=duration
        )

    def _summary(self, context, start, **kwargs):
        """Generate a brief financial summary."""
        summary_data = context.get('summary_data', {})
        subscriptions = context.get('subscriptions', [])
        anomalies = context.get('anomalies', [])

        parts = []
        income = summary_data.get('month_income', 0)
        expense = summary_data.get('month_expense', 0)
        if income > 0 or expense > 0:
            parts.append(f"本月收支: 收入¥{income:,.0f} / 支出¥{expense:,.0f} / 结余¥{income-expense:,.0f}")

        if subscriptions:
            annual = sum(s.get('annual_cost', 0) for s in subscriptions)
            parts.append(f"订阅服务: {len(subscriptions)}个，年费约¥{annual:,.0f}")

        if anomalies:
            high = sum(1 for a in anomalies if a.get('severity') == 'high')
            if high:
                parts.append(f"风险提示: {high}笔高风险异常消费")

        content = " | ".join(parts) if parts else "暂无足够数据生成摘要"

        context.set('summary', content, self.name)
        duration = (time.time() - start) * 1000
        self._record_call(context, 'ok', duration, [], ['summary'])

        return AgentResult(
            success=True,
            data={'summary': content},
            agent_name=self.name,
            duration_ms=duration
        )
