from dataclasses import dataclass
from typing import Type

from aiohttp import web


# noinspection PyPep8Naming
@dataclass(init=True, repr=True)
class url:
    path: str
    handler: Type[web.View]
    method: str = "*"
    name: str = None

    @property
    def as_dict(self):
        return {
            "path": self.path,
            "handler": self.handler,
            "method": self.method,
            "name": self.name,
        }
