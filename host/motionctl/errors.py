"""motionctl 项目异常与稳定退出码。"""

EXIT_SUCCESS = 0
EXIT_RUNTIME = 1
EXIT_USAGE = 2
EXIT_CONNECTION = 3
EXIT_PROTOCOL = 4
EXIT_COMMAND = 5
EXIT_VALIDATION = 6
EXIT_REPORT = 7


class MotionCtlError(RuntimeError):
    exit_code = EXIT_RUNTIME


class ConnectionError(MotionCtlError):
    exit_code = EXIT_CONNECTION


class ProtocolError(MotionCtlError):
    exit_code = EXIT_PROTOCOL


class CommandError(MotionCtlError):
    exit_code = EXIT_COMMAND

    def __init__(self, message: str, *, status: int | None = None,
                 detail: int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.detail = detail


class RequestTimeout(ConnectionError):
    pass


class ValidationError(MotionCtlError):
    exit_code = EXIT_VALIDATION


class ReportError(MotionCtlError):
    exit_code = EXIT_REPORT
