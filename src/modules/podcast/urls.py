from common.urls import url
from modules.podcast import views


urls = (
    url("/", views.IndexView, name="index"),
    url("/progress/", views.ProgressView, name="progress"),
    url("/api/progress/", views.ProgressApiView, name="api_progress"),
    url("/api/playlist/", views.PlayListVideosApiView, name="api_playlist"),
    url("/podcasts/", views.PodcastListCreateApiView, name="podcast_list"),
    url(
        "/podcasts/default/",
        views.DefaultPodcastRetrieveUpdateApiView,
        name="default_podcast_details",
    ),
    url("/podcasts/{podcast_id}/", views.PodcastRetrieveUpdateApiView, name="podcast_details",),
    url("/podcasts/{podcast_id}/delete/", views.PodcastDeleteApiView, name="podcast_delete",),
    url("/podcasts/{podcast_id}/playlist/", views.PodcastPlayListView, name="podcast_playlist",),
    url(
        "/podcasts/{podcast_id}/rss-update/",
        views.PodcastUpdateRSSApiView,
        name="podcast_rss_update",
    ),
    url("/podcasts/{podcast_id}/episodes/", views.EpisodeCreateApiView, name="episode_create",),
    url(
        "/podcasts/{podcast_id}/episodes/{episode_id}/",
        views.EpisodeRetrieveUpdateApiView,
        name="episode_details",
    ),
    url(
        "/podcasts/{podcast_id}/episodes/{episode_id}/delete/",
        views.EpisodeDeleteApiView,
        name="episode_delete",
    ),
    url(
        "/podcasts/{podcast_id}/episodes/{episode_id}/download/",
        views.EpisodeDownloadApiView,
        name="episode_download",
    ),
)
