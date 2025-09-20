import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from aiogram import Bot
from aiogram.types import Message
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройки email
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# Настройки Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Инициализация логгера
logger = logging.getLogger(__name__)

async def send_email_notification(subject: str, body: str):
    """
    Отправка уведомления по email.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_USER
        msg["To"] = ADMIN_EMAIL
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent to {ADMIN_EMAIL}: {subject}")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")


async def send_telegram_notification(message: str):
    """
    Отправка уведомления в Telegram.
    """
    try:
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(f"Telegram message sent to chat ID: {TELEGRAM_CHAT_ID}")
    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")


async def send_low_balance_alert(balance: float, threshold: float = 10.0):
    """
    Отправка уведомления о низком балансе.
    """
    subject = f"⚠️ Низкий баланс: {balance:.2f} (порог: {threshold})"
    body = f"Баланс системы опустился до {balance:.2f}, что ниже порога в {threshold}. Пожалуйста, пополните баланс."

    # Отправляем по email
    await send_email_notification(subject, body)

    # Отправляем в Telegram
    await send_telegram_notification(body)
