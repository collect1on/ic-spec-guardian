import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
load_dotenv()



SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")

# 郵件設定
FROM_ADDR = os.getenv("FROM_ADDR")
TO_ADDR = os.getenv("TO_ADDR")



def send_failure_email():
    msg = MIMEMultipart()
    msg["From"]    = FROM_ADDR
    msg["To"]      = TO_ADDR
    msg["Subject"] = f"[IC Spec Guardian] 審查失敗通知"

    body = """
🔔 IC Spec Guardian 審查流程通知

有項目需要人工 Review，請登入系統確認。

謝謝。
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_ADDR, TO_ADDR, msg.as_string())
        print(f"   📧 失敗通知已寄送至 {TO_ADDR}")
    except Exception as e:
        print(f"   ❌ 郵件寄送失敗：{e}")
        
# 接續上方 notifier.py

def send_success_email():
    """寄送「審核完成」通知信（無參數版本）"""
    msg = MIMEMultipart()
    msg["From"]    = FROM_ADDR
    msg["To"]      = TO_ADDR
    msg["Subject"] = "[IC Spec Guardian] 審核完成通知"

    body = """
✅ IC Spec Guardian 審查流程通知

所有章節已自動判斷通過，無需人工介入。
報告已自動生成，請查收。

謝謝。
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_ADDR, TO_ADDR, msg.as_string())
        print("   📧 審核完成通知已寄出")
    except Exception as e:
        print(f"   ❌ 郵件寄送失敗：{e}")