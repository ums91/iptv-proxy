from flask import Flask, Response, request
import requests
import urllib.parse

app = Flask(__name__)

CHANNELS = {
    "aryqtv": {
        "url": "https://aryqtv.aryzap.com/38cfadb3eacf7857d79f42495143de3a/699d629f/v1/0183ea2a0eec0b8ed5941a38bc76/0183ea2a4e470b8ed5aa4d793457/ARYQTVH264_480p.m3u8?isSubM3u8=1",
        "headers": {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://live.aryqtv.tv/",
            "Origin": "https://live.aryqtv.tv"
        }
    }
}

def rewrite_m3u8(content, base_url, channel_key):
    lines = content.splitlines()
    rewritten = []

    for line in lines:
        if line.startswith("#") or line.strip() == "":
            rewritten.append(line)
        else:
            absolute = urllib.parse.urljoin(base_url, line)
            encoded = urllib.parse.quote(absolute, safe="")
            proxy_url = f"/segment/{channel_key}?url={encoded}"
            rewritten.append(proxy_url)

    return "\n".join(rewritten)

@app.route("/<channel>.m3u8")
def playlist(channel):
    if channel not in CHANNELS:
        return "Channel not found", 404

    config = CHANNELS[channel]
    r = requests.get(config["url"], headers=config["headers"])

    rewritten = rewrite_m3u8(r.text, config["url"], channel)

    return Response(
        rewritten,
        content_type="application/vnd.apple.mpegurl"
    )

@app.route("/segment/<channel>")
def segment(channel):
    if channel not in CHANNELS:
        return "Channel not found", 404

    url = request.args.get("url")
    decoded = urllib.parse.unquote(url)

    config = CHANNELS[channel]
    r = requests.get(decoded, headers=config["headers"], stream=True)

    return Response(
        r.iter_content(chunk_size=8192),
        content_type=r.headers.get("Content-Type")
    )

@app.route("/")
def home():
    return "IPTV Proxy Running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
