"""Serve the catalog at http://localhost:8000/animated-titles.html (YouTube embeds need an http origin)."""
import functools
import http.server
import os
import sys
import webbrowser

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
url = f"http://localhost:{PORT}/animated-titles.html"
print(f"Serving {ROOT}\nOpen {url}  (Ctrl+C to stop)", flush=True)
if "--no-browser" not in sys.argv:
    webbrowser.open(url)
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
