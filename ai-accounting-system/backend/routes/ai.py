import os
import re
import uuid
import logging
import tempfile
from datetime import date, datetime, timedelta
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from extensions import db, limiter
from models.transaction import Transaction
from utils.jwt_helper import token_required
from services.ai_service import AIService
from services.ocr_service import OCRService
from services import billing_service

logger = logging.getLogger(__name__)
biz_logger = logging.getLogger('business')

ai_bp = Blueprint('ai', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_receipt_image(file):
    """Save uploaded receipt image via storage service. Returns (temp_path, storage_key)."""
    from services.storage import get_storage
    from services.image_service import ImageService

    file_data = file.read()

    # Compress image
    quality = current_app.config.get('STORAGE_COMPRESS_QUALITY', 85)
    compressed = ImageService.compress(file_data, quality=quality)

    # Upload to storage
    filename = f"receipt_{uuid.uuid4().hex}.jpg"
    key = f"receipts/{filename}"
    storage = get_storage()
    storage.upload(compressed, key, content_type='image/jpeg')

    # Write temp file for OCR (needs a file path)
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    tmp.write(compressed)
    tmp.close()

    logger.info(f"Receipt image saved: {key} ({len(compressed)} bytes)")
    return tmp.name, key


@ai_bp.route('/parse', methods=['POST'])
@token_required
@limiter.limit("30 per minute")
def parse_transaction():
    """Parse transaction info from natural language text."""
    user_id = request.current_user.id

    # Check AI quota
    allowed, quota_details = billing_service.check_ai_quota(user_id)
    if not allowed:
        return jsonify({'error': quota_details.get('message', 'AI额度已用尽'), 'quota': quota_details}), 429

    data = request.get_json()

    if not data or not data.get('text'):
        return jsonify({'error': '请输入交易描述'}), 400

    text = data['text'].strip()
    if len(text) < 2:
        return jsonify({'error': '描述太短，请输入更多信息'}), 400

    biz_logger.info(f"AI parse request: user_id={user_id} text_len={len(text)}")

    result = AIService.parse_transaction(text)

    if result['success']:
        # Consume AI usage
        billing_service.consume_ai_usage(user_id, tokens_used=0)

        category_id = AIService.get_category_id(
            result['data']['category'],
            result['data']['type']
        )

        biz_logger.info(
            f"AI parse success: user_id={user_id} "
            f"type={result['data']['type']} amount={result['data']['amount']} "
            f"confidence={result['data']['confidence']}"
        )

        return jsonify({
            'parsed': result['data'],
            'category_id': category_id,
            'original_text': text
        })
    else:
        logger.error(f"AI parse failed for user_id={user_id}")
        return jsonify({'error': '解析失败，请重试'}), 500


@ai_bp.route('/receipt', methods=['POST'])
@token_required
@limiter.limit("15 per minute")
def parse_receipt():
    """Upload receipt image, OCR extract text, then AI parse."""
    user = request.current_user

    # Check AI quota
    allowed, quota_details = billing_service.check_ai_quota(user.id)
    if not allowed:
        return jsonify({'error': quota_details.get('message', 'AI额度已用尽'), 'quota': quota_details}), 429

    # Validate file
    if 'image' not in request.files:
        return jsonify({'error': '请上传小票图片'}), 400

    file = request.files['image']
    if not file or not file.filename:
        return jsonify({'error': '请选择图片文件'}), 400

    if not _allowed_file(file.filename):
        return jsonify({'error': '不支持的图片格式，请使用 JPG/PNG/WEBP'}), 400

    # Check file size
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)

    if file_size > MAX_FILE_SIZE:
        return jsonify({'error': f'图片大小不能超过 {MAX_FILE_SIZE // (1024*1024)}MB'}), 400

    if file_size == 0:
        return jsonify({'error': '图片文件为空'}), 400

    biz_logger.info(f"Receipt upload: user_id={user.id} filename={file.filename} size={file_size}")

    # Check OCR availability
    if not OCRService.is_available():
        return jsonify({
            'error': 'OCR引擎不可用',
            'detail': '请安装 pytesseract 或 paddleocr',
            'engine': 'none'
        }), 503

    # Save image (uploads to storage, returns temp file for OCR)
    try:
        temp_path, storage_key = _save_receipt_image(file)
    except Exception as e:
        logger.error(f"Failed to save receipt image: {e}")
        return jsonify({'error': '图片保存失败'}), 500

    # OCR extract text (uses temp file)
    try:
        ocr_result = OCRService.extract_text(temp_path)

        if not ocr_result['success']:
            return jsonify({
                'error': ocr_result.get('error', 'OCR识别失败'),
                'engine': ocr_result.get('engine', 'unknown')
            }), 500

        ocr_text = ocr_result['text']
    except Exception as e:
        logger.error(f"OCR processing failed: {e}", exc_info=True)
        return jsonify({'error': 'OCR处理失败'}), 500
    finally:
        # Clean up temp file
        try:
            os.unlink(temp_path)
        except OSError:
            pass

    # Validate OCR result
    if not ocr_text or len(ocr_text.strip()) < 3:
        return jsonify({
            'error': '未能从图片中识别出有效文字，请确保图片清晰',
            'ocr_text': ocr_text,
            'engine': ocr_result['engine']
        }), 400

    # Validate image is actually a receipt/bill (not an unrelated photo)
    receipt_keywords = [
        '合计', '总计', '总额', '应付', '实付', '找零', '小计',
        '元', '¥', '￥', '$',
        '收据', '发票', '小票', '订单', '账单',
        '数量', '单价', '金额', '价格',
        '日期', '时间', '店名', '超市', '商场', '餐厅', '药店',
        '微信', '支付宝', '现金', '刷卡', '支付',
        '消费', '购物', '购买',
    ]
    amount_pattern = re.search(r'\d+\.?\d{0,2}\s*元', ocr_text)
    currency_pattern = re.search(r'[¥￥$]\s*\d+', ocr_text)
    has_receipt_keyword = any(kw in ocr_text for kw in receipt_keywords)
    has_numeric = bool(re.search(r'\d{2,}', ocr_text))  # at least 2+ digit number

    is_receipt_like = (has_receipt_keyword and has_numeric) or amount_pattern or currency_pattern

    if not is_receipt_like:
        biz_logger.info(f"Receipt rejected: not receipt-like. user_id={user.id} ocr_text={ocr_text[:100]}")
        return jsonify({
            'error': '图片未识别为有效小票或账单，请上传消费小票、发票或账单截图',
            'ocr_text': ocr_text[:200],
            'engine': ocr_result['engine'],
            'hint': '支持的图片类型：超市小票、餐厅账单、电商订单截图、发票等'
        }), 400

    # Parse receipt info from OCR text
    receipt_info = OCRService.parse_receipt_info(ocr_text)

    # Call AI to analyze the OCR text
    try:
        ai_result = AIService.parse_transaction(ocr_text)

        if ai_result['success']:
            parsed = ai_result['data']

            # Consume AI usage
            billing_service.consume_ai_usage(user.id, tokens_used=0)

            # Merge receipt info with AI result
            if receipt_info['merchant'] and not parsed.get('description'):
                parsed['description'] = f"{receipt_info['merchant']}消费"
            if receipt_info['total_amount'] and receipt_info['total_amount'] != parsed.get('amount'):
                # Use AI amount if confident, otherwise use receipt amount
                if parsed.get('confidence', 0) < 0.8:
                    parsed['amount'] = receipt_info['total_amount']

            category_id = AIService.get_category_id(parsed['category'], parsed['type'])

            biz_logger.info(
                f"Receipt AI success: user_id={user.id} type={parsed['type']} "
                f"amount={parsed['amount']} merchant={receipt_info['merchant']} "
                f"engine={ocr_result['engine']}"
            )

            return jsonify({
                'parsed': parsed,
                'category_id': category_id,
                'original_text': ocr_text,
                'receipt_image': storage_key,
                'receipt_info': receipt_info,
                'ocr_engine': ocr_result['engine'],
                'line_count': ocr_result.get('line_count', 0)
            })
        else:
            # AI failed, return receipt info only
            return jsonify({
                'parsed': {
                    'type': 'expense',
                    'amount': receipt_info['total_amount'] or 0,
                    'category': '其他',
                    'description': receipt_info['merchant'] or '小票消费',
                    'note': f'OCR识别: {ocr_text[:100]}',
                    'confidence': 0.5
                },
                'category_id': None,
                'original_text': ocr_text,
                'receipt_image': storage_key,
                'receipt_info': receipt_info,
                'ocr_engine': ocr_result['engine'],
                'line_count': ocr_result.get('line_count', 0)
            })

    except Exception as e:
        logger.error(f"Receipt AI analysis failed: {e}", exc_info=True)
        return jsonify({'error': 'AI分析失败'}), 500


@ai_bp.route('/confirm', methods=['POST'])
@token_required
def confirm_transaction():
    """Confirm and save an AI-parsed transaction."""
    user = request.current_user
    data = request.get_json()

    if not data:
        return jsonify({'error': '缺少数据'}), 400

    if not data.get('type') or not data.get('amount'):
        return jsonify({'error': '缺少交易类型或金额'}), 400

    transaction_date = date.today()
    if data.get('date'):
        try:
            transaction_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        except ValueError:
            pass

    # Resolve tenant_id: use user's tenant, or look up from tenant context
    tenant_id = user.tenant_id
    if not tenant_id:
        from flask import g
        tenant = getattr(g, 'current_tenant', None)
        tenant_id = tenant.id if tenant else None
    if not tenant_id:
        from models.tenant import Tenant
        default_tenant = Tenant.query.first()
        tenant_id = default_tenant.id if default_tenant else None
    if not tenant_id:
        return jsonify({'error': '无法确定租户，请联系管理员'}), 400

    # Resolve category_id if not provided
    category_id = data.get('category_id')
    if not category_id and data.get('type'):
        category_id = AIService.get_category_id(
            data.get('category', '其他'), data['type']
        )

    transaction = Transaction(
        user_id=user.id,
        tenant_id=tenant_id,
        type=data['type'],
        amount=float(data['amount']),
        category_id=category_id,
        description=data.get('description', ''),
        note=data.get('note', ''),
        date=transaction_date,
        ai_generated=True,
        ai_confidence=data.get('confidence', 0.8),
        original_text=data.get('original_text', ''),
        merchant=data.get('merchant', ''),
        receipt_image=data.get('receipt_image', ''),
        ocr_text=data.get('ocr_text', '')
    )

    db.session.add(transaction)
    db.session.commit()

    biz_logger.info(
        f"AI transaction confirmed: user_id={user.id} type={data['type']} "
        f"amount={data['amount']} merchant={data.get('merchant', '')}"
    )

    return jsonify({
        'message': '记录保存成功',
        'transaction': transaction.to_dict()
    }), 201


@ai_bp.route('/quick-add', methods=['POST'])
@token_required
@limiter.limit("20 per minute")
def quick_add():
    """Parse and save in one step."""
    user = request.current_user

    # Check AI quota
    allowed, quota_details = billing_service.check_ai_quota(user.id)
    if not allowed:
        return jsonify({'error': quota_details.get('message', 'AI额度已用尽'), 'quota': quota_details}), 429

    data = request.get_json()

    if not data or not data.get('text'):
        return jsonify({'error': '请输入交易描述'}), 400

    text = data['text'].strip()

    biz_logger.info(f"AI quick-add request: user_id={user.id}")

    parse_result = AIService.parse_transaction(text)

    if not parse_result['success']:
        logger.error(f"AI quick-add parse failed: user_id={user.id}")
        return jsonify({'error': 'AI解析失败'}), 500

    parsed = parse_result['data']

    # Consume AI usage
    billing_service.consume_ai_usage(user.id, tokens_used=0)
    category_id = AIService.get_category_id(parsed['category'], parsed['type'])

    # Resolve tenant_id
    tenant_id = user.tenant_id
    if not tenant_id:
        from flask import g
        tenant = getattr(g, 'current_tenant', None)
        tenant_id = tenant.id if tenant else None
    if not tenant_id:
        from models.tenant import Tenant
        default_tenant = Tenant.query.first()
        tenant_id = default_tenant.id if default_tenant else None
    if not tenant_id:
        return jsonify({'error': '无法确定租户，请联系管理员'}), 400

    transaction = Transaction(
        user_id=user.id,
        tenant_id=tenant_id,
        type=parsed['type'],
        amount=float(parsed['amount']),
        category_id=category_id,
        description=parsed.get('description', text[:50]),
        note=parsed.get('note', ''),
        date=date.today(),
        ai_generated=True,
        ai_confidence=parsed.get('confidence', 0.8),
        original_text=text
    )

    db.session.add(transaction)
    db.session.commit()

    biz_logger.info(
        f"AI quick-add success: user_id={user.id} type={parsed['type']} "
        f"amount={parsed['amount']} category={parsed['category']}"
    )

    return jsonify({
        'message': 'AI记账成功',
        'transaction': transaction.to_dict(),
        'parsed': parsed
    }), 201


@ai_bp.route('/ocr-status', methods=['GET'])
@token_required
def ocr_status():
    """Check OCR engine availability."""
    return jsonify({
        'available': OCRService.is_available(),
        'engine': OCRService.get_engine()
    })


@ai_bp.route('/analyze', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
def analyze_spending():
    """Generate AI financial analysis for the current user."""
    user = request.current_user

    # Check AI quota
    allowed, quota_details = billing_service.check_ai_quota(user.id)
    if not allowed:
        return jsonify({'error': quota_details.get('message', 'AI额度已用尽'), 'quota': quota_details}), 429
    today = date.today()
    month_start = today.replace(day=1)

    # Get summary data
    from sqlalchemy import func
    from models.transaction import Category

    month_income = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'income',
        Transaction.date >= month_start
    ).scalar() or 0

    month_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= month_start
    ).scalar() or 0

    month_count = Transaction.query.filter(
        Transaction.user_id == user.id, Transaction.date >= month_start
    ).count()

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    week_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date >= week_start, Transaction.date <= week_end
    ).scalar() or 0

    today_expense = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id, Transaction.type == 'expense',
        Transaction.date == today
    ).scalar() or 0

    # Category stats
    cat_stats = db.session.query(
        Category.name, Category.color,
        func.sum(Transaction.amount).label('total'),
        func.count(Transaction.id).label('count')
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id,
        Transaction.type == 'expense',
        Transaction.date >= month_start
    ).group_by(Category.id).order_by(func.sum(Transaction.amount).desc()).all()

    total_cat = sum(float(c.total) for c in cat_stats) or 1
    categories = [{
        'name': c.name,
        'color': c.color,
        'amount': float(c.total),
        'count': c.count,
        'percentage': round(float(c.total) / total_cat * 100, 1)
    } for c in cat_stats]

    # Recent transactions
    recent = Transaction.query.filter_by(user_id=user.id).order_by(
        Transaction.date.desc(), Transaction.created_at.desc()
    ).limit(10).all()

    transactions_data = [{
        'date': t.date.isoformat(),
        'type': t.type,
        'amount': float(t.amount),
        'category_name': t.category.name if t.category else '未分类',
        'merchant': t.merchant or '',
        'description': t.description or ''
    } for t in recent]

    summary_data = {
        'month_income': float(month_income),
        'month_expense': float(month_expense),
        'month_balance': float(month_income) - float(month_expense),
        'month_count': month_count,
        'week_expense': float(week_expense),
        'today_expense': float(today_expense),
        'categories': categories
    }

    biz_logger.info(f"AI analyze request: user_id={user.id} expense={month_expense} categories={len(categories)}")

    result = AIService.analyze_spending(transactions_data, summary_data)

    if result['success']:
        # Consume AI usage
        billing_service.consume_ai_usage(user.id, tokens_used=0)
        return jsonify({
            'content': result['content'],
            'summary': summary_data
        })
    else:
        return jsonify({'error': '分析失败，请稍后重试'}), 500
