import logging
from typing import Union
from dapr.ext.workflow.logger.options import LoggerOptions


class Logger:
    def __init__(self, name: str, options: Union[LoggerOptions, None] = None):
        # If options is None, then create a new LoggerOptions object
        if options is None:
            options = LoggerOptions()
        log_handler = options.log_handler
        log_handler.setLevel(options.log_level)
        log_handler.setFormatter(options.log_formatter)
        logger = logging.getLogger(name)
        logger.handlers.append(log_handler)
        self._logger_options = options
        self._logger = logger

    def get_options(self) -> LoggerOptions:
        return self._logger_options

    def debug(self, msg, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        self._logger.critical(msg, *args, **kwargs)
