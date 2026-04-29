import datetime
import os
import random
import re
import sys
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from abstracts.cdc_abstract import CDCAbstract, Types
from src.utils.common import selenium_common


def _jitter(seconds, pct=0.08):
    delta = seconds * pct
    return max(0.0, seconds + random.uniform(-delta, delta))


def _sleep(seconds):
    time.sleep(_jitter(seconds))


def convert_to_datetime(date_str, time_str=None):
    try:
        if time_str:
            ts = time_str.split(" ")[0]
            return datetime.datetime.strptime(f"{date_str} | {ts}", "%d/%b/%Y | %H:%M")
        return datetime.datetime.strptime(date_str, "%d/%b/%Y")
    except ValueError as e:
        raise ValueError(f"Cannot parse date='{date_str}' time='{time_str}': {e}")


class handler(CDCAbstract):

    def __init__(self, login_credentials, captcha_solver, log,
                 notification_manager, browser_config, program_config):

        headless = browser_config.get("headless_mode", False)

        self.home_url    = "https://www.cdc.com.sg"
        self.booking_url = "https://bookingportal.cdc.com.sg:"
        self.port        = ""

        self.captcha_solver       = captcha_solver
        self.log                  = log
        self.notification_manager = notification_manager
        self.browser_config       = browser_config
        self.program_config       = program_config

        self.auto_reserve         = program_config["auto_reserve"]
        self.auto_restart         = program_config["auto_restart"]
        self.reserve_for_same_day = program_config["reserve_for_same_day"]

        self.username  = login_credentials["username"]
        self.password  = login_credentials["password"]
        self.logged_in = False
        self.notification_update_msg = ""
        self.has_slots_reserved      = False

        self.opening_booking_page_callback_map = {
            Types.BTT:       self.open_theory_test_booking_page,
            Types.RTT:       self.open_theory_test_booking_page,
            Types.FTT:       self.open_theory_test_booking_page,
            Types.PRACTICAL: self.open_practical_lessons_booking_page,
            Types.SIMULATOR: self.open_simulator_lessons_booking_page,
            Types.PT:        self.open_practical_test_booking_page,
        }

        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--no-proxy-server")

        executable_path = os.path.join("drivers", "windows", "chromedriver.exe")
        self.driver = webdriver.Chrome(executable_path=executable_path, options=options)
        self.driver.set_window_size(1600, 768)

        super().__init__(username=self.username, password=self.password, headless=headless)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        try:
            self.driver.close()
        except Exception:
            pass

    def __str__(self):
        return super().__str__()

    def _open_index(self, path, sleep_delay=None):
        url = f"{self.booking_url}{self.port}/{path}"
        self.log.debug(f"Opening: {url}")
        self.driver.get(url)
        if sleep_delay:
            _sleep(sleep_delay)

    def reset_state(self):
        self.reset_attributes_for_all_fieldtypes()
        self.notification_update_msg = ""
        self.has_slots_reserved      = False

    def is_date_in_view(self, date_str, field_type):
        return date_str in self.get_attribute_with_fieldtype("days_in_view", field_type)

    def get_earliest_time_slots(self, sessions_data, length, field_type):
        flat = [
            (date_str, ts)
            for date_str, slots in sessions_data.items()
            for ts in slots
        ]
        flat.sort(key=lambda x: convert_to_datetime(x[0], x[1]))

        step   = 2 if field_type == Types.SIMULATOR else 1
        result = {}
        count  = 0
        for i in range(0, len(flat), step):
            if count >= length:
                break
            date_str, ts = flat[i]
            result.setdefault(date_str, []).append(ts)
            count += 1
        return result

    def check_if_same_sessions(self, session0, session1):
        # BUG FIX: original returned True when different, so notifications never fired
        for date_str, slots in session0.items():
            if date_str not in session1:
                return False
            for ts in slots:
                if ts not in session1[date_str]:
                    return False
        for date_str, slots in session1.items():
            if date_str not in session0:
                return False
            for ts in slots:
                if ts not in session0[date_str]:
                    return False
        return True

    def check_call_depth(self, call_depth):
        if call_depth > 4:
            self.account_logout()
            self.account_login()
            return False
        return True

    def check_access_rights(self, webpage):
        if "Alert.aspx" in self.driver.current_url:
            self.log.info(f"No access to {webpage}.")
            return False
        return True

    def check_logged_in(self):
        self._open_index("NewPortal/Booking/StatementBooking.aspx")
        if self.port not in self.driver.current_url:
            self.log.info("Session timed out. Logging back in...")
            self.account_logout()
            self.account_login()
            _sleep(0.5)

    def dismiss_normal_captcha(self, caller_identifier, solve_captcha=False,
                               secondary_alert_timeout=5, force_enabled=False):
        is_present = selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_CaptchaImg", timeout=5
        )
        if not is_present:
            return True

        if solve_captcha:
            success, _ = self.captcha_solver.solve(
                driver=self.driver, captcha_type="normal_captcha", force_enable=force_enabled
            )
            if not success:
                return False
            btn = selenium_common.wait_for_elem(
                self.driver, By.ID, "ctl00_ContentPlaceHolder1_Button1"
            )
            btn.click()
        else:
            close_btn = selenium_common.wait_for_elem(self.driver, By.CLASS_NAME, "close")
            close_btn.click()

        _, alert_text = selenium_common.dismiss_alert(self.driver, timeout=2)
        if "incorrect captcha" in alert_text.lower():
            selenium_common.dismiss_alert(self.driver, timeout=secondary_alert_timeout)
            self.log.info(f"CAPTCHA failed for {caller_identifier}.")
            return False
        return True

    def accept_terms_and_conditions(self):
        checkbox = selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_chkTermsAndCond"
        )
        btn = selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_btnAgreeTerms"
        )
        if checkbox and btn:
            checkbox.click()
            btn.click()

    def get_course_data(self, course_element_id=None):
        course = selenium_common.is_elem_present(
            self.driver, By.ID,
            course_element_id or "ctl00_ContentPlaceHolder1_ddlCourse"
        )
        if not course:
            return False
        sel     = Select(course)
        options = [str(o.text.strip()) for o in sel.options]
        return {"course_selection": sel, "available_courses": options}

    def select_course_from_name(self, course_data, course_name):
        for idx, name in enumerate(course_data["available_courses"]):
            if course_name in name:
                course_data["course_selection"].select_by_index(idx)
                return idx
        return False

    def select_course_from_idx(self, course_data, course_idx):
        courses = course_data["available_courses"]
        if course_idx < 0 or course_idx >= len(courses):
            self.log.error(f"Course index {course_idx} out of range.")
            return False
        course_data["course_selection"].select_by_index(course_idx)
        return courses[course_idx]

    def open_home_page(self, sleep_delay=None):
        self.driver.get(self.home_url)
        if sleep_delay:
            _sleep(sleep_delay)

    def account_login(self, _depth=0):
        if _depth > 5:
            self.log.error("Too many login retries.")
            return False

        self.open_home_page(sleep_delay=2)
        prompt_btn = selenium_common.wait_for_elem(
            self.driver, By.XPATH, "//*[@id='top-menu']/ul/li[10]/a"
        )
        prompt_btn.click()

        id_input  = selenium_common.wait_for_elem(self.driver, By.NAME, "userId")
        pw_input  = selenium_common.wait_for_elem(self.driver, By.NAME, "password")
        id_input.send_keys(self.username)
        pw_input.send_keys(self.password)

        success, _ = self.captcha_solver.solve(driver=self.driver, captcha_type="recaptcha_v2")
        if not success:
            self.log.warning("CAPTCHA failed, retrying login...")
            _sleep(1)
            return self.account_login(_depth + 1)

        login_btn = selenium_common.wait_for_elem(self.driver, By.ID, "BTNSERVICE2")
        login_btn.click()

        _, alert_text = selenium_common.dismiss_alert(self.driver, timeout=5)
        if "complete the captcha" in alert_text.lower():
            self.log.info("Server rejected CAPTCHA, retrying...")
            self.account_logout()
            _sleep(1)
            return self.account_login(_depth + 1)

        url_digits = re.findall(r"\d+", self.driver.current_url)
        if url_digits:
            self.port      = str(url_digits[-1])
            self.logged_in = True
            self.log.info(f"Logged in (port={self.port}).")
            return True

        self.log.warning("Login may have failed, retrying...")
        self.account_logout()
        _sleep(1)
        return self.account_login(_depth + 1)

    def account_logout(self):
        try:
            self._open_index("NewPortal/logOut.aspx?PageName=Logout")
        except Exception:
            pass
        self.log.info("Logged out.")
        self.logged_in = False

    def open_booking_overview(self):
        self.check_logged_in()
        self._open_index("NewPortal/Booking/Dashboard.aspx")
        selenium_common.dismiss_alert(self.driver, timeout=5)

    def _parse_session_rows(self, table_css, field_type_attr):
        rows = self.driver.find_elements(By.CSS_SELECTOR, table_css + " tr")
        for row in rows:
            tds = row.find_elements(By.TAG_NAME, "td")
            if len(tds) < 5:
                continue
            lesson_name = tds[4].text
            field_type = (
                Types.SIMULATOR if "SIMULATOR" in lesson_name else
                Types.PRACTICAL if "AUTOCAR"   in lesson_name else
                Types.PRACTICAL if "2BL"        in lesson_name else
                Types.PRACTICAL if "ONETEAM"   in lesson_name else
                Types.BTT       if "BTT"        in lesson_name else
                Types.RTT       if "RTT"        in lesson_name else
                Types.FTT       if "FTT"        in lesson_name else
                Types.PT        if "PT"         in lesson_name else
                None
            )
            if not field_type:
                continue
            if field_type_attr == "reserved_sessions" and field_type == Types.PRACTICAL:
                continue
            self.set_attribute_with_fieldtype("lesson_name", field_type, lesson_name)
            sessions = self.get_attribute_with_fieldtype(field_type_attr, field_type)
            date_key = tds[0].text
            time_val = f"{tds[2].text[:-3]} - {tds[3].text[:-3]}"
            if date_key not in sessions:
                sessions[date_key] = [time_val]
            elif time_val not in sessions[date_key]:
                sessions[date_key].append(time_val)

    def get_reserved_lesson_date_time(self):
        self._parse_session_rows(
            "table#ctl00_ContentPlaceHolder1_gvReserved", "reserved_sessions"
        )

    def get_booked_lesson_date_time(self):
        self._parse_session_rows(
            "table#ctl00_ContentPlaceHolder1_gvBooked", "booked_sessions"
        )

    def open_field_type_booking_page(self, field_type):
        return self.opening_booking_page_callback_map[field_type](field_type)

    def open_theory_test_booking_page(self, field_type, call_depth=0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingTT.aspx", sleep_delay=1)
        if not self.check_access_rights("BookingTT.aspx"):
            return False
        if not self.dismiss_normal_captcha(f"{field_type.upper()} Booking", solve_captcha=False):
            return self.open_theory_test_booking_page(field_type, call_depth + 1)
        _sleep(0.5)
        self.accept_terms_and_conditions()
        if selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg"
        ):
            self.log.info(f"No available {field_type.upper()} sessions.")
            return False
        name_el   = selenium_common.wait_for_elem(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblResAsmBlyDesc"
        )
        test_name = name_el.text
        return (
            (field_type == Types.BTT and "Basic Theory Test"  in test_name) or
            (field_type == Types.RTT and "Riding Theory Test" in test_name) or
            (field_type == Types.FTT and "Final Theory Test"  in test_name)
        )

    def open_practical_lessons_booking_page(self, field_type, call_depth=0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingPL.aspx", sleep_delay=1)
        if not self.check_access_rights("BookingPL.aspx"):
            return False
        course_data = self.get_course_data()
        if not course_data:
            raise RuntimeError("Could not get course data (hCaptcha?)")
        if len(course_data["available_courses"]) <= 1:
            self.log.warning("No practical courses available.")
            return False
        if not (
            self.select_course_from_name(course_data, "Class 3A Motorcar") or
            self.select_course_from_idx(course_data, 1)
        ):
            return False
        if not self.dismiss_normal_captcha("Practical Lessons Booking", solve_captcha=True):
            return self.open_practical_lessons_booking_page(field_type, call_depth + 1)
        _sleep(2)
        if selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg"
        ):
            self.log.info("No available practical lessons.")
            return False
        return True

    def open_simulator_lessons_booking_page(self, field_type, call_depth=0):
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingSimulator.aspx", sleep_delay=1)
        if not self.check_access_rights("BookingSimulator.aspx"):
            return False
        course_data = self.get_course_data()
        if not course_data:
            raise RuntimeError("Could not get course data (hCaptcha?)")
        if len(course_data["available_courses"]) <= 1:
            return False
        if not (
            self.select_course_from_name(course_data, "Simulator Course - Car (School)") or
            self.select_course_from_idx(course_data, 1)
        ):
            return False
        if not self.dismiss_normal_captcha("Simulator Booking", solve_captcha=True):
            return self.open_simulator_lessons_booking_page(field_type, call_depth + 1)
        _sleep(2)
        if selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg"
        ):
            self.log.info("No available simulator lessons.")
            return False
        return True

    def open_practical_test_booking_page(self, field_type, call_depth=0):
        lesson_name = self.get_attribute_with_fieldtype("lesson_name", Types.PRACTICAL)
        if "REVISION" in lesson_name:
            self.log.info("Practical lessons complete (REVISION detected).")
            return False
        if not self.check_call_depth(call_depth):
            call_depth = 0
        self._open_index("NewPortal/Booking/BookingPT.aspx", sleep_delay=1)
        if not self.check_access_rights("BookingPT.aspx"):
            return False
        if not self.dismiss_normal_captcha("Practical Test Booking", solve_captcha=True):
            return self.open_practical_test_booking_page(field_type, call_depth + 1)
        _sleep(0.5)
        self.accept_terms_and_conditions()
        if selenium_common.is_elem_present(
            self.driver, By.ID, "ctl00_ContentPlaceHolder1_lblFullBookMsg"
        ):
            self.log.info(f"No available {field_type.upper()} sessions.")
            return False
        return True

    def get_all_session_date_times(self, field_type):
        for row in self.driver.find_elements(
            By.CSS_SELECTOR, "table#ctl00_ContentPlaceHolder1_gvLatestav tr"
        ):
            th_cells     = row.find_elements(By.TAG_NAME, "th")
            times_in_view = self.get_attribute_with_fieldtype("times_in_view", field_type)
            days_in_view  = self.get_attribute_with_fieldtype("days_in_view",  field_type)

            for i in range(2, len(th_cells)):
                ts = str(th_cells[i].text).split("\n")[1]
                if ts not in times_in_view:
                    times_in_view.append(ts)

            td_cells = row.find_elements(By.TAG_NAME, "td")
            if td_cells:
                day = td_cells[0].text
                if day not in days_in_view:
                    days_in_view.append(day)

    def get_all_available_sessions(self, field_type, local_tb=None):
        input_elements             = self.driver.find_elements(By.TAG_NAME, "input")
        last_practical_input       = None
        has_booked_lessons_in_view = False

        for elem in input_elements:
            src = elem.get_attribute("src") or ""
            if not any(g in src for g in ("Images1.gif", "Images2.gif", "Images3.gif")):
                continue

            elem_id    = str(elem.get_attribute("id"))
            parts      = elem_id.split("_")
            column     = int(parts[-1][10:]) - 1
            parent_table = elem.find_element(By.XPATH, "../../..")
            parent_row   = elem.find_element(By.XPATH, "../..")
            td_cells     = parent_row.find_elements(By.TAG_NAME, "td")
            tr_rows      = parent_table.find_elements(By.TAG_NAME, "tr")
            th_cells     = tr_rows[0].find_elements(By.TAG_NAME, "th")

            session_date = td_cells[0].text
            start_col    = 4 if field_type == Types.SIMULATOR else 2
            session_time = str(th_cells[column + start_col].text).split("\n")[1]

            web_els = (
                local_tb if local_tb is not None
                else self.get_attribute_with_fieldtype("web_elements_in_view", field_type)
            )
            key = f"{session_date} : {session_time}"
            if key not in web_els:
                web_els[key] = elem_id

            if "Images1.gif" in src:
                available = (
                    local_tb if local_tb is not None
                    else self.get_attribute_with_fieldtype("available_sessions", field_type)
                )
                if field_type in (Types.PRACTICAL, Types.PT, Types.SIMULATOR):
                    last_practical_input = elem
                if session_date not in available:
                    available[session_date] = [session_time]
                elif session_time not in available[session_date]:
                    available[session_date].append(session_time)
            elif "Images3.gif" in src:
                has_booked_lessons_in_view = True

        booked = self.get_attribute_with_fieldtype("booked_sessions", field_type)
        if last_practical_input is None or has_booked_lessons_in_view or booked:
            return

        last_id = last_practical_input.get_attribute("id")
        try:
            self.log.info(f"Probing if user can book {field_type.upper()}...")
            last_practical_input.click()
            WebDriverWait(self.driver, 5).until(EC.alert_is_present())
            alert = self.driver.switch_to.alert
            self.log.warning(f"Cannot book {field_type.upper()}: '{alert.text}'")
            self.set_attribute_with_fieldtype("can_book_next", field_type, False)
            alert.accept()
        except Exception:
            self.driver.find_element(By.ID, last_id).click()
            self.log.info("Probe click reverted.")
            _sleep(2)

    def update_earlier_sessions(self, field_type):
        available = self.get_attribute_with_fieldtype("available_sessions", field_type)
        booked    = self.get_attribute_with_fieldtype("booked_sessions",   field_type)
        earlier   = {}

        if booked:
            for avail_date_str, avail_slots in available.items():
                avail_dt = convert_to_datetime(avail_date_str)
                for booked_date_str in booked:
                    booked_dt = convert_to_datetime(booked_date_str)
                    is_earlier = avail_dt < booked_dt
                    is_same    = self.reserve_for_same_day and avail_dt == booked_dt
                    if (is_earlier or is_same) and avail_date_str not in earlier:
                        earlier[avail_date_str] = list(avail_slots)
        else:
            earlier = dict(available)

        self.set_attribute_with_fieldtype("earlier_sessions", field_type, earlier)

    def create_notification_update(self, field_type):
        earlier  = self.get_attribute_with_fieldtype("earlier_sessions",  field_type)
        booked   = self.get_attribute_with_fieldtype("booked_sessions",   field_type)
        reserved = self.get_attribute_with_fieldtype("reserved_sessions", field_type)

        lines = [
            "\n=======================",
            f"{field_type.upper()} UPDATE",
            "=======================\n",
            "Booked sessions:",
        ]
        for d, slots in booked.items():
            lines.append(d + ":")
            lines.extend(f"  -> {s}" for s in slots)
        lines += ["\nReserved sessions:"]
        for d, slots in reserved.items():
            self.has_slots_reserved = True
            lines.append(d + ":")
            lines.extend(f"  -> {s}" for s in slots)
        lines += ["\nAvailable earlier sessions:"]
        for d, slots in earlier.items():
            lines.append(d + ":")
            lines.extend(f"  -> {s}" for s in slots)
            lines.append("")

        msg = "\n".join(lines)
        self.notification_update_msg += msg
        return msg

    def flush_notification_update(self):
        if self.notification_update_msg:
            self.notification_manager.send_notification_all(
                title=str(datetime.datetime.now()),
                msg=self.notification_update_msg,
            )
            if self.has_slots_reserved:
                self.notification_manager.send_notification_all(
                    title="RESERVED SLOTS DETECTED",
                    msg="You have reserved slots! Log in to CDC to confirm them before they expire.",
                )
        self.reset_state()

    def check_if_earlier_available_sessions(self, field_type):
        self.update_earlier_sessions(field_type)

        available = self.get_attribute_with_fieldtype("available_sessions",      field_type)
        web_els   = self.get_attribute_with_fieldtype("web_elements_in_view",    field_type)
        earlier   = self.get_attribute_with_fieldtype("earlier_sessions",        field_type)
        reserved  = self.get_attribute_with_fieldtype("reserved_sessions",       field_type)
        cached    = self.get_attribute_with_fieldtype("cached_earlier_sessions", field_type)

        if self.check_if_same_sessions(cached, earlier):
            return False  # nothing new

        n_slots = self.program_config["slots_per_type"][field_type]

        if self.auto_reserve and n_slots > 0:
            # Step 1: unreserve slots that are no longer earliest
            to_remove = {}
            for res_date_str, res_slots in list(reserved.items()):
                if not self.is_date_in_view(res_date_str, field_type):
                    n_slots -= len(res_slots)
                    continue
                res_dt        = convert_to_datetime(res_date_str)
                keep_reserved = False
                for early_date_str in self.get_earliest_time_slots(earlier, n_slots, field_type):
                    if res_dt <= convert_to_datetime(early_date_str):
                        n_slots -= len(res_slots)
                        keep_reserved = True
                        break
                if not keep_reserved:
                    to_remove[res_date_str] = []
                    for ts in res_slots:
                        elem_id = web_els.get(f"{res_date_str} : {ts}")
                        if not elem_id:
                            continue
                        elem = selenium_common.wait_for_elem(self.driver, By.ID, elem_id)
                        elem.click()
                        alert_found, alert_text = selenium_common.dismiss_alert(
                            self.driver, timeout=10
                        )
                        if alert_found:
                            self.log.error(f"Failed to unreserve {res_date_str} {ts}: {alert_text}")
                            n_slots -= 1
                        else:
                            to_remove[res_date_str].append(ts)

            for d, slots in to_remove.items():
                available.setdefault(d, [])
                for ts in slots:
                    reserved[d].remove(ts)
                    available[d].append(ts)
                if not reserved[d]:
                    del reserved[d]

            # Step 2: reserve earliest available slots
            if n_slots > 0:
                targets   = self.get_earliest_time_slots(earlier, n_slots, field_type)
                stop_outer = False
                for date_str, slots in targets.items():
                    if stop_outer:
                        break
                    for ts in slots:
                        key     = f"{date_str} : {ts}"
                        elem_id = web_els.get(key)
                        if not elem_id:
                            continue
                        elem = selenium_common.wait_for_elem(self.driver, By.ID, elem_id)
                        elem.click()
                        self.log.info(f"Attempting to reserve {field_type.upper()} {date_str} {ts}...")

                        alert_found, alert_text = selenium_common.dismiss_alert(
                            self.driver, timeout=10
                        )
                        if alert_found and "non-computerised" in alert_text:
                            alert_found, alert_text = selenium_common.dismiss_alert(
                                self.driver, timeout=10
                            )

                        if alert_found:
                            self.log.error(f"Reservation failed {date_str} {ts}: {alert_text}")
                            fatal = ["Store Value:", "before", "exceeded the maximum number"]
                            if any(k in alert_text for k in fatal):
                                stop_outer = True
                                break
                            if "Back to Back session is not allowed" in alert_text:
                                continue
                        else:
                            reserved.setdefault(date_str, []).append(ts)
                            available[date_str].remove(ts)
                            if not available[date_str]:
                                del available[date_str]
                            self.log.info(f"Reserved {field_type.upper()} {date_str} {ts}.")

        self.set_attribute_with_fieldtype("reserved_sessions",      field_type, reserved)
        self.set_attribute_with_fieldtype("available_sessions",     field_type, available)
        self.update_earlier_sessions(field_type)
        self.set_attribute_with_fieldtype(
            "cached_earlier_sessions", field_type,
            dict(self.get_attribute_with_fieldtype("earlier_sessions", field_type))
        )
        notif_msg = self.create_notification_update(field_type)
        self.log.info(f"Earlier {field_type.upper()} sessions found:\n{notif_msg}")
        return True
