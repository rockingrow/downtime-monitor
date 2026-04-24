#!/usr/bin/env python3
"""
Internet downtime monitor.

Usage:
    python monitor.py              # run in foreground
    python monitor.py --daemon     # run in background (detached)
    python monitor.py --stop       # stop background instance (uses PID file)
"""

import os
import sys
import time
import socket
import datetime

UTC = datetime.timezone.utc

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DNS_TARGETS = [
    ("8.8.8.8", 53),   # Google
    ("1.1.1.1", 53),   # Cloudflare
]
CHECK_INTERVAL = 5    # seconds between each connectivity probe
SOCK_TIMEOUT   = 3    # socket connect timeout
PING_OVER      = 100  # ms; log a warning when DNS connect latency exceeds this

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR  = os.path.join(BASE_DIR, "logs")
PID_FILE = os.path.join(BASE_DIR, "monitor.pid")

# ---------------------------------------------------------------------------
# Connectivity check
# ---------------------------------------------------------------------------

def check_connection() -> tuple[bool, float | None]:
    """Return (reachable, ping_ms). ping_ms is None when all targets are unreachable."""
    for host, port in DNS_TARGETS:
        try:
            t0 = time.monotonic()
            s = socket.create_connection((host, port), timeout=SOCK_TIMEOUT)
            s.close()
            return True, (time.monotonic() - t0) * 1000
        except OSError:
            pass
    return False, None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log_downtime(start: datetime.datetime, end: datetime.datetime) -> None:
    """Append one downtime record to the daily log file for *end* date."""
    os.makedirs(LOG_DIR, exist_ok=True)
    duration = int((end - start).total_seconds())
    path = os.path.join(LOG_DIR, end.strftime("%Y%m%d") + ".txt")
    line = (
        f"{start.strftime('%Y-%m-%d %H:%M:%S')} UTC -> "
        f"{end.strftime('%Y-%m-%d %H:%M:%S')} UTC | "
        f"duration: {duration}s\n"
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
    print(f"[logged] {line.rstrip()}", flush=True)

def log_event(msg: str) -> None:
    """Append a timestamped operational event to today's log."""
    os.makedirs(LOG_DIR, exist_ok=True)
    now  = datetime.datetime.now(UTC)
    path = os.path.join(LOG_DIR, now.strftime("%Y%m%d") + ".txt")
    line = f"{now.strftime('%Y-%m-%d %H:%M:%S')} UTC | {msg}\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
    print(f"[event]  {msg}", flush=True)

# ---------------------------------------------------------------------------
# Main monitoring loop
# ---------------------------------------------------------------------------

def monitor_loop() -> None:
    log_event("🟢 Monitor started")
    down_since: datetime.datetime | None = None

    while True:
        now = datetime.datetime.now(UTC)
        up, ping_ms = check_connection()

        if not up and down_since is None:
            down_since = now
            log_event(f"⚠️ Internet DOWN at {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        elif up and down_since is not None:
            log_downtime(down_since, now)
            down_since = None

        if ping_ms is not None and ping_ms > PING_OVER:
            log_event(f"🐢 High ping {ping_ms:.0f}ms (threshold: {PING_OVER}ms)")

        time.sleep(CHECK_INTERVAL)

# ---------------------------------------------------------------------------
# Background / daemon helpers
# ---------------------------------------------------------------------------

def _daemonize_unix() -> None:
    """Double-fork daemonize; redirect stdio to /dev/null."""
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)

    sys.stdout.flush()
    sys.stderr.flush()
    devnull = open(os.devnull, "a+")
    os.dup2(open(os.devnull, "r").fileno(), sys.stdin.fileno())
    os.dup2(devnull.fileno(), sys.stdout.fileno())
    os.dup2(devnull.fileno(), sys.stderr.fileno())


def _spawn_detached_windows() -> None:
    """Re-launch this script as a detached background process on Windows."""
    import subprocess
    script = os.path.abspath(sys.argv[0])
    proc = subprocess.Popen(
        [sys.executable, script, "--run"],
        creationflags=(
            subprocess.DETACHED_PROCESS |
            subprocess.CREATE_NEW_PROCESS_GROUP |
            subprocess.CREATE_NO_WINDOW
        ),
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(f"Monitor started in background (PID {proc.pid})")
    sys.exit(0)


def write_pid() -> None:
    with open(PID_FILE, "w") as fh:
        fh.write(str(os.getpid()))


def stop_background() -> None:
    if not os.path.exists(PID_FILE):
        print("No PID file found — monitor may not be running.")
        return
    with open(PID_FILE) as fh:
        pid = int(fh.read().strip())
    try:
        if sys.platform == "win32":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
            ctypes.windll.kernel32.TerminateProcess(handle, 0)
        else:
            import signal
            os.kill(pid, signal.SIGTERM)
        os.remove(PID_FILE)
        print(f"Stopped monitor (PID {pid})")
    except (ProcessLookupError, OSError):
        print(f"Process {pid} not found — removing stale PID file.")
        os.remove(PID_FILE)

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    if "--stop" in args:
        stop_background()
        return

    # --run is the internal flag set when Windows re-launches the script
    run_directly = "--run" in args or not args or "--daemon" not in args

    if "--daemon" in args:
        if sys.platform == "win32":
            _spawn_detached_windows()
        else:
            _daemonize_unix()
            write_pid()
            monitor_loop()
        return

    if run_directly:
        # Write PID so --stop works even for foreground runs
        write_pid()
        try:
            monitor_loop()
        except KeyboardInterrupt:
            log_event("🛑 Monitor stopped by user")
        finally:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)


if __name__ == "__main__":
    main()
