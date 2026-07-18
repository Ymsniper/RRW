#!/usr/bin/env python3
"""
RRW - RICKROLL CAPTIVE PORTAL – PROFESSIONAL TOS UI
"""

import os
import sys
import time
import threading
import subprocess
import re
import signal
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============ CONFIGURATION ============
# Dynamically find the video in the same directory as this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(SCRIPT_DIR, "rickroll.mp4")

SSID = "FREE_WIFI"
CHANNEL = 6
AP_IFACE = None

server = None

# ============ UTILITY FUNCTIONS ============
def get_wireless_interfaces():
    result = subprocess.run("iw dev | grep Interface | awk '{print $2}'",
                            shell=True, capture_output=True, text=True)
    return [iface for iface in result.stdout.strip().split('\n') if iface]

def check_dependencies():
    deps = ['hostapd', 'dnsmasq']
    for dep in deps:
        result = subprocess.run(f"which {dep}", shell=True, capture_output=True)
        if result.returncode != 0:
            print(f"❌ Missing dependency: {dep}. (sudo apt install {dep})")
            sys.exit(1)

# ============ HTTP HANDLER ============
class RickrollHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/rickroll.mp4':
            self.serve_video()
        else:
            self.serve_html()

    def serve_video(self):
        try:
            if not os.path.exists(VIDEO_PATH):
                self.send_error(404, "Video not found")
                return
            file_size = os.path.getsize(VIDEO_PATH)
            range_header = self.headers.get('Range')

            if range_header:
                match = re.search(r'bytes=(\d+)-(\d*)', range_header)
                if match:
                    start = int(match.group(1))
                    end = match.group(2)
                    end = int(end) if end else file_size - 1
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header('Content-Type', 'video/mp4')
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Content-Length', str(length))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.end_headers()
                    with open(VIDEO_PATH, 'rb') as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk: break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                    return

            self.send_response(200)
            self.send_header('Content-Type', 'video/mp4')
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            with open(VIDEO_PATH, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    self.wfile.write(chunk)
        except Exception as e:
            pass

    def serve_html(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()

        # Professional Captive Portal UI
        html = '''<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wi-Fi Login</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #f4f5f7;
            margin: 0; padding: 0;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh;
        }
        .card {
            background: #ffffff;
            width: 90%; max-width: 400px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            padding: 30px 20px;
            text-align: center;
        }
        .wifi-icon {
            width: 40px; height: 40px; margin-bottom: 15px;
            fill: #333;
        }
        h2 { margin: 0 0 5px 0; color: #1a1a1a; font-size: 22px; }
        .subtitle { color: #666; font-size: 14px; margin-bottom: 20px; }
        .tos-box {
            text-align: left;
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
            padding: 15px;
            height: 180px;
            overflow-y: auto;
            font-size: 13px;
            color: #444;
            line-height: 1.5;
            margin-bottom: 25px;
        }
        .tos-box h4 { margin: 0 0 8px 0; font-size: 13px; color: #222; }
        .tos-box p { margin: 0 0 10px 0; }
        .accept-btn {
            background-color: #0066cc;
            color: white;
            border: none;
            padding: 14px;
            width: 100%;
            border-radius: 4px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .accept-btn:hover { background-color: #0052a3; }

        /* Hidden Video Layer */
        #video-layer {
            display: none;
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background-color: #000; z-index: 9999;
        }
        video { width: 100%; height: 100%; object-fit: cover; }

        /* Invisible fallback for iOS if it blocks the audio from the button click */
        #ios-unmute-fallback {
            display: none; position: fixed; top:0; left:0; width:100%; height:100%; z-index: 10000;
        }
    </style>
</head>
<body>

    <!-- Professional Login UI -->
    <div class="card" id="tos-ui">
        <svg class="wifi-icon" viewBox="0 0 24 24">
            <path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/>
        </svg>
        <h2>FREE_WIFI</h2>
        <p class="subtitle">Network Login Required</p>

        <div class="tos-box">
            <h4>Terms of Service</h4>
            <p><strong>Welcome to FREE_WIFI</strong></p>
            <p>To continue browsing, please review and accept our network terms:</p>
            <p><strong>1. Data Allowance</strong><br>This Wi-Fi network is limited to 20GB per 24-hour period per device. Once this limit is reached, your connection may be paused or restricted until the 24-hour cycle resets.</p>
            <p><strong>2. Acceptable Use</strong><br>You agree to use this network for lawful purposes only and in a way that does not infringe upon the rights of others.</p>
            <p><strong>3. Privacy & Security</strong><br>This is a public network. We do not monitor, log, or store your personal browsing data. However, as with any public Wi-Fi, we recommend using a VPN when accessing sensitive information.</p>
            <p><strong>4. Service Availability</strong><br>We strive to provide a stable connection, but do not guarantee uninterrupted service, speed, or bandwidth at all times.</p>
            <p>By clicking the button below, you acknowledge that you have read and agree to these terms.</p>
        </div>

        <button class="accept-btn" id="accept-btn">I Accept & Connect</button>
    </div>

    <!-- Hidden Rickroll Layer -->
    <div id="video-layer">
        <!-- Invisible overlay to catch a tap if iOS blocks the audio on button press -->
        <div id="ios-unmute-fallback"></div>
        <video id="rickroll-video" autoplay loop playsinline>
            <source src="rickroll.mp4" type="video/mp4">
        </video>
    </div>

    <script>
        var video = document.getElementById('rickroll-video');
        var tosUI = document.getElementById('tos-ui');
        var videoLayer = document.getElementById('video-layer');
        var acceptBtn = document.getElementById('accept-btn');
        var iosFallback = document.getElementById('ios-unmute-fallback');

        // When user clicks "I Accept & Connect"
        acceptBtn.addEventListener('click', function() {
            // Hide the professional UI
            tosUI.style.display = 'none';

            // Show the video full screen
            videoLayer.style.display = 'block';

            // Attempt to play WITH SOUND (works on most Android/Chrome)
            video.muted = false;
            var playPromise = video.play();

            if (playPromise !== undefined) {
                playPromise.then(_ => {
                    // Sound worked! Do nothing.
                    iosFallback.style.display = 'none';
                }).catch(error => {
                    // Sound was blocked (Strict iOS Safari). Fallback to muted play.
                    video.muted = true;
                    video.play();
                    // Show invisible fallback overlay so 1 tap unmutes it
                    iosFallback.style.display = 'block';
                });
            }
        });

        // Fallback: If iOS blocked the sound, this listens for a tap on the video
        iosFallback.addEventListener('click', function() {
            video.muted = false;
            video.play();
            iosFallback.style.display = 'none'; // Remove fallback after tapped
        });
    </script>
</body>
</html>'''
        self.wfile.write(html.encode())
        print(f"[🎵] RICKROLL DELIVERED to {self.client_address[0]}")
        with open('rickroll_victims.txt', 'a') as f:
            f.write(f"{time.ctime()},{self.client_address[0]}\n")

    # Silently ignore the encrypted HTTPS garbage logs
    def log_request(self, code='-', size='-'):
        if code == 400:
            return
        super().log_request(code, size)

    def log_message(self, format, *args):
        print(f"   [HTTP] {format % args}")

# ============ NETWORK SETUP ============
def start_hostapd():
    global AP_IFACE, SSID, CHANNEL
    config = f"""interface={AP_IFACE}
driver=nl80211
ssid={SSID}
hw_mode=g
channel={CHANNEL}
ieee80211n=1
wmm_enabled=1
auth_algs=1
ignore_broadcast_ssid=0
"""
    with open('/tmp/hostapd.conf', 'w') as f:
        f.write(config)
    subprocess.run("killall -9 hostapd 2>/dev/null", shell=True)
    time.sleep(1)
    subprocess.run(f"ip addr flush dev {AP_IFACE}", shell=True)
    subprocess.run(f"ip link set {AP_IFACE} up", shell=True)
    try:
        subprocess.run(f"hostapd /tmp/hostapd.conf -B", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        result = subprocess.run("pgrep -f 'hostapd /tmp/hostapd.conf'", shell=True, capture_output=True)
        if not result.stdout:
            print("[-] hostapd died. Adapter might not support AP mode.")
            return False
        print(f"[+] AP started: {SSID} on {AP_IFACE}")
        return True
    except subprocess.CalledProcessError:
        print("[-] Failed to execute hostapd.")
        return False

def start_dnsmasq():
    global AP_IFACE
    config = f"""interface={AP_IFACE}
listen-address=10.0.0.1
bind-interfaces
dhcp-range=10.0.0.10,10.0.0.100,255.255.255.0,12h
dhcp-option=3,10.0.0.1
address=/#/10.0.0.1
no-resolv
"""
    with open('/tmp/dnsmasq.conf', 'w') as f:
        f.write(config)
    subprocess.run("killall -9 dnsmasq 2>/dev/null", shell=True)
    subprocess.run("rm -f /var/run/dnsmasq/dnsmasq.pid", shell=True)
    time.sleep(1)
    subprocess.run(f"ip addr add 10.0.0.1/24 dev {AP_IFACE}", shell=True)
    try:
        subprocess.run(f"dnsmasq -C /tmp/dnsmasq.conf", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run("pgrep -f 'dnsmasq -C /tmp/dnsmasq.conf'", shell=True, capture_output=True)
        if not result.stdout:
            print("[-] dnsmasq died silently.")
            return False
        print("[+] dnsmasq started successfully")
        return True
    except subprocess.CalledProcessError:
        print("[-] Failed to execute dnsmasq.")
        return False

def setup_iptables():
    global AP_IFACE
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p udp --dport 67:68 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p udp --dport 53 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p tcp --dport 80 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p tcp --dport 443 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -t nat -A PREROUTING -i {AP_IFACE} -p tcp --dport 80 -j DNAT --to-destination 10.0.0.1:80", shell=True)
    subprocess.run(f"iptables -t nat -A PREROUTING -i {AP_IFACE} -p tcp --dport 443 -j DNAT --to-destination 10.0.0.1:80", shell=True)
    print("[+] IPtables configured (Firewall opened, Traffic redirected)")

# ============ CLEANUP ============
def cleanup():
    global AP_IFACE
    print("\n[*] Cleaning up...")
    subprocess.run("killall -9 hostapd dnsmasq 2>/dev/null", shell=True)
    time.sleep(1)
    if AP_IFACE:
        subprocess.run(f"ip addr flush dev {AP_IFACE}", shell=True)
        subprocess.run(f"ip link set {AP_IFACE} down", shell=True)
        subprocess.run(f"ip link set {AP_IFACE} up", shell=True)
        subprocess.run(f"iptables -D INPUT -i {AP_IFACE} -p udp --dport 67:68 -j ACCEPT 2>/dev/null", shell=True)
        subprocess.run(f"iptables -D INPUT -i {AP_IFACE} -p udp --dport 53 -j ACCEPT 2>/dev/null", shell=True)
        subprocess.run(f"iptables -D INPUT -i {AP_IFACE} -p tcp --dport 80 -j ACCEPT 2>/dev/null", shell=True)
        subprocess.run(f"iptables -D INPUT -i {AP_IFACE} -p tcp --dport 443 -j ACCEPT 2>/dev/null", shell=True)
        subprocess.run(f"iptables -t nat -D PREROUTING -i {AP_IFACE} -p tcp --dport 80 -j DNAT --to-destination 10.0.0.1:80 2>/dev/null", shell=True)
        subprocess.run(f"iptables -t nat -D PREROUTING -i {AP_IFACE} -p tcp --dport 443 -j DNAT --to-destination 10.0.0.1:80 2>/dev/null", shell=True)
    # Hand the interface back to NetworkManager — does NOT disturb other interfaces
    subprocess.run(f"nmcli device set {AP_IFACE} managed yes 2>/dev/null", shell=True)
    print("[+] Cleanup complete.")

def signal_handler(sig, frame):
    if server:
        server.shutdown()
    cleanup()
    sys.exit(0)

# ============ MAIN ============
def main():
    global AP_IFACE, SSID, server
    print("\n" + "="*60)
    print("  🎵 RRW - RICKROLL PORTAL – PROFESSIONAL UI")
    print("="*60)
    if os.geteuid() != 0:
        print("❌ Must run as root!")
        sys.exit(1)
    check_dependencies()
    if not os.path.exists(VIDEO_PATH):
        print(f"❌ Video not found at: {VIDEO_PATH}")
        print("   Please place 'rickroll.mp4' in the same folder as this script.")
        sys.exit(1)
    custom_ssid = input("\n📱 Enter WiFi name [FREE_WIFI]: ").strip()
    if custom_ssid:
        SSID = custom_ssid
    interfaces = get_wireless_interfaces()
    if not interfaces:
        print("❌ No wireless interfaces found!")
        sys.exit(1)
    print("\nAvailable wireless interfaces:")
    for i, iface in enumerate(interfaces, 1):
        print(f"  {i}. {iface}")
    while True:
        choice = input("\nSelect AP interface (number/name): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(interfaces):
                AP_IFACE = interfaces[idx]
                break
        elif choice in interfaces:
            AP_IFACE = choice
            break
        print("Invalid choice.")
    print(f"\n[*] Unmanaging {AP_IFACE} from NetworkManager (other interfaces unaffected)...")
    # Tell NetworkManager to release ONLY this interface — no global kills
    subprocess.run(f"nmcli device set {AP_IFACE} managed no 2>/dev/null", shell=True)
    # Disconnect wpa_supplicant from this interface only, without killing the daemon
    subprocess.run(f"wpa_cli -i {AP_IFACE} terminate 2>/dev/null", shell=True)
    time.sleep(1)
    if not start_hostapd():
        cleanup()
        sys.exit(1)
    if not start_dnsmasq():
        cleanup()
        sys.exit(1)
    setup_iptables()
    server = HTTPServer(('0.0.0.0', 80), RickrollHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("\n" + "="*60)
    print("  ✅ RICKROLL DEPLOYED!")
    print("="*60)
    print(f"  SSID: {SSID} | AP: {AP_IFACE}")
    print("="*60 + "\n")
    try:
        while True:
            res = subprocess.run(f"iw dev {AP_IFACE} station dump", shell=True, capture_output=True, text=True)
            clients = res.stdout.count('Station')
            print(f"\r[+] Connected clients: {clients}    ", end='', flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
