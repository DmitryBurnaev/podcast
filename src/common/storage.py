import asyncio
import logging
import os
from functools import partial
from typing import Callable, List, Optional, Tuple

import boto3
import botocore
from botocore import exceptions

import settings

logger = logging.getLogger(__name__)





class StorageS3:
    """ Simple client (singleton) for access to S3 bucket """

    __instance = None
    BUCKET_NAME = settings.S3_BUCKET_NAME
    CODE_OK = 0
    CODE_CLIENT_ERROR = 1
    CODE_COMMON_ERROR = 2

    def __new__(cls, *args, **kwargs):
        if not cls.__instance:
            cls.__instance = super().__new__(cls, *args, **kwargs)

        return cls.__instance

    def __init__(self):
        logger.debug("Creating s3 client's session (boto3)...")
        session = boto3.session.Session(
            aws_access_key_id=settings.S3_AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_AWS_SECRET_ACCESS_KEY,
            region_name="ru-central1"
        )
        logger.debug("Boto3 (s3) Session <%s> created", session)
        self.s3 = session.client(service_name='s3', endpoint_url=settings.S3_STORAGE_URL)
        logger.debug("S3 client %s created", self.s3)

    def __call(self, handler: Callable, *args, **kwargs) -> Tuple[int, Optional[dict]]:
        try:
            logger.info("Executing request (%s) to S3 args: %s | kwargs: %s", handler.__name__, args, kwargs)
            response = handler(*args, **kwargs)
        except botocore.exceptions.ClientError as error:
            logger.error("Couldn't execute request (%s) to S3: ClientError %s", handler.__name__, error)
            return self.CODE_CLIENT_ERROR, None
        except Exception as error:
            logger.exception("Shit! We couldn't execute %s to S3: %s", handler.__name__, error)
            return self.CODE_COMMON_ERROR, None
        else:
            return self.CODE_OK, response

    def head_file(self, filename: str, remote_path: str = settings.S3_BUCKET_AUDIO_PATH) -> Optional[dict]:
        dst_path = os.path.join(remote_path, filename)
        code, result = self.__call(self.s3.head_object, Key=dst_path, Bucket=self.BUCKET_NAME)
        return result

    def upload_file(self, src_path: str, dst_path: str, callback: Callable = None) -> int:
        code, result = self.__call(
            self.s3.upload_file, src_path, settings.S3_BUCKET_NAME, dst_path,
            Callback=callback,
            ExtraArgs={"ACL": "public-read"}
        )
        return code

    def get_file_info(self, filename: str, remote_path: str = settings.S3_BUCKET_AUDIO_PATH) -> Optional[dict]:
        """
        Allows to find file information (headers) on remote storage (S3)
        Headers content info about downloaded file
        """
        dst_path = os.path.join(remote_path, filename)
        code, result = self.__call(self.s3.head_object, Key=dst_path, Bucket=self.BUCKET_NAME)
        return result

    def get_file_size(self, filename: Optional[str], remote_path: str = settings.S3_BUCKET_AUDIO_PATH) -> int:
        """ Allows to find file on remote storage (S3) and calculate size (content-length / file size) """

        if filename:
            file_info = self.get_file_info(filename, remote_path)
            if file_info:
                return int(file_info['ResponseMetadata']['HTTPHeaders']['content-length'])

        logger.info("File %s was not found on s3 storage", filename)
        return 0

    def delete_file(self, filename: str, remote_path: str = settings.S3_BUCKET_AUDIO_PATH):
        dst_path = os.path.join(remote_path, filename)
        code, result = self.__call(self.s3.delete_object, Key=dst_path, Bucket=self.BUCKET_NAME)
        return result

    async def delete_files_async(self, filenames: List[str], remote_path: str = settings.S3_BUCKET_AUDIO_PATH):
        loop = asyncio.get_running_loop()
        for filename in filenames:
            dst_path = os.path.join(remote_path, filename)
            await loop.run_in_executor(
                None, partial(self.__call, self.s3.delete_object, Key=dst_path, Bucket=self.BUCKET_NAME)
            )
