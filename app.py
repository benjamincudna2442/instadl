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
    Returns a modern, responsive HTML page with API status, form for testing, and developer info.
    """
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram Post Scraper API</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-gradient-to-br from-purple-100 to-pink-100 min-h-screen flex items-center justify-center p-4">
        <div class="max-w-4xl w-full bg-white rounded-2xl shadow-xl p-8 md:p-12">
            <h1 class="text-4xl md:text-5xl font-bold text-center text-purple-600 mb-4">Instagram Post Scraper API</h1>
            <p class="text-center text-xl text-green-600 font-semibold mb-6">API Status: <span id="api-status">Checking...</span> 🚀</p>
            <p class="text-center text-lg text-gray-600 mb-8">Extract direct media URLs from Instagram posts effortlessly!</p>
            
            <!-- API Test Form -->
            <div class="bg-gray-50 p-6 rounded-lg mb-8">
                <h2 class="text-2xl font-semibold text-gray-800 mb-4">Try It Out</h2>
                <div class="flex flex-col md:flex-row gap-4">
                    <input id="instagram-url" type="text" placeholder="Enter Instagram post URL (e.g., https://www.instagram.com/p/XXXXX/)" 
                           class="flex-1 p-3 border rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500">
                    <button id="submit-url" class="bg-purple-600 text-white px-6 py-3 rounded-lg hover:bg-purple-700 transition">Get Media URLs</button>
                </div>
                <div id="result" class="mt-4 text-gray-700"></div>
            </div>
            
            <!-- Why Use This API -->
            <h2 class="text-2xl font-semibold text-gray-800 mb-4">Why Use This API?</h2>
            <p class="text-gray-600 mb-6">Fast, reliable, and developer-friendly! Scrape Instagram post media (images/videos) in seconds, including multi-media sidecar posts. Perfect for automation, content analysis, or media downloading.</p>
            
            <!-- API Documentation -->
            <h2 class="text-2xl font-semibold text-gray-800 mb-4">POST /download - How It Works</h2>
            <p class="text-gray-600 mb-4">Send a POST request to <code class="bg-gray-100 p-1 rounded">/download</code> with a JSON payload containing an Instagram post URL.</p>
            <pre class="bg-gray-900 text-white p-4 rounded-lg overflow-x-auto">
<strong>Request Example:</strong>
curl -X POST https://your-api-url/download \\
-H "Content-Type: application/json" \\
-d '{"url": "https://www.instagram.com/p/XXXXX/"}'

<strong>Response Example (Success):</strong>
{
  "status": "success",
  "message": "Media URLs extracted successfully.",
  "media_urls": [
    "https://instagram.com/.../media1.jpg",
    "https://instagram.com/.../media2.mp4"
  ]
}

<strong>Response Example (Error):</strong>
{
  "status": "error",
  "message": "Invalid Instagram URL! Please ensure it contains a valid post code.",
  "media_urls": []
}
            </pre>
            <p class="text-gray-600 mt-4"><strong>Note:</strong> Requires valid Instagram session cookies (<code>cookies/cookies.txt</code>) in Netscape format with <code>sessionid</code> and <code>csrftoken</code>.</p>
            
            <!-- Footer -->
            <div class="mt-12 text-center">
                <p class="text-gray-600">Built with ❤️ by <a href="https://x.com/ISmartDevs" target="_blank" class="text-purple-600 hover:underline">@ISmartDevs</a></p>
                <p class="text-gray-600">Join our community at <a href="https://t.me/TheSmartDev" target="_blank" class="text-purple-600 hover:underline">@TheSmartDev</a></p>
                <p class="text-gray-500 mt-4">© 2025 Instagram Post Scraper API | Powered by <a href="https://x.ai" target="_blank" class="text-purple-600 hover:underline">xAI</a></p>
            </div>
        </div>
        
        <!-- Client-side JavaScript for API status and form submission -->
        <script>
            // Check API status
            async function checkApiStatus() {
                try {
                    const response = await fetch('/download', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url: '' }) });
                    document.getElementById('api-status').textContent = response.ok ? 'Live' : 'Down';
                    document.getElementById('api-status').className = response.ok ? 'text-green-600' : 'text-red-600';
                } catch (error) {
                    document.getElementById('api-status').textContent = 'Down';
                    document.getElementById('api-status').className = 'text-red-600';
                }
            }
            checkApiStatus();

            // Handle form submission
            document.getElementById('submit-url').addEventListener('click', async () => {
                const url = document.getElementById('instagram-url').value;
                const resultDiv = document.getElementById('result');
                resultDiv.innerHTML = 'Loading...';
                
                try {
                    const response = await fetch('/download', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ url })
                    });
                    const data = await response.json();
                    if (data.status === 'success') {
                        resultDiv.innerHTML = `<p class="text-green-600">Success: ${data.message}</p><ul class="list-disc pl-5">${data.media_urls.map(url => `<li><a href="${url}" target="_blank" class="text-blue-600 hover:underline">${url}</a></li>`).join('')}</ul>`;
                    } else {
                        resultDiv.innerHTML = `<p class="text-red-600">Error: ${data.message}</p>`;
                    }
                } catch (error) {
                    resultDiv.innerHTML = `<p class="text-red-600">Error: Failed to fetch media URLs. Please try again.</p>`;
                }
            });
        </script>
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
