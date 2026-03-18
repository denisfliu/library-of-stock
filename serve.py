"""
serve.py — Simple web server to browse generated stock guides.

Usage:
    python serve.py [port]
    python serve.py         # defaults to port 8000

Opens a browser-based interface listing all generated stock guides
with search/filter. Click any guide to open it.
"""

import http.server
import json
import os
import socketserver
from pathlib import Path

PORT = 8000
OUTPUT_DIR = Path("output")


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Stock Knowledge Guides</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, 'Segoe UI', Roboto, sans-serif;
    background: #101418;
    color: #c8ccd1;
    max-width: 700px;
    margin: 0 auto;
    padding: 2rem 1.5rem;
}
h1 {
    font-family: 'Linux Libertine', Georgia, serif;
    font-weight: normal;
    font-size: 1.6rem;
    color: #e0e0e0;
    border-bottom: 1px solid #3a3f47;
    padding-bottom: 0.3rem;
    margin-bottom: 1rem;
}
.search {
    width: 100%;
    padding: 0.5rem 0.8rem;
    font-size: 0.95rem;
    background: #1a1f25;
    color: #c8ccd1;
    border: 1px solid #3a3f47;
    border-radius: 4px;
    margin-bottom: 1rem;
    outline: none;
}
.search:focus {
    border-color: #6b9eff;
}
.search::placeholder {
    color: #666;
}
.guide-list {
    list-style: none;
}
.guide-item {
    border: 1px solid #3a3f47;
    background: #1a1f25;
    margin-bottom: 0.5rem;
    border-radius: 4px;
    overflow: hidden;
}
.guide-item a {
    display: block;
    padding: 0.6rem 0.8rem;
    color: #6b9eff;
    text-decoration: none;
    font-size: 0.95rem;
}
.guide-item a:hover {
    background: #262d37;
}
.guide-meta {
    font-size: 0.78rem;
    color: #808790;
    margin-top: 0.15rem;
}
.empty {
    color: #666;
    font-style: italic;
    padding: 1rem 0;
}
.count {
    font-size: 0.82rem;
    color: #808790;
    margin-bottom: 0.8rem;
}
</style>
</head>
<body>
<h1>Stock Knowledge Guides</h1>
<input class="search" type="text" placeholder="Search guides..." autofocus>
<div class="count"></div>
<ul class="guide-list"></ul>
<script>
const guides = GUIDE_DATA;
const list = document.querySelector('.guide-list');
const search = document.querySelector('.search');
const count = document.querySelector('.count');

function render(filter) {
    const q = (filter || '').toLowerCase();
    const filtered = guides.filter(g => g.name.toLowerCase().includes(q));
    count.textContent = filtered.length + ' guide' + (filtered.length !== 1 ? 's' : '');
    if (filtered.length === 0) {
        list.innerHTML = '<li class="empty">No guides found.</li>';
        return;
    }
    list.innerHTML = filtered.map(g => `
        <li class="guide-item">
            <a href="${g.path}">
                ${g.name}
                <div class="guide-meta">${g.works} works &middot; ${g.size} &middot; ${g.modified}</div>
            </a>
        </li>
    `).join('');
}

search.addEventListener('input', e => render(e.target.value));
render('');
</script>
</body>
</html>"""


class StockHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_index()
        else:
            super().do_GET()

    def send_index(self):
        guides = []
        for f in sorted(OUTPUT_DIR.glob("*_stock.html")):
            name = f.stem.replace("_stock", "").replace("_", " ").title()
            size = f.stat().st_size
            if size > 1024:
                size_str = f"{size / 1024:.0f} KB"
            else:
                size_str = f"{size} B"
            # Try to count works from the analysis JSON
            analysis_path = OUTPUT_DIR / f.stem.replace("_stock", "_analysis") / ""
            analysis_json = f.with_name(f.stem.replace("_stock", "_analysis") + ".json")
            works_count = "?"
            if analysis_json.exists():
                try:
                    with open(analysis_json) as af:
                        data = json.load(af)
                        works_count = str(len(data.get("works", [])))
                except Exception:
                    pass
            from datetime import datetime
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
            guides.append({
                "name": name,
                "path": f"output/{f.name}",
                "works": works_count,
                "size": size_str,
                "modified": mtime,
            })

        html = INDEX_HTML.replace("GUIDE_DATA", json.dumps(guides))
        content = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        print(f"  {args[0]}")


def main():
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    with socketserver.TCPServer(("", port), StockHandler) as httpd:
        print(f"Stock Knowledge server running at http://localhost:{port}")
        print(f"Serving {len(list(OUTPUT_DIR.glob('*_stock.html')))} guides")
        print("Press Ctrl+C to stop.\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
