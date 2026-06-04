"""Agent Router — intent classification and agent dispatch.

Two-layer architecture:
  Layer 1: Rule engine (fast, keyword matching)
  Layer 2: LLM fallback (accurate, structured output)
"""

import json
import logging

logger = logging.getLogger(__name__)

# Intent → (agent_name, task) mapping
INTENT_MAP = {
    'record':      ('finance', 'parse'),
    'analyze':     ('finance', 'analyze'),
    'risk':        ('risk', 'full_scan'),
    'budget':      ('recommendation', 'budget'),
    'tax':         ('tax', 'consult'),
    'investment':  ('investment', 'analysis'),
    'report':      ('report', 'generate'),
    'ocr':         ('ocr', 'process_receipt'),
    'chat':        ('finance', 'chat_context'),
}

# Rule-based keyword patterns
_RULES = [
    # OCR / Receipt
    (['拍照', '识别', '扫描', '收据', '发票', 'OCR', 'receipt'], 'ocr'),
    # Recording transactions
    (['记账', '记录', '花了', '收入', '支出', '消费了', '买了', '付了', '转账', '入账'], 'record'),
    # Risk detection
    (['风险', '异常', '可疑', '欺诈', '异常消费', '不正常'], 'risk'),
    # Budget
    (['预算', '节省', '存钱', '理财建议', '花钱太多', '超支', '预算分配'], 'budget'),
    # Tax
    (['税', '报税', '扣税', '抵扣', '个税', '税务', '发票抵扣', 'tax'], 'tax'),
    # Investment
    (['投资', '基金', '股票', '收益', '回报', '理财', '证券', 'portfolio'], 'investment'),
    # Report
    (['报告', '报表', '汇总', '总结', '导出', '月报', '年报', 'report'], 'report'),
    # Analysis
    (['分析', '趋势', '统计', '对比', '变化', '环比', '同比', '花在哪'], 'analyze'),
]


class AgentRouter:
    """Routes user messages to the appropriate agent and task."""

    def __init__(self):
        pass

    def route(self, user_message, context=None):
        """Classify intent and return (agent_name, task, params).

        Args:
            user_message: User's natural language input
            context: Optional AgentContext for additional info

        Returns:
            dict with keys: agent, task, confidence, params
        """
        # Layer 1: Rule-based matching
        rule_result = self._rule_match(user_message)
        if rule_result and rule_result['confidence'] >= 0.8:
            return rule_result

        # Layer 2: LLM classification
        try:
            llm_result = self._llm_classify(user_message)
            if llm_result:
                # If LLM is more confident, use it; otherwise prefer rule result
                if rule_result and rule_result['confidence'] >= llm_result.get('confidence', 0):
                    return rule_result
                return llm_result
        except Exception as e:
            logger.warning(f"LLM classification failed, falling back to rules: {e}")

        if rule_result:
            return rule_result

        # Default: general chat
        return {
            'agent': 'finance',
            'task': 'chat_context',
            'confidence': 0.3,
            'params': {'message': user_message}
        }

    def classify_intent(self, user_message, context=None):
        """Alias for route() — returns same dict."""
        return self.route(user_message, context)

    def _rule_match(self, text):
        """Layer 1: Fast keyword matching."""
        text_lower = text.lower()
        best = None
        best_score = 0

        for keywords, intent in _RULES:
            matched = sum(1 for kw in keywords if kw.lower() in text_lower)
            if matched == 0:
                continue
            # Confidence based on match count
            confidence = min(0.5 + matched * 0.2, 1.0)
            if confidence > best_score:
                best_score = confidence
                agent, task = INTENT_MAP[intent]
                best = {
                    'agent': agent,
                    'task': task,
                    'confidence': round(confidence, 2),
                    'params': {'message': text, 'intent': intent},
                    'source': 'rules',
                }
        return best

    def _llm_classify(self, text):
        """Layer 2: LLM-based classification with structured output."""
        from services.llm_client import get_llm_client

        llm = get_llm_client()
        system_prompt = (
            '你是一个意图分类器。根据用户消息，输出JSON格式的分类结果。\n'
            '可选意图: record(记账), analyze(分析), risk(风险), budget(预算), '
            'tax(税务), investment(投资), report(报告), ocr(OCR识别), chat(闲聊)\n'
            '输出格式: {"intent": "xxx", "confidence": 0.0-1.0, "reason": "简短说明"}\n'
            '只输出JSON，不要其他内容。'
        )

        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': text}
        ]

        try:
            result = llm.chat(messages, max_tokens=150, temperature=0.1)
            content = result.get('content', '').strip()

            # Try to parse JSON from response
            if content.startswith('{'):
                data = json.loads(content)
            else:
                # Try to find JSON in the response
                import re
                match = re.search(r'\{[^}]+\}', content)
                if match:
                    data = json.loads(match.group())
                else:
                    return None

            intent = data.get('intent', 'chat')
            if intent not in INTENT_MAP:
                intent = 'chat'

            agent, task = INTENT_MAP[intent]
            return {
                'agent': agent,
                'task': task,
                'confidence': float(data.get('confidence', 0.6)),
                'params': {'message': text, 'intent': intent, 'reason': data.get('reason', '')},
                'source': 'llm',
            }
        except Exception as e:
            logger.error(f"LLM classification error: {e}")
            return None
