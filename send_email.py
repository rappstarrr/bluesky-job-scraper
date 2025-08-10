import os
import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT"))

# Email content
msg = EmailMessage()
msg["Subject"] = "Your Daily Bluesky Psychiatry Job Listings"
msg["From"] = EMAIL_ADDRESS
msg["To"] = EMAIL_ADDRESS
msg.set_content("Hey! Here is your latest Bluesky psychiatry research job listing spreadsheet attached.")

# Attach the Excel file
with open("bluesky_jobs_sorted.xlsx", "rb") as f:
    file_data = f.read()
    file_name = "bluesky_jobs_sorted.xlsx"
msg.add_attachment(file_data, maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=file_name)

# Send the email
with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as smtp:
    smtp.starttls()
    smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    smtp.send_message(msg)

print("Email sent successfully!")
