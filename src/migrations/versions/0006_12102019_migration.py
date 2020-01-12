""" 
Created_at: 12 Oct. 2019 09:48:08
Target: Episodes: update current status

"""
import peewee

from common.models import database, BaseModel
from common.utils import database_init


previous = "0005_12102019_migration"


class Episode(BaseModel):
    """ Migration version for model `modules.podcast.models.Episode` """

    STATUS_NEW = "new"
    STATUS_DOWNLOADING = "downloading"
    STATUS_PUBLISHED = "published"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = (
        (STATUS_NEW, "new",),
        (STATUS_DOWNLOADING, "Downloading"),
        (STATUS_PUBLISHED, "Published"),
        (STATUS_ARCHIVED, "Archived"),
    )

    status = peewee.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_NEW, null=False
    )
    downloaded = peewee.BooleanField(default=False)

    class Meta:
        db_table = "episodes"  # old version of table name


def upgrade():
    database_init(database)
    query = Episode.update(status=Episode.STATUS_PUBLISHED).where(
        Episode.downloaded == True
    )
    query.execute()


def downgrade():
    database_init(database)
    query = Episode.update(downloaded=True).where(
        Episode.status == Episode.STATUS_PUBLISHED
    )
    query.execute()
