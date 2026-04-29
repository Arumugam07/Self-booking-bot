import os
import shutil
import yaml
from datetime import date, datetime


class selenium_common:

    @staticmethod
    def wait_for_elem(driver, locator_type, locator, timeout=5):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((locator_type, locator))
        )

    @staticmethod
    def is_elem_present(driver, locator_type, locator, timeout=2):
        from selenium.common.exceptions import TimeoutException
        try:
            return selenium_common.wait_for_elem(driver, locator_type, locator, timeout)
        except TimeoutException:
            return False

    @staticmethod
    def dismiss_alert(driver, timeout=2):
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        alert_txt = ""
        try:
            WebDriverWait(driver, timeout).until(EC.alert_is_present())
            alert = driver.switch_to.alert
            if alert:
                alert_txt = alert.text
                alert.accept()
        except Exception as e:
            return False, str(e)
        return True, alert_txt


class utils:

    _DATE_FORMATS = {
        "dd/mm/yyyy":          "%d/%m/%Y",
        "dd-mm-yyyy":          "%d-%m-%Y",
        "ddmmyyyy":            "%d%m%Y",
        "dd/mm/yyyy hh:mm:ss": "%d/%m/%Y %H:%M:%S",
        "dd-mm-yyyy hh:mm:ss": "%d-%m-%Y %H:%M:%S",
        "dd-mm-yyyy hhmmss":   "%d-%m-%Y %H%M%S",
        "ddmmyyyy hhmmss":     "%d%m%Y %H%M%S",
        "yyyymmdd-hhmmss":     "%Y%m%d-%H%M%S",
    }

    @staticmethod
    def load_config_from_yaml_file(file_path):
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"No config file at {file_path}")
        with open(file_path) as f:
            return yaml.safe_load(f) or {}

    @staticmethod
    def init_config_with_default(config, default_config):
        # BUG FIX: original used enumerate() which set values to 0,1,2... instead of defaults
        for key, default_value in default_config.items():
            if key not in config:
                config[key] = default_value
        return config

    @staticmethod
    def concat_tuple(output_tuple):
        return " ".join(str(m) for m in output_tuple)

    @staticmethod
    def clear_directory(directory, log=None):
        if not os.path.isdir(directory):
            return
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                if log:
                    log.error(f"Failed to delete {file_path}: {e}")

    @staticmethod
    def remove_files(files, log=None):
        for file in files:
            if os.path.exists(file):
                try:
                    os.remove(file)
                except Exception as e:
                    if log:
                        log.error(f"Failed to delete {file}: {e}")

    @classmethod
    def get_datetime_now(cls, format_option="ddmmyyyy hhmmss"):
        fmt = cls._DATE_FORMATS.get(format_option, "%d%m%Y %H%M%S")
        return datetime.now().strftime(fmt)

    @classmethod
    def get_date_now(cls, format_option="dd-mm-yyyy"):
        fmt = cls._DATE_FORMATS.get(format_option, "%d-%m-%Y")
        return date.today().strftime(fmt)
