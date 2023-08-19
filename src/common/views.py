import copy
import datetime
import json
from json import JSONDecodeError
from logging import Logger
from typing import List

import peewee_async
from aiohttp import web

from common.excpetions import InvalidParameterError
from common.models import BaseModel


class BaseApiView(web.View):
    kwarg_pk = "pk"
    validator = NotImplemented

    @property
    def model_class(self) -> type(BaseModel):
        raise NotImplementedError

    @property
    def logger(self) -> Logger:
        return self.request.app.logger

    @property
    def user(self):
        return self.request.user

    @property
    def db_objects(self) -> peewee_async.Manager:
        return self.request.app.objects

    async def _get_object(self) -> BaseModel:
        object_id = self.request.match_info.get(self.kwarg_pk)
        object_ = await self.request.app.objects.get(
            self.model_class, self.model_class.id == object_id
        )
        self._check_owner(object_)
        return object_

    def _check_owner(self, target_object: BaseModel):
        if self.user.id != target_object.created_by_id:
            raise web.HTTPForbidden(body=f"You have not access to {target_object}")

    async def _validate(
        self, request_data=None, validator=None, raise_exception=True, allow_empty=False
    ) -> dict:
        cleaned_data = {}
        validator = validator or self.validator
        content_type = (
            self.request.content_type
            or self.request.headers.get("HTTP_CONTENT_TYPE")
            or "application/json"
        )
        if not request_data:
            # TODO: get data from specific attribute/method (post, put)  json/form-data
            request_data = await self.request.post()

        if content_type == "application/json":
            request_data = await self.request.content.read()
            try:
                request_data = json.loads(request_data)
            except JSONDecodeError as ex:
                if raise_exception:
                    raise InvalidParameterError(
                        "JSON request has invalid json content",
                        details=f"Invalid Request {request_data}. Exception: {ex}",
                    )

        elif content_type in (
            "multipart/form-data",
            "application/x-www-form-urlencoded",
        ):
            res_request_data = {}
            for key in request_data:
                value = request_data.getall(key)
                if "[]" in key or len(value) > 1:
                    res_request_data[key] = value
                else:
                    res_request_data[key] = value[0]
            request_data = res_request_data

        if request_data:
            try:
                cleaned_data = validator.validated(request_data)
            except Exception as ex:
                if raise_exception:
                    raise InvalidParameterError(
                        details=f"Invalid Request {request_data}. Exception: {ex}"
                    )

            if not cleaned_data and raise_exception:
                raise InvalidParameterError(details=validator.errors)

        elif not allow_empty and raise_exception:
            raise InvalidParameterError(details="Request body can not be empty")

        logger_data = copy.copy(cleaned_data)

        for user_sensitive_field in ("password", "password_1", "password_2"):
            if user_sensitive_field in logger_data:
                logger_data[user_sensitive_field] = "***"

        self.logger.info(f"Data was validated and normalized: {logger_data}")
        return cleaned_data

    @staticmethod
    def model_to_dict(instance, fields: List[str] = None, exclude: List[str] = None):
        """Serialize model for json-friendly dict"""

        exclude = exclude or []
        field_names = fields or list(instance.__class__._meta.sorted_field_names)  # noqa
        res = {}
        for field in filter(lambda x: x not in exclude, field_names):
            value = getattr(instance, field)
            if isinstance(value, datetime.datetime):
                value = value.isoformat()
            elif isinstance(value, BaseModel):
                value = value.id

            res[field] = value

        return res
