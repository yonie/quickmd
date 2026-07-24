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
#toolbar {
    position: sticky; top: 0; z-index: 10;
    display: flex; align-items: center; gap: 4px;
    padding: 6px 10px;
    background: #f6f8fa; border-bottom: 1px solid #d8dee4;
    font-size: 13px;
    user-select: none; -webkit-user-select: none;
}
#toolbar button {
    font: inherit; color: inherit;
    background: transparent; border: 1px solid transparent; border-radius: 6px;
    padding: 3px 10px;
}
#toolbar button:hover { background: rgba(129, 139, 152, 0.2); }
#toolbar button.active { background: rgba(129, 139, 152, 0.25); border-color: #d8dee4; }
#toolbar .sep { width: 1px; align-self: stretch; background: #d8dee4; margin: 2px 6px; }
#copybtn { min-width: 6.5em; }
#help {
    position: fixed; inset: 0; z-index: 20;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.4);
}
#help[hidden] { display: none; }
#help .card {
    background: #ffffff; border-radius: 8px; padding: 20px 28px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2); font-size: 14px;
}
#help .row { margin: 6px 0; }
kbd {
    font-family: ui-monospace, "Cascadia Code", Menlo, Consolas, monospace;
    font-size: 85%; padding: 0.1em 0.5em;
    background: rgba(129, 139, 152, 0.18);
    border: 1px solid #d8dee4; border-radius: 4px;
}
#rawview {
    display: block; width: 100%; min-height: calc(100vh - 160px);
    border: none; outline: none; resize: none; padding: 0;
    background: transparent; color: inherit;
    font-family: ui-monospace, "Cascadia Code", "Source Code Pro", Menlo, Consolas, "DejaVu Sans Mono", monospace;
    font-size: 85%; line-height: 1.6;
    white-space: pre-wrap; word-break: break-word;
}
#welcome { text-align: center; color: #59636e; margin-top: 30vh; }
@media (prefers-color-scheme: dark) {
    body { color: #e6edf3; background: #1e1e1e; }
    h1, h2, hr { border-color: #3d444d; }
    a { color: #4493f8; }
    blockquote { color: #9198a1; border-left-color: #3d444d; }
    pre, .codehilite { background: #2b2b2b; }
    th, td { border-color: #3d444d; }
    tr:nth-child(2n) { background: #262626; }
    #toolbar { background: #2b2b2b; border-bottom-color: #3d444d; }
    #toolbar button.active { border-color: #3d444d; }
    #toolbar .sep { background: #3d444d; }
    #help .card { background: #2b2b2b; }
    kbd { border-color: #3d444d; }
    #welcome { color: #9198a1; }
}
"""

SCRIPT = """
var rawText = __RAW__;
var rawMode = false;
var renderedHtml = null;
var dirty = false;
var zoom = 1.0;
try { zoom = parseFloat(sessionStorage.getItem('quickmd-zoom')) || 1.0; } catch (e) {}

function setZoom(z) {
    zoom = Math.min(4, Math.max(0.3, Math.round(z * 10) / 10));
    document.getElementById('content').style.zoom = zoom;
    document.getElementById('zoomlabel').textContent = Math.round(zoom * 100) + '%';
    try { sessionStorage.setItem('quickmd-zoom', zoom); } catch (e) {}
}
setZoom(zoom);

function showRaw(on) {
    if (on === rawMode) return;
    var c = document.getElementById('content');
    if (on) {
        renderedHtml = c.innerHTML;
        c.innerHTML = '';
        var ta = document.createElement('textarea');
        ta.id = 'rawview';
        ta.value = rawText;
        ta.spellcheck = false;
        ta.addEventListener('input', function () { rawText = ta.value; dirty = true; });
        c.appendChild(ta);
    } else {
        if (dirty) {
            pywebview.api.render_text(rawText).then(function (html) {
                renderedHtml = html;
                if (!rawMode) c.innerHTML = html;
            });
        }
        c.innerHTML = renderedHtml;
    }
    rawMode = on;
    document.getElementById('rawbtn').classList.toggle('active', on);
}

function toggleRaw() { showRaw(!rawMode); }

function quickmdUpdate(html, raw) {
    if (dirty) return;
    rawText = raw;
    renderedHtml = html;
    if (rawMode) {
        var ta = document.getElementById('rawview');
        if (ta) ta.value = raw;
    } else {
        document.getElementById('content').innerHTML = html;
    }
}

function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); } catch (e) {}
    document.body.removeChild(ta);
}

var copyLabel = document.getElementById('copybtn').textContent;

function toggleHelp() {
    var h = document.getElementById('help');
    h.hidden = !h.hidden;
}

function doPaste() {
    pywebview.api.paste_clipboard().then(function (text) {
        if (!text) return;
        rawText = text;
        dirty = true;
        if (rawMode) document.getElementById('rawview').value = text;
        else showRaw(true);
    });
}

function doCopy() {
    var sel = '';
    var ta = document.getElementById('rawview');
    if (ta) sel = ta.value.substring(ta.selectionStart, ta.selectionEnd);
    else sel = window.getSelection().toString();
    var text = sel || rawText;
    function done() {
        var b = document.getElementById('copybtn');
        b.textContent = '\\u2714 Copied';
        setTimeout(function () { b.textContent = copyLabel; }, 1200);
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    } else {
        fallbackCopy(text);
        done();
    }
}

window.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { document.getElementById('help').hidden = true; return; }
    if (!e.ctrlKey) return;
    if (e.key === '=' || e.key === '+') { setZoom(zoom + 0.1); e.preventDefault(); }
    else if (e.key === '-') { setZoom(zoom - 0.1); e.preventDefault(); }
    else if (e.key === '0') { setZoom(1.0); e.preventDefault(); }
    else if (e.key === 's') { pywebview.api.save_as(rawText); e.preventDefault(); }
    else if (e.key === 'v' && !rawMode) { doPaste(); e.preventDefault(); }
    else if (e.key === 'u') { toggleRaw(); e.preventDefault(); }
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
<div id="toolbar" onmousedown="event.preventDefault()">
<button onclick="pywebview.api.open_dialog()" title="Open a file (Ctrl+O)">&#128194; Open...</button>
<button onclick="doPaste()" title="Paste clipboard text as a new document (Ctrl+V)">&#128203; Paste</button>
<button onclick="pywebview.api.save_as(rawText)" title="Save a copy, including your edits (Ctrl+S)">&#128190; Save as...</button>
<span class="sep"></span>
<button id="copybtn" onclick="doCopy()" title="Copy selection, or the whole source">&#128196; Copy</button>
<button id="rawbtn" onclick="toggleRaw()" title="Toggle raw Markdown source (Ctrl+U)">&#128220; Raw</button>
<span class="sep"></span>
<button onclick="setZoom(zoom - 0.1)" title="Zoom out (Ctrl+-)">&#128269;&minus;</button>
<button id="zoomlabel" onclick="setZoom(1.0)" title="Reset zoom (Ctrl+0)">100%</button>
<button onclick="setZoom(zoom + 0.1)" title="Zoom in (Ctrl+=)">&#128269;+</button>
<span class="sep"></span>
<button onclick="toggleHelp()" title="Keyboard shortcuts">&#10067; Help</button>
</div>
<div id="help" hidden onclick="toggleHelp()">
<div class="card">
<div class="row"><kbd>Ctrl+O</kbd> Open a file</div>
<div class="row"><kbd>Ctrl+V</kbd> Paste clipboard as a new document</div>
<div class="row"><kbd>Ctrl+S</kbd> Save a copy</div>
<div class="row"><kbd>Ctrl+C</kbd> Copy selected text</div>
<div class="row"><kbd>Ctrl+U</kbd> Toggle raw source</div>
<div class="row"><kbd>Ctrl+R</kbd> Reload file</div>
<div class="row"><kbd>Ctrl+scroll</kbd> <kbd>Ctrl+=</kbd> <kbd>Ctrl+-</kbd> Zoom</div>
<div class="row"><kbd>Ctrl+0</kbd> Reset zoom</div>
<div class="row"><kbd>Ctrl+W</kbd> <kbd>Ctrl+Q</kbd> Quit</div>
</div>
</div>
<div id="content">{body}</div>
<script>{script}</script>
</body>
</html>
"""

WELCOME = ('<div id="welcome"><h1>QuickMD</h1>'
           '<p>Open a Markdown file with <kbd>Ctrl+O</kbd>,'
           ' paste clipboard text with <kbd>Ctrl+V</kbd>,<br>'
           'or switch to Raw with <kbd>Ctrl+U</kbd> to start writing a new one.</p>'
           '<p>Save your work with <kbd>Ctrl+S</kbd>.</p></div>')


def clipboard_text():
    if sys.platform == "win32":
        import ctypes
        CF_UNICODETEXT = 13
        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        u32.GetClipboardData.restype = ctypes.c_void_p
        k32.GlobalLock.restype = ctypes.c_void_p
        k32.GlobalLock.argtypes = [ctypes.c_void_p]
        k32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        if not u32.OpenClipboard(0):
            return ""
        try:
            handle = u32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = k32.GlobalLock(handle)
            try:
                return ctypes.wstring_at(ptr) if ptr else ""
            finally:
                k32.GlobalUnlock(handle)
        finally:
            u32.CloseClipboard()
    for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b"]):
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
            if out.returncode == 0:
                return out.stdout
        except OSError:
            continue
    return ""


def read_raw(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return "Could not read {}: {}".format(path, e)


def render_body(path):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return "<p>Could not read {}: {}</p>".format(path, e)
    return markdown.markdown(text, extensions=markdown_extensions())


def build_page(body, title, base_dir=None, raw=""):
    base = ""
    if base_dir is not None:
        base = '<base href="{}/">'.format(base_dir.resolve().as_uri())
    return PAGE.format(base=base, title=title, css=CSS + pygments_css(),
                       body=body, script=SCRIPT.replace("__RAW__", json.dumps(raw)))


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
            html = build_page(render_body(path), path.name + " - " + APP_NAME,
                              path.parent, read_raw(path))
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
        raw = read_raw(self._path)
        self._window.evaluate_js(
            "quickmdUpdate({}, {});".format(json.dumps(body), json.dumps(raw)))

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

    def render_text(self, text):
        return markdown.markdown(text, extensions=markdown_extensions())

    def paste_clipboard(self):
        return clipboard_text()

    def save_as(self, text):
        name = self._path.name if self._path else "untitled.md"
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG, save_filename=name,
            file_types=("Markdown files (*.md;*.markdown;*.mdown;*.mkd;*.txt)", "All files (*.*)"))
        if not result:
            return
        if isinstance(result, (list, tuple)):
            result = result[0]
        target = Path(result)
        try:
            target.write_text(text, encoding="utf-8")
        except OSError as e:
            print("Could not save {}: {}".format(target, e), file=sys.stderr)
            return
        self._load(target)

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
