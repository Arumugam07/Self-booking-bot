from urllib.parse import quote
import requests

TIMEOUT = 10


class TelegramBot:
    def __init__(self, token, default_chat_id, log):
        self.token           = token
        self.default_chat_id = str(default_chat_id)
        self.log             = log

    def send_msg(self, msg_subject, msg_body, chat_id=None):
        target = str(chat_id or self.default_chat_id)
        text   = f"<b>{msg_subject}</b>\n{msg_body}" if msg_subject else msg_body
        url = (
            f"https://api.telegram.org/bot{self.token}/sendMessage"
            f"?chat_id={target}"
            f"&text={quote(text)}"
            f"&parse_mode=HTML"
        )
        try:
            resp = requests.get(url, timeout=TIMEOUT)
            if not resp.ok:
                self.log.error(f"Telegram error {resp.status_code}: {resp.text[:200]}")
                return False
            return True
        except requests.RequestException as e:
            self.log.error(f"Telegram request failed: {e}")
            return False
