"""OCR Celery tasks — receipt image processing."""

import re
import logging
from celery_app import celery

logger = logging.getLogger(__name__)


def _update_task_record(task_id, status, result=None, error=None):
    """Update the TaskRecord in DB."""
    from models.task_record import TaskRecord
    from extensions import db
    from datetime import datetime

    record = TaskRecord.query.filter_by(task_id=task_id).first()
    if not record:
        return
    record.status = status
    if status == 'running':
        record.started_at = datetime.utcnow()
    elif status in ('success', 'failed'):
        record.completed_at = datetime.utcnow()
    if result is not None:
        record.result = result
    if error is not None:
        record.error = error
    db.session.commit()


def _validate_receipt(parsed_info, ocr_text):
    """Basic receipt validity check.

    A valid receipt must have at least 2 of these 3 fields:
    - amount (total_amount > 0)
    - date (found in OCR text)
    - merchant or meaningful description

    Returns (is_valid: bool, reason: str).
    """
    checks = 0

    # Check 1: Amount
    if parsed_info.get('total_amount', 0) > 0:
        checks += 1

    # Check 2: Date (look for date patterns in OCR text)
    date_patterns = [
        r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',   # 2024-01-15 or 2024/01/15
        r'\d{1,2}[-/]\d{1,2}',              # 01-15 or 01/15
        r'\d{4}年\d{1,2}月\d{1,2}日',        # 2024年1月15日
        r'\d{1,2}月\d{1,2}日',               # 1月15日
    ]
    has_date = any(re.search(p, ocr_text) for p in date_patterns)
    if has_date:
        checks += 1

    # Check 3: Merchant or meaningful description
    merchant = parsed_info.get('merchant', '')
    if merchant and len(merchant.strip()) >= 2:
        checks += 1
    elif len(ocr_text.strip()) >= 20:
        # If there's enough text, consider it has a meaningful description
        checks += 1

    if checks >= 2:
        return True, 'valid receipt'
    else:
        return False, f'未识别到有效账单信息（仅匹配 {checks}/3 项：金额、日期、商户），请上传消费小票、发票或账单截图'


@celery.task(bind=True, queue='ocr', max_retries=2, soft_time_limit=60, time_limit=90,
             name='tasks.ocr_tasks.process_receipt')
def process_receipt(self, user_id, image_path, storage_key=None):
    """Process a receipt image: OCR → parse → validate → AI transaction extraction.

    Args:
        user_id: Owner of the receipt
        image_path: Local path to the image file
        storage_key: Optional cloud storage key

    Returns:
        dict with 'ocr_result', 'parsed_info', 'transaction', 'valid'
    """
    _update_task_record(self.request.id, 'running')

    try:
        from services.ocr_service import OCRService

        # Step 1: OCR extraction
        ocr_result = OCRService.extract_text(image_path)
        if not ocr_result.get('success'):
            _update_task_record(self.request.id, 'failed', error=ocr_result.get('error', 'OCR failed'))
            return {'error': ocr_result.get('error', 'OCR failed'), 'valid': False}

        # Step 2: Parse receipt info
        parsed = OCRService.parse_receipt_info(ocr_result['text'])

        # Step 3: Validate receipt (must have at least 2 of: amount, date, merchant)
        is_valid, reason = _validate_receipt(parsed, ocr_result['text'])
        if not is_valid:
            logger.info(f"Receipt rejected: {reason}")
            _update_task_record(self.request.id, 'success', result={'valid': False, 'reason': reason})
            return {
                'ocr_result': ocr_result,
                'parsed_info': parsed,
                'transaction': None,
                'valid': False,
                'reason': reason,
            }

        output = {
            'ocr_result': ocr_result,
            'parsed_info': parsed,
            'valid': True,
        }

        # Step 4: Optional AI transaction parsing
        if parsed.get('total_amount', 0) > 0:
            try:
                from services.ai_service import AIService
                ai_result = AIService.parse_transaction(ocr_result['text'])
                if ai_result.get('success'):
                    # Merge OCR parsed info with AI result
                    ai_data = ai_result['data']
                    # Use OCR amount if AI confidence is low
                    if ai_data.get('confidence', 0) < 0.8 and parsed.get('total_amount'):
                        ai_data['amount'] = parsed['total_amount']
                    if parsed.get('merchant') and not ai_data.get('description'):
                        ai_data['description'] = f"{parsed['merchant']}消费"
                    output['transaction'] = ai_result
                else:
                    output['transaction'] = None
            except Exception as e:
                logger.warning(f"AI transaction parse failed (non-fatal): {e}")
                output['transaction'] = None

        _update_task_record(self.request.id, 'success', result=output)
        return output

    except Exception as exc:
        logger.error(f"process_receipt failed: {exc}")
        _update_task_record(self.request.id, 'failed', error=str(exc))
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
