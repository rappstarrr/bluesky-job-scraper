import praw
from atproto import Client
import pandas as pd
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
import time
from typing import List, Dict

# Environment variables (no python-dotemail needed)
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT')
REDDIT_USERNAME = os.getenv('REDDIT_USERNAME')
REDDIT_PASSWORD = os.getenv('REDDIT_PASSWORD')
BSKY_USERNAME = os.getenv('BSKY_USERNAME')
BSKY_PASSWORD = os.getenv('BSKY_PASSWORD')
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_SMTP_SERVER = os.getenv('EMAIL_SMTP_SERVER')
EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', '587'))  # Default to 587

# Search parameters - customize these!
KEYWORDS = ['psych', 'psychiatry', 'neuroscience', 'neurology', 
           'mental health', 'research assistant', 'postbac', 'lab tech', 'research coordinator',
            'clinical research coordinator', 'CRC', 'project manager']
LOCATIONS = ['nyc', 'new york', 'remote', 'telehealth', 'new york city', 'cuny', 'stony brook', 'columbia',
            'mount sinai', 'nyu', 'langone', 'hunter college', 'fordham', 'chop', 'penn', 'upenn']
JOB_TYPES = ['job', 'position', 'hire', 'opportunity', 'hiring', 'postgrad', 'postbac', 'full time']

def is_job_post(title: str, text: str) -> bool:
    """Check if post contains relevant keywords"""
    content = f"{title.lower()} {text.lower()}"
    return (any(kw in content for kw in KEYWORDS) and 
            (any(loc in content for loc in LOCATIONS) or 
             any(job_type in content for job_type in JOB_TYPES)))

def scrape_reddit() -> List[Dict]:
    """Scrape Reddit for psychology jobs"""
    print("Scraping Reddit...")
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD
    )
    
    jobs = []
    subreddits = ["forhire", "jobs", "psychology", "Neuropsychology", "remotework", "gradadmissions", "postbac", "clinicalpsych"]
    
    for sub in subreddits:
        try:
            for submission in reddit.subreddit(sub).new(limit=50):
                if is_job_post(submission.title, submission.selftext):
                    jobs.append({
                        'source': f'Reddit/r/{sub}',
                        'title': submission.title,
                        'text': submission.selftext[:500] + '...' if len(submission.selftext) > 500 else submission.selftext,
                        'url': f"https://reddit.com{submission.permalink}",
                        'date': datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M'),
                        'author': submission.author.name if submission.author else 'Unknown'
                    })
        except Exception as e:
            print(f"⚠️ Error in r/{sub}: {str(e)}")
    
    return jobs

def scrape_bluesky() -> List[Dict]:
    """Scrape Bluesky for psychology jobs"""
    print("Scraping Bluesky...")
    client = Client()
    jobs = []
    
    try:
        client.login(BSKY_USERNAME, BSKY_PASSWORD)
        for keyword in KEYWORDS:
            response = client.app.bsky.feed.search_posts(q=f"{keyword} job")
            for post in response.posts:
                if is_job_post(post.record.text, ""):
                    jobs.append({
                        'source': 'Bluesky',
                        'title': post.record.text[:100] + '...' if len(post.record.text) > 100 else post.record.text,
                        'text': post.record.text,
                        'url': f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}",
                        'date': datetime.fromisoformat(post.record.created_at[:-5]).strftime('%Y-%m-%d %H:%M'),
                        'author': post.author.handle
                    })
    except Exception as e:
        print(f"⚠️ Bluesky error: {str(e)}")
    
    return jobs

def create_excel(reddit_jobs: List[Dict], bluesky_jobs: List[Dict]) -> str:
    """Generate Excel file with two sheets"""
    filename = f"psych_jobs_{datetime.now().strftime('%Y%m%d')}.xlsx"
    
    with pd.ExcelWriter(filename) as writer:
        pd.DataFrame(reddit_jobs).to_excel(writer, sheet_name='Reddit', index=False)
        pd.DataFrame(bluesky_jobs).to_excel(writer, sheet_name='Bluesky', index=False)
    
    return filename

def send_email(filename: str, reddit_count: int, bluesky_count: int):
    """Send results via email"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS
    msg['Subject'] = f"🧠 Psychology Jobs Report - {datetime.now().strftime('%m/%d/%Y')}"
    
    body = f"""
    <h2>Daily Psychology Jobs Report</h2>
    <p><strong>Date:</strong> {datetime.now().strftime('%A, %B %d, %Y')}</p>
    <p><strong>Reddit:</strong> {reddit_count} new posts</p>
    <p><strong>Bluesky:</strong> {bluesky_count} new posts</p>
    """
    
    if reddit_count + bluesky_count == 0:
        body += "<p>🔍 No new jobs found today.</p>"
    else:
        body += "<p>📎 See attached Excel file for details.</p>"
    
    msg.attach(MIMEText(body, 'html'))
    
    if reddit_count + bluesky_count > 0:
        with open(filename, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
        msg.attach(part)
    
    with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

def main():
    print(f"🚀 Starting job scrape at {datetime.now()}")
    reddit = scrape_reddit()
    bluesky = scrape_bluesky()
    
    if reddit or bluesky:
        filename = create_excel(reddit, bluesky)
        send_email(filename, len(reddit), len(bluesky))
        print(f"✅ Found {len(reddit)} Reddit and {len(bluesky)} Bluesky jobs")
    else:
        send_email("", 0, 0)
        print("❌ No jobs found today")
    
    print("🏁 Scrape complete")

if __name__ == "__main__":
    main()
