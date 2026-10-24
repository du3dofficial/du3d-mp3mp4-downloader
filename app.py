import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
MAX_PLAYLIST_ITEMS = int(os.environ.get("MAX_PLAYLIST_ITEMS", "20"))
MAX_ACTIVE_DOWNLOADS = int(os.environ.get("MAX_ACTIVE_DOWNLOADS", "2"))
DOWNLOAD_SLOTS = threading.BoundedSemaphore(MAX_ACTIVE_DOWNLOADS)
RECENT_REQUESTS = {}
RATE_LIMIT_LOCK = threading.Lock()


def valid_media_url(value):
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    allowed = ("youtube.com", "youtu.be", "youtube-nocookie.com", "tiktok.com")
    return parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in allowed)


def rate_limited(ip):
    now = time.time()
    with RATE_LIMIT_LOCK:
        for key, stamp in list(RECENT_REQUESTS.items()):
            if now - stamp > 60:
                RECENT_REQUESTS.pop(key, None)
        if ip in RECENT_REQUESTS and now - RECENT_REQUESTS[ip] < 20:
            return True
        RECENT_REQUESTS[ip] = now
        return False


@app.get("/")
def home():
    return render_template("index.html")


@app.post("/api/download")
def download():
    payload = request.get_json(silent=True) or {}
    url = str(payload.get("url", "")).strip()
    media_format = str(payload.get("format", "mp3")).lower()
    if not valid_media_url(url):
        return jsonify(error="Enter a valid HTTPS YouTube or TikTok link."), 400
    if media_format not in ("mp3", "mp4"):
        return jsonify(error="Choose MP3 or MP4."), 400
    if rate_limited(request.remote_addr or "unknown"):
        return jsonify(error="Please wait a little before starting another download."), 429
    if not DOWNLOAD_SLOTS.acquire(blocking=False):
        return jsonify(error="The server is busy. Try again shortly."), 503

    temp_dir = Path(tempfile.mkdtemp(prefix="du3d-download-"))
    try:
        template = str(temp_dir / "%(playlist_index)03d-%(title).120B.%(ext)s")
        args = ["yt-dlp", "--no-warnings", "--restrict-filenames", "--max-filesize", "500M",
                "--yes-playlist", "--playlist-end", str(MAX_PLAYLIST_ITEMS), "-o", template]
        if media_format == "mp3":
            args += ["-x", "--audio-format", "mp3", "--audio-quality", "0"]
        else:
            args += ["-f", "bv*[height<=1080]+ba/b[height<=1080]/b", "--merge-output-format", "mp4"]
        args.append(url)
        result = subprocess.run(args, capture_output=True, text=True, timeout=900, check=False)
        files = [p for p in temp_dir.iterdir() if p.is_file() and p.suffix.lower() in (".mp3", ".mp4", ".m4a", ".webm", ".mkv")]
        if result.returncode != 0 or not files:
            details = (result.stderr or result.stdout or "No media file was produced.")[-900:]
            shutil.rmtree(temp_dir, ignore_errors=True)
            return jsonify(error="Download failed. " + details), 502
        if len(files) == 1:
            output = files[0]
        else:
            import zipfile
            output = temp_dir / "DU3D-Downloads.zip"
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in files:
                    archive.write(file, arcname=file.name)
        response = send_file(output, as_attachment=True, download_name=output.name)
        response.call_on_close(lambda: shutil.rmtree(temp_dir, ignore_errors=True))
        return response
    except subprocess.TimeoutExpired:
        shutil.rmtree(temp_dir, ignore_errors=True)
        return jsonify(error="The download timed out. Try a shorter video or smaller playlist."), 504
    except Exception as error:
        shutil.rmtree(temp_dir, ignore_errors=True)
        app.logger.exception("Download request failed")
        return jsonify(error="The server could not complete this download."), 500
    finally:
        DOWNLOAD_SLOTS.release()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
