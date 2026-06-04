import os
import logging
from .base import StorageProvider

logger = logging.getLogger(__name__)


class LocalStorage(StorageProvider):
    """Local filesystem storage provider."""

    def __init__(self, upload_dir: str):
        self.upload_dir = upload_dir

    def upload(self, file_data: bytes, key: str, content_type: str = None) -> str:
        filepath = os.path.join(self.upload_dir, key)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'wb') as f:
            f.write(file_data)
        logger.info(f"Local upload: {key} ({len(file_data)} bytes)")
        return key

    def delete(self, key: str) -> bool:
        filepath = os.path.join(self.upload_dir, key)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f"Local delete: {key}")
            return True
        return False

    def get_url(self, key: str, expires: int = 3600) -> str:
        return f'/uploads/{key}'

    def exists(self, key: str) -> bool:
        return os.path.exists(os.path.join(self.upload_dir, key))


class MinIOStorage(StorageProvider):
    """MinIO object storage provider."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str,
                 bucket: str, secure: bool = False):
        from minio import Minio
        self.client = Minio(endpoint, access_key=access_key,
                            secret_key=secret_key, secure=secure)
        self.bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self):
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)
            logger.info(f"MinIO bucket created: {self.bucket}")

    def upload(self, file_data: bytes, key: str, content_type: str = None) -> str:
        from io import BytesIO
        self.client.put_object(
            self.bucket, key, BytesIO(file_data), len(file_data),
            content_type=content_type or 'application/octet-stream'
        )
        logger.info(f"MinIO upload: {self.bucket}/{key} ({len(file_data)} bytes)")
        return key

    def delete(self, key: str) -> bool:
        try:
            self.client.remove_object(self.bucket, key)
            logger.info(f"MinIO delete: {self.bucket}/{key}")
            return True
        except Exception as e:
            logger.warning(f"MinIO delete failed: {key} - {e}")
            return False

    def get_url(self, key: str, expires: int = 3600) -> str:
        from datetime import timedelta
        return self.client.presigned_get_object(
            self.bucket, key, expires=timedelta(seconds=expires)
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except Exception:
            return False


class OSSStorage(StorageProvider):
    """Alibaba Cloud OSS storage provider."""

    def __init__(self, access_key_id: str, access_key_secret: str,
                 endpoint: str, bucket: str):
        import oss2
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket)

    def upload(self, file_data: bytes, key: str, content_type: str = None) -> str:
        headers = {}
        if content_type:
            headers['Content-Type'] = content_type
        self.bucket.put_object(key, file_data, headers=headers)
        logger.info(f"OSS upload: {key} ({len(file_data)} bytes)")
        return key

    def delete(self, key: str) -> bool:
        try:
            self.bucket.delete_object(key)
            logger.info(f"OSS delete: {key}")
            return True
        except Exception as e:
            logger.warning(f"OSS delete failed: {key} - {e}")
            return False

    def get_url(self, key: str, expires: int = 3600) -> str:
        return self.bucket.sign_url('GET', key, expires)

    def exists(self, key: str) -> bool:
        return self.bucket.object_exists(key)


class COSStorage(StorageProvider):
    """Tencent Cloud COS storage provider."""

    def __init__(self, secret_id: str, secret_key: str,
                 region: str, bucket: str):
        from qcloud_cos import CosConfig, CosS3Client
        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
        self.client = CosS3Client(config)
        self.bucket = bucket

    def upload(self, file_data: bytes, key: str, content_type: str = None) -> str:
        from io import BytesIO
        kwargs = {'Bucket': self.bucket, 'Key': key, 'Body': BytesIO(file_data)}
        if content_type:
            kwargs['ContentType'] = content_type
        self.client.put_object(**kwargs)
        logger.info(f"COS upload: {key} ({len(file_data)} bytes)")
        return key

    def delete(self, key: str) -> bool:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            logger.info(f"COS delete: {key}")
            return True
        except Exception as e:
            logger.warning(f"COS delete failed: {key} - {e}")
            return False

    def get_url(self, key: str, expires: int = 3600) -> str:
        return self.client.get_presigned_url(
            Method='GET', Bucket=self.bucket, Key=key, Expired=expires
        )

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False
