import base64
import os
import time
import traceback

from selenium.webdriver.common.by import By
from twocaptcha import TwoCaptcha as _TwoCaptchaClient
from twocaptcha.api import ApiException, NetworkException
from twocaptcha.solver import TimeoutException

from src.utils.common import selenium_common, utils

DEFAULT_CONFIG = {
    "api_key":     None,
    "enabled":     True,
    "debug_mode":  True,
    "max_retries": 2,
}


class Captcha:
    def __init__(self, log, config=None):
        cfg = utils.init_config_with_default(dict(config or {}), DEFAULT_CONFIG)
        self.solver        = _TwoCaptchaClient(apiKey=cfg["api_key"])
        self.log           = log
        self.enabled       = cfg["enabled"]
        self.debug_enabled = cfg["debug_mode"]
        self.max_retries   = int(cfg.get("max_retries", 2))

    def _solve_captcha(self, solve_callback, result_callback, debug_enabled, attempts=1):
        last = (False, "NOT_ATTEMPTED", None)
        for attempt in range(1, attempts + 1):
            try:
                api_result = solve_callback()
                self.log.debug_if(debug_enabled, f"[2captcha] attempt {attempt}: got response")
                result_callback(api_result)
                last = (True, "SOLVED", api_result)
                break
            except TimeoutException as e:
                self.log.debug_if(debug_enabled, f"[2captcha] attempt {attempt}: TIMEOUT")
                last = (False, "TIMEOUT", e)
            except NetworkException as e:
                self.log.debug_if(debug_enabled, f"[2captcha] attempt {attempt}: NETWORK_ERROR")
                last = (False, "NETWORK_ERROR", e)
            except ApiException as e:
                self.log.debug_if(debug_enabled, f"[2captcha] attempt {attempt}: API_ERROR - {e}")
                last = (False, "API_ERROR", e)
                break  # API errors won't recover on retry
            except Exception as e:
                self.log.error(e)
                self.log.error(traceback.format_exc())
                last = (False, "UNKNOWN_ERROR", e)
                break
            if attempt < attempts:
                self.log.debug_if(debug_enabled, "[2captcha] retrying in 3s...")
                time.sleep(3)
        self.log.debug_if(debug_enabled, f"[2captcha] result: {last}")
        return last

    def save_captcha(self, driver, captcha_image_filepath):
        captcha_element = selenium_common.is_elem_present(
            driver, By.ID, "ctl00_ContentPlaceHolder1_CaptchaImg"
        )
        captcha_input = selenium_common.is_elem_present(
            driver, By.ID, "ctl00_ContentPlaceHolder1_txtVerificationCode"
        )
        if captcha_element and captcha_input:
            src = captcha_element.get_attribute("src") or ""
            b64 = src[23:] if src.startswith("data:") else src
            os.makedirs(os.path.dirname(captcha_image_filepath) or ".", exist_ok=True)
            with open(captcha_image_filepath, "wb") as f:
                f.write(base64.decodebytes(b64.encode()))
            return captcha_input
        return False

    def normal_captcha(self, driver, page_url, debug_enabled):
        path = os.path.join("temp", "normal_captcha.jpeg")
        captcha_input = self.save_captcha(driver, path)
        if not captcha_input:
            return False, "NO_CAPTCHA_FOUND", page_url

        success, status, msg = self._solve_captcha(
            solve_callback=lambda: self.solver.normal(
                path, caseSensitive=1, minLength=6, maxLength=6
            ),
            result_callback=lambda r: captcha_input.send_keys(str(r["code"])),
            debug_enabled=debug_enabled,
            attempts=self.max_retries,
        )
        if self.log.config.get("save_solved_captchas") and success:
            os.rename(path, os.path.join("solved_captchas", f"{msg['code']}.jpeg"))
        else:
            utils.remove_files([path])
        return success, status, msg

    def recaptcha_v2(self, driver, page_url, debug_enabled):
        site_key_element = selenium_common.is_elem_present(
            driver, By.CSS_SELECTOR, "[data-sitekey]"
        )
        if not site_key_element:
            return False, "NO_RECAPTCHA_V2_FOUND", page_url

        site_key = site_key_element.get_attribute("data-sitekey")
        return self._solve_captcha(
            solve_callback=lambda: self.solver.recaptcha(sitekey=site_key, url=page_url),
            result_callback=lambda r: driver.execute_script(
                f"document.querySelector('[name=\"g-recaptcha-response\"]').innerText='{r['code']}'"
            ),
            debug_enabled=debug_enabled,
            attempts=self.max_retries,
        )

    def solve(self, driver, captcha_type=None, page_url=None, force_enable=False, force_debug=False):
        t_start       = time.perf_counter()
        page_url      = page_url or driver.current_url
        captcha_type  = (captcha_type or "recaptcha_v2").lower()
        debug_enabled = self.debug_enabled or force_debug

        if self.enabled or force_enable:
            self.log.debug_if(debug_enabled, f"Solving {captcha_type.upper()} for: {page_url}")
            if captcha_type == "recaptcha_v2":
                success, status, msg = self.recaptcha_v2(driver, page_url, debug_enabled)
            elif captcha_type == "normal_captcha":
                success, status, msg = self.normal_captcha(driver, page_url, debug_enabled)
            else:
                return False, f"UNKNOWN_CAPTCHA_TYPE:{captcha_type}"

            if success:
                self.log.debug_if(
                    debug_enabled,
                    f"Solved in {time.perf_counter() - t_start:.1f}s"
                )
            return success, f"{status}: {msg}"

        # Manual mode
        self.log.debug_if(debug_enabled, f"Manual CAPTCHA needed for: {page_url}")
        input("Solve the CAPTCHA in the browser, then press ENTER: ")
        return True, "MANUALLY_SOLVED"
