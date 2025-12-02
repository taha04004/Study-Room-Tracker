import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_config import EMAIL_ADDRESS, EMAIL_PASSWORD

def send_confirmation_email(to_email, room_number, date, start, end):
    subject = "Your Study Room Booking Confirmation"

    html = f"""
    <h2>Booking Confirmed</h2>
    <p>Your study room is booked successfully.</p>
    <ul>
        <li><strong>Room:</strong> {room_number}</li>
        <li><strong>Date:</strong> {date}</li>
        <li><strong>Start:</strong> {start}</li>
        <li><strong>End:</strong> {end}</li>
    </ul>
    <p>Thank you for using the Study Room Tracker.</p>
    """

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        print("Email sent successfully!")
    except Exception as e:
        print("Email failed:", e)
