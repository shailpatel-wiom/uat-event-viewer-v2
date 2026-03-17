"""
UAT Event Viewer — Live CleverTap (+ Firebase/Meta/Branch) event dashboard.
Tails `adb logcat`, parses analytics events, streams them to a browser via SSE.

Usage:
    python server.py              # default port 8070
    python server.py --port 9000  # custom port
"""

import subprocess
import threading
import json
import re
import queue
import argparse
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime

event_queue = queue.Queue()

# --- Logcat parsing -----------------------------------------------------------

# CleverTap "Queued event" pattern — this is the main one in this build
CT_QUEUED = re.compile(r"CleverTap.*?Queued event:\s*(\{.+\})", re.IGNORECASE)

# CleverTap other event patterns
CT_EVENT_PUSH = re.compile(
    r"CleverTap.*?(?:Pushing event|Recording event|Event recorded|Raised event)"
    r".*?[:\-]\s*(.+)",
    re.IGNORECASE,
)

# Generic CleverTap log (for non-event SDK messages we still want to surface)
CT_GENERIC = re.compile(r"CleverTap[^(]*\(\s*\d+\):\s*(.+)", re.IGNORECASE)

# Firebase Analytics
FA_EVENT = re.compile(r"FA(?:-SVC)?\s*:\s*(.+)", re.IGNORECASE)

# Facebook/Meta SDK
META_EVENT = re.compile(
    r"(?:Facebook|FB|AppEvents|FBSDKLog)\s*[:\-]\s*(.+)", re.IGNORECASE
)

# Branch SDK
BRANCH_EVENT = re.compile(r"Branch(?:SDK)?\s*[:\-]\s*(.+)", re.IGNORECASE)

# Noisy CleverTap messages to skip
CT_SKIP = [
    "account id", "token", "network", "inbox", "geofence",
    "location", "device id", "guid", "send queue", "sending request",
    "queue sent", "processing variable", "json object",
    "sdk version", "lifecycle callback", "present", "not present",
    "referrer data", "retry", "delay frequency", "initialized with",
    "delivery_mode", "pushamp", "stringbody",
]


def parse_queued_event(line: str):
    """Parse CleverTap 'Queued event: {...}' lines — the primary event format."""
    m = CT_QUEUED.search(line)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    event_name = data.get("evtName", "")
    if not event_name:
        return None

    props = data.get("evtData", {})
    return {"event": event_name, "props": props}


def parse_clevertap(line: str):
    """Try to extract a CleverTap event from a logcat line."""
    # First try the "Queued event" JSON format
    result = parse_queued_event(line)
    if result:
        return result

    # Try other event patterns
    m = CT_EVENT_PUSH.search(line)
    if m:
        event_text = m.group(1).strip()
        # Try to find JSON payload
        json_match = re.search(r'\{.*\}', event_text)
        props = {}
        if json_match:
            try:
                props = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        name_match = re.match(r'^["\']?([^"\'{\[,]+)["\']?', event_text)
        event_name = name_match.group(1).strip() if name_match else event_text[:80]
        return {"event": event_name, "props": props}

    return None


def classify_line(line: str):
    """Return (sdk, parsed_dict) or None."""

    # CleverTap — primary
    if "CleverTap" in line:
        parsed = parse_clevertap(line)
        if parsed:
            return ("clevertap", parsed)

        # Show generic CleverTap logs (but skip noisy ones)
        m = CT_GENERIC.search(line)
        if m:
            text = m.group(1).strip()
            if any(skip in text.lower() for skip in CT_SKIP):
                return None
            # Skip very short or bracket-heavy internal logs
            if len(text) < 5 or text.startswith("{") or text.startswith("["):
                return None
            return ("clevertap", {"event": text, "props": {}})
        return None

    # Firebase
    if "/FA" in line or "FA-SVC" in line or "FA :" in line:
        m = FA_EVENT.search(line)
        if m:
            return ("firebase", {"event": m.group(1).strip(), "props": {}})

    # Meta
    for kw in ("Facebook", "FB", "FBSDKLog", "AppEvents"):
        if kw in line:
            m = META_EVENT.search(line)
            if m:
                return ("meta", {"event": m.group(1).strip(), "props": {}})
            break

    # Branch
    if "Branch" in line:
        m = BRANCH_EVENT.search(line)
        if m:
            return ("branch", {"event": m.group(1).strip(), "props": {}})

    return None


def tail_logcat():
    """Run adb logcat and push parsed events into the queue."""
    # Use broad filter — CleverTap tags include account ID (e.g. CleverTap:ACCT-ID)
    cmd = ["adb", "logcat", "-v", "time"]
    print(f"[logcat] Starting: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
    )
    for raw_line in proc.stdout:
        line = raw_line.strip()
        if not line:
            continue
        # Quick pre-filter to avoid parsing every logcat line
        if not any(kw in line for kw in (
            "CleverTap", "FA", "Facebook", "FB", "AppEvents",
            "FBSDKLog", "Branch",
        )):
            continue
        result = classify_line(line)
        if result:
            sdk, data = result
            event = {
                "ts": datetime.now().strftime("%H:%M:%S.%f")[:-3],
                "sdk": sdk,
                "event": data["event"],
                "props": data.get("props", {}),
                "raw": line,
            }
            event_queue.put(event)
            # Also print to terminal
            label = f"[{sdk.upper():10s}]"
            print(f"[{event['ts']}] {label} {data['event']}")


# --- HTTP + SSE server --------------------------------------------------------

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(
            *args, directory=os.path.dirname(os.path.abspath(__file__)), **kwargs
        )

    def do_GET(self):
        if self.path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                while True:
                    try:
                        event = event_queue.get(timeout=1)
                        payload = json.dumps(event)
                        self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                    except queue.Empty:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        elif self.path == "/" or self.path == "/index.html":
            self.path = "/index.html"
            super().do_GET()
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description="UAT Event Viewer")
    parser.add_argument("--port", type=int, default=8070)
    args = parser.parse_args()

    # Start logcat reader thread
    t = threading.Thread(target=tail_logcat, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", args.port), Handler)
    print(f"[server] Dashboard -> http://localhost:{args.port}")
    print(f"[server] Make sure emulator is running and app is open.")
    print(f"[server] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[server] Stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
