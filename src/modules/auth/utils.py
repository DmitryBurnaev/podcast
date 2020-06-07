import datetime

import settings
import jwt


def encode_jwt(payload: dict, expiration_seconds: int = 0) -> str:
    """ Allows to get HS512 based JWT token for payload """

    if expiration_seconds:
        payload["exp"] = datetime.datetime.utcnow() + datetime.timedelta(seconds=expiration_seconds)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM).decode()


def decode_jwt(encoded_jwt: str) -> dict:
    """ Allows to decode received JWT token to payload """

    return jwt.decode(encoded_jwt, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
