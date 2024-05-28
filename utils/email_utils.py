import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import settings


def send_verification_email(to_email: str, code: str):
    msg = MIMEMultipart()
    msg['From'] = settings.EMAIL_FROM
    msg['To'] = to_email
    msg['Subject'] = 'Your Verification Code'

    body = f'Your verification code is: {code}'
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT)
        server.starttls()
        server.login(settings.EMAIL_USERNAME, settings.EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(settings.EMAIL_FROM, to_email, text)
        server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")
