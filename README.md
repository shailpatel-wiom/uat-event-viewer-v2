# Wiom UAT Event Viewer

Live dashboard to see **CleverTap** (+ Firebase, Meta, Branch) events firing from a debug APK in real-time. No SDK knowledge needed — just run the script and follow the prompts.

![Dashboard](https://img.shields.io/badge/dashboard-localhost:8070-blue)

## Quick Start

1. **Download this repo** — click the green `Code` button above, then `Download ZIP`, and extract it

2. **Double-click `start.bat`** — the wizard will:
   - Check if Python and ADB are installed (and help you install them if not)
   - Connect to your phone or emulator
   - Ask you for the debug APK path
   - Verify it's a debug build
   - Install the app, launch it, and open the dashboard

3. **Use the app** — events stream into the dashboard in real-time

That's it. Everything else is handled for you.

## What You Need

| Requirement | The wizard handles it? |
|---|---|
| Windows PC | - |
| Debug APK file | You provide this (ask your developer if you don't have one) |
| Android phone OR emulator | Wizard guides you through connecting either |
| Python 3.8+ | Wizard installs it if missing |
| ADB (Android Debug Bridge) | Wizard installs it if missing |

**Important:** The APK must be a **debug build**. Release builds don't log events to logcat. If you're not sure, the wizard will detect this and warn you.

## Dashboard Features

- **Real-time event streaming** as you interact with the app
- **Click any event** to expand and see all properties
- **Filter by SDK** — toggle CleverTap / Firebase / Meta / Branch
- **Search** — filter by event name or property value
- **Download JSON** — export all visible events for sharing or documentation

## Manual Setup (Advanced)

If you prefer to run things manually instead of using the wizard:

```bash
# 1. Connect device
adb devices

# 2. Install APK
adb install -r path/to/debug.apk

# 3. Launch app
adb shell am start -n com.i2e1.wiom_gold/com.wiom.app.MainActivity

# 4. Start event viewer
python server.py

# 5. Open http://localhost:8070
```

### Options

```bash
python server.py --port 9000   # use a different port
```

### Fresh Start

```bash
adb shell pm clear com.i2e1.wiom_gold   # clear app data
adb logcat -c                             # clear log buffer
# restart server.py and refresh browser
```

## Troubleshooting

| Problem | Fix |
|---|---|
| No events showing up | Make sure you have a **debug** APK. Release builds don't log events. |
| Phone not detected | Enable USB Debugging: Settings > Developer Options > USB Debugging |
| `adb devices` empty | Try: `adb kill-server && adb start-server`, reconnect USB |
| Port 8070 in use | Run `python server.py --port 9000` |
| Emulator won't start | Open Android Studio > Device Manager, start it from there |
| Python not found after install | Close and reopen the terminal, then try again |

## Files

| File | Purpose |
|---|---|
| `start.bat` | Entry point — checks prerequisites, runs setup wizard |
| `setup.py` | Interactive wizard — device connection, APK install, launch |
| `server.py` | Event parser + web server (no dependencies, stdlib only) |
| `index.html` | Dashboard UI |
