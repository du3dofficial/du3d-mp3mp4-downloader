# DU3D Downloader website

This package contains a responsive website front end and a small yt-dlp server. It supports YouTube and TikTok links, MP3/MP4 conversion, and YouTube playlists (up to 20 items, returned as a ZIP). The logo links to the DU3D YouTube channel.

## Run locally

Install Python 3.12+, FFmpeg, and yt-dlp, then from this folder run:

```sh
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m pip install yt-dlp
python app.py
```

Open http://localhost:8080.

## Upload/deploy

This is a Docker website because media extraction and MP3 conversion need a server with yt-dlp and FFmpeg. Upload this `website` folder to a Docker-capable web host, create a Web Service from its Dockerfile, and expose port 8080. A static-only host cannot perform the downloads; it would need this backend hosted separately and the page API URL configured for that host.

Before making the service public, add the host's persistent rate limit, storage limits, and abuse controls. The included basic per-process rate limit is only a starting point and resets when the server restarts. Keep playlist and file size limits appropriate for your hosting plan. Hosting providers may restrict media downloading, so check the provider's terms.

Use the service only for media you own or have permission to download, and follow the platform and hosting provider terms.
