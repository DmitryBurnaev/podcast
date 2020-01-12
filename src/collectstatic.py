import os
import shutil
from contextlib import suppress

import settings


def update_static():
    source_root = os.path.join(settings.BASE_DIR, "static")
    destination_root = settings.STATIC_PATH

    print("Removing old static content... ")
    for static_item in os.listdir(destination_root):
        static_item = os.path.join(destination_root, static_item)
        with suppress(FileNotFoundError):
            if os.path.isdir(static_item):
                shutil.rmtree(static_item)
            else:
                os.remove(static_item)

    print(f'Copying static content from "{source_root}" to "{destination_root}"...')
    for static_item in os.listdir(source_root):
        src_path = os.path.join(source_root, static_item)
        dst_path = os.path.join(destination_root, static_item)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy(src_path, dst_path)


if __name__ == "__main__":
    update_static()
