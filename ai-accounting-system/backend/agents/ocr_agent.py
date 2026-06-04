"""OCR Agent - Receipt image processing and text extraction."""

import time
import logging
from agents.base import BaseAgent, AgentResult
from services.ocr_service import OCRService

logger = logging.getLogger(__name__)


class OCRAgent(BaseAgent):
    """Agent for OCR processing of receipt images."""

    @property
    def name(self):
        return 'ocr'

    @property
    def description(self):
        return 'Receipt image OCR processing and text extraction'

    @property
    def capabilities(self):
        return ['process_receipt']

    def execute(self, context, **kwargs):
        start = time.time()
        image_path = kwargs.get('image_path', '')
        input_keys = []
        output_keys = []

        if not image_path:
            return AgentResult(success=False, error='No image path provided',
                               agent_name=self.name)

        try:
            # Extract text from image
            ocr_result = OCRService.extract_text(image_path)
            if not ocr_result.get('success'):
                return AgentResult(
                    success=False,
                    error=ocr_result.get('error', 'OCR extraction failed'),
                    agent_name=self.name,
                    duration_ms=(time.time() - start) * 1000
                )

            ocr_text = ocr_result['text']
            context.set('ocr_text', ocr_text, self.name)
            context.set('ocr_engine', ocr_result.get('engine', 'unknown'), self.name)
            context.set('line_count', ocr_result.get('line_count', 0), self.name)
            output_keys.extend(['ocr_text', 'ocr_engine', 'line_count'])

            # Parse receipt info from OCR text
            if ocr_text:
                receipt_info = OCRService.parse_receipt_info(ocr_text)
                context.set('receipt_info', receipt_info, self.name)
                output_keys.append('receipt_info')

            duration = (time.time() - start) * 1000
            self._record_call(context, 'ok', duration, input_keys, output_keys)

            return AgentResult(
                success=True,
                data={
                    'ocr_text': ocr_text,
                    'ocr_engine': ocr_result.get('engine'),
                    'line_count': ocr_result.get('line_count', 0),
                    'receipt_info': context.get('receipt_info')
                },
                agent_name=self.name,
                duration_ms=duration
            )

        except Exception as e:
            duration = (time.time() - start) * 1000
            self._record_call(context, 'error', duration, input_keys, output_keys)
            logger.error(f"OCRAgent failed: {e}")
            return AgentResult(success=False, error=str(e),
                               agent_name=self.name, duration_ms=duration)
