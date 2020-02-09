import time
from hashlib import blake2b
from unittest.mock import Mock


class MockYoutube:
    watch_url: str = None
    video_id: str = None
    description = "Test youtube video description"
    thumbnail_url = "http://path.to-image.com"
    title = "Test youtube video"
    author = "Test author"
    length = 110

    def __init__(self):
        self.video_id = blake2b(
            key=bytes(str(time.time()), encoding="utf-8"), digest_size=6
        ).hexdigest()[:11]
        self.watch_url = f"https://www.youtube.com/watch?v={self.video_id}"
        self.extract_info = Mock(return_value=self.info)
        self.download = Mock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        ...

    @property
    def info(self, *args, **kwargs):
        return {
            "id": self.video_id,
            "title": self.title,
            "description": self.description,
            "webpage_url": self.watch_url,
            "thumbnail": self.thumbnail_url,
            "uploader": self.author,
            "duration": self.length,
        }


class MockRedisClient:
    def __init__(self, content=None):
        self._content = content or {}
        self.get_many = Mock(return_value=self._content)

    async def async_get_many(self, *_, **__):
        return self.get_many()
