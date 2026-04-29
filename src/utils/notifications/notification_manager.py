from src.utils.notifications.telegram_bot import TelegramBot


class NotificationManager:
    def __init__(self, log, telegram_config=None, mail_config=None):
        self.log          = log
        self.telegram_bot = None
        self.mail_server  = None  # placeholder if you add email later

        if telegram_config and telegram_config.get("telegram_notification_enabled"):
            self.telegram_bot = TelegramBot(
                token=telegram_config["telegram_bot_token"],
                default_chat_id=telegram_config["telegram_chat_id"],
                log=log,
            )

    def send_notification_all(self, title, msg):
        if self.telegram_bot:
            self.telegram_bot.send_msg(msg_subject=title, msg_body=msg)

    def send_notification_telegram(self, title, msg):
        if self.telegram_bot:
            return self.telegram_bot.send_msg(msg_subject=title, msg_body=msg)
