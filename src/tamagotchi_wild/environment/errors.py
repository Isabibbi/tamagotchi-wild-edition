

class EnvironmentError(Exception):
    pass


class DuplicateEntityError(EnvironmentError):
    pass


class UnknownEntityError(EnvironmentError):
    pass


class InvalidActionError(EnvironmentError):
    pass
