import logging
import os
import sys

FORMATTER = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_CONFIG = {
    "log_level":                 2,
    "print_log_to_output":       True,
    "write_log_to_file":         True,
    "clear_logs_init":           False,
    "appends_stack_call_to_log": False,
    "save_solved_captchas":      False,
}


class Log:
    def __init__(self, directory, name="cdc-bot", config=None):
        cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.config    = cfg
        self.directory = directory
        self.name      = name

        os.makedirs(directory, exist_ok=True)

        if cfg.get("save_solved_captchas"):
            os.makedirs("solved_captchas", exist_ok=True)

        log = logging.getLogger(name)
        log.handlers.clear()

        if cfg.get("print_log_to_output", True):
            sh = logging.StreamHandler(sys.stdout)
            sh.setFormatter(FORMATTER)
            log.addHandler(sh)

        if cfg.get("write_log_to_file", True):
            from src.utils.common import utils
            log_path = os.path.join(
                directory,
                f"tracker_{utils.get_datetime_now('yyyymmdd-hhmmss')}.log"
            )
            fh = logging.FileHandler(log_path)
            fh.setFormatter(FORMATTER)
            log.addHandler(fh)

        log.setLevel(int(cfg.get("log_level", 2)) * 10)
        self.logger = log

    def _log(self, fn, *output):
        msg = " ".join(str(o) for o in output)
        fn(msg)

    def info(self, *output):    self._log(self.logger.info,    *output)
    def debug(self, *output):   self._log(self.logger.debug,   *output)
    def error(self, *output):   self._log(self.logger.error,   *output)
    def warning(self, *output): self._log(self.logger.warning, *output)

    def info_if(self, condition, *output):
        if condition: self.info(*output)
    def debug_if(self, condition, *output):
        if condition: self.debug(*output)
    def error_if(self, condition, *output):
        if condition: self.error(*output)
    def warning_if(self, condition, *output):
        if condition: self.warning(*output)
