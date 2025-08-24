# api/index.py (Aesthetic Dashboard Version)

import os
import datetime
from http.server import BaseHTTPRequestHandler
import traceback

try:
    from supabase import create_client, Client
    import pytz
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: Failed to import a library: {e}")

# --- Helper function to get source favicons ---
def get_favicon(source):
    # Using high-quality, reliable favicon URLs
    favicons = {
        "BBC": "https://www.bbc.com/favicon.ico",
        "Reuters": "https://www.reuters.com/favicon.ico",
        "CNN": "https://www.cnn.com/favicon.ico",
        "The New York Times": "https://www.nytimes.com/favicon.ico",
        "The Wall Street Journal": "https://www.wsj.com/favicon.ico"
    }
    return favicons.get(source, "") # Return the URL or an empty string if not found


# This is the main function Vercel will run
class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        html_output = ""
        try:
            # --- 1. Connect to Supabase ---
            SUPABASE_URL = os.environ.get("SUPABASE_URL")
            SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
            supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

            # --- 2. Fetch the latest 20 summaries, newest first ---
            response = supabase.table('summaries').select('*').order('gmt6_timestamp', desc=True).limit(20).execute()
            summaries = response.data

            # --- 3. Build the HTML Page ---
            if not summaries:
                # A simple message if the database is empty
                last_updated_message = "No summaries found yet. The agent is scheduled to run automatically."
                cards_html = "<p>Please check back later.</p>"
            else:
                # Format the "Last Updated" timestamp
                gmt6_tz = pytz.timezone('Asia/Dhaka')
                last_updated_dt = datetime.datetime.fromisoformat(summaries[0]['gmt6_timestamp']).astimezone(gmt6_tz)
                formatted_time = last_updated_dt.strftime('%B %d, %Y at %I:%M %p GMT+6')
                last_updated_message = f"<strong>Last updated:</strong> {formatted_time}"

                # Build an HTML card for each summary
                card_builder = []
                for item in summaries:
                    favicon_url = get_favicon(item["source"])
                    card_builder.append(f"""
                    <article class="card">
                        <div class="card-header">
                            <img src="{favicon_url}" alt="{item['source']} favicon" class="favicon">
                            <span>{item['source']}</span>
                        </div>
                        <h2>{item['title']}</h2>
                        <p class="summary">{item['summary']}</p>
                        <div class="card-footer">
                            <a href="{item['link']}" target="_blank" class="read-more-btn">Read Full Article</a>
                        </div>
                    </article>
                    """)
                cards_html = "\n".join(card_builder)
            
            # --- 4. Assemble the final HTML with embedded CSS ---
            html_output = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>AI News Digest</title>
                <link rel="preconnect" href="https://fonts.googleapis.com">
                <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap" rel="stylesheet">
                <style>
                    :root {{
                        --bg-color: #f8f9fa;
                        --card-bg: #ffffff;
                        --text-color: #343a40;
                        --heading-color: #212529;
                        --accent-color: #007bff;
                        --border-color: #dee2e6;
                        --shadow-color: rgba(0, 0, 0, 0.05);
                    }}
                    body {{
                        font-family: 'Inter', sans-serif;
                        background-color: var(--bg-color);
                        color: var(--text-color);
                        margin: 0;
                        padding: 1em;
                    }}
                    .container {{
                        max-width: 1200px;
                        margin: 0 auto;
                        padding: 2em;
                    }}
                    header {{
                        text-align: center;
                        margin-bottom: 2.5em;
                    }}
                    header h1 {{
                        font-size: 2.5em;
                        color: var(--heading-color);
                        margin-bottom: 0.25em;
                    }}
                    header p {{
                        color: #6c757d;
                    }}
                    .card-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                        gap: 1.5em;
                    }}
                    .card {{
                        background: var(--card-bg);
                        border: 1px solid var(--border-color);
                        border-radius: 12px;
                        padding: 1.5em;
                        box-shadow: 0 4px 12px var(--shadow-color);
                        display: flex;
                        flex-direction: column;
                        transition: transform 0.2s ease, box-shadow 0.2s ease;
                    }}
                    .card:hover {{
                        transform: translateY(-5px);
                        box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
                    }}
                    .card-header {{
                        display: flex;
                        align-items: center;
                        gap: 0.5em;
                        font-size: 0.9em;
                        color: #6c757d;
                        margin-bottom: 1em;
                    }}
                    .favicon {{
                        width: 16px;
                        height: 16px;
                    }}
                    .card h2 {{
                        font-size: 1.25em;
                        margin: 0 0 0.75em 0;
                        color: var(--heading-color);
                    }}
                    .card .summary {{
                        line-height: 1.6;
                        flex-grow: 1; /* Pushes the footer down */
                    }}
                    .card-footer {{
                        margin-top: 1.5em;
                    }}
                    .read-more-btn {{
                        display: inline-block;
                        text-decoration: none;
                        background-color: var(--accent-color);
                        color: #ffffff;
                        padding: 0.75em 1.5em;
                        border-radius: 8px;
                        font-weight: 600;
                        text-align: center;
                        transition: background-color 0.2s ease;
                    }}
                    .read-more-btn:hover {{
                        background-color: #0056b3;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <header>
                        <h1>AI News Digest</h1>
                        <p>{last_updated_message}</p>
                    </header>
                    <main class="card-grid">
                        {cards_html}
                    </main>
                </div>
            </body>
            </html>
            """

            # --- 5. Send the HTML as the response ---
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_output.encode('utf-8'))

        except Exception:
            # If anything goes wrong, display a nicely formatted error page
            error_details = traceback.format_exc()
            error_html = f"<html><head><title>Error</title></head><body style='font-family:monospace; padding:2em;'><h1>An Error Occurred</h1><pre>{error_details}</pre></body></html>"
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(error_html.encode('utf-8'))
            
        return
