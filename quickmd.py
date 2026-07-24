#!/usr/bin/env python3
"""QuickMD - a simple Markdown viewer for Linux and Windows."""

import atexit
import glob
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import markdown
import webview

APP_NAME = "QuickMD"
MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown", ".mkd", ".txt")


def markdown_extensions():
    extensions = ["extra", "sane_lists"]
    try:
        import pygments  # noqa: F401
        extensions.append("codehilite")
    except ImportError:
        pass
    try:
        import pymdownx  # noqa: F401
        extensions += ["pymdownx.tasklist", "pymdownx.tilde"]
    except ImportError:
        pass
    return extensions


def pygments_css():
    try:
        from pygments.formatters import HtmlFormatter
    except ImportError:
        return ""
    light = HtmlFormatter(style="default").get_style_defs(".codehilite")
    try:
        dark_formatter = HtmlFormatter(style="github-dark")
    except Exception:
        dark_formatter = HtmlFormatter(style="monokai")
    dark = dark_formatter.get_style_defs(".codehilite")
    return light + "\n@media (prefers-color-scheme: dark) {\n" + dark + "\n}"


CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
    margin: 0;
    font-family: -apple-system, "Segoe UI", Cantarell, Ubuntu, Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.55;
    color: #1f2328;
    background: #ffffff;
}
#content { max-width: 860px; margin: 0 auto; padding: 32px 24px 64px; word-wrap: break-word; }
h1, h2, h3, h4, h5, h6 { margin-top: 1.4em; margin-bottom: 0.5em; line-height: 1.25; font-weight: 600; }
h1 { font-size: 2em; border-bottom: 1px solid #d8dee4; padding-bottom: 0.3em; }
h2 { font-size: 1.5em; border-bottom: 1px solid #d8dee4; padding-bottom: 0.3em; }
h3 { font-size: 1.25em; }
a { color: #0969da; text-decoration: none; }
a:hover { text-decoration: underline; }
p, ul, ol, table, blockquote, pre { margin-top: 0; margin-bottom: 16px; }
ul, ol { padding-left: 2em; }
li + li { margin-top: 0.25em; }
img { max-width: 100%; }
hr { border: 0; border-top: 1px solid #d8dee4; margin: 24px 0; }
blockquote { margin-left: 0; padding: 0 1em; color: #59636e; border-left: 4px solid #d8dee4; }
code, pre {
    font-family: ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, Consolas, "DejaVu Sans Mono", monospace;
    font-size: 85%;
}
code { background: rgba(129, 139, 152, 0.18); padding: 0.2em 0.4em; border-radius: 4px; }
pre { background: #f6f8fa; padding: 16px; border-radius: 6px; overflow-x: auto; line-height: 1.45; }
pre code { background: transparent; padding: 0; font-size: 100%; }
.codehilite { background: #f6f8fa; border-radius: 6px; margin-bottom: 16px; }
.codehilite pre { margin-bottom: 0; }
table { border-collapse: collapse; display: block; max-width: 100%; overflow-x: auto; }
th, td { border: 1px solid #d8dee4; padding: 6px 13px; }
th { font-weight: 600; }
tr:nth-child(2n) { background: #f6f8fa; }
input[type="checkbox"] { margin-right: 0.4em; }
.task-list-item { list-style-type: none; }
.task-list-item input { margin-left: -1.5em; }
#welcome { text-align: center; color: #59636e; margin-top: 30vh; }
@media (prefers-color-scheme: dark) {
    body { color: #e6edf3; background: #1e1e1e; }
    h1, h2, hr { border-color: #3d444d; }
    a { color: #4493f8; }
    blockquote { color: #9198a1; border-left-color: #3d444d; }
    pre, .codehilite { background: #2b2b2b; }
    th, td { border-color: #3d444d; }
    tr:nth-child(2n) { background: #262626; }
    #welcome { color: #9198a1; }
}
"""

SCRIPT = """
var zoom = 1.0;
try { zoom = parseFloat(sessionStorage.getItem('quickmd-zoom')) || 1.0; } catch (e) {}

function setZoom(z) {
    zoom = Math.min(4, Math.max(0.3, Math.round(z * 10) / 10));
    document.body.style.zoom = zoom;
    try { sessionStorage.setItem('quickmd-zoom', zoom); } catch (e) {}
}
setZoom(zoom);

window.addEventListener('keydown', function (e) {
    if (!e.ctrlKey) return;
    if (e.key === '=' || e.key === '+') { setZoom(zoom + 0.1); e.preventDefault(); }
    else if (e.key === '-') { setZoom(zoom - 0.1); e.preventDefault(); }
    else if (e.key === '0') { setZoom(1.0); e.preventDefault(); }
    else if (e.key === 'o') { pywebview.api.open_dialog(); e.preventDefault(); }
    else if (e.key === 'r') { pywebview.api.reload(); e.preventDefault(); }
    else if (e.key === 'w' || e.key === 'q') { pywebview.api.close(); e.preventDefault(); }
});

window.addEventListener('wheel', function (e) {
    if (!e.ctrlKey) return;
    setZoom(zoom + (e.deltaY < 0 ? 0.1 : -0.1));
    e.preventDefault();
}, { passive: false });

document.addEventListener('click', function (e) {
    var a = e.target.closest('a');
    if (!a) return;
    var href = a.getAttribute('href') || '';
    if (href.startsWith('#') || href === '') return;
    e.preventDefault();
    pywebview.api.open_link(href);
});
"""

PAGE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{base}
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div id="content">{body}</div>
<script>{script}</script>
</body>
</html>
"""

WELCOME = '<div id="welcome"><h1>QuickMD</h1><p>Open a Markdown file with Ctrl+O</p></div>'


def render_body(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return "<p>Could not read {}: {}</p>".format(path, e)
    return markdown.markdown(text, extensions=markdown_extensions())


def build_page(body, title, base_dir=None):
    base = ""
    if base_dir is not None:
        base = '<base href="{}/">'.format(base_dir.resolve().as_uri())
    return PAGE.format(base=base, title=title, css=CSS + pygments_css(),
                       body=body, script=SCRIPT)


class Api:
    def __init__(self):
        self._window = None
        self._path = None
        self._mtime = 0
        self._counter = 0
        self._temp_dir = tempfile.gettempdir()
        atexit.register(self._cleanup)

    def _temp_file(self):
        self._counter += 1
        return os.path.join(self._temp_dir, "quickmd-{}-{}.html".format(os.getpid(), self._counter))

    def _cleanup(self):
        for f in glob.glob(os.path.join(self._temp_dir, "quickmd-{}-*.html".format(os.getpid()))):
            try:
                os.remove(f)
            except OSError:
                pass

    def _write_page(self, path):
        """Render the file (or the welcome page) to a fresh temp file, return its URI."""
        if path is None:
            html = build_page(WELCOME, APP_NAME)
        else:
            html = build_page(render_body(path), path.name + " - " + APP_NAME, path.parent)
        temp = self._temp_file()
        with open(temp, "w", encoding="utf-8") as f:
            f.write(html)
        return Path(temp).as_uri()

    def _load(self, path):
        path = Path(path).resolve()
        self._path = path
        try:
            self._mtime = path.stat().st_mtime
        except OSError:
            self._mtime = 0
        uri = self._write_page(path)
        if self._window is not None:
            self._window.load_url(uri)
            self._window.set_title(path.name + " - " + APP_NAME)
        return uri

    def _refresh(self):
        """Re-render in place, keeping scroll position and zoom."""
        if self._path is None or self._window is None:
            return
        body = render_body(self._path)
        self._window.evaluate_js(
            "document.getElementById('content').innerHTML = {};".format(json.dumps(body)))

    def _watch(self):
        while True:
            time.sleep(0.5)
            if self._path is None:
                continue
            try:
                mtime = self._path.stat().st_mtime
            except OSError:
                continue
            if mtime != self._mtime:
                self._mtime = mtime
                self._refresh()

    # Methods below are called from JavaScript via pywebview.api.

    def open_link(self, href):
        if href.startswith(("http://", "https://", "mailto:")):
            webbrowser.open(href)
            return
        if self._path is None:
            return
        target = (self._path.parent / href.split("#")[0].split("?")[0]).resolve()
        if not target.exists():
            return
        if target.suffix.lower() in MARKDOWN_SUFFIXES:
            self._load(target)
        elif sys.platform == "win32":
            os.startfile(target)
        else:
            subprocess.Popen(["xdg-open", str(target)])

    def open_dialog(self):
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Markdown files (*.md;*.markdown;*.mdown;*.mkd;*.txt)", "All files (*.*)"))
        if result:
            self._load(result[0])

    def reload(self):
        if self._path is not None:
            self._load(self._path)

    def close(self):
        self._window.destroy()


def main():
    path = None
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        if not path.is_file():
            print("File not found: {}".format(path), file=sys.stderr)
            sys.exit(1)

    api = Api()
    if path is not None:
        api._path = path.resolve()
        try:
            api._mtime = api._path.stat().st_mtime
        except OSError:
            pass
    uri = api._write_page(api._path)
    title = api._path.name + " - " + APP_NAME if api._path else APP_NAME
    api._window = webview.create_window(
        title, url=uri, js_api=api, width=920, height=840, text_select=True)
    webview.start(lambda: threading.Thread(target=api._watch, daemon=True).start())


if __name__ == "__main__":
    main()
