from modules.auth.urls import urls as accounts_urls
from modules.podcast.urls import urls as podcast_urls


urls = (
    *accounts_urls,
    *podcast_urls,
)
