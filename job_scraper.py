import praw
from atproto import Client
import pandas as pd
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import os
import schedule
import time
from typing import List, Dict

# Load environment variables
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
EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', '587'))

# Search parameters
KEYWORDS = ['psych', 'psychiatry', 'neuroscience', 'neurology', 'mental health', 
            'research assistant', 'postbac', 'post-bac', 'post bac', 'lab tech']
LOCATIONS = ['nyc', 'new york', 'remote', 'telehealth']
JOB_TYPES = ['job', 'position', 'hire', 'opportunity', 'opening']

def is_job_post(title: str, text: str) -> bool:
    """Check if post contains relevant keywords"""
    content = f"{title.lower()} {text.lower()}"
    has_keyword = any(keyword in content for keyword in KEYWORDS)
    has_location = any(location in content for location in LOCATIONS)
    has_job_type = any(job_type in content for job_type in JOB_TYPES)
    
    return has_keyword and (has_location or has_job_type)

def scrape_reddit() -> List[Dict]:
    """Scrape Reddit for psychology jobs"""
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
        username=REDDIT_USERNAME,
        password=REDDIT_PASSWORD
    )
    
    subreddits = ["forhire", "jobs", "psychology", "neuro", "science", "remotework"]
    jobs = []
    
    for sub in subreddits:
        try:
            for submission in reddit.subreddit(sub).new(limit=50):
                if is_job_post(submission.title, submission.selftext):
                    jobs.append({
                        'source': 'Reddit',
                        'subreddit': sub,
                        'title': submission.title,
                        'text': submission.selftext,
                        'url': f"https://reddit.com{submission.permalink}",
                        'date': datetime.fromtimestamp(submission.created_utc),
                        'author': submission.author.name if submission.author else 'Unknown'
                    })
        except Exception as e:
            print(f"Error scraping Reddit subreddit {sub}: {e}")
    
    return jobs

def scrape_bluesky() -> List[Dict]:
    """Scrape Bluesky for psychology jobs"""
    client = Client()
    jobs = []
    
    try:
        client.login(BSKY_USERNAME, BSKY_PASSWORD)
        
        # Search for each keyword combination
        for keyword in KEYWORDS:
            response = client.app.bsky.feed.search_posts(q=f"{keyword} job")
            for post in response.posts:
                text = post.record.text.lower()
                if is_job_post(post.record.text, ""):
                    jobs.append({
                        'source': 'Bluesky',
                        'title': post.record.text[:100] + '...' if len(post.record.text) > 100 else post.record.text,
                        'text': post.record.text,
                        'url': f"https://bsky.app/profile/{post.author.handle}/post/{post.uri.split('/')[-1]}",
                        'date': datetime.fromisoformat(post.record.created_at[:-5]),  # Remove timezone offset
                        'author': post.author.handle
                    })
    except Exception as e:
        print(f"Error scraping Bluesky: {e}")
    
    return jobs

def create_excel_file(reddit_jobs: List[Dict], bluesky_jobs: List[Dict]) -> str:
    """Create Excel file with separate sheets for Reddit and Bluesky jobs"""
    filename = f"psych_jobs_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    
    # Convert to DataFrames
    df_reddit = pd.DataFrame(reddit_jobs)
    df_bluesky = pd.DataFrame(bluesky_jobs)
    
    # Sort by date (newest first)
    if not df_reddit.empty:
        df_reddit = df_reddit.sort_values('date', ascending=False)
    if not df_bluesky.empty:
        df_bluesky = df_bluesky.sort_values('date', ascending=False)
    
    # Save to Excel
    with pd.ExcelWriter(filename) as writer:
        df_reddit.to_excel(writer, sheet_name='Reddit', index=False)
        df_bluesky.to_excel(writer, sheet_name='Bluesky', index=False)
    
    return filename

def send_email(filename: str, reddit_count: int, bluesky_count: int):
    """Send email with Excel attachment"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = EMAIL_ADDRESS
    msg['Subject'] = f"Daily Psychology Jobs Report - {datetime.now().strftime('%m/%d/%Y')}"
    
    # Email body
    body = f"""
    <h2>Daily Psychology Jobs Report</h2>
    <p>Date: {datetime.now().strftime('%m/%d/%Y')}</p>
    <p>Found {reddit_count} new jobs on Reddit</p>
    <p>Found {bluesky_count} new jobs on Bluesky</p>
    """
    
    if reddit_count == 0 and bluesky_count == 0:
        body += "<p><strong>No new jobs found today.</strong></p>"
    else:
        body += "<p>See attached Excel file for details.</p>"
    
    msg.attach(MIMEText(body, 'html'))
    
    # Attach Excel file if jobs were found
    if reddit_count > 0 or bluesky_count > 0:
        with open(filename, 'rb') as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename= {filename}',
        )
        msg.attach(part)
    
    # Send email
    with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

def job_scraper_task():
    """Main task to run daily"""
    print(f"Running job scraper at {datetime.now()}")
    
    # Scrape both platforms
    reddit_jobs = scrape_reddit()
    bluesky_jobs = scrape_bluesky()
    
    # Create Excel file
    filename = create_excel_file(reddit_jobs, bluesky_jobs)
    
    # Send email
    send_email(filename, len(reddit_jobs), len(bluesky_jobs))
    
    print(f"Completed at {datetime.now()}. Found {len(reddit_jobs)} Reddit jobs and {len(bluesky_jobs)} Bluesky jobs.")

def main():
    # Run immediately (for testing)
    job_scraper_task()
    
    # Schedule daily at 9 AM
    schedule.every().day.at("09:00").do(job_scraper_task)
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
