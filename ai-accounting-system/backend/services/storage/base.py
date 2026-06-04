from abc import ABC, abstractmethod


class StorageProvider(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    def upload(self, file_data: bytes, key: str, content_type: str = None) -> str:
        """Upload file data and return the storage key."""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a file by key. Returns True if deleted."""
        pass

    @abstractmethod
    def get_url(self, key: str, expires: int = 3600) -> str:
        """Get a URL for accessing the file."""
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check if a file exists."""
        pass
