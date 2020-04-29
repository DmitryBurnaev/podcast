from modules.auth.urls import urls as auth_urls
from modules.podcast.urls import urls as podcast_urls


urls = (
    *auth_urls,
    *podcast_urls,
)
