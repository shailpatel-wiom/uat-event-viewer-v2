"""
Interactive setup wizard for Wiom UAT Event Viewer.
Guides through device connection, APK installation, and launches the dashboard.
"""

import subprocess
import sys
import os
import time
import webbrowser
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = 8070

# --- Helpers ------------------------------------------------------------------

def run(cmd, timeout=30, capture=True):
    """Run a shell command and return stdout."""
    try:
        r = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.stdout.strip() if capture else ""
    except subprocess.TimeoutExpired:
        return ""
    except Exception as e:
        return ""


def ask(prompt, options=None, default=None):
    """Ask user for input with optional numbered choices."""
    if options:
        print()
        for i, (label, desc) in enumerate(options, 1):
            print(f"    {i}. {label}")
            if desc:
                print(f"       {desc}")
        print()
        while True:
            d = f" (default: {default})" if default else ""
            choice = input(f"  Enter choice{d}: ").strip()
            if not choice and default:
                return default
            try:
                idx = int(choice)
                if 1 <= idx <= len(options):
                    return str(idx)
            except ValueError:
                pass
            print(f"  Please enter a number between 1 and {len(options)}")
    else:
        return input(f"  {prompt}: ").strip()


def wait_message(msg):
    print(f"\n  {msg}", end="", flush=True)


def ok(msg):
    print(f"  [OK] {msg}")


def fail(msg):
    print(f"  [X] {msg}")


def info(msg):
    print(f"  [i] {msg}")


def separator():
    print()
    print("  " + "-" * 50)


# --- Steps --------------------------------------------------------------------

def step_device():
    """Connect to an Android device (emulator or physical)."""
    separator()
    print("\n  STEP 1: Connect an Android device\n")

    # Check for already connected devices
    output = run("adb devices")
    lines = [l for l in output.splitlines()[1:] if l.strip() and "device" in l]

    if lines:
        devices = []
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].strip() == "device":
                dev_id = parts[0].strip()
                # Get device model
                model = run(f'adb -s {dev_id} shell getprop ro.product.model')
                devices.append((dev_id, model or "Unknown"))

        if devices:
            print("  Found connected device(s):\n")
            for dev_id, model in devices:
                print(f"    - {dev_id}  ({model})")
            print()

            if len(devices) == 1:
                choice = ask("Use this device? (y/n)", default="y")
                if choice.lower() in ("y", "yes", ""):
                    return devices[0][0]

            # Multiple devices
            print("  Which device do you want to use?\n")
            for i, (dev_id, model) in enumerate(devices, 1):
                print(f"    {i}. {dev_id}  ({model})")
            print(f"    {len(devices)+1}. Connect a different device")
            print()
            choice = input("  Enter choice: ").strip()
            try:
                idx = int(choice)
                if 1 <= idx <= len(devices):
                    return devices[idx - 1][0]
            except ValueError:
                pass

    # No device connected — guide them
    print("  No Android device detected. How would you like to connect?\n")
    choice = ask("Choose connection method", [
        ("Physical Android phone (USB)", "Easier setup, use your real phone"),
        ("Android Emulator", "Requires Android Studio, runs a virtual phone on your PC"),
    ])

    if choice == "1":
        return setup_physical_device()
    else:
        return setup_emulator()


def setup_physical_device():
    """Guide through connecting a physical phone."""
    print()
    print("  Follow these steps to connect your phone:\n")
    print("  1. On your phone, go to Settings > About Phone")
    print("     Tap 'Build Number' 7 times to enable Developer Options")
    print()
    print("  2. Go to Settings > Developer Options")
    print("     Turn ON 'USB Debugging'")
    print()
    print("  3. Connect your phone to this PC with a USB cable")
    print()
    print("  4. On your phone, tap 'Allow' on the USB debugging prompt")
    print("     (Check 'Always allow from this computer')")
    print()
    input("  Press Enter when your phone is connected...")

    # Poll for device
    print()
    for attempt in range(10):
        output = run("adb devices")
        lines = [l for l in output.splitlines()[1:] if l.strip() and "device" in l]
        for line in lines:
            parts = line.split("\t")
            if len(parts) >= 2 and parts[1].strip() == "device":
                dev_id = parts[0].strip()
                model = run(f'adb -s {dev_id} shell getprop ro.product.model')
                ok(f"Phone connected: {model} ({dev_id})")
                return dev_id

        if attempt == 0:
            print("  Waiting for device...", end="", flush=True)
        else:
            print(".", end="", flush=True)
        time.sleep(2)

    print()
    fail("Could not detect your phone.")
    print("  Troubleshooting:")
    print("    - Make sure USB Debugging is ON")
    print("    - Try a different USB cable (use one that supports data transfer)")
    print("    - Tap 'Allow' on the debugging prompt on your phone")
    print("    - Run 'adb kill-server && adb start-server' then try again")
    sys.exit(1)


def setup_emulator():
    """Guide through emulator setup."""
    # Check if emulator binary exists
    sdk_base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
    emulator_exe = os.path.join(sdk_base, "emulator", "emulator.exe")

    if not os.path.exists(emulator_exe):
        print()
        fail("Android emulator not found.")
        print()
        print("  To use an emulator, you need Android Studio:")
        print("    1. Download: https://developer.android.com/studio")
        print("    2. Install Android Studio")
        print("    3. Open Android Studio > Tools > Device Manager")
        print("    4. Create a Virtual Device (any Phone, API 33+)")
        print("    5. Run start.bat again")
        print()
        print("  OR use a physical phone instead (much easier!) — run start.bat again")
        sys.exit(1)

    # List available AVDs
    avd_output = run(f'"{emulator_exe}" -list-avds')
    avds = [a.strip() for a in avd_output.splitlines() if a.strip()]

    if not avds:
        fail("No emulator images (AVDs) found.")
        print()
        print("  Create one in Android Studio:")
        print("    Tools > Device Manager > Create Device")
        print("  Then run start.bat again.")
        sys.exit(1)

    print()
    if len(avds) == 1:
        avd = avds[0]
        info(f"Found emulator: {avd}")
    else:
        print("  Available emulators:\n")
        for i, avd_name in enumerate(avds, 1):
            print(f"    {i}. {avd_name}")
        print()
        choice = input("  Which one? Enter number: ").strip()
        try:
            avd = avds[int(choice) - 1]
        except (ValueError, IndexError):
            avd = avds[0]
            info(f"Using: {avd}")

    print(f"\n  Launching emulator '{avd}'... (this may take 30-60 seconds)")
    subprocess.Popen(
        [emulator_exe, "-avd", avd],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # Wait for boot
    print("  Waiting for emulator to boot", end="", flush=True)
    run("adb wait-for-device", timeout=120, capture=False)

    for _ in range(60):
        boot = run("adb shell getprop sys.boot_completed")
        if boot.strip() == "1":
            break
        print(".", end="", flush=True)
        time.sleep(2)
    print()

    # Get device ID
    output = run("adb devices")
    for line in output.splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].strip() == "device":
            dev_id = parts[0].strip()
            ok(f"Emulator ready: {dev_id}")
            return dev_id

    fail("Emulator started but device not detected.")
    sys.exit(1)


def step_apk(device_id):
    """Ask for APK path, validate it's a debug build, install it."""
    separator()
    print("\n  STEP 2: Install the debug APK\n")

    while True:
        print("  Drag and drop the APK file here, or type/paste the full path:")
        apk_path = input("\n  APK path: ").strip().strip('"').strip("'")

        if not apk_path:
            print("  Please enter a path.\n")
            continue
        if not os.path.isfile(apk_path):
            fail(f"File not found: {apk_path}")
            print()
            continue
        if not apk_path.lower().endswith(".apk"):
            fail("That doesn't look like an APK file.")
            print()
            continue
        break

    # Check if it's a debug build by trying to detect debuggable flag
    info("Checking if APK is a debug build...")
    # Install first, then check debuggable flag via package manager
    print(f"\n  Installing APK on device... (this may take a moment)")
    result = run(f'adb -s {device_id} install -r "{apk_path}"', timeout=120)

    if "Success" not in result:
        fail(f"APK installation failed: {result}")
        print("  Make sure the device is unlocked and try again.")
        sys.exit(1)

    ok("APK installed successfully")

    # Find the package name (most recently installed)
    # Get package name from the APK via aapt or by checking installed packages
    pkg = find_package(device_id, apk_path)
    if not pkg:
        print("\n  Could not auto-detect package name.")
        pkg = input("  Enter the app's package name (e.g. com.i2e1.wiom_gold): ").strip()

    info(f"Package: {pkg}")

    # Check if debuggable
    flags = run(f'adb -s {device_id} shell dumpsys package {pkg}')
    is_debug = "DEBUGGABLE" in flags.upper() if flags else False

    if not is_debug:
        print()
        print("  ========================================")
        print("  [!] WARNING: This may NOT be a debug build.")
        print("  ========================================")
        print()
        print("  CleverTap only logs events to logcat in debug builds.")
        print("  If you don't see any events after launching the app,")
        print("  ask your developer for a debug APK.")
        print()
        choice = input("  Continue anyway? (y/n): ").strip().lower()
        if choice not in ("y", "yes"):
            sys.exit(0)
    else:
        ok("Debug build confirmed")

    return pkg


def find_package(device_id, apk_path):
    """Try to determine the package name from the installed APK."""
    # Method 1: Use aapt if available
    sdk_base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")
    # Find aapt2 in build-tools
    build_tools = os.path.join(sdk_base, "build-tools")
    if os.path.isdir(build_tools):
        versions = sorted(os.listdir(build_tools), reverse=True)
        for v in versions:
            aapt = os.path.join(build_tools, v, "aapt2.exe")
            if os.path.exists(aapt):
                result = run(f'"{aapt}" dump packagename "{apk_path}"')
                if result and "." in result:
                    return result.strip().splitlines()[0]
            aapt = os.path.join(build_tools, v, "aapt.exe")
            if os.path.exists(aapt):
                result = run(f'"{aapt}" dump badging "{apk_path}"')
                m = re.search(r"package:\s*name='([^']+)'", result)
                if m:
                    return m.group(1)

    # Method 2: Look for wiom packages on device
    pkgs = run(f"adb -s {device_id} shell pm list packages")
    wiom_pkgs = [l.replace("package:", "").strip()
                 for l in pkgs.splitlines() if "wiom" in l.lower()]
    if len(wiom_pkgs) == 1:
        return wiom_pkgs[0]
    if len(wiom_pkgs) > 1:
        print("\n  Multiple Wiom packages found:\n")
        for i, p in enumerate(wiom_pkgs, 1):
            print(f"    {i}. {p}")
        print()
        choice = input("  Which one was just installed? Enter number: ").strip()
        try:
            return wiom_pkgs[int(choice) - 1]
        except (ValueError, IndexError):
            return wiom_pkgs[0]

    return None


def step_launch(device_id, package):
    """Launch the app and verify CleverTap logging."""
    separator()
    print("\n  STEP 3: Launch the app\n")

    # Find launcher activity
    resolve = run(
        f'adb -s {device_id} shell cmd package resolve-activity '
        f'--brief -c android.intent.category.LAUNCHER {package}'
    )
    activity = None
    for line in resolve.splitlines():
        if "/" in line and package in line:
            activity = line.strip()
            break

    if not activity:
        # Fallback: try monkey
        info("Launching app...")
        run(f'adb -s {device_id} shell monkey -p {package} -c android.intent.category.LAUNCHER 1')
    else:
        info(f"Launching {activity}...")
        run(f'adb -s {device_id} shell am start -n {activity}')

    ok("App launched")

    # Clear logcat and check for CleverTap events
    run("adb logcat -c")
    print("\n  Checking for CleverTap logs... (interact with the app for a few seconds)")
    time.sleep(5)

    logcat = run(f'adb -s {device_id} logcat -d')
    ct_lines = [l for l in logcat.splitlines() if "CleverTap" in l]

    if ct_lines:
        ok(f"CleverTap logging detected ({len(ct_lines)} log lines)")
    else:
        print()
        print("  [!] No CleverTap logs detected yet.")
        print("      This is normal if you haven't interacted with the app.")
        print("      If events still don't appear after using the app,")
        print("      the APK may not have debug logging enabled.")
        print()

    return activity


def step_dashboard():
    """Start the event viewer server and open the browser."""
    separator()
    print("\n  STEP 4: Starting Event Viewer Dashboard\n")

    # Clear logcat for a fresh start
    run("adb logcat -c")

    server_script = os.path.join(SCRIPT_DIR, "server.py")
    info(f"Starting server on port {PORT}...")

    # Start server as a subprocess
    proc = subprocess.Popen(
        [sys.executable, server_script, "--port", str(PORT)],
        cwd=SCRIPT_DIR,
    )

    time.sleep(1)

    if proc.poll() is not None:
        fail("Server failed to start. Check if port 8070 is already in use.")
        print(f"  Try: python server.py --port 9000")
        sys.exit(1)

    url = f"http://localhost:{PORT}"
    ok(f"Dashboard running at {url}")

    print(f"\n  Opening browser...")
    webbrowser.open(url)

    print()
    print("  ============================================")
    print("  All set! Use the app and watch events")
    print("  stream into the dashboard in real-time.")
    print("  ============================================")
    print()
    print("  Tips:")
    print("    - Click an event row to see its properties")
    print("    - Use the search box to filter events")
    print("    - Toggle SDK buttons to show/hide sources")
    print("    - Click 'Download JSON' to export events")
    print()
    print("  Press Ctrl+C to stop the server.")
    print()

    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        print("\n  Server stopped. Goodbye!")


# --- Main ---------------------------------------------------------------------

def main():
    print()
    print("  Welcome to the Wiom UAT Event Viewer!")
    print("  This wizard will set up everything for you.")

    device_id = step_device()
    package = step_apk(device_id)
    step_launch(device_id, package)
    step_dashboard()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled. Goodbye!")
    except Exception as e:
        print(f"\n  [X] Unexpected error: {e}")
        print("  Please report this to the team.")
        input("\n  Press Enter to exit...")
