import os
import datetime
import pytz
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import feedparser
from newspaper import Article
import google.generativeai as genai
from supabase import create_client, Client

# This is the main function Vercel will run
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # --- Run the main news agent logic ---
        try:
            run_news_agent()
            # --- Send a success response ---
            self.send_response(200)
            self.send_header('Content-type','text/plain')
            self.end_headers()
            self.wfile.write(b"News digest process completed successfully.")
        except Exception as e:
            # --- Send an error response if something fails ---
            self.send_response(500)
            self.send_header('Content-type','text/plain')
            self.end_headers()
            self.wfile.write(f"An error occurred: {str(e)}".encode())
        return

# --- All your helper functions go here ---

def get_top_news():
    news_feeds = {
        'BBC': 'http://feeds.bbci.co.uk/news/rss.xml',
        'Reuters': 'http://feeds.reuters.com/reuters/topNews',
        'The New York Times': 'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
        'CNN': 'http://rss.cnn.com/rss/edition.rss',
        'The Wall Street Journal': 'https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml'
    }
    all_articles = []
    print("Fetching news feeds...")
    for source, url in news_feeds.items():
        feed = feedparser.parse(url)
        for entry in feed.entries[:5]: # Get top 5 from each source
            all_articles.append({
                'source': source,
                'title': entry.title,
                'link': entry.link
            })
    print(f"Found {len(all_articles)} articles.")
    return all_articles

def summarize_article(article_text):
    print("Summarizing article...")
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(f"Summarize the following news article in two to three sentences:\n\n{article_text}")
        return response.text.strip()
    except Exception as e:
        print(f"Error summarizing: {e}")
        return "Summary not available."

def store_summary(supabase_client, article_data):
    print(f"Storing summary for: {article_data['title']}")
    try:
        gmt6_tz = pytz.timezone('Asia/Dhaka')
        gmt6_time = datetime.datetime.now(gmt6_tz)
        
        supabase_client.table('summaries').insert({
            'title': article_data['title'],
            'summary': article_data['summary'],
            'link': article_data['link'],
            'source': article_data['source'],
            'gmt6_timestamp': gmt6_time.isoformat()
        }).execute()
    except Exception as e:
        print(f"Error storing summary: {e}")

def send_email_digest(summaries):
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
    SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print("Fetching recipients...")
    recipients_response = supabase.table('recipients').select('email').execute()
    recipient_emails = [item['email'] for item in recipients_response.data]

    if not recipient_emails:
        print("No recipients found. Skipping email.")
        return

    print(f"Sending digest to {len(recipient_emails)} recipients...")
    message = MIMEMultipart("alternative")
    message["Subject"] = f"Your News Digest - {datetime.date.today().strftime('%B %d, %Y')}"
    message["From"] = SENDER_EMAIL
    message["To"] = ", ".join(recipient_emails)

    html_body = "<html><body><h1>Today's Top News</h1>"
    for summary in summaries:
        html_body += f"<h2>{summary['title']} ({summary['source']})</h2>"
        html_body += f"<p>{summary['summary']}</p>"
        html_body += f"<a href='{summary['link']}'>Read more</a><hr>"
    html_body += "</body></html>"
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, recipient_emails, message.as_string())
        print("Email digest sent successfully.")
    except Exception as e:
        print(f"Error sending email: {e}")

# --- Main orchestrator function ---
def run_news_agent():
    # --- Securely get credentials from environment variables ---
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

    # --- Configure APIs ---
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    genai.configure(api_key=GEMINI_API_KEY)

    articles_to_process = get_top_news()
    summarized_articles = []

    for article_info in articles_to_process:
        try:
            article = Article(article_info['link'])
            article.download()
            article.parse()
            
            # Skip if article body is too short
            if len(article.text) < 300:
                print(f"Skipping short article: {article_info['title']}")
                continue

            summary = summarize_article(article.text)
            article_data = {
                'title': article_info['title'],
                'summary': summary,
                'link': article_info['link'],
                'source': article_info['source']
            }
            summarized_articles.append(article_data)
            store_summary(supabase, article_data)
        except Exception as e:
            print(f"Could not process article {article_info['link']}: {e}")

    if summarized_articles:
        send_email_digest(summarized_articles)
    else:
        print("No new articles were summarized. No email sent.")
