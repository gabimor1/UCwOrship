"""
UCwOrship companion web server.

Runs a Flask app in a background daemon thread. The tkinter main thread calls
push_image() whenever the current song/image changes; connected browsers fetch
the new image from /image and receive a trigger via SSE.
"""

import base64
import io
import json
import os
import queue
import socket
import sys
import threading

from flask import Flask, Response, render_template

# ---------------------------------------------------------------------------
# Flask app — resolve templates dir for both dev and PyInstaller frozen mode
# ---------------------------------------------------------------------------
_here = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
_templates = os.path.join(_here, "ucworship", "templates") if getattr(sys, "frozen", False) \
    else os.path.join(os.path.dirname(__file__), "templates")

app = Flask(__name__, template_folder=_templates)
app.logger.disabled = True

import logging
logging.getLogger("werkzeug").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Shared state
# ---------------------------------------------------------------------------
_image_lock = threading.Lock()
_current_image_bytes: bytes | None = None   # PNG bytes of the current slide
_current_title: str = ""
_current_type: str = "idle"                 # "idle" | "song" | "image"

_subscribers: list[queue.Queue] = []
_subscribers_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Public API (called from tkinter thread)
# ---------------------------------------------------------------------------
def push_image(pil_image, title: str = "", slide_type: str = "song") -> None:
    """
    Thread-safe. Called from the tkinter main thread whenever the displayed
    slide changes. pil_image is a PIL.Image object (or None for idle).
    """
    global _current_image_bytes, _current_title, _current_type
    if pil_image is not None:
        # Downscale to max 1800px wide for fast mobile loading
        img = pil_image.copy()
        if img.width > 1800:
            ratio = 1800 / img.width
            img = img.resize((1800, int(img.height * ratio)), resample=1)  # 1 = LANCZOS
        # JPEG requires RGB — flatten RGBA onto white background
        if img.mode != "RGB":
            from PIL import Image as _Image
            bg = _Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                bg.paste(img, mask=img.split()[3])
            else:
                bg.paste(img.convert("RGB"))
            img = bg
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        image_bytes = buf.getvalue()
    else:
        image_bytes = None

    b64 = base64.b64encode(image_bytes).decode() if image_bytes else None

    with _image_lock:
        _current_image_bytes = image_bytes
        _current_title = title
        _current_type = slide_type if image_bytes else "idle"

    payload = {"type": _current_type, "title": title, "image": b64}
    with _subscribers_lock:
        for q in _subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def start_server(port: int = 5050):
    """Start Flask in a daemon thread. Returns (server, ip, actual_port)."""
    import socket as _socket
    from werkzeug.serving import make_server

    # Find a free port ourselves before handing it to Werkzeug
    actual_port = None
    for p in range(port, port + 10):
        with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
            s.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            if s.connect_ex(("127.0.0.1", p)) != 0:
                actual_port = p
                break

    if actual_port is None:
        return None, get_local_ip(), port

    server = make_server("0.0.0.0", actual_port, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, get_local_ip(), actual_port


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("musician.html")


@app.route("/image")
def image():
    with _image_lock:
        data = _current_image_bytes
    if not data:
        return Response(status=204)  # No Content
    return Response(data, mimetype="image/jpeg",
                    headers={"Cache-Control": "no-store"})


@app.route("/stream")
def stream():
    q: queue.Queue = queue.Queue(maxsize=10)
    with _subscribers_lock:
        _subscribers.append(q)

    def generate():
        # Send current state immediately on connect
        with _image_lock:
            b64 = base64.b64encode(_current_image_bytes).decode() if _current_image_bytes else None
            payload = {"type": _current_type, "title": _current_title, "image": b64}
        yield f"data: {json.dumps(payload)}\n\n"
        while True:
            try:
                payload = q.get(timeout=25)
                yield f"data: {json.dumps(payload)}\n\n"
            except queue.Empty:
                yield ": heartbeat\n\n"

    def guarded_generate():
        try:
            yield from generate()
        finally:
            with _subscribers_lock:
                try:
                    _subscribers.remove(q)
                except ValueError:
                    pass

    return Response(
        guarded_generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
