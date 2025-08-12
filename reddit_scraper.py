import praw
import pandas as pd
from datetime import datetime
import os

# Reddit API credentials (set as GitHub Actions secrets)
reddit = praw.Reddit(
    client_id=os.getenv("REDDIT_CLIENT_ID"),
    client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
    user_agent=os.getenv("REDDIT_USER_AGENT"),
    username=os.getenv("REDDIT_USERNAME"),
    password=os.getenv("REDDIT_PASSWORD"),
)

# Keywords & subreddits
keywords = [
    "psychiatry", "psychology", "neuroscience",
    "research assistant", "lab manager", "postbac",
    "bachelor's degree", "BA/BS", "RA position",
    "psych", "research coordinator", "CRC",
    "clinical research coordinator"
]
locations = ["nyc", "new york", "brooklyn", "queens", "manhattan", "bronx", "remote", "work from home", "new york city"]

subreddits = ["psychology", "neuro", "jobs", "nycjobs", "sciencejobs", "gradadmissions", "clinicalpsychology", "clinicalpsych"]

posts_data = []

# Fetch posts
for sub in subreddits:
    subreddit = reddit.subreddit(sub)
    for post in subreddit.new(limit=200):
        title_lower = post.title.lower()
        if any(kw in title_lower for kw in keywords) and any(loc in title_lower for loc in locations):
            location_tag = "Remote" if "remote" in title_lower or "work from home" in title_lower else "NYC/Commutable"
            posts_data.append({
                "Date": datetime.utcfromtimestamp(post.created_utc).strftime("%Y-%m-%d %H:%M:%S"),
                "Title": post.title,
                "URL": post.url,
                "Location": location_tag
            })

# Sort newest first
df = pd.DataFrame(posts_data)
df.sort_values("Date", ascending=False, inplace=True)

# Save Excel
excel_file = "reddit_jobs_sorted.xlsx"
df.to_excel(excel_file, index=False)

# Build HTML email table with color-coding
def make_html_table(df):
    table_html = "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>"
    table_html += "<tr><th>Date</th><th>Title</th><th>Location</th></tr>"
    for _, row in df.iterrows():
        color = "#d0f0c0" if row["Location"] == "Remote" else "#add8e6"
        table_html += f"<tr style='background-color:{color};'>"
        table_html += f"<td>{row['Date']}</td>"
        table_html += f"<td><a href='{row['URL']}'>{row['Title']}</a></td>"
        table_html += f"<td>{row['Location']}</td>"
        table_html += "</tr>"
    table_html += "</table>"
    return table_html

html_table = make_html_table(df)

# Email sending
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

email_user = os.getenv("EMAIL_USER")
email_password = os.getenv("EMAIL_PASSWORD")
email_send = os.getenv("EMAIL_SEND_TO")

if df.empty:
    html_table = "<p>No new psychiatry/neuro research jobs found on Reddit today.</p>"
else:
    html_table = make_html_table(df)

msg = MIMEMultipart("alternative")
msg["From"] = email_user
msg["To"] = email_send
msg["Subject"] = "Daily Reddit Psych/Neuro Job Listings"

msg.attach(MIMEText(html_table, "html"))

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(email_user, email_password)
    server.sendmail(email_user, email_send, msg.as_string())

print("✅ Email sent with today's Reddit job listings!")
