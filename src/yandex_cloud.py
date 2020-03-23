import os
import uuid

from podcast.utils import get_file_size

import boto3
session = boto3.session.Session(
    region_name="ru-central1",
    aws_access_key_id=os.getenv("S3_AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("S3_AWS_SECRET_ACCESS_KEY")
)
s3 = session.client(
    service_name='s3',
    endpoint_url='https://storage.yandexcloud.net/'
)
'https://storage.yandexcloud.net/podcast-media/audio/mIje48733uU_dba4d8220f754851b7bd91201cf97864.mp3'
# Из файла
FILENAME = 'mIje48733uU_sound.mp3'
file_size = get_file_size(FILENAME)
uploaded_size = 0


def callback(chunk):
    global uploaded_size
    uploaded_size += chunk
    print(f"completed: {(uploaded_size / file_size) * 100:.2f} %")


print("upload .... ")
res = s3.upload_file(
    FILENAME,
    'podcast-media',
    f"audio/mIje48733uU_{uuid.uuid4().hex}.mp3",
    Callback=callback,
    ExtraArgs={'ACL': 'public-read'}
)

# Получить список объектов в бакете
for key in s3.list_objects(Bucket='podcast-media')['Contents']:
    print(key['Key'], key)
