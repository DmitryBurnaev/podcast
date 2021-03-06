class BaseApplicationError(Exception):
    message = "Something went wrong"
    details = None
    status_code = 500

    def __init__(self, message=None, details=None):
        self.message = message or self.message
        self.details = details or self.details


class AuthenticationFailedError(BaseApplicationError):
    status_code = 401
    message = "Authentication credentials are invalid"


class AuthenticationRequiredError(BaseApplicationError):
    status_code = 401
    message = "Authentication is required"


class InviteTokenInvalidationError(BaseApplicationError):
    status_code = 401
    message = "Requested token is expired or does not exist"


class InvalidParameterError(BaseApplicationError):
    status_code = 400
    message = "Input data is invalid"


class Forbidden(BaseApplicationError):
    status_code = 403
    message = "You don't have permission to perform this action"


class YoutubeFetchError(Exception):
    ...


class SendRequestError(BaseApplicationError):
    status_code = 503
    message = "Got unexpected error for sending request"
    request_url = ""
    response_status = None

    def __init__(self, message: str, details: str, request_url: str, response_status: int):
        super().__init__(message, details)
        self.response_status = response_status
        self.request_url = request_url
