"""OCR service for receipt image text extraction.

Primary engine: RapidOCR (pure Python, no external binary needed)
Fallback: pytesseract (requires Tesseract binary installed)
"""

import os
import re
import logging
from PIL import Image

logger = logging.getLogger(__name__)

# Try to import OCR engines
_RAPIDOCR_AVAILABLE = False
_TESSERACT_AVAILABLE = False

try:
    from rapidocr_onnxruntime import RapidOCR
    _RAPIDOCR_AVAILABLE = True
    logger.info("RapidOCR available")
except ImportError:
    logger.info("rapidocr-onnxruntime not installed")

try:
    import pytesseract
    _TESSERACT_AVAILABLE = True
    logger.info("pytesseract available")
except ImportError:
    logger.info("pytesseract not installed")


class OCRService:
    """OCR service for extracting text from receipt images."""

    _rapid_instance = None

    @staticmethod
    def is_available():
        """Check if any OCR engine is available."""
        return _RAPIDOCR_AVAILABLE or _TESSERACT_AVAILABLE

    @staticmethod
    def get_engine():
        """Return the name of the active OCR engine."""
        if _RAPIDOCR_AVAILABLE:
            return 'rapidocr'
        if _TESSERACT_AVAILABLE:
            return 'tesseract'
        return 'none'

    @staticmethod
    def preprocess_image(image_path):
        """Resize image if too large; RapidOCR handles its own preprocessing."""
        try:
            img = Image.open(image_path)

            # Resize if too large (max 2000px on longest side)
            max_size = 2000
            if max(img.size) > max_size:
                ratio = max_size / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
                resized_path = image_path + '.resized.png'
                img.save(resized_path, 'PNG')
                return resized_path

            return image_path

        except Exception as e:
            logger.error(f"Image preprocessing failed: {e}")
            return image_path

    @staticmethod
    def extract_text(image_path):
        """Extract text from an image using available OCR engine."""
        if not OCRService.is_available():
            return {
                'success': False,
                'error': 'OCR引擎不可用，请安装 rapidocr-onnxruntime',
                'text': '',
                'engine': 'none'
            }

        preprocessed_path = OCRService.preprocess_image(image_path)

        try:
            if _RAPIDOCR_AVAILABLE:
                result = OCRService._extract_with_rapid(preprocessed_path)
            elif _TESSERACT_AVAILABLE:
                result = OCRService._extract_with_tesseract(preprocessed_path)
            else:
                return {
                    'success': False,
                    'error': '无可用的OCR引擎',
                    'text': '',
                    'engine': 'none'
                }

            # Clean up preprocessed file
            if preprocessed_path != image_path and os.path.exists(preprocessed_path):
                try:
                    os.remove(preprocessed_path)
                except OSError:
                    pass

            return result

        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            if preprocessed_path != image_path and os.path.exists(preprocessed_path):
                try:
                    os.remove(preprocessed_path)
                except OSError:
                    pass
            return {
                'success': False,
                'error': f'OCR识别失败: {str(e)}',
                'text': '',
                'engine': 'error'
            }

    @staticmethod
    def _extract_with_rapid(image_path):
        """Extract text using RapidOCR."""
        try:
            if OCRService._rapid_instance is None:
                OCRService._rapid_instance = RapidOCR()

            result, elapse = OCRService._rapid_instance(image_path)

            lines = []
            if result:
                for item in result:
                    # item = [box, text, confidence]  confidence can be str or float
                    if len(item) >= 3:
                        text = item[1]
                        try:
                            confidence = float(item[2])
                        except (ValueError, TypeError):
                            confidence = 0.0
                        if confidence > 0.5:
                            lines.append(text)

            full_text = '\n'.join(lines)
            if elapse and isinstance(elapse, (list, tuple)):
                elapse_str = f"{sum(elapse):.2f}s"
            elif elapse:
                elapse_str = f"{elapse:.2f}s"
            else:
                elapse_str = "N/A"
            logger.info(f"RapidOCR extracted {len(lines)} lines, {len(full_text)} chars, time={elapse_str}")

            return {
                'success': True,
                'text': full_text,
                'lines': lines,
                'engine': 'rapidocr',
                'line_count': len(lines)
            }

        except Exception as e:
            logger.error(f"RapidOCR failed: {e}")
            raise

    @staticmethod
    def _extract_with_tesseract(image_path):
        """Extract text using Tesseract OCR."""
        try:
            try:
                text = pytesseract.image_to_string(
                    Image.open(image_path),
                    lang='chi_sim+eng',
                    config='--psm 6'
                )
            except Exception:
                text = pytesseract.image_to_string(
                    Image.open(image_path),
                    lang='eng',
                    config='--psm 6'
                )

            lines = [line.strip() for line in text.split('\n') if line.strip()]
            full_text = '\n'.join(lines)

            logger.info(f"Tesseract extracted {len(lines)} lines, {len(full_text)} chars")

            return {
                'success': True,
                'text': full_text,
                'lines': lines,
                'engine': 'tesseract',
                'line_count': len(lines)
            }

        except Exception as e:
            logger.error(f"Tesseract failed: {e}")
            raise

    @staticmethod
    def parse_receipt_info(ocr_text):
        """Extract structured receipt info from OCR text."""
        info = {
            'merchant': '',
            'total_amount': 0,
            'date': '',
            'items': []
        }

        lines = ocr_text.split('\n')

        # Extract merchant (usually first few lines)
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 2 and not re.search(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', line):
                if not re.match(r'^[\d\s.¥￥]+$', line):
                    info['merchant'] = line
                    break

        # Extract total amount
        amount_patterns = [
            r'合\s*计[：:]\s*[¥￥]?\s*([\d,.]+)',
            r'总\s*[计价额][：:]\s*[¥￥]?\s*([\d,.]+)',
            r'实\s*[付收][：:]\s*[¥￥]?\s*([\d,.]+)',
            r'应\s*付[：:]\s*[¥￥]?\s*([\d,.]+)',
            r'总\s*额[：:]\s*[¥￥]?\s*([\d,.]+)',
            r'[¥￥]\s*([\d,.]+)',
            r'(\d+\.?\d{0,2})\s*元',
        ]

        for pattern in amount_patterns:
            matches = re.findall(pattern, ocr_text)
            if matches:
                amounts = []
                for m in matches:
                    try:
                        amounts.append(float(m.replace(',', '')))
                    except ValueError:
                        continue
                if amounts:
                    info['total_amount'] = max(amounts)
                    break

        # Extract date
        date_patterns = [
            r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{2}[-/]\d{1,2}[-/]\d{1,2})',
        ]

        for pattern in date_patterns:
            match = re.search(pattern, ocr_text)
            if match:
                info['date'] = match.group(1)
                break

        # Extract line items
        item_pattern = r'(.+?)\s+[¥￥]?\s*(\d+\.?\d{0,2})\s*$'
        for line in lines:
            match = re.match(item_pattern, line.strip())
            if match:
                item_name = match.group(1).strip()
                try:
                    item_amount = float(match.group(2))
                    if 0 < item_amount < 100000 and len(item_name) > 1:
                        info['items'].append({
                            'name': item_name,
                            'amount': item_amount
                        })
                except ValueError:
                    continue

        logger.info(
            f"Receipt parsed: merchant={info['merchant']} "
            f"amount={info['total_amount']} items={len(info['items'])}"
        )

        return info
