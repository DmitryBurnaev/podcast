from common.utils import is_mobile_app
from modules.podcast.models import Podcast


async def podcast_items(request):
    authenticated_user_id = getattr(request.user, "id", None)
    if authenticated_user_id:
        podcasts = await Podcast.get_all(request.app.objects, request.user.id)
        return {"podcasts": podcasts}
    return {}


async def mobile_app_web_view(request):
    """Detects requests from mobile application (It will change some view)"""
    return {"mobile_app_web_view": is_mobile_app(request)}
