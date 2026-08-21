import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import json

from kraken.config.settings import settings
from kraken.core.logger import logger

class NotificationService:
    """Servicio de notificaciones (Telegram, Slack, Email, Webhook)."""

    def __init__(self):
        self.telegram_bot_token = settings.TELEGRAM_BOT_TOKEN
        self.telegram_chat_id = settings.TELEGRAM_CHAT_ID
        self.slack_webhook_url = settings.SLACK_WEBHOOK_URL
        self.email_smtp_server = settings.EMAIL_SMTP_SERVER
        self.email_smtp_port = settings.EMAIL_SMTP_PORT
        self.email_username = settings.EMAIL_USERNAME
        self.email_password = settings.EMAIL_PASSWORD
        self.email_from = settings.EMAIL_FROM
        self.email_to = settings.EMAIL_TO
        self.webhook_urls = settings.WEBHOOK_URLS

    def send_telegram(self, message: str, parse_mode: str = "HTML") -> bool:
        """Envía un mensaje a Telegram."""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("No se ha configurado TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID")
            return False

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message[:4000],
            "parse_mode": parse_mode
        }

        try:
            response = requests.post(url, data=data, timeout=10)
            if response.status_code == 200:
                logger.debug(f"📤 Notificación Telegram enviada")
                return True
            else:
                logger.error(f"Error enviando a Telegram: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error enviando a Telegram: {e}")
            return False

    def send_slack(self, message: str) -> bool:
        """Envía un mensaje a Slack."""
        if not self.slack_webhook_url:
            logger.warning("No se ha configurado SLACK_WEBHOOK_URL")
            return False

        payload = {
            "text": message,
            "username": "KRAKEN v3.0",
            "icon_emoji": ":shark:"
        }

        try:
            response = requests.post(
                self.slack_webhook_url,
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            if response.status_code == 200:
                logger.debug(f"📤 Notificación Slack enviada")
                return True
            else:
                logger.error(f"Error enviando a Slack: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error enviando a Slack: {e}")
            return False

    def send_email(self, subject: str, body: str, is_html: bool = False) -> bool:
        """Envía un correo electrónico."""
        if not self.email_smtp_server or not self.email_to:
            logger.warning("No se ha configurado EMAIL_SMTP_SERVER o EMAIL_TO")
            return False

        msg = MIMEMultipart()
        msg["From"] = self.email_from or self.email_username
        msg["To"] = ", ".join(self.email_to)
        msg["Subject"] = f"[KRAKEN] {subject}"

        if is_html:
            msg.attach(MIMEText(body, "html"))
        else:
            msg.attach(MIMEText(body, "plain"))

        try:
            if self.email_smtp_port == 465:
                server = smtplib.SMTP_SSL(self.email_smtp_server, self.email_smtp_port)
            else:
                server = smtplib.SMTP(self.email_smtp_server, self.email_smtp_port)
                server.starttls()

            server.login(self.email_username, self.email_password)
            server.send_message(msg)
            server.quit()
            logger.debug(f"📤 Correo electrónico enviado")
            return True
        except Exception as e:
            logger.error(f"Error enviando correo: {e}")
            return False

    def send_webhook(self, payload: Dict) -> bool:
        """Envía un payload a un webhook."""
        if not self.webhook_urls:
            logger.warning("No se han configurado WEBHOOK_URLS")
            return False

        success = True
        for url in self.webhook_urls:
            try:
                response = requests.post(
                    url,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if response.status_code != 200:
                    logger.error(f"Error enviando a webhook {url}: {response.status_code} - {response.text}")
                    success = False
            except Exception as e:
                logger.error(f"Error enviando a webhook {url}: {e}")
                success = False

        if success:
            logger.debug(f"📤 Webhook enviado a {len(self.webhook_urls)} URLs")
        return success

    def send_notification(self, message: str, subject: Optional[str] = None, is_html: bool = False) -> bool:
        """Envía una notificación a todos los canales configurados."""
        results = []

        # Telegram
        if self.telegram_bot_token and self.telegram_chat_id:
            results.append(self.send_telegram(message))

        # Slack
        if self.slack_webhook_url:
            results.append(self.send_slack(message))

        # Email
        if self.email_smtp_server and self.email_to:
            email_subject = subject or "Notificación de KRAKEN"
            results.append(self.send_email(email_subject, message, is_html))

        # Webhooks
        if self.webhook_urls:
            results.append(self.send_webhook({"message": message, "source": "kraken"}))

        return any(results)

    def send_critical_alert(self, title: str, message: str) -> bool:
        """Envía una alerta crítica con formato especial."""
        formatted_message = f"🚨 <b>{title}</b>\n\n{message}\n\n<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
        return self.send_notification(formatted_message, title, is_html=True)

    def send_exploit_alert(self, title: str, message: str) -> bool:
        """Envía una alerta de exploit exitoso."""
        formatted_message = f"💀 <b>{title}</b>\n\n{message}\n\n<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
        return self.send_notification(formatted_message, title, is_html=True)

    def send_scan_report(self, report: Dict) -> bool:
        """Envía un informe de escaneo."""
        summary = report.get("summary", {})
        formatted_message = (
            f"📊 <b>Informe de Escaneo KRAKEN</b>\n\n"
            f"📅 Período: {report.get('start_date')} - {report.get('end_date')}\n"
            f"🖥️  Hosts: {summary.get('total_hosts', 0)}\n"
            f"🔴 Vulns Críticas: {summary.get('vulnerabilities', {}).get('critical', 0)}\n"
            f"🟠 Vulns Altas: {summary.get('vulnerabilities', {}).get('high', 0)}\n"
            f"💀 Exploits: {summary.get('total_exploits', 0)}\n\n"
            f"<code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</code>"
        )
        return self.send_notification(formatted_message, "Informe de Escaneo KRAKEN", is_html=True)
