import sys
import subprocess
import importlib.util

# Auto install required packages
required_packages = {
    "flask": "flask",
    "requests": "requests"
}

for module, package in required_packages.items():
    if importlib.util.find_spec(module) is None:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", package
        ])

import requests
import re
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Accept-Language": "en-US,en;q=0.9",
}

def check_uid(uid: str) -> dict:
    uid = uid.strip()
    result = {
        "uid": uid,
        "status": "UNKNOWN",
        "detail": ""
    }

    if not uid.isdigit():
        result["status"] = "INVALID"
        result["detail"] = "Not a valid numeric UID"
        return result

    # Method 1: Picture endpoint (fastest)
    pic_url = f"https://graph2.facebook.com/v3.3/{uid}/picture?redirect=0"
    try:
        r = requests.get(pic_url, headers=HEADERS, timeout=8)
        text = r.text.lower()
        has_picture = '"height"' in text and '"width"' in text
    except:
        has_picture = False

    # Method 2: Mobile profile page (more accurate)
    profile_url = f"https://m.facebook.com/profile.php?id={uid}"
    try:
        r = requests.get(profile_url, headers=HEADERS, timeout=10, allow_redirects=True)
        html = r.text.lower()
        final_url = r.url.lower()

        # Strong indicators of LIVE
        live_indicators = [
            'og:title',
            'fb://profile/',
            'timeline',
            'about',
            'friends',
        ]
        is_live_page = any(ind in html for ind in live_indicators) and "content isn't available" not in html

        # Restricted / Suspended indicators
        restricted_phrases = [
            "content isn't available",
            "this content isn't available right now",
            "the link you followed may be broken",
            "page isn't available",
        ]
        is_restricted = any(p in html for p in restricted_phrases)

        # Disabled / Gone
        disabled_phrases = [
            "this account is not available",
            "account has been disabled",
            "profile is not available",
        ]
        is_disabled = any(p in html for p in disabled_phrases)

        if has_picture and is_live_page:
            result["status"] = "LIVE"
            result["detail"] = "Account is active and profile is public"
        elif is_restricted or (not has_picture and "login" not in final_url):
            result["status"] = "RESTRICTED"
            result["detail"] = "Profile hidden (Suspended / Checkpoint / Limited)"
        elif is_disabled or (not has_picture and not is_live_page):
            result["status"] = "DISABLED"
            result["detail"] = "Permanently disabled / FAQ / Deleted"
        else:
            result["status"] = "DISABLED"
            result["detail"] = "Cannot determine (possible temporary issue)"

    except Exception as e:
        if has_picture:
            result["status"] = "LIVE"
            result["detail"] = "Picture exists (profile page check failed)"
        else:
            result["status"] = "DISABLED"
            result["detail"] = f"No picture + error: {str(e)[:50]}"

    return result


@app.route("/check", methods=["GET"])
def check():
    uid = request.args.get("uid", "").strip()

    if not uid:
        return jsonify("INVALID"), 400

    res = check_uid(uid)

    status_map = {
        "LIVE": "ALIVE",
        "RESTRICTED": "SUSPENDED",
        "DISABLED": "DISABLED",
        "INVALID": "DISABLED",
        "UNKNOWN": "DISABLED"
    }

    return jsonify(status_map.get(res["status"], "DISABLED"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
      
