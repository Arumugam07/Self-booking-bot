import datetime
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.website_handler.handler import handler
from src.utils.common import utils
from src.utils.log import Log
from src.utils.captcha.two_captcha import Captcha as TwoCaptcha
from src.utils.notifications.notification_manager import NotificationManager


def _jitter(base, pct=0.05):
    return max(0.0, base + random.uniform(-base * pct, base * pct))


def _sleep_with_keepalive(total_seconds, cdc_handler, log, chunk=60.0):
    remaining = total_seconds
    while remaining > chunk:
        time.sleep(_jitter(chunk))
        remaining -= chunk
        cdc_handler.check_logged_in()
    if remaining > 0:
        time.sleep(_jitter(remaining))


def main():
    config         = utils.load_config_from_yaml_file("config.yaml")
    program_config = config["program_config"]

    log = Log(directory="logs", name="cdc-bot", config=config.get("log_config"))
    log.info("=" * 60)
    log.info("CDC BOT STARTING")
    log.info("=" * 60)

    captcha_solver       = TwoCaptcha(log=log, config=config["two_captcha_config"])
    notification_manager = NotificationManager(
        log=log,
        telegram_config=config.get("telegram_config"),
    )

    os.makedirs("temp", exist_ok=True)
    utils.clear_directory("temp", log)

    restart_delay_hours = float(program_config.get("restart_delay_hours", 1))

    while True:
        with handler(
            login_credentials=config["cdc_login_credentials"],
            captcha_solver=captcha_solver,
            log=log,
            notification_manager=notification_manager,
            browser_config=config["browser_config"],
            program_config=program_config,
        ) as cdc_handler:

            cdc_handler.account_login()
            monitored_types = program_config["monitored_types"]

            try:
                while True:
                    cdc_handler.open_booking_overview()
                    cdc_handler.get_booked_lesson_date_time()
                    cdc_handler.get_reserved_lesson_date_time()

                    for monitor_type, active in monitored_types.items():
                        if not active:
                            continue
                        if cdc_handler.open_field_type_booking_page(field_type=monitor_type):
                            cdc_handler.get_all_session_date_times(field_type=monitor_type)
                            cdc_handler.get_all_available_sessions(field_type=monitor_type)
                            cdc_handler.check_if_earlier_available_sessions(field_type=monitor_type)

                    log.info(str(cdc_handler))
                    cdc_handler.flush_notification_update()

                    refresh_rate = program_config.get("refresh_rate", 0)
                    if refresh_rate <= 0:
                        break

                    now           = datetime.datetime.now()
                    sleep_secs    = _jitter(refresh_rate)
                    next_run_time = now + datetime.timedelta(seconds=sleep_secs)

                    if 3 <= next_run_time.hour < 6:
                        extra = next_run_time.replace(hour=6, minute=0, second=0) - next_run_time
                        sleep_secs += extra.total_seconds()

                    log.info(f"Sleeping {sleep_secs:.0f}s, next check at {now + datetime.timedelta(seconds=sleep_secs):%H:%M:%S}")
                    _sleep_with_keepalive(sleep_secs, cdc_handler, log)
                    log.info("Resuming...")

            except KeyboardInterrupt:
                log.info("Stopped by user.")
            except Exception as exc:
                log.error(f"Unhandled error: {exc}")
                notification_manager.send_notification_all(title="CDC Bot Error", msg=str(exc))
            finally:
                cdc_handler.account_logout()

                if not program_config.get("auto_restart", False):
                    break

                delay      = datetime.timedelta(hours=restart_delay_hours)
                restart_at = datetime.datetime.now() + delay
                msg = f"Restarting at {restart_at:%H:%M:%S}..."
                log.info(msg)
                notification_manager.send_notification_all(title="CDC Bot Restart", msg=msg)
                time.sleep(delay.total_seconds())

    log.info("CDC Bot exited.")


if __name__ == "__main__":
    main()
