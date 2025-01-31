class BaseQuadsException(Exception):
    pass


class CliException(BaseQuadsException):
    pass


class APIServerException(Exception):
    pass


class APIBadRequest(Exception):
    pass
