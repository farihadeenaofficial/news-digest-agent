# api/index.py (Dashboard Version)

import os
import datetime
from http.server import BaseHTTPRequestHandler
import traceback

try:
    from supabase import create_client, Client
    import pytz
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: Failed to import a library: {e}")


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
                html_output = """
                <!DOCTYPE html>
                <html lang="en">
                <head><meta charset="UTF-8"><title>News Digest</title></head>
                <body style="font-family: sans-serif; padding: 2em;">
                    <h1>News Digest Dashboard</h1>
                    <p>No summaries found in the database yet. The agent might be running for the first time.</p>
                </body>
                </html>
                """
            else:
                # Get the timestamp of the newest article for the "Last Updated" message
                gmt6_tz = pytz.timezone('Asia/Dhaka')
                last_updated_string = summaries[0]['gmt6_timestamp']
                last_updated_dt = datetime.datetime.fromisoformat(last_updated_string).astimezone(gmt6_tz)
                formatted_time = last_updated_dt.strftime('%B %d, %Y at %I:%M %p GMT+6')

                # Start building the HTML
                html_builder = [
                    '<!DOCTYPE html>',
                    '<html lang="en">',
                    '<head><meta charset="UTF-8"><title>News Digest</title></head>',
                    '<body style="font-family: sans-serif; padding: 2em; line-height: 1.6;">',
                    '<h1>News Digest Dashboard</h1>',
                    f'<p><strong>Last updated:</strong> {formatted_time}</p><hr>'
                ]

                # Loop through each summary and add it to the page
                for item in summaries:
                    html_builder.append(f'<h2>{item["title"]}</h2>')
                    html_builder.append(f'<p>{item["summary"]}</p>')
                    html_builder.append(f'<p><a href="{item["link"]}" target="_blank">Read Full Article</a></p>')
                    html_builder.append(f'<p><em>Source: {item["source"]}</em></p><hr>')
                
                html_builder.extend(['</body>', '</html>'])
                html_output = "\n".join(html_builder)

            # --- 4. Send the HTML as the response ---
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html_output.encode('utf-8'))

        except Exception as e:
            # If anything goes wrong, display an error page
            error_details = traceback.format_exc()
            error_html = f"""
            <!DOCTYPE html><html lang="en"><head><title>Error</title></head><body>
            <h1>An Error Occurred</h1><pre>{error_details}</pre>
            </body></html>
            """
            self.send_response(500)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(error_html.encode('utf-8'))
            
        return
