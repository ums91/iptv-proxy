from flask import Flask, Response, request, jsonify
import requests
import re
import time
import threading
import json
import urllib.parse

app = Flask(__name__)

CACHE_DURATION = 1200  # 20 minutes
HEADERS = {"User-Agent": "Mozilla/5.0"}

with open("channels.json") as f:
    channels = json.load(f)

# Add runtime state
for name in channels:
    channels[name]["master"] = None
    channels[name]["last_refresh"] = 0
    channels[name]["status"] = "idle"

# ---------------- MASTER EXTRACTION ---------------- #

def extract_master_web(channel):
    try:
        page = requests.get(channel["live_page"], headers=HEADERS, timeout=10).text
        match = re.search(r'https://[^"]+main\.m3u8', page)
        return match.group(0) if match else None
    except:
        return None


def refresh_master(name):
    channel = channels[name]
    channel["status"] = "refreshing"

    master = extract_master_web(channel)

    if master:
        channel["master"] = master
        channel["last_refresh"] = time.time()
        channel["status"] = "online"
    else:
        channel["status"] = "error"


def get_master(name):
    channel = channels.get(name)
    if not channel:
        return None

    if channel["master"] and time.time() - channel["last_refresh"] < CACHE_DURATION:
        return channel["master"]

    refresh_master(name)
    return channel["master"]


# ---------------- BACKGROUND REFRESH THREAD ---------------- #

def auto_refresh():
    while True:
        for name in channels:
            if time.time() - channels[name]["last_refresh"] > CACHE_DURATION:
                refresh_master(name)
        time.sleep(300)

threading.Thread(target=auto_refresh, daemon=True).start()

# ---------------- CHANNEL ROUTE ---------------- #

@app.route("/<channel>.m3u8")
def serve_channel(channel):
    master = get_master(channel)
    if not master:
        return "Channel not found", 404

    try:
        r = requests.get(master, headers=HEADERS)
        content = r.text

        base = master.rsplit("/", 1)[0] + "/"
        host = request.host_url.rstrip("/")

        rewritten = []

        for line in content.splitlines():
            if line.startswith("#") or not line.strip():
                rewritten.append(line)
            else:
                absolute = urllib.parse.urljoin(base, line)
                proxy_url = f"{host}/proxy?url={urllib.parse.quote(absolute)}"
                rewritten.append(proxy_url)

        return Response("\n".join(rewritten),
                        content_type="application/vnd.apple.mpegurl")

    except:
        return "Error loading master", 500


# ---------------- PROXY ROUTE ---------------- #

@app.route("/proxy")
def proxy():
    url = request.args.get("url")

    if not url:
        return "Missing URL", 400

    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=10)

        if r.status_code != 200:
            raise Exception("Bad segment")

        return Response(
            r.iter_content(chunk_size=65536),
            content_type=r.headers.get("Content-Type")
        )

    except:
        # Force refresh on failure
        for name in channels:
            channels[name]["last_refresh"] = 0
        return "Segment error, refreshing", 500


# ---------------- DASHBOARD ---------------- #

@app.route("/admin")
def admin():
    return jsonify({
        name: {
            "status": ch["status"],
            "last_refresh": ch["last_refresh"]
        }
        for name, ch in channels.items()
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
