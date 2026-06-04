import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)


class ImageService:
    """Image compression and thumbnail generation."""

    @staticmethod
    def compress(image_bytes: bytes, quality: int = 85, max_size: int = 2048) -> bytes:
        """Compress and resize image. Returns processed bytes as JPEG."""
        img = Image.open(BytesIO(image_bytes))

        # Resize if longest side exceeds max_size (proportional)
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        # Convert RGBA/P to RGB for JPEG compatibility
        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        output = BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)
        result = output.getvalue()

        logger.info(f"Image compressed: {len(image_bytes)} -> {len(result)} bytes "
                     f"({len(result)/len(image_bytes)*100:.0f}%)")
        return result

    @staticmethod
    def generate_thumbnail(image_bytes: bytes, sizes: list = None) -> dict:
        """Generate thumbnails at specified sizes. Returns {size: bytes}."""
        if sizes is None:
            sizes = [150, 300]

        img = Image.open(BytesIO(image_bytes))

        if img.mode in ('RGBA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        thumbnails = {}
        for size in sizes:
            ratio = size / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            thumb = img.resize(new_size, Image.Resampling.LANCZOS)

            output = BytesIO()
            thumb.save(output, format='JPEG', quality=80, optimize=True)
            thumbnails[size] = output.getvalue()

        logger.info(f"Thumbnails generated: {list(thumbnails.keys())}")
        return thumbnails

    @staticmethod
    def get_image_info(image_bytes: bytes) -> dict:
        """Get image metadata."""
        img = Image.open(BytesIO(image_bytes))
        return {
            'width': img.width,
            'height': img.height,
            'format': img.format or 'UNKNOWN',
            'size_bytes': len(image_bytes),
        }
