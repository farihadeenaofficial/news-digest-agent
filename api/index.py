# api/index.py (Enhanced Version for Browser Logging)

import os
import datetime
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from http.server import BaseHTTPRequestHandler
import traceback  # Import traceback to get detailed error info

# We will try to import everything. If this fails, the logs will show an error.
try:
    import feedparser
    from newspaper import Article
    import google.generativeai as genai
    from supabase import create_client, Client
except Exception as e:
    # This is a critical failure if libraries don't load.
    # We can't do much but print to the server log.
    print(f"CRITICAL STARTUP ERROR: Failed to import a library: {e}")

# This is the main function Vercel will run
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        log_messages = []
        log_messages.append("LOG: Handler received a GET request. Starting agent...")
        
        try:
            # Run the agent and get the logs it generated
            run_logs = run_news_agent()
            log_messages.extend(run_logs) # Add the logs from the agent
            
            # Send a success response with the full log as the body
            self.send_response(200)
            self.send_header('Content-type','text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write("\n".join(log_messages).encode('utf-8'))
            
        except Exception as e:
            # If a major error happens, capture it and send it to the browser
            error_details = traceback.format_exc()
            log_messages.append("\n--- A CRITICAL ERROR OCCURRED ---\n")
            log_messages.append(error_details)
            
            self.send_response(500)
            self.send_header('Content-type','text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write("\n".join(log_messages).encode('utf-8'))
        return

# --- Helper Functions ---
# (These now append to a log list instead of printing)

def get_top_news(logs):
    logs.append("LOG: Fetching news feeds...")
    news_feeds = {
        'BBC': 'http://feeds.bbci.co.uk/news/rss.xml',
        'Reuters': 'http://feeds.reuters.com/reuters/topNews',
        'CNN': 'http://rss.cnn.com/rss/edition.rss'
    }
    articles = []
    for source, url in news_feeds.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]: # Getting 3 from each to speed up testing
            articles.append({'source': source, 'title': entry.title, 'link': entry.link})
    logs.append(f"LOG: Found {len(articles)} articles.")
    return articles

def summarize_article(logs, article_text):
    logs.append("LOG: Summarizing an article...")
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(f"Summarize this in 2 sentences:\n\n{article_text}")
    return response.text.strip()

def store_summary(logs, supabase_client, article_data):
    logs.append(f"LOG: Storing summary for: {article_data['title']}")
    gmt6_tz = pytz.timezone('Asia/Dhaka')
    gmt6_time = datetime.datetime.now(gmt6_tz)
    supabase_client.table('summaries').insert({
        'title': article_data['title'], 'summary': article_data['summary'], 'link': article_data['link'],
        'source': article_data['source'], 'gmt6_timestamp': gmt6_time.isoformat()
    }).execute()

def send_email_digest(logs, summaries, supabase_client):
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
    SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
    logs.append("LOG: Fetching recipients from Supabase...")
    recipients_response = supabase_client.table('recipients').select('email').execute()
    recipient_emails = [item['email'] for item in recipients_response.data]
    if not recipient_emails:
        logs.append("LOG: No recipients found in the database. Skipping email.")
        return
    logs.append(f"LOG: Preparing to send digest to {len(recipient_emails)} recipient(s)...")
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your News Digest - {datetime.date.today().strftime('%B %d, %Y')}"
    message["From"] = SENDER_EMAIL
    message["To"] = ", ".join(recipient_emails)
    html_body = "<html><body><h1>Today's Top News</h1>"
    for summary in summaries:
        html_body += f"<h2>{summary['title']} ({summary['source']})</h2><p>{summary['summary']}</p><a href='{summary['link']}'>Read more</a><hr>"
    html_body += "</body></html>"
    message.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        logs.append("LOG: Logging into Gmail SMTP server...")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        logs.append("LOG: Sending the email...")
        server.sendmail(SENDER_EMAIL, recipient_emails, message.as_string())
    logs.append("LOG: Email digest sent successfully!")

# --- Main orchestrator function ---
def run_news_agent():
    logs = []
    logs.append("--- Starting News Agent ---")
    
    # --- Securely get credentials from environment variables ---
    logs.append("LOG: Retrieving environment variables...")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
    SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")

    if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_API_KEY, SENDER_EMAIL, SENDER_PASSWORD]):
        logs.append("CRITICAL ERROR: One or more environment variables are missing! Check Vercel settings.")
        return logs

    logs.append("LOG: Environment variables retrieved successfully.")
    
    # --- Configure APIs ---
    logs.append("LOG: Configuring API clients...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)
    logs.append("LOG: API configuration successful.")

    articles_to_process = get_top_news(logs)
    summarized_articles = []

    for article_info in articles_to_process:
        try:
            article = Article(article_info['link'])
            article.download(); article.parse()
            if len(article.text) < 200:
                logs.append(f"LOG: Skipping short article: {article_info['title']}")
                continue
            summary = summarize_article(logs, article.text)
            article_data = {'title': article_info['title'], 'summary': summary, 'link': article_info['link'], 'source': article_info['source']}
            summarized_articles.append(article_data)
            store_summary(logs, supabase, article_data)
        except Exception as e:
            logs.append(f"ERROR processing article {article_info['link']}: {e}")

    if summarized_articles:
        send_email_digest(logs, summarized_articles, supabase)
    else:
        logs.append("LOG: No new articles were summarized. No email will be sent.")
    
    logs.append("--- News Agent Finished ---")
    return logs
