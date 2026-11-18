class AppError(Exception):
    def __init__(self, status: int, message: str, extra=None):
        self.status = status
        self.message = message
        self.extra = extra or {}
        super().__init__(message)
