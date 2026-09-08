#!/usr/bin/env python3
"""Local admin page for the WIn Lab website.

    python3 admin.py            # opens http://localhost:8765/admin/ in your browser

Runs only on your computer. Edits data/site.json and data/publications.json, rebuilds the
HTML with build.py, and serves the built site at http://localhost:8765/ for preview.
Nothing here needs to be uploaded to GitHub except the files the page lists after a build.
"""
import base64, json, os, sys, threading, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

# When packaged as an exe (PyInstaller), work relative to the exe's folder, not the temp extraction dir.
ROOT = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
sys.path.insert(0, ROOT)
import build  # noqa: E402
build.ROOT = ROOT
build.SITE = SITE = os.path.join(ROOT, "docs")
build.DATA = DATA = os.path.join(ROOT, "data")
build.SITE_JSON = os.path.join(DATA, "site.json")
build.PUBS_JSON = os.path.join(DATA, "publications.json")

PORT = 8765
LOCK = threading.Lock()


def read_json(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


def write_json(name, data):
    with open(os.path.join(DATA, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=SITE, **kw)   # "/" serves the built site (preview)

    def translate_path(self, path):
        # "/admin/..." is served from the tools folder, everything else from ./docs
        p = urlparse(path).path
        if p == "/admin" or p.startswith("/admin/"):
            rel = p[len("/admin"):].lstrip("/") or "index.html"
            return os.path.join(ROOT, "admin", rel)
        return super().translate_path(path)

    def log_message(self, fmt, *args):  # keep the console quiet: only show API calls
        if args and "/api/" in str(args[0]):
            super().log_message(fmt, *args)

    def log_error(self, fmt, *args):    # 404s etc. are not interesting during local preview
        pass

    # ---- helpers
    def send_json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def read_body(self):
        n = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(n).decode("utf-8")) if n else {}

    def end_headers(self):
        # never cache during local preview, so edits show up immediately
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # ---- routes
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/data":
            return self.send_json({"site": read_json("site.json"), "pubs": read_json("publications.json"), "root": ROOT,
                                   "photos": sorted(os.listdir(os.path.join(SITE, "assets/photos"))),
                                   "research_images": sorted(os.listdir(os.path.join(SITE, "assets/research")))})
        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            if path == "/api/save":
                data = self.read_body()
                with LOCK:
                    write_json("site.json", data["site"])
                    write_json("publications.json", data["pubs"])
                    written = build.build() if data.get("build", True) else []
                return self.send_json({"ok": True, "written": written})
            if path == "/api/build":
                with LOCK:
                    written = build.build()
                return self.send_json({"ok": True, "written": written})
            if path == "/api/upload":
                d = self.read_body()
                folder = "assets/photos" if d.get("kind") == "photo" else "assets/research"
                name = os.path.basename(d["name"])
                if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                    return self.send_json({"ok": False, "error": "jpg/png only"}, 400)
                with open(os.path.join(SITE, folder, name), "wb") as f:
                    f.write(base64.b64decode(d["data"].split(",")[-1]))
                return self.send_json({"ok": True, "path": f"{folder}/{name}"})
            if path == "/api/delete-photo":
                d = self.read_body()
                p = os.path.join(SITE, "assets/photos", os.path.basename(d["name"]))
                if os.path.exists(p):
                    os.remove(p)
                return self.send_json({"ok": True})
            return self.send_json({"ok": False, "error": "unknown endpoint"}, 404)
        except Exception as e:  # show the error in the page instead of dying
            return self.send_json({"ok": False, "error": f"{type(e).__name__}: {e}"}, 500)


if __name__ == "__main__":
    # If another admin (e.g. from an older copy of this folder) is still running on 8765, use the next free port
    # so this window never silently edits the wrong folder.
    server = None
    for port in range(PORT, PORT + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            print(f"Port {port} is in use (another admin window is probably open) - trying {port + 1}")
    if server is None:
        print("Could not open a port. Close other admin windows and try again."); input("Press Enter to exit."); sys.exit(1)
    PORT = port
    url = f"http://localhost:{PORT}/admin/"
    for need in ("admin/index.html", "data/site.json", "data/publications.json", "docs/assets/style.css"):
        if not os.path.exists(os.path.join(ROOT, need)):
            print(f"'{need}' not found next to this program. Put {'WInLabAdmin.exe' if getattr(sys, 'frozen', False) else 'admin.py'} in the winlab-website folder (next to data/ and docs/) and run it again.")
            input("Press Enter to exit."); sys.exit(1)
    print(f"WIn Lab admin\n  Admin page:   {url}\n  Site preview: http://localhost:{PORT}/\n  Site folder:  {SITE}  (served by GitHub Pages)\nClose this window (or press Ctrl+C) to stop.")
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
