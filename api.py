from flask import Flask, request, jsonify
import instaloader
import os
import re
import http.cookiejar

app = Flask(__name__)

def validate_url(url):
    """
    Validate and extract shortcode from Instagram URL.
    
    Args:
        url (str): Instagram post URL
    Returns:
        str: Shortcode if valid, None otherwise
    """
    pattern = r'instagram\.com/p/([A-Za-z0-9-_]+)'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def load_cookies_from_file(cookies_path):
    """
    Load Instagram cookies from a Netscape-format cookies.txt file.
    
    Args:
        cookies_path (str): Path to cookies.txt file
    Returns:
        dict: Dictionary of cookies (sessionid, csrftoken) or None if invalid
    """
    cookies = {}
    try:
        cookie_jar = http.cookiejar.MozillaCookieJar()
        cookie_jar.load(cookies_path, ignore_discard=True, ignore_expires=True)
        for cookie in cookie_jar:
            if cookie.name in ["sessionid", "csrftoken"] and cookie.domain == ".instagram.com":
                cookies[cookie.name] = cookie.value
        if "sessionid" in cookies and "csrftoken" in cookies:
            return cookies
        else:
            return None
    except Exception as e:
        return None

def get_instagram_post_urls(url, cookies_file="cookies/cookies.txt"):
    """
    Extract direct media URLs for an Instagram post.
    Requires valid cookies in cookies_file.
    
    Args:
        url (str): Instagram post URL
        cookies_file (str): Path to cookies.txt file for session authentication
    Returns:
        dict: Result with status, message, and media URLs (if successful)
    """
    result = {"status": "error", "message": "", "media_urls": []}
    
    # Validate URL
    shortcode = validate_url(url)
    if not shortcode:
        result["message"] = "Invalid Instagram URL! Please ensure it contains a valid post code (e.g., instagram.com/p/XXXXX)."
        return result

    try:
        # Initialize Instaloader with custom User-Agent
        loader = instaloader.Instaloader(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        )

        # Resolve absolute path for cookies file relative to script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cookies_path = os.path.join(script_dir, cookies_file)

        # Check if cookies file exists
        if not os.path.isfile(cookies_path):
            result["message"] = f"Cookies file not found at {cookies_path}. Ensure {cookies_file} exists with valid Instagram cookies in Netscape format."
            return result

        # Load cookies
        cookies = load_cookies_from_file(cookies_path)
        if not cookies:
            result["message"] = "Failed to load session from cookies.txt: Missing required cookies (sessionid, csrftoken) or invalid format."
            return result

        # Set cookies in the Instaloader context
        loader.context._session.cookies.set("sessionid", cookies["sessionid"], domain=".instagram.com")
        loader.context._session.cookies.set("csrftoken", cookies["csrftoken"], domain=".instagram.com")

        # Get post and extract media URLs
        post = instaloader.Post.from_shortcode(loader.context, shortcode)
        media_urls = []

        if post.is_video:
            media_urls.append(post.video_url)
        else:
            media_urls.append(post.url)

        # Handle multi-media posts (sidecar)
        if post.typename == "GraphSidecar":
            for node in post.get_sidecar_nodes():
                media_urls.append(node.video_url if node.is_video else node.display_url)

        result["status"] = "success"
        result["message"] = "Media URLs extracted successfully."
        result["media_urls"] = media_urls
        return result

    except instaloader.exceptions.LoginRequiredException:
        result["message"] = f"Login required! This post may be private or requires authentication. Provide a valid {cookies_file} with active session cookies."
        return result
    except instaloader.exceptions.BadResponseException as bre:
        result["message"] = f"Instagram blocked the request (403 Forbidden): {str(bre)}. Ensure {cookies_file} contains valid, non-expired session cookies."
        return result
    except Exception as e:
        result["message"] = f"Oops! Something went wrong: {str(e)}. Check your internet connection, URL, cookies file, or try again later."
        return result

@app.route('/', methods=['GET'])
def api_status():
    """
    Flask endpoint for API status page (GET request).
    Returns an HTML page with API status, developer info, and POST method details.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram Post Scraper API</title>
        <style>
            body {
                font-family: 'Arial', sans-serif;
                background-color: #f0f2f5;
                color: #333;
                text-align: center;
                padding: 50px;
                margin: 0;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
                background: #fff;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            }
            h1 {
                color: #e1306c;
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            h2 {
                color: #405de6;
                font-size: 1.8em;
                margin-top: 20px;
            }
            p {
                font-size: 1.2em;
                line-height: 1.6;
                margin: 10px 0;
            }
            .status-live {
                color: #2ecc71;
                font-weight: bold;
                font-size: 1.5em;
            }
            .highlight {
                background-color: #ffeaa7;
                padding: 5px 10px;
                border-radius: 5px;
            }
            .code-block {
                background-color: #2d2d2d;
                color: #f8f8f2;
                text-align: left;
                padding: 15px;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
                margin: 20px 0;
                overflow-x: auto;
            }
            a {
                color: #1da1f2;
                text-decoration: none;
                font-weight: bold;
            }
            a:hover {
                text-decoration: underline;
            }
            .footer {
                margin-top: 30px;
                font-size: 1em;
                color: #777;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Instagram Post Scraper API</h1>
            <p class="status-live">API Status: Live 🚀</p>
            <p>Effortlessly extract direct media URLs from Instagram posts with a single API call!</p>
            <p class="highlight">Built with ❤️ by <a href="https://x.com/ISmartDevs" target="_blank">@ISmartDevs</a></p>
            <p>Stay updated with the latest features and fixes at <a href="https://t.me/TheSmartDev" target="_blank">@TheSmartDev</a></p>

            <h2>Why Use This API?</h2>
            <p>Fast, reliable, and developer-friendly! Scrape Instagram post media (images/videos) in seconds, even for multi-media sidecar posts. Perfect for automation, content analysis, or media downloading.</p>

            <h2>POST /download - How It Works</h2>
            <p>Send a POST request to <code>/download</code> with a JSON payload containing an Instagram post URL to retrieve direct media URLs.</p>
            <div class="code-block">
                <strong>Request Example:</strong><br>
                curl -X POST https://your-api-url/download \<br>
                -H "Content-Type: application/json" \<br>
                -d '{"url": "https://www.instagram.com/p/XXXXX/"}'
                <br><br>
                <strong>Response Example (Success):</strong><br>
                {<br>
                &nbsp;&nbsp;"status": "success",<br>
                &nbsp;&nbsp;"message": "Media URLs extracted successfully.",<br>
                &nbsp;&nbsp;"media_urls": [<br>
                &nbsp;&nbsp;&nbsp;&nbsp;"https://instagram.com/.../media1.jpg",<br>
                &nbsp;&nbsp;&nbsp;&nbsp;"https://instagram.com/.../media2.mp4"<br>
                &nbsp;&nbsp;]<br>
                }<br><br>
                <strong>Response Example (Error):</strong><br>
                {<br>
                &nbsp;&nbsp;"status": "error",<br>
                &nbsp;&nbsp;"message": "Invalid Instagram URL! Please ensure it contains a valid post code.",<br>
                &nbsp;&nbsp;"media_urls": []<br>
                }
            </div>
            <p><strong>Note:</strong> This API requires valid Instagram session cookies (<code>cookies/cookies.txt</code>) in Netscape format with <code>sessionid</code> and <code>csrftoken</code>. Private posts need authenticated cookies.</p>

            <h2>Explore More</h2>
            <p>Join our community of developers and innovators! Follow <a href="https://x.com/ISmartDevs" target="_blank">@ISmartDevs</a> on X for tips, tricks, and API updates.</p>
            <p>Got feedback or ideas? Reach out via <a href="https://t.me/TheSmartDev" target="_blank">@TheSmartDev</a> on Telegram!</p>

            <div class="footer">
                <p>© 2025 Instagram Post Scraper API | Powered by <a href="https://x.ai" target="_blank">xAI</a></p>
                <p>Unleashing the power of social media scraping, one post at a time! 🌟</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content, 200

@app.route('/download', methods=['POST'])
def download_post():
    """
    Flask endpoint to extract Instagram post media URLs.
    Expects JSON payload: {"url": "https://www.instagram.com/p/XXXXX/"}
    Returns JSON response with status, message, and media URLs.
    """
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({
            "status": "error",
            "message": "Invalid request. Please provide a JSON payload with a 'url' field."
        }), 400

    url = data["url"].strip()
    if not url:
        return jsonify({
            "status": "error",
            "message": "URL cannot be empty."
        }), 400

    # Get media URLs
    result = get_instagram_post_urls(url)
    status_code = 200 if result["status"] == "success" else 400
    return jsonify(result), status_code

# For Vercel serverless (WSGI export)
application = app
