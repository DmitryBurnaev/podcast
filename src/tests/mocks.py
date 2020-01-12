import time
from hashlib import blake2b
from unittest.mock import Mock


class MockYoutubeStream:
    filesize = 10
    subtype = "mp4"


class MockStreams:
    streams = [MockYoutubeStream()]

    def filter(self, **_):
        return self

    def order_by(self, *_):
        return self

    def all(self):
        return self.streams


class MockYoutube:
    streams: MockStreams = None
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
        self.streams = MockStreams()
        self.init = Mock()
        self.prefetch = Mock()
        # self.title = Mock(return_value="Test youtube video")
