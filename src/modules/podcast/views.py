import asyncio
import http
import re
from abc import ABC
from functools import partial
from typing import List, Iterable
import logging

import aiohttp_jinja2
import peewee
from aiohttp import web
from cerberus import Validator
import yt_dlp

from app_i18n import aiohttp_translations
from common.storage import StorageS3
from modules.youtube.exceptions import YoutubeExtractInfoError

import settings
from common.decorators import (
    login_required,
    errors_wrapped,
    json_response,
    login_api_required,
    errors_api_wrapped,
)
from common.excpetions import YoutubeFetchError, InvalidParameterError
from common.models import BaseModel
from common.utils import redirect, add_message, is_mobile_app, cut_string
from common.views import BaseApiView
from modules.podcast import tasks
from modules.podcast.models import Podcast, Episode
from modules.podcast.utils import get_file_name, EpisodeStatuses
from modules.youtube.utils import get_youtube_info, get_video_id
from modules.podcast.utils import check_state


_ = aiohttp_translations.gettext
logger = logging.getLogger(__name__)


class BasePodcastApiView(BaseApiView, ABC):
    kwarg_pk = "pk"

    async def _get_object(self) -> BaseModel:
        instance_id = self.request.match_info.get(self.kwarg_pk)
        try:
            instance = await self.request.app.objects.get(
                self.model_class, self.model_class.id == instance_id
            )
        except peewee.DoesNotExist:
            raise web.HTTPNotFound(body=f"{self.model_class.__name__} #{instance_id} not found.")

        self._check_owner(instance)
        return instance

    async def _generate_rss(self, podcast_id):
        await self._enqueue_task(tasks.generate_rss, podcast_id)

    async def _enqueue_task(self, task, *args, **kwargs):
        loop = asyncio.get_running_loop()
        handler = partial(self.request.app.rq_queue.enqueue, task, *args, **kwargs)
        await loop.run_in_executor(None, handler)

    def _check_owner(self, target_object: BaseModel):
        if self.user.id != target_object.created_by_id:
            raise web.HTTPForbidden(body=f"You have not access to {target_object}")


class IndexView(web.View):
    template_name = "index.html"

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        return {}


class DefaultPodcastRetrieveUpdateApiView(BasePodcastApiView):
    template_name = "podcast/podcast.html"
    model_class = Podcast

    async def _get_object(self) -> Podcast:
        try:
            podcast = await self.request.app.objects.get(
                Podcast.select()
                .where(Podcast.created_by_id == self.user.id)
                .order_by(Podcast.created_at.desc())
            )
        except peewee.DoesNotExist:
            podcast = await Podcast.create_first_podcast(self.request.app.objects, self.user.id)

        return podcast

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        podcast: Podcast = await self._get_object()
        podcast.episodes = await podcast.get_episodes_async(self.request.app.objects, self.user.id)
        return {"podcast": podcast, "settings": settings}


class PodcastRetrieveUpdateApiView(BasePodcastApiView):
    template_name = "podcast/podcast.html"
    model_class = Podcast
    kwarg_pk = "podcast_id"
    validator = Validator(
        {
            "name": {"type": "string", "minlength": 1, "maxlength": 256, "required": False},
            "description": {"type": "string", "minlength": 1, "required": False},
        }
    )

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        podcast: Podcast = await self._get_object()
        podcast.episodes = await podcast.get_episodes_async(self.request.app.objects, self.user.id)
        return {"podcast": podcast, "settings": settings}

    @login_required
    async def delete(self):
        podcast = await self._get_object()
        await self.request.app.objects.delete(podcast)
        return web.json_response({"status": "OK"})

    @login_required
    @errors_wrapped
    async def post(self):
        podcast = await self._get_object()
        cleaned_data = await self._validate()
        for key, value in cleaned_data.items():
            setattr(podcast, key, value)
        await self.request.app.objects.update(podcast)
        redirect_url = self.request.headers.get("Referer") or self.request.path
        return redirect(self.request, "podcast_details", url=redirect_url)


class PodcastDeleteApiView(BasePodcastApiView):
    model_class = Podcast
    kwarg_pk = "podcast_id"

    async def _delete_files(self, podcast: Podcast, episodes: List[Episode]):
        podcast_file_names = {episode.file_name for episode in episodes}
        same_file_episodes = await self.request.app.objects.execute(
            Episode.select().where(
                Episode.podcast_id != podcast.id,
                Episode.file_name.in_(podcast_file_names),
            )
        )
        exist_file_names = {episode.file_name for episode in same_file_episodes or []}

        files_to_remove = podcast_file_names - exist_file_names
        files_to_skip = exist_file_names & podcast_file_names
        if files_to_skip:
            self.logger.warning(
                "There are another episodes with files %s. Skip this files removing.",
                files_to_skip,
            )

        storage = StorageS3()
        await storage.delete_files_async(list(files_to_remove))
        await storage.delete_files_async(
            [f"{podcast.publish_id}.xml"], remote_path=settings.S3_BUCKET_RSS_PATH
        )

    @login_required
    async def get(self):
        podcast: Podcast = await self._get_object()
        episodes = await podcast.get_episodes_async(self.request.app.objects, self.user.id)
        await self._delete_files(podcast, episodes)
        await self.request.app.objects.delete(podcast, recursive=True)
        add_message(self.request, f'Podcast "{podcast.name}" was deleted')
        return redirect(self.request, "podcast_list")


class PodcastUpdateRSSApiView(BasePodcastApiView):
    model_class = Podcast
    kwarg_pk = "podcast_id"

    @login_required
    async def get(self):
        podcast = await self._get_object()
        await self._generate_rss(podcast.id)
        add_message(self.request, f"RSS for podcast {podcast.name} will be refreshed soon")
        return redirect(self.request, "podcast_details", podcast_id=podcast.id)


class PodcastListCreateApiView(BasePodcastApiView):
    template_name = "podcast/list.html"
    model_class = Podcast
    validator = Validator(
        {
            "name": {"type": "string", "minlength": 1, "maxlength": 256, "required": True},
            "description": {"type": "string", "required": False},
        }
    )

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        podcasts = await Podcast.get_all(self.request.app.objects, self.user.id)
        return {"podcasts": podcasts}

    @login_required
    @errors_wrapped
    async def post(self):
        cleaned_data = await self._validate()
        podcast = await self.request.app.objects.create(
            Podcast,
            **dict(
                publish_id=Podcast.generate_publish_id(),
                name=cleaned_data["name"],
                description=cleaned_data.get("description", ""),
                created_by_id=self.user.id,
            ),
        )
        return redirect(self.request, "podcast_details", podcast_id=podcast.id)


class EpisodeRetrieveUpdateApiView(BasePodcastApiView):
    template_name = "podcast/episode.html"
    kwarg_pk = "episode_id"
    model_class = Episode
    validator = Validator(
        {
            "title": {"type": "string", "minlength": 1, "maxlength": 256, "required": False},
            "author": {"type": "string", "maxlength": 256, "required": False},
            "watch_url": {"type": "string", "minlength": 6, "maxlength": 256, "required": False},
            "description": {"type": "string", "required": False},
        }
    )

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        podcast_id = self.request.match_info.get("podcast_id")
        podcast = await self.request.app.objects.get(Podcast, Podcast.id == podcast_id)
        episode = await self._get_object()
        return {"podcast": podcast, "episode": episode}

    @login_required
    async def delete(self):
        episode = await self._get_object()
        await self.request.app.objects.delete(episode)
        return web.json_response({"status": "OK"})

    @login_required
    @errors_wrapped
    async def post(self):
        podcast_id = self.request.match_info.get("podcast_id")
        episode = await self._get_object()
        cleaned_data = await self._validate()
        for key, value in cleaned_data.items():
            setattr(episode, key, value)

        await self.request.app.objects.update(episode)
        return redirect(
            self.request,
            "episode_details",
            podcast_id=podcast_id,
            episode_id=episode.id,
        )


class EpisodeDeleteApiView(BasePodcastApiView):
    model_class = Episode
    kwarg_pk = "episode_id"

    async def _delete_file(self, episode: Episode):
        """Removing file associated with requested episode"""

        same_file_episodes = await self.request.app.objects.execute(
            Episode.select().where(
                Episode.source_id == episode.source_id,
                Episode.status != Episode.STATUS_NEW,
                Episode.id != episode.id,
            )
        )
        if same_file_episodes:
            episode_ids = ",".join([f"#{episode.id}" for episode in same_file_episodes])
            self.logger.warning(
                f"There are another episodes for file {episode.file_name}: {episode_ids}. "
                f"Skip file removing."
            )
            return

        return await StorageS3().delete_files_async([episode.file_name])

    @login_required
    async def get(self):
        podcast_id = self.request.match_info.get("podcast_id")
        episode: Episode = await self._get_object()
        await self._delete_file(episode)
        await self.request.app.objects.delete(episode, recursive=True)
        await self._generate_rss(podcast_id)
        self.logger.info(f"Episode {episode} successful removed.")
        add_message(self.request, f"Episode for youtube ID {episode.source_id} was removed.")
        return redirect(self.request, "podcast_details", podcast_id=podcast_id)


class EpisodeDownloadApiView(BasePodcastApiView):
    model_class = Episode
    kwarg_pk = "episode_id"

    @login_required
    async def get(self):
        episode: Episode = await self._get_object()
        self.logger.info(f'Start download process for "{episode.watch_url}"')
        add_message(self.request, f"Downloading for youtube {episode.source_id} started.")
        episode.status = Episode.STATUS_DOWNLOADING
        await self.request.app.objects.update(episode)
        await self._enqueue_task(
            tasks.download_episode,
            youtube_link=episode.watch_url,
            episode_id=episode.id,
        )
        return redirect(self.request, "progress")


class EpisodeCreateApiView(BasePodcastApiView):
    template_name = "podcast/list.html"
    symbols_regex = re.compile("[&^<>*#]")
    http_link_regex = re.compile(
        "http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%-[0-9a-fA-F][0-9a-fA-F]))+"
    )
    model_class = Podcast
    kwarg_pk = "podcast_id"
    validator = Validator(
        {"youtube_link": {"type": "string", "minlength": 6, "maxlength": 256, "required": True}}
    )

    @login_required
    @errors_wrapped
    @json_response
    async def get(self):
        podcast: Podcast = await self._get_object()
        episodes = await podcast.get_episodes_async(self.request.app.objects, self.user.id)
        return [{"id": episode.id, "title": episode.title} for episode in episodes], 200

    @login_required
    @errors_wrapped
    async def post(self):
        podcast_id = int(self.request.match_info.get("podcast_id"))
        podcast: Podcast = await self._get_object()
        cleaned_data = await self._validate()
        youtube_link = cleaned_data["youtube_link"].strip()

        video_id = get_video_id(youtube_link)
        if not video_id:
            add_message(self.request, f"YouTube link is not correct: {youtube_link}")
            return redirect(self.request, "podcast_details", podcast_id=podcast_id)

        same_episodes: Iterable[Episode] = await self.request.app.objects.execute(
            Episode.select()
            .where(Episode.source_id == video_id)
            .order_by(Episode.created_at.desc())
        )
        episode_in_podcast, last_same_episode = None, None
        for episode in same_episodes:
            last_same_episode = last_same_episode or episode
            if episode.podcast_id == podcast_id:
                episode_in_podcast = episode
                break

        if episode_in_podcast:
            self.logger.info(
                f"Episode for video [{video_id}] already exists for current "
                f"podcast {podcast_id}. Redirecting to {episode_in_podcast}..."
            )
            add_message(self.request, "Episode already exists in podcast.")
            return redirect(
                self.request,
                "episode_details",
                podcast_id=podcast_id,
                episode_id=episode_in_podcast.id,
            )

        try:
            episode_data = await self._get_episode_data(
                same_episode=last_same_episode,
                podcast_id=podcast_id,
                video_id=video_id,
                youtube_link=youtube_link,
            )
        except YoutubeFetchError:
            return redirect(self.request, "podcast_details", podcast_id=podcast_id)

        episode = await self.request.app.objects.create(Episode, **episode_data)

        if podcast.download_automatically:
            episode.status = Episode.STATUS_DOWNLOADING
            await self.request.app.objects.update(episode)
            await self._enqueue_task(
                tasks.download_episode,
                youtube_link=episode.watch_url,
                episode_id=episode.id,
            )
            add_message(
                self.request,
                f"Downloading for youtube {episode.source_id} was started.",
            )

        if is_mobile_app(self.request):
            return redirect(self.request, "progress")

        return redirect(
            self.request,
            "episode_details",
            podcast_id=podcast_id,
            episode_id=str(episode.id),
        )

    def _replace_special_symbols(self, value):
        res = self.http_link_regex.sub("[LINK]", value)
        return self.symbols_regex.sub("", res)

    async def _get_episode_data(
        self, same_episode: Episode, podcast_id: int, video_id: str, youtube_link: str
    ) -> dict:
        """
        Allows to get information for new episode.
        This info can be given from same episode (episode which has same source_id)
        and part information - from YouTube.

        :return: dict with information for new episode
        """

        if same_episode:
            self.logger.info(
                f"Episode for video {video_id} already exists: {same_episode}. "
                f"Using for information about downloaded file."
            )
            same_episode_data = same_episode.to_dict(
                field_names=[
                    "source_id",
                    "watch_url",
                    "title",
                    "description",
                    "image_url",
                    "author",
                    "length",
                    "file_size",
                    "file_name",
                    "remote_url",
                ]
            )
        else:
            self.logger.info(f"New episode for video {video_id} will be created.")
            same_episode_data = {}

        youtube_info = None
        try:
            youtube_info = await get_youtube_info(youtube_link)
        except YoutubeExtractInfoError:
            add_message(self.request, "Sorry.. Fetching YouTube video was failed", kind="error")

        if youtube_info:
            new_episode_data = {
                "source_id": video_id,
                "watch_url": youtube_info.watch_url,
                "title": self._replace_special_symbols(youtube_info.title),
                "description": self._replace_special_symbols(youtube_info.description),
                "image_url": youtube_info.thumbnail_url,
                "author": youtube_info.author,
                "length": youtube_info.length,
                "file_size": same_episode_data.get("file_size"),
                "file_name": same_episode_data.get("file_name") or get_file_name(video_id),
                "remote_url": same_episode_data.get("remote_url"),
            }
            message = "Episode was successfully created from the YouTube video."
            self.logger.info(message)
            self.logger.debug("New episode data = %s", new_episode_data)
            add_message(self.request, message)
        elif same_episode:
            message = "Episode will be copied from other episode with same video."
            self.logger.info(message)
            add_message(self.request, message)
            new_episode_data = same_episode_data
        else:
            raise YoutubeFetchError

        new_episode_data.update({"podcast_id": podcast_id, "created_by_id": self.user.id})
        return new_episode_data


class ProgressView(web.View):
    template_name = "podcast/progress.html"

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        return {}


class ProgressApiView(web.View):
    @login_required
    @errors_wrapped
    async def get(self):
        status_choices = {
            EpisodeStatuses.pending: _("Pending"),
            EpisodeStatuses.error: _("Error"),
            EpisodeStatuses.finished: _("Finished"),
            EpisodeStatuses.episode_downloading: _("Downloading"),
            EpisodeStatuses.episode_postprocessing: _("Post processing"),
            EpisodeStatuses.episode_uploading: _("Uploading to the cloud"),
            EpisodeStatuses.cover_downloading: _("Cover is downloading"),
            EpisodeStatuses.cover_uploading: _("Cover is uploading"),
        }

        podcast_items = {
            podcast.id: podcast
            for podcast in await Podcast.get_all(self.request.app.objects, self.request.user.id)
        }
        episodes = await Episode.get_in_progress(self.request.app.objects, self.request.user.id)
        progress = await check_state(episodes)
        if progress:
            for progress_item in progress:
                podcast = podcast_items.get(progress_item["podcast_id"])
                progress_item["podcast_publish_id"] = getattr(podcast, "publish_id", None)
                progress_item["status_display"] = status_choices.get(progress_item["status"])
        else:
            progress = []

        return web.json_response({"progress": progress})


class PodcastPlayListView(BasePodcastApiView):
    template_name = "podcast/playlist.html"
    model_class = Podcast
    kwarg_pk = "podcast_id"

    @login_required
    @aiohttp_jinja2.template(template_name)
    async def get(self):
        podcast: Podcast = await self._get_object()
        return {"podcast": podcast}


class PlayListVideosApiView(BaseApiView):
    model_class = None
    validator = Validator({"playlist_url": {"type": "string", "required": False}})

    @json_response
    @errors_api_wrapped
    @login_api_required
    async def post(self):
        cleaned_data = await self._validate(allow_empty=True)
        playlist_url = cleaned_data.get("playlist_url")
        loop = asyncio.get_running_loop()

        with yt_dlp.YoutubeDL({"logger": self.logger, "noplaylist": False}) as ydl:
            extract_info = partial(ydl.extract_info, playlist_url, download=False)
            youtube_details = await loop.run_in_executor(None, extract_info)

        yt_content_type = youtube_details.get("_type")
        if not yt_content_type == "playlist":
            logger.warning("Unknown type of returned youtube details: %s", yt_content_type)
            logger.debug("Returned info: {%s}", youtube_details)
            raise InvalidParameterError(
                details=f"It seems like incorrect playlist. {yt_content_type=}"
            )

        entries = [
            {
                "id": video["id"],
                "title": video["title"],
                "description": cut_string(video["description"], 200),
                "thumbnail_url": video["thumbnails"][0]["url"] if video.get("thumbnails") else "",
                "url": video["webpage_url"],
            }
            for video in youtube_details["entries"]
        ]
        res = {"id": youtube_details["id"], "title": youtube_details["title"], "entries": entries}
        return res, http.HTTPStatus.OK
