import logging
from flask import current_app

logger = logging.getLogger(__name__)

_storage = None


def get_storage():
    """Get or create the storage provider based on config."""
    global _storage
    if _storage is not None:
        return _storage

    provider = current_app.config.get('STORAGE_PROVIDER', 'local')

    if provider == 'minio':
        from .providers import MinIOStorage
        _storage = MinIOStorage(
            endpoint=current_app.config['MINIO_ENDPOINT'],
            access_key=current_app.config['MINIO_ACCESS_KEY'],
            secret_key=current_app.config['MINIO_SECRET_KEY'],
            bucket=current_app.config['MINIO_BUCKET'],
            secure=current_app.config.get('MINIO_SECURE', False),
        )
    elif provider == 'oss':
        from .providers import OSSStorage
        _storage = OSSStorage(
            access_key_id=current_app.config['OSS_ACCESS_KEY_ID'],
            access_key_secret=current_app.config['OSS_ACCESS_KEY_SECRET'],
            endpoint=current_app.config['OSS_ENDPOINT'],
            bucket=current_app.config['OSS_BUCKET'],
        )
    elif provider == 'cos':
        from .providers import COSStorage
        _storage = COSStorage(
            secret_id=current_app.config['COS_SECRET_ID'],
            secret_key=current_app.config['COS_SECRET_KEY'],
            region=current_app.config['COS_REGION'],
            bucket=current_app.config['COS_BUCKET'],
        )
    else:
        import os
        from .providers import LocalStorage
        upload_dir = os.path.join(current_app.root_path, 'uploads')
        _storage = LocalStorage(upload_dir)

    logger.info(f"Storage provider initialized: {provider}")
    return _storage


def reset_storage():
    """Reset the cached storage instance (for testing or config changes)."""
    global _storage
    _storage = None
