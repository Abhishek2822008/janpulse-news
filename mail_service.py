import os
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app

logger = logging.getLogger(__name__)

RESET_SALT = 'janpulse-password-reset-salt'
TOKEN_MAX_AGE = 900  # 15 minutes in seconds

def generate_reset_token(user_id: int) -> str:
    """Generates a secure, time-limited cryptographic token for password reset."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps({'user_id': user_id}, salt=RESET_SALT)

def verify_reset_token(token: str, max_age: int = TOKEN_MAX_AGE) -> int | None:
    """
    Verifies a reset token. Returns user_id if valid and not expired; else None.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        data = serializer.loads(token, salt=RESET_SALT, max_age=max_age)
        return data.get('user_id')
    except (SignatureExpired, BadSignature) as e:
        logger.warning(f"[MailService] Token verification failed: {e}")
        return None

def send_password_reset_email(to_email: str, user_name: str, reset_url: str) -> dict:
    """
    Sends a password reset email via SMTP.
    If SMTP credentials are not configured, prints the reset link to console for local testing.
    """
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(current_app.config.get('MAIL_PORT', 587))
    mail_use_tls = current_app.config.get('MAIL_USE_TLS', True)
    mail_username = str(current_app.config.get('MAIL_USERNAME', '')).strip().strip('"').strip("'")
    mail_password = str(current_app.config.get('MAIL_PASSWORD', '')).strip().strip('"').strip("'")
    mail_sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'JanPulse News <noreply@janpulse.com>')

    # If empty in config, reload from .env dynamically
    if not mail_username or not mail_password:
        from dotenv import load_dotenv
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            mail_username = os.environ.get('MAIL_USERNAME', '').strip().strip('"').strip("'")
            mail_password = os.environ.get('MAIL_PASSWORD', '').strip().strip('"').strip("'")
            if os.environ.get('MAIL_DEFAULT_SENDER'):
                mail_sender = os.environ.get('MAIL_DEFAULT_SENDER').strip().strip('"').strip("'")

    # 1. Fallback for Local Development / Testing without SMTP setup
    if not mail_username or not mail_password:
        msg = f"[JanPulse Dev Mode] SMTP credentials not set. Password Reset Link for {to_email} ({user_name}): {reset_url}"
        print("=" * 80)
        print(msg)
        print("=" * 80)
        return {'success': True, 'mode': 'dev_console', 'reset_url': reset_url}

    # 2. Build HTML and Plain Text Email
    subject = "JanPulse | Password Reset Request / पासवर्ड रीसेट लिंक"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
            .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; }}
            .header {{ background-color: #0B192C; padding: 24px; text-align: center; }}
            .logo {{ color: #ffffff; font-size: 22px; font-weight: 900; letter-spacing: 0.5px; }}
            .logo span {{ color: #E11D48; }}
            .body {{ padding: 32px 24px; }}
            .greeting {{ font-size: 18px; font-weight: bold; margin-bottom: 12px; color: #0f172a; }}
            .text {{ font-size: 14px; line-height: 1.6; color: #475569; margin-bottom: 20px; }}
            .btn-wrapper {{ text-align: center; margin: 30px 0; }}
            .btn {{ display: inline-block; background-color: #E11D48; color: #ffffff !important; padding: 12px 28px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 14px; box-shadow: 0 4px 6px -1px rgba(225, 29, 72, 0.2); }}
            .btn:hover {{ background-color: #BE123C; }}
            .warning {{ background-color: #fff1f2; border-left: 4px solid #E11D48; padding: 12px; border-radius: 4px; font-size: 12px; color: #9f1239; margin-bottom: 20px; }}
            .footer {{ background-color: #f1f5f9; padding: 16px 24px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">JAN<span>PULSE</span></div>
                <div style="color: #94a3b8; font-size: 11px; margin-top: 4px;">Voice of the People | जन आवाज़</div>
            </div>
            <div class="body">
                <div class="greeting">नमस्ते / Hello, {user_name}!</div>
                <div class="text">
                    Aapke JanPulse account ke liye password reset karne ki request prapt hui hai.<br>
                    We received a request to reset your JanPulse account password.
                </div>
                <div class="btn-wrapper">
                    <a href="{reset_url}" target="_blank" class="btn">Reset Password / पासवर्ड रीसेट करें</a>
                </div>
                <div class="warning">
                    ⏱️ <strong>Note:</strong> Yeh link agle <strong>15 minute</strong> tak hi valid hai.<br>
                    This secure password reset link expires in 15 minutes.
                </div>
                <div class="text" style="font-size: 12px; color: #64748b;">
                    Agar aapne yeh request nahi ki hai, to is email ko ignore karein. Aapka password surakshit rahega.<br>
                    If you did not request a password reset, please ignore this email.
                </div>
                <div class="text" style="font-size: 11px; word-break: break-all; color: #94a3b8;">
                    Button kaam na kare to is link ko browser me paste karein:<br>
                    {reset_url}
                </div>
            </div>
            <div class="footer">
                &copy; 2026 JanPulse News Network Ltd. All rights reserved.<br>
                This is an automated system notification.
            </div>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
JanPulse | Password Reset Request
---------------------------------------
Hello {user_name},

We received a request to reset your JanPulse password.
Please click the link below (valid for 15 minutes):

{reset_url}

If you did not request this, you can safely ignore this email.

---
JanPulse Media Network
    """

    try:
        from_display = f"JanPulse News <{mail_username}>" if mail_username else mail_sender
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_display
        msg['To'] = to_email

        msg.attach(MIMEText(plain_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if mail_use_tls:
            server.starttls()
        server.login(mail_username, mail_password)
        envelope_from = mail_username if mail_username else mail_sender
        server.sendmail(envelope_from, [to_email], msg.as_string())
        server.quit()
        logger.info(f"[MailService] Password reset email sent successfully to {to_email}")
        return {'success': True, 'mode': 'smtp_sent'}
    except Exception as e:
        logger.error(f"[MailService] Failed to send email via SMTP: {e}")
        return {'success': False, 'error': str(e)}

def generate_otp_code() -> str:
    """Generates a secure 6-digit numeric OTP."""
    import secrets
    return f"{secrets.randbelow(900000) + 100000}"

def send_password_reset_otp_email(to_email: str, user_name: str, otp_code: str) -> dict:
    """
    Sends a 6-digit OTP email for password reset via SMTP.
    If SMTP credentials are not configured, prints OTP to console for local testing.
    """
    mail_server = current_app.config.get('MAIL_SERVER', 'smtp.gmail.com')
    mail_port = int(current_app.config.get('MAIL_PORT', 587))
    mail_use_tls = current_app.config.get('MAIL_USE_TLS', True)
    mail_username = str(current_app.config.get('MAIL_USERNAME', '')).strip().strip('"').strip("'")
    mail_password = str(current_app.config.get('MAIL_PASSWORD', '')).strip().strip('"').strip("'")
    mail_sender = current_app.config.get('MAIL_DEFAULT_SENDER', 'JanPulse News <noreply@janpulse.com>')

    # If empty in config, reload from .env dynamically
    if not mail_username or not mail_password:
        from dotenv import load_dotenv
        env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
        if os.path.exists(env_file):
            load_dotenv(env_file, override=True)
            mail_username = os.environ.get('MAIL_USERNAME', '').strip().strip('"').strip("'")
            mail_password = os.environ.get('MAIL_PASSWORD', '').strip().strip('"').strip("'")
            if os.environ.get('MAIL_DEFAULT_SENDER'):
                mail_sender = os.environ.get('MAIL_DEFAULT_SENDER').strip().strip('"').strip("'")

    # 1. Dev Fallback
    if not mail_username or not mail_password:
        msg = f"[JanPulse Dev Mode] Password Reset OTP for {to_email} ({user_name}): {otp_code}"
        print("=" * 80)
        print(msg)
        print("=" * 80)
        return {'success': True, 'mode': 'dev_console', 'otp_code': otp_code}

    # 2. Build OTP Email
    subject = f"JanPulse | Your Password Reset OTP: {otp_code} / पासवर्ड रीसेट ओटीपी"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b; }}
            .container {{ max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); }}
            .header {{ background-color: #0B192C; padding: 24px; text-align: center; }}
            .logo {{ color: #ffffff; font-size: 22px; font-weight: 900; letter-spacing: 0.5px; }}
            .logo span {{ color: #E11D48; }}
            .body {{ padding: 32px 28px; }}
            .greeting {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; color: #0f172a; }}
            .text {{ font-size: 14px; line-height: 1.6; color: #475569; margin-bottom: 20px; }}
            .otp-box {{ text-align: center; margin: 24px 0; background: #fdf2f4; border: 2px dashed #f43f5e; border-radius: 12px; padding: 18px 24px; }}
            .otp-label {{ font-size: 11px; text-transform: uppercase; color: #9f1239; font-weight: bold; letter-spacing: 1px; margin-bottom: 6px; }}
            .otp-digits {{ font-size: 32px; font-weight: 900; letter-spacing: 8px; color: #BE123C; font-family: 'Courier New', monospace; }}
            .notice {{ background-color: #fff1f2; border-left: 4px solid #E11D48; padding: 12px; border-radius: 6px; font-size: 12px; color: #9f1239; margin-bottom: 20px; line-height: 1.5; }}
            .footer {{ background-color: #f1f5f9; padding: 16px 24px; text-align: center; font-size: 11px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="logo">JAN<span>PULSE</span></div>
                <div style="color: #94a3b8; font-size: 11px; margin-top: 4px;">Voice of the People | जन आवाज़</div>
            </div>
            <div class="body">
                <div class="greeting">नमस्ते / Hello, {user_name}!</div>
                <div class="text">
                    Aapke JanPulse account ka password reset karne ke liye One-Time Password (OTP) request kiya gaya hai.<br>
                    Use this One-Time Password (OTP) to reset your JanPulse account password.
                </div>
                <div class="otp-box">
                    <div class="otp-label">Your 6-Digit Verification OTP / आपका ओटीपी</div>
                    <div class="otp-digits">{otp_code}</div>
                </div>
                <div class="notice">
                    ⏱️ <strong>Validity:</strong> Yeh OTP agle <strong>10 minute</strong> tak hi valid hai.<br>
                    🔒 <strong>Security Warning:</strong> Kripya yeh OTP kisi ke saath share na karein (JanPulse team kabhi aapse OTP nahi mangti).
                </div>
                <div class="text" style="font-size: 12px; color: #64748b;">
                    Agar aapne yeh request nahi ki hai, to kripya is email ko ignore karein. Aapka password bilkul surakshit hai.
                </div>
            </div>
            <div class="footer">
                &copy; 2026 JanPulse News Network Ltd. All rights reserved.<br>
                This is an automated security verification email.
            </div>
        </div>
    </body>
    </html>
    """

    plain_content = f"""
JanPulse | Password Reset OTP
---------------------------------------
Hello {user_name},

Your 6-Digit Password Reset OTP is: {otp_code}

This OTP is valid for 10 minutes.
Do NOT share this code with anyone.

If you did not request this, please ignore this email.

---
JanPulse Media Network
    """

    try:
        from_display = f"JanPulse News <{mail_username}>" if mail_username else mail_sender
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_display
        msg['To'] = to_email

        msg.attach(MIMEText(plain_content, 'plain', 'utf-8'))
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if mail_use_tls:
            server.starttls()
        server.login(mail_username, mail_password)
        envelope_from = mail_username if mail_username else mail_sender
        server.sendmail(envelope_from, [to_email], msg.as_string())
        server.quit()
        logger.info(f"[MailService] Password reset OTP sent successfully to {to_email}")
        return {'success': True, 'mode': 'smtp_sent'}
    except Exception as e:
        logger.error(f"[MailService] Failed to send OTP email via SMTP: {e}")
        return {'success': False, 'error': str(e)}
