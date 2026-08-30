# -*- coding: utf-8 -*-
"""
独立推送模块 - 供日报/周报共用
支持：本地保存 + 钉钉推送（含加签） + 邮件推送
"""

import os
import datetime
import requests
import smtplib
import hmac
import hashlib
import base64
import urllib.parse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置 ====================
BASE_PATH = r"D:\MyProject\house_data_RAG"

DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
DINGTALK_SECRET = os.getenv("DINGTALK_SECRET", "")

EMAIL_CONFIG = {
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.qq.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", 465)),
    "sender": os.getenv("EMAIL_SENDER", ""),
    "password": os.getenv("EMAIL_PASSWORD", ""),
    "receiver": os.getenv("EMAIL_RECEIVER", "")
}


def save_locally(content, report_type="日报"):
    output_dir = os.path.join(BASE_PATH, "1_data", "reports")
    os.makedirs(output_dir, exist_ok=True)
    today = datetime.datetime.now().strftime('%Y%m%d')
    report_file = os.path.join(output_dir, f"{report_type}_{today}.md")
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"# 珠三角{report_type}\n\n")
        f.write(f"**生成时间：** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("---\n\n")
        f.write(content)
    print("本地保存：" + report_file)
    return report_file


def send_dingtalk(content, report_type="日报"):
    if not DINGTALK_WEBHOOK:
        print("跳过钉钉推送（未配置 Webhook）")
        return False

    try:
        if DINGTALK_SECRET:
            timestamp = str(round(datetime.datetime.now().timestamp() * 1000))
            secret_enc = DINGTALK_SECRET.encode('utf-8')
            string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
            string_to_sign_enc = string_to_sign.encode('utf-8')
            hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode('utf-8'))
            webhook_url = f"{DINGTALK_WEBHOOK}&timestamp={timestamp}&sign={sign}"
        else:
            webhook_url = DINGTALK_WEBHOOK

        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"珠三角{report_type} {datetime.datetime.now().strftime('%Y-%m-%d')}",
                "text": f"## 珠三角{report_type}\n\n{content}\n\n---\n*生成时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
            }
        }
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('errcode') == 0:
                print("钉钉推送成功")
                return True
            else:
                print("钉钉推送失败：" + result.get('errmsg', ''))
                return False
        else:
            print("钉钉推送失败：" + str(response.status_code))
            return False
    except Exception as e:
        print("钉钉推送异常：" + str(e))
        return False


def send_email(content, report_type="日报"):
    if not EMAIL_CONFIG.get("sender") or not EMAIL_CONFIG.get("password"):
        print("跳过邮件推送（未配置邮箱）")
        return False

    try:
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        subject = f"珠三角{report_type} {today}"

        html_content = f"""
        <html>
        <head><meta charset="UTF-8"></head>
        <body>
            <h2>珠三角{report_type}</h2>
            <p><b>生成时间：</b>{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <hr>
            <div style="white-space: pre-wrap; font-size: 14px; line-height: 1.8;">
                {content.replace('\n', '<br>')}
            </div>
            <hr>
            <p style="color: #999; font-size: 12px;">此邮件由珠三角房产智能问答系统自动生成。</p>
        </body>
        </html>
        """

        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = EMAIL_CONFIG['sender']
        msg['To'] = EMAIL_CONFIG['receiver']

        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)

        with smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port']) as server:
            server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            server.sendmail(EMAIL_CONFIG['sender'], EMAIL_CONFIG['receiver'].split(','), msg.as_string())

        print("邮件推送成功 -> " + EMAIL_CONFIG['receiver'])
        return True
    except Exception as e:
        print("邮件推送失败：" + str(e))
        return False


def push_report(content, report_type="日报"):
    print("\n开始推送" + report_type + "...")
    save_locally(content, report_type)
    send_dingtalk(content, report_type)
    send_email(content, report_type)
    print(report_type + "推送完成")


def push_daily_report(content):
    push_report(content, "日报")


def push_weekly_report(content):
    push_report(content, "周报")