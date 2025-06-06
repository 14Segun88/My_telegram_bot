# email_sender.py
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formatdate, make_msgid, formataddr
import config

logger = logging.getLogger(__name__)

def send_email(recipient_email: str, subject: str, html_body: str, sender_name: str = None) -> bool:
    """
    Отправляет email через Gmail SMTP.
    """
    effective_sender_name = sender_name if sender_name else config.EMAIL_SENDER_NAME
    
    if not all([
        hasattr(config, 'EMAIL_HOST_USER') and config.EMAIL_HOST_USER,
        hasattr(config, 'EMAIL_HOST_PASSWORD') and config.EMAIL_HOST_PASSWORD,
        hasattr(config, 'EMAIL_HOST') and config.EMAIL_HOST,
        hasattr(config, 'EMAIL_PORT') and config.EMAIL_PORT,
        recipient_email,
        html_body
    ]):
        logger.error("send_email: Отсутствуют необходимые конфигурационные данные для отправки email.")
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = formataddr((str(Header(effective_sender_name, 'utf-8')), config.EMAIL_HOST_USER))
    msg['To'] = recipient_email
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid()

    # Убедимся, что html_body это строка
    if not isinstance(html_body, str):
        logger.error(f"html_body не является строкой, а {type(html_body)}. Преобразование в строку.")
        html_body = str(html_body)

    part_html = MIMEText(html_body, 'html', 'utf-8')
    msg.attach(part_html)

    try:
        # Для Gmail используем SMTP с TLS
        server = smtplib.SMTP(config.EMAIL_HOST, config.EMAIL_PORT)
        server.starttls()  # Включаем TLS
        server.login(config.EMAIL_HOST_USER, config.EMAIL_HOST_PASSWORD)
        server.sendmail(config.EMAIL_HOST_USER, [recipient_email], msg.as_string())
        server.quit()
        logger.info(f"Email успешно отправлен на {recipient_email}, тема: {subject}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке email на {recipient_email}: {e}")
        return False