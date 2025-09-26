from bot.config_loader import load_config
import smtplib
from email.mime.text import MIMEText
import requests

def notify_email(subject: str, body: str):
    cfg = load_config()
    em = cfg.get("notifications", {}).get("email", {})
    if not em.get("enabled", False):
        return
    server = em.get("smtp_server")
    port = em.get("smtp_port")
    sender = em.get("sender")
    pwd = em.get("password")
    recips = em.get("recipients", [])
    if not (server and sender and pwd and recips):
        print("⚠️ Email config incomplete")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recips)
    try:
        smtp = smtplib.SMTP(server, port, timeout=10)
        smtp.starttls()
        smtp.login(sender, pwd)
        smtp.sendmail(sender, recips, msg.as_string())
        smtp.quit()
    except Exception as e:
        print("Email notify failed:", e)

def notify_telegram(text: str):
    cfg = load_config()
    tg = cfg.get("notifications", {}).get("telegram", {})
    if not tg.get("enabled", False):
        return
    token = tg.get("bot_token")
    chat = tg.get("chat_id")
    if not (token and chat):
        print("⚠️ Telegram config incomplete")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram notify failed:", e)
