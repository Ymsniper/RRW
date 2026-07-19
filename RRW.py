#!/usr/bin/env python3
"""
RRW - Rickroll Captive Portal
"""

import os
import sys
import time
import threading
import subprocess
import re
import signal
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# -- config --
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH     = None   # set at startup
VIDEO_FILENAME = None   # bare filename for URL routing, e.g. "rickroll.mp4"
RICKROLLS_DIR  = os.path.join(SCRIPT_DIR, "rickrolls")
TEMPLATES_DIR  = os.path.join(SCRIPT_DIR, "templates")
TEMPLATE_PATH  = None   # set at startup

# extension to MIME type
VIDEO_EXTENSIONS = {
    '.mp4':  'video/mp4',
    '.m4v':  'video/mp4',
    '.webm': 'video/webm',
    '.mkv':  'video/x-matroska',
    '.avi':  'video/x-msvideo',
    '.mov':  'video/quicktime',
    '.ogv':  'video/ogg',
    '.flv':  'video/x-flv',
    '.wmv':  'video/x-ms-wmv',
    '.ts':   'video/mp2t',
    '.3gp':  'video/3gpp',
}

SSID = "FREE WIFI"
CHANNEL = 6
AP_IFACE = None

server = None
victims_set = set()
victims_lock = threading.Lock()


def get_wireless_interfaces():
    result = subprocess.run("iw dev | grep Interface | awk '{print $2}'",
                            shell=True, capture_output=True, text=True)
    return [iface for iface in result.stdout.strip().split('\n') if iface]

def check_dependencies():
    deps = ['hostapd', 'dnsmasq']
    for dep in deps:
        result = subprocess.run(f"which {dep}", shell=True, capture_output=True)
        if result.returncode != 0:
            print(f"[!] Missing dependency: {dep}. (sudo apt install {dep})")
            sys.exit(1)


# probe hosts used by OSes to detect captive portals
PROBE_HOSTS = {
    'captive.apple.com', 'www.apple.com', 'apple.com', 'appleiphonecell.com', 'www.appleiphonecell.com',
    'connectivitycheck.gstatic.com', 'connectivitycheck.android.com', 'clients1.google.com', 'clients2.google.com', 'clients3.google.com', 'www.gstatic.com',
    'www.msftconnecttest.com', 'msftconnecttest.com', 'www.msftncsi.com', 'msftncsi.com',
    'detectportal.firefox.com', 'kindle-wifi.amazon.com',
    'nmcheck.gnome.org', 'nm-check.gnome.org', 'connectivity-check.ubuntu.com', 'networkcheck.kde.org',
    'www.archlinux.org', 'ping.archlinux.org', 'redirect.archlinux.org',
    'fedoraproject.org', 'www.fedoraproject.org', 'conncheck.opensuse.org',
}

PROBE_PATHS = {
    '/hotspot-detect.html', '/library/test/success.html', '/generate_204', '/gen_204',
    '/connecttest.txt', '/ncsi.txt', '/canonical.html', '/success.txt',
    '/kindle-wifi/wifistub.html', '/redirect', '/check_network_status.txt',
    '/static/hotspot.txt', '/check',
}

PORTAL_URL = 'http://10.0.0.1/'


class RickrollHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        host = self.headers.get('Host', '').split(':')[0].lower().strip()

        # redirect probe requests to trigger the portal popup
        if host in PROBE_HOSTS or self.path in PROBE_PATHS:
            self.send_response(302)
            self.send_header('Location', PORTAL_URL)
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
            return

        if self.path == f'/{VIDEO_FILENAME}':
            self.serve_video()
        else:
            self.serve_html()

    def serve_video(self):
        try:
            if not os.path.exists(VIDEO_PATH):
                self.send_error(404, "Video not found")
                return
            ext = os.path.splitext(VIDEO_FILENAME)[1].lower()
            mime_type = VIDEO_EXTENSIONS.get(ext, 'application/octet-stream')
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
                    self.send_header('Content-Type', mime_type)
                    self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                    self.send_header('Content-Length', str(length))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    with open(VIDEO_PATH, 'rb') as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk: break
                            try: self.wfile.write(chunk)
                            except BrokenPipeError: break
                            remaining -= len(chunk)
                    return

            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Connection', 'close')
            self.end_headers()
            with open(VIDEO_PATH, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    try: self.wfile.write(chunk)
                    except BrokenPipeError: break
        except Exception:
            pass

    def serve_html(self):
        try:
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            self.send_error(404, "template.html not found")
            return

        html_content = html_content.replace('{SSID}', SSID)
        html_content = html_content.replace('{VIDEO_SRC}', f'/{VIDEO_FILENAME}')
        ext = os.path.splitext(VIDEO_FILENAME)[1].lower()
        html_content = html_content.replace('{VIDEO_MIME}', VIDEO_EXTENSIONS.get(ext, 'video/mp4'))

        body = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()

        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

        # log each victim IP once
        ip_address = self.client_address[0]
        with victims_lock:
            if ip_address not in victims_set:
                victims_set.add(ip_address)
                print(f"\n[+] rickroll delivered to {ip_address}\n", flush=True)
                with open('rickroll_victims.txt', 'a') as f:
                    f.write(f"{time.ctime()},{ip_address}\n")

    # suppress default access logs so they don't clobber the client counter
    def log_request(self, code='-', size='-'):
        pass

    def log_message(self, format, *args):
        pass


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
    with open('/tmp/hostapd.conf', 'w') as f: f.write(config)
    subprocess.run("killall -9 hostapd 2>/dev/null", shell=True)
    time.sleep(1)
    subprocess.run(f"ip addr flush dev {AP_IFACE}", shell=True)
    subprocess.run(f"ip link set {AP_IFACE} up", shell=True)
    try:
        subprocess.run(f"hostapd /tmp/hostapd.conf -B", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        result = subprocess.run("pgrep -f 'hostapd /tmp/hostapd.conf'", shell=True, capture_output=True)
        if not result.stdout: return False
        return True
    except subprocess.CalledProcessError: return False

def start_dnsmasq():
    global AP_IFACE
    config = f"""interface={AP_IFACE}
listen-address=10.0.0.1
bind-interfaces
dhcp-range=10.0.0.10,10.0.0.100,255.255.255.0,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
dhcp-option=114,http://10.0.0.1/
address=/#/10.0.0.1
no-resolv
"""
    with open('/tmp/dnsmasq.conf', 'w') as f: f.write(config)
    subprocess.run("killall -9 dnsmasq 2>/dev/null", shell=True)
    subprocess.run("rm -f /var/run/dnsmasq/dnsmasq.pid", shell=True)
    time.sleep(1)
    subprocess.run(f"ip addr add 10.0.0.1/24 dev {AP_IFACE}", shell=True)
    try:
        subprocess.run(f"dnsmasq -C /tmp/dnsmasq.conf", shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run("pgrep -f 'dnsmasq -C /tmp/dnsmasq.conf'", shell=True, capture_output=True)
        if not result.stdout: return False
        return True
    except subprocess.CalledProcessError: return False

def setup_iptables():
    global AP_IFACE
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p udp --dport 67:68 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p udp --dport 53 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p tcp --dport 80 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -I INPUT -i {AP_IFACE} -p tcp --dport 443 -j ACCEPT", shell=True)
    subprocess.run(f"iptables -t nat -A PREROUTING -i {AP_IFACE} -p tcp --dport 80 -j DNAT --to-destination 10.0.0.1:80", shell=True)
    subprocess.run(f"iptables -t nat -A PREROUTING -i {AP_IFACE} -p tcp --dport 443 -j DNAT --to-destination 10.0.0.1:80", shell=True)
    print("[+] iptables configured")


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
    subprocess.run(f"nmcli device set {AP_IFACE} managed yes 2>/dev/null", shell=True)
    print("[+] Cleanup complete.")

def signal_handler(sig, frame):
    if server: server.shutdown()
    cleanup()
    sys.exit(0)


def resolve_video(name):
    global VIDEO_PATH, VIDEO_FILENAME
    ext = os.path.splitext(name)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        print(f"[!] Unsupported video format: '{ext}'")
        print(f"   Supported: {', '.join(VIDEO_EXTENSIONS.keys())}")
        sys.exit(1)
    # check rickrolls/ first, then treat as explicit path
    folder_path = os.path.join(RICKROLLS_DIR, os.path.basename(name))
    if os.path.isfile(folder_path):
        VIDEO_PATH     = folder_path
        VIDEO_FILENAME = os.path.basename(name)
        print(f"[+] Using video: {VIDEO_FILENAME}  (from rickrolls/)")
        return
    explicit = os.path.abspath(name)
    if os.path.isfile(explicit):
        VIDEO_PATH     = explicit
        VIDEO_FILENAME = os.path.basename(explicit)
        print(f"[+] Using video: {VIDEO_FILENAME}  (from explicit path)")
        return
    print(f"[!] Video not found: '{name}'")
    print(f"   Checked: {folder_path}")
    print(f"   Checked: {explicit}")
    sys.exit(1)

def resolve_template(name):
    if not name.lower().endswith('.html'):
        print(f"[!] Template must be an .html file, got: '{name}'")
        sys.exit(1)
    # check templates/ first, then treat as explicit path
    folder_path = os.path.join(TEMPLATES_DIR, os.path.basename(name))
    if os.path.isfile(folder_path):
        print(f"[+] Using template: {os.path.basename(name)}  (from templates/)")
        return folder_path
    explicit = os.path.abspath(name)
    if os.path.isfile(explicit):
        print(f"[+] Using template: {os.path.basename(explicit)}  (from explicit path)")
        return explicit
    print(f"[!] Template not found: '{name}'")
    print(f"   Checked: {folder_path}")
    print(f"   Checked: {explicit}")
    sys.exit(1)


def pick_video():
    global VIDEO_PATH, VIDEO_FILENAME
    if not os.path.isdir(RICKROLLS_DIR):
        print(f"[!] Rickrolls folder not found at: {RICKROLLS_DIR}")
        print("   Create a 'rickrolls' folder next to this script and add video files to it.")
        sys.exit(1)

    video_files = sorted(
        f for f in os.listdir(RICKROLLS_DIR)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
        and os.path.isfile(os.path.join(RICKROLLS_DIR, f))
    )

    if not video_files:
        exts = ', '.join(VIDEO_EXTENSIONS.keys())
        print(f"[!] No video files found in: {RICKROLLS_DIR}")
        print(f"   Supported formats: {exts}")
        sys.exit(1)

    print("\nAvailable videos:")
    for i, name in enumerate(video_files, 1):
        size_mb = os.path.getsize(os.path.join(RICKROLLS_DIR, name)) / (1024 * 1024)
        print(f"  {i}. {name}  ({size_mb:.1f} MB)")

    while True:
        choice = input("\nSelect video (number): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(video_files):
                VIDEO_FILENAME = video_files[idx]
                VIDEO_PATH     = os.path.join(RICKROLLS_DIR, VIDEO_FILENAME)
                print(f"[+] Using video: {VIDEO_FILENAME}")
                return
        print("  Invalid choice, try again.")


def pick_template():
    if not os.path.isdir(TEMPLATES_DIR):
        print(f"[!] Templates folder not found at: {TEMPLATES_DIR}")
        print("   Create a 'templates' folder next to this script and add .html files to it.")
        sys.exit(1)

    html_files = sorted(
        f for f in os.listdir(TEMPLATES_DIR)
        if f.lower().endswith('.html') and os.path.isfile(os.path.join(TEMPLATES_DIR, f))
    )

    if not html_files:
        print(f"[!] No .html files found in: {TEMPLATES_DIR}")
        print("   Add at least one .html template file to the templates/ folder.")
        sys.exit(1)

    print("\nAvailable templates:")
    for i, name in enumerate(html_files, 1):
        print(f"  {i}. {name}")

    while True:
        choice = input("\nSelect template (number): ").strip()
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(html_files):
                chosen = os.path.join(TEMPLATES_DIR, html_files[idx])
                print(f"[+] Using template: {html_files[idx]}")
                return chosen
        print("  Invalid choice, try again.")


def parse_args():
    parser = argparse.ArgumentParser(
        description='RRW - Rickroll Captive Portal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  # fully flag-driven (no prompts):
  sudo python3 RRW.py -s "FREE WIFI" -v rickroll.mp4 -t portal.html -i wlan1

  # video/template from outside their folders (explicit paths):
  sudo python3 RRW.py -s "Airport WiFi" -v /tmp/bait.webm -t /tmp/evil.html -i wlan0

  # mix flags + interactive (omit any flag to be prompted):
  sudo python3 RRW.py -i wlan1 -s "FREE WIFI"

  # fully interactive:
  sudo python3 RRW.py
        """)
    parser.add_argument('-s', '--ssid',
                        metavar='NAME',
                        help='WiFi SSID name')
    parser.add_argument('-v', '--video',
                        metavar='FILE',
                        help='Video filename (looked up in rickrolls/) or explicit path')
    parser.add_argument('-t', '--template',
                        metavar='FILE',
                        help='HTML template filename (looked up in templates/) or explicit path')
    parser.add_argument('-i', '--interface',
                        metavar='IFACE',
                        help='Wireless interface to use as AP')
    return parser.parse_args()


def main():
    global AP_IFACE, SSID, server, VIDEO_PATH, VIDEO_FILENAME, TEMPLATE_PATH

    args = parse_args()

    print("\n" + "="*60)
    print("  RRW - RICKROLL PORTAL")
    print("="*60)
    if os.geteuid() != 0:
        print("[!] Must run as root!"); sys.exit(1)
    check_dependencies()

    if args.ssid:
        SSID = args.ssid
        print(f"[+] SSID: {SSID}")
    else:
        custom_ssid = input(f"\nEnter WiFi name [{SSID}]: ").strip()
        if custom_ssid: SSID = custom_ssid

    if args.video:
        resolve_video(args.video)
    else:
        pick_video()

    if args.template:
        TEMPLATE_PATH = resolve_template(args.template)
    else:
        TEMPLATE_PATH = pick_template()

    interfaces = get_wireless_interfaces()
    if not interfaces:
        print("[!] No wireless interfaces found!"); sys.exit(1)

    if args.interface:
        if args.interface not in interfaces:
            print(f"[!] Interface '{args.interface}' not found.")
            print(f"   Available: {', '.join(interfaces)}")
            sys.exit(1)
        AP_IFACE = args.interface
        print(f"[+] Using interface: {AP_IFACE}")
    else:
        print("\nAvailable wireless interfaces:")
        for i, iface in enumerate(interfaces, 1): print(f"  {i}. {iface}")
        while True:
            choice = input("\nSelect AP interface (number/name): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(interfaces):
                    AP_IFACE = interfaces[idx]; break
            elif choice in interfaces:
                AP_IFACE = choice; break
            print("Invalid choice.")

    print(f"\n[*] Unmanaging {AP_IFACE} from NetworkManager (other interfaces unaffected)...")
    subprocess.run(f"nmcli device set {AP_IFACE} managed no 2>/dev/null", shell=True)

    try:
        subprocess.run(f"wpa_cli -i {AP_IFACE} terminate", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except subprocess.TimeoutExpired:
        pass

    time.sleep(1)
    if not start_hostapd(): cleanup(); sys.exit(1)
    if not start_dnsmasq(): cleanup(); sys.exit(1)
    setup_iptables()

    server = ThreadingHTTPServer(('0.0.0.0', 80), RickrollHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("\n" + "="*60)
    print("  [+] RICKROLL DEPLOYED!")
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
