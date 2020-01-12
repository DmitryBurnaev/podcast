class BaseApplicationError(Exception):
    message = "Something went wrong"
    details = None
    status_code = 500

    def __init__(self, message=None, details=None):
        self.message = message or self.message
        self.details = details or self.details


class NotAuthenticatedError(BaseApplicationError):
    status_code = 401
    message = "User or password invalid"


class InvalidParameterError(BaseApplicationError):
    status_code = 400
    message = "Input data is invalid"


class YoutubeFetchError(Exception):
    ...
