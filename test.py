from flask import Flask, request, jsonify
import instaloader
import os
import re
from datetime import datetime
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
            print("❌ Missing required cookies (sessionid, csrftoken) in cookies.txt 😔")
            return None
    except Exception as e:
        print(f"❌ Failed to parse cookies file: {str(e)} 😔")
        print("💡 Tip: Ensure cookies.txt is in Netscape format with valid sessionid and csrftoken.")
        return None

def download_instagram_post(url, save_dir="downloads", cookies_file="cookies/cookies.txt", max_retries=2):
    """
    Download Instagram post media (image 📸 or video 🎥) from a given URL.
    Requires valid cookies in cookies_file.
    
    Args:
        url (str): Instagram post URL
        save_dir (str): Directory to save downloaded media
        cookies_file (str): Path to cookies.txt file for session authentication
        max_retries (int): Number of retry attempts for failed downloads
    Returns:
        dict: Result with status, message, and file paths (if successful)
    """
    result = {"status": "error", "message": "", "files": []}
    
    # Validate URL
    shortcode = validate_url(url)
    if not shortcode:
        result["message"] = "Invalid Instagram URL! Please ensure it contains a valid post code (e.g., instagram.com/p/XXXXX)."
        return result

    try:
        # Initialize Instaloader with custom User-Agent
        loader = instaloader.Instaloader(
            download_pictures=True,
            download_videos=True,
            download_comments=False,
            download_geotags=False,
            download_video_thumbnails=False,
            save_metadata=False,
            filename_pattern="{shortcode}",
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

        # Create save directory if it doesn't exist
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        # Attempt download with retries
        downloaded_files = []
        for attempt in range(max_retries + 1):
            try:
                post = instaloader.Post.from_shortcode(loader.context, shortcode)
                loader.download_post(post, target=save_dir)
                # Collect downloaded file paths
                for file in os.listdir(save_dir):
                    if file.startswith(shortcode):
                        downloaded_files.append(os.path.join(save_dir, file))
                result["status"] = "success"
                result["message"] = f"Download complete! Files saved in {save_dir}."
                result["files"] = downloaded_files
                return result
            except instaloader.exceptions.ConnectionException as ce:
                if attempt < max_retries:
                    continue
                result["message"] = f"Failed after {max_retries} retries: {str(ce)}."
                return result
            except instaloader.exceptions.BadResponseException as bre:
                result["message"] = f"Instagram blocked the request (403 Forbidden): {str(bre)}. Ensure {cookies_file} contains valid, non-expired session cookies."
                return result

    except instaloader.exceptions.LoginRequiredException:
        result["message"] = f"Login required! This post may be private or requires authentication. Provide a valid {cookies_file} with active session cookies."
        return result
    except Exception as e:
        result["message"] = f"Oops! Something went wrong: {str(e)}. Check your internet connection, URL, cookies file, or try again later."
        return result

@app.route('/download', methods=['POST'])
def download_post():
    """
    Flask endpoint to download Instagram post media.
    Expects JSON payload: {"url": "https://www.instagram.com/p/XXXXX/"}
    Returns JSON response with status, message, and file paths.
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

    # Create unique save directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_dir = f"ig_downloads_{timestamp}"

    # Download post
    result = download_instagram_post(url, save_dir)
    status_code = 200 if result["status"] == "success" else 400
    return jsonify(result), status_code

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)