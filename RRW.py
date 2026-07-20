"""
RRW - Rickroll Captive Portal
"""

import os
import sys
import ssl
import json
import time
import threading
import subprocess
import re
import signal
import argparse
import tempfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# ── config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR     = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH     = None
VIDEO_FILENAME = None
RICKROLLS_DIR  = os.path.join(SCRIPT_DIR, "rickrolls")
TEMPLATES_DIR  = os.path.join(SCRIPT_DIR, "templates")
TEMPLATE_PATH  = None

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

IMAGE_EXTENSIONS = {
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif':  'image/gif',
    '.ico':  'image/x-icon',
    '.svg':  'image/svg+xml',
    '.webp': 'image/webp',
}

SSID     = "FREE WIFI"
CHANNEL  = 6
AP_IFACE = None

# Android 12+ sends simultaneous HTTP + HTTPS probes; if HTTPS gets a TLS
# error (443 DNATed to plain HTTP) Android marks the network "partial
# connectivity" and never shows the captive portal popup.
HTTPS_PORT = 4443

# RFC 8908 — Android 12+ fetches this via DHCP option 114.
# {"captive": true, "user-portal-url": "..."} skips all probes entirely.
CAPPORT_PATH = '/capport-api'

PORTAL_URL  = 'http://10.0.0.1/'
CAPPORT_URL = f'http://10.0.0.1{CAPPORT_PATH}'

server       = None
https_server = None
victims_set  = set()
victims_lock = threading.Lock()

_CERT_FILE = None   # deleted on exit
_KEY_FILE  = None


# ── helpers ──────────────────────────────────────────────────────────────────

def get_wireless_interfaces():
    result = subprocess.run("iw dev | grep Interface | awk '{print $2}'",
                            shell=True, capture_output=True, text=True)
    return [i for i in result.stdout.strip().split('\n') if i]


def check_dependencies():
    for dep in ['hostapd', 'dnsmasq', 'openssl']:
        if subprocess.run(f"which {dep}", shell=True, capture_output=True).returncode != 0:
            print(f"[!] Missing dependency: {dep}. (sudo apt install {dep})")
            sys.exit(1)


# ── probe tables ─────────────────────────────────────────────────────────────

PROBE_HOSTS = {
    # Apple
    'captive.apple.com', 'www.apple.com', 'apple.com',
    'appleiphonecell.com', 'www.appleiphonecell.com',
    # Android / Google
    'connectivitycheck.gstatic.com', 'connectivitycheck.android.com',
    'clients1.google.com', 'clients2.google.com', 'clients3.google.com',
    'www.gstatic.com',
    # Microsoft
    'www.msftconnecttest.com', 'msftconnecttest.com',
    'www.msftncsi.com', 'msftncsi.com',
    # Other
    'detectportal.firefox.com', 'kindle-wifi.amazon.com',
    'nmcheck.gnome.org', 'nm-check.gnome.org',
    'connectivity-check.ubuntu.com', 'networkcheck.kde.org',
    'www.archlinux.org', 'ping.archlinux.org', 'redirect.archlinux.org',
    'fedoraproject.org', 'www.fedoraproject.org', 'conncheck.opensuse.org',
}

PROBE_PATHS = {
    # Android / Google
    '/generate_204', '/gen_204',
    # Apple
    '/hotspot-detect.html', '/library/test/success.html',
    # Microsoft
    '/connecttest.txt', '/ncsi.txt',
    # Other
    '/canonical.html', '/success.txt',
    '/kindle-wifi/wifistub.html', '/redirect',
    '/check_network_status.txt', '/static/hotspot.txt', '/check',
}


# ── HTTP/HTTPS request handler ────────────────────────────────────────────────

class RickrollHandler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        host = self.headers.get('Host', '').split(':')[0].lower().strip()
        path = self.path.split('?')[0]   # Android appends ?ts=… to probe URLs

        if path == CAPPORT_PATH:
            self._serve_capport_api()
            return

        if host in PROBE_HOSTS or path in PROBE_PATHS:
            self.send_response(302)
            self.send_header('Location', PORTAL_URL)
            self.send_header('Content-Length', '0')
            self.send_header('Connection', 'close')
            self.end_headers()
            return

        ext = os.path.splitext(path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            self._serve_image(path)
            return

        if path == f'/{VIDEO_FILENAME}':
            self._serve_video()
        else:
            self._serve_html()

    def _serve_capport_api(self):
        # RFC 8908 §4 — Content-Type must be application/captive+json
        payload = json.dumps({
            "captive":         True,
            "user-portal-url": PORTAL_URL,
        }).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type',   'application/captive+json')
        self.send_header('Content-Length', str(len(payload)))
        self.send_header('Cache-Control',  'no-store')
        self.send_header('Connection',     'close')
        self.end_headers()
        try:
            self.wfile.write(payload)
        except BrokenPipeError:
            pass

    def _serve_video(self):
        try:
            if not os.path.exists(VIDEO_PATH):
                self.send_error(404, "Video not found")
                return
            ext       = os.path.splitext(VIDEO_FILENAME)[1].lower()
            mime_type = VIDEO_EXTENSIONS.get(ext, 'application/octet-stream')
            file_size = os.path.getsize(VIDEO_PATH)
            rng       = self.headers.get('Range')

            if rng:
                m = re.search(r'bytes=(\d+)-(\d*)', rng)
                if m:
                    start  = int(m.group(1))
                    end    = int(m.group(2)) if m.group(2) else file_size - 1
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header('Content-Type',   mime_type)
                    self.send_header('Content-Range',  f'bytes {start}-{end}/{file_size}')
                    self.send_header('Content-Length', str(length))
                    self.send_header('Accept-Ranges',  'bytes')
                    self.send_header('Connection',     'close')
                    self.end_headers()
                    with open(VIDEO_PATH, 'rb') as f:
                        f.seek(start)
                        rem = length
                        while rem > 0:
                            chunk = f.read(min(65536, rem))
                            if not chunk: break
                            try:    self.wfile.write(chunk)
                            except BrokenPipeError: break
                            rem -= len(chunk)
                    return

            self.send_response(200)
            self.send_header('Content-Type',   mime_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Accept-Ranges',  'bytes')
            self.send_header('Connection',     'close')
            self.end_headers()
            with open(VIDEO_PATH, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    try:    self.wfile.write(chunk)
                    except BrokenPipeError: break
        except Exception:
            pass

    def _serve_image(self, path):
        filename   = os.path.basename(path)
        # resolve relative to template so each portal can bundle its own assets
        image_path = os.path.join(os.path.dirname(os.path.abspath(TEMPLATE_PATH)), filename)

        if not os.path.isfile(image_path):
            self.send_error(404, f"Asset not found: {filename}")
            return

        ext       = os.path.splitext(filename)[1].lower()
        mime_type = IMAGE_EXTENSIONS.get(ext, 'application/octet-stream')
        file_size = os.path.getsize(image_path)

        self.send_response(200)
        self.send_header('Content-Type',   mime_type)
        self.send_header('Content-Length', str(file_size))
        self.send_header('Cache-Control',  'public, max-age=3600')
        self.send_header('Connection',     'close')
        self.end_headers()
        try:
            with open(image_path, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk: break
                    try:    self.wfile.write(chunk)
                    except BrokenPipeError: break
        except Exception:
            pass

    def _serve_html(self):
        try:
            with open(TEMPLATE_PATH, 'r', encoding='utf-8') as f:
                html = f.read()
        except FileNotFoundError:
            self.send_error(404, "template.html not found")
            return

        ext  = os.path.splitext(VIDEO_FILENAME)[1].lower()
        html = (html
                .replace('{SSID}',       SSID)
                .replace('{VIDEO_SRC}',  f'/{VIDEO_FILENAME}')
                .replace('{VIDEO_MIME}', VIDEO_EXTENSIONS.get(ext, 'video/mp4')))

        body = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type',   'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection',     'close')
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

        ip = self.client_address[0]
        with victims_lock:
            if ip not in victims_set:
                victims_set.add(ip)
                print(f"\n[+] rickroll delivered to {ip}\n", flush=True)
                with open('rickroll_victims.txt', 'a') as f:
                    f.write(f"{time.ctime()},{ip}\n")

    def log_request(self, code='-', size='-'):
        pass

    def log_message(self, format, *args):
        pass


# ── TLS cert generation ──────────────────────────────────────────────────────

def generate_self_signed_cert():
    # Android's NetworkMonitor uses a permissive SSL context during captive
    # portal probing — cert errors are ignored, so self-signed is sufficient.
    global _CERT_FILE, _KEY_FILE

    cfd, cpath = tempfile.mkstemp(suffix='.crt', prefix='rrw_')
    kfd, kpath = tempfile.mkstemp(suffix='.key', prefix='rrw_')
    os.close(cfd); os.close(kfd)

    # openssl >= 1.1.1 with SAN
    r = subprocess.run([
        'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
        '-keyout', kpath, '-out', cpath,
        '-days', '1', '-nodes',
        '-subj', '/CN=connectivitycheck.gstatic.com/O=RRW/C=US',
        '-addext', 'subjectAltName=IP:10.0.0.1,DNS:connectivitycheck.gstatic.com',
    ], capture_output=True)

    if r.returncode != 0:
        # fallback for openssl < 1.1.1 (no -addext)
        r = subprocess.run([
            'openssl', 'req', '-x509', '-newkey', 'rsa:2048',
            '-keyout', kpath, '-out', cpath,
            '-days', '1', '-nodes',
            '-subj', '/CN=10.0.0.1',
        ], capture_output=True)

    if r.returncode != 0:
        print(f"[!] openssl cert generation failed — HTTPS probe server disabled")
        print(f"    {r.stderr.decode().strip()}")
        for p in (cpath, kpath):
            try: os.remove(p)
            except: pass
        return False

    _CERT_FILE = cpath
    _KEY_FILE  = kpath
    print(f"[+] Self-signed TLS cert generated for HTTPS probe server")
    return True


# ── service startup ──────────────────────────────────────────────────────────

def start_hostapd():
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
        subprocess.run("hostapd /tmp/hostapd.conf -B", shell=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        ok = subprocess.run("pgrep -f 'hostapd /tmp/hostapd.conf'",
                            shell=True, capture_output=True)
        return bool(ok.stdout)
    except subprocess.CalledProcessError:
        return False


def start_dnsmasq():
    # dhcp-option=114 → RFC 8908 CAPPORT API URL, not the portal HTML.
    # Android fetches it post-DHCP, parses the JSON, and opens the portal
    # directly without running HTTP/HTTPS connectivity probes.
    config = f"""interface={AP_IFACE}
listen-address=10.0.0.1
bind-interfaces
dhcp-range=10.0.0.10,10.0.0.100,255.255.255.0,12h
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1
dhcp-option=114,{CAPPORT_URL}
address=/#/10.0.0.1
no-resolv
"""
    with open('/tmp/dnsmasq.conf', 'w') as f: f.write(config)
    subprocess.run("killall -9 dnsmasq 2>/dev/null", shell=True)
    subprocess.run("rm -f /var/run/dnsmasq/dnsmasq.pid", shell=True)
    time.sleep(1)
    subprocess.run(f"ip addr add 10.0.0.1/24 dev {AP_IFACE}", shell=True)
    try:
        subprocess.run("dnsmasq -C /tmp/dnsmasq.conf", shell=True, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        ok = subprocess.run("pgrep -f 'dnsmasq -C /tmp/dnsmasq.conf'",
                            shell=True, capture_output=True)
        return bool(ok.stdout)
    except subprocess.CalledProcessError:
        return False


def setup_iptables():
    for proto, port in [('udp','67:68'), ('udp','53'), ('tcp','80'),
                        ('tcp','443'), ('tcp', str(HTTPS_PORT))]:
        subprocess.run(
            f"iptables -I INPUT -i {AP_IFACE} -p {proto} --dport {port} -j ACCEPT",
            shell=True)

    subprocess.run(
        f"iptables -t nat -A PREROUTING -i {AP_IFACE} -p tcp --dport 80 "
        f"-j DNAT --to-destination 10.0.0.1:80",
        shell=True)

    # 443 → HTTPS_PORT, not 80 — a TLS ClientHello hitting a plain HTTP server
    # makes Android classify the network as "broken" rather than captive.
    subprocess.run(
        f"iptables -t nat -A PREROUTING -i {AP_IFACE} -p tcp --dport 443 "
        f"-j DNAT --to-destination 10.0.0.1:{HTTPS_PORT}",
        shell=True)

    print(f"[+] iptables: HTTP→:80, HTTPS→:{HTTPS_PORT}")


def start_https_server():
    # Android's NetworkMonitor bypasses cert validation during captive portal
    # probing — a 302 from a self-signed server resolves the "partial
    # connectivity" / '?' state on Android 12+/15.
    global https_server

    if not _CERT_FILE or not _KEY_FILE:
        print("[!] No TLS cert available — HTTPS probe server skipped")
        return False

    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(_CERT_FILE, _KEY_FILE)
        ctx.check_hostname = False
        ctx.verify_mode    = ssl.CERT_NONE

        https_server = ThreadingHTTPServer(('0.0.0.0', HTTPS_PORT), RickrollHandler)
        https_server.socket = ctx.wrap_socket(https_server.socket, server_side=True)

        t = threading.Thread(target=https_server.serve_forever, daemon=True)
        t.start()
        print(f"[+] HTTPS probe server listening on :{HTTPS_PORT}")
        return True
    except Exception as e:
        print(f"[!] HTTPS server failed to start: {e}")
        return False


# ── cleanup & signals ────────────────────────────────────────────────────────

def cleanup():
    print("\n[*] Cleaning up...")
    subprocess.run("killall -9 hostapd dnsmasq 2>/dev/null", shell=True)
    time.sleep(1)
    if AP_IFACE:
        subprocess.run(f"ip addr flush dev {AP_IFACE}", shell=True)
        subprocess.run(f"ip link set {AP_IFACE} down", shell=True)
        subprocess.run(f"ip link set {AP_IFACE} up",   shell=True)
        for proto, port in [('udp','67:68'), ('udp','53'), ('tcp','80'),
                            ('tcp','443'), ('tcp', str(HTTPS_PORT))]:
            subprocess.run(
                f"iptables -D INPUT -i {AP_IFACE} -p {proto} --dport {port} -j ACCEPT 2>/dev/null",
                shell=True)
        subprocess.run(
            f"iptables -t nat -D PREROUTING -i {AP_IFACE} -p tcp --dport 80 "
            f"-j DNAT --to-destination 10.0.0.1:80 2>/dev/null", shell=True)
        subprocess.run(
            f"iptables -t nat -D PREROUTING -i {AP_IFACE} -p tcp --dport 443 "
            f"-j DNAT --to-destination 10.0.0.1:{HTTPS_PORT} 2>/dev/null", shell=True)
    subprocess.run(f"nmcli device set {AP_IFACE} managed yes 2>/dev/null", shell=True)
    for p in (_CERT_FILE, _KEY_FILE):
        if p and os.path.exists(p):
            try: os.remove(p)
            except: pass
    print("[+] Cleanup complete.")


def signal_handler(sig, frame):
    if server:       server.shutdown()
    if https_server: https_server.shutdown()
    cleanup()
    sys.exit(0)


# ── video / template resolution ──────────────────────────────────────────────

def resolve_video(name):
    global VIDEO_PATH, VIDEO_FILENAME
    ext = os.path.splitext(name)[1].lower()
    if ext not in VIDEO_EXTENSIONS:
        print(f"[!] Unsupported video format: '{ext}'")
        print(f"   Supported: {', '.join(VIDEO_EXTENSIONS.keys())}")
        sys.exit(1)
    folder_path = os.path.join(RICKROLLS_DIR, os.path.basename(name))
    if os.path.isfile(folder_path):
        VIDEO_PATH = folder_path; VIDEO_FILENAME = os.path.basename(name)
        print(f"[+] Using video: {VIDEO_FILENAME}  (from rickrolls/)")
        return
    explicit = os.path.abspath(name)
    if os.path.isfile(explicit):
        VIDEO_PATH = explicit; VIDEO_FILENAME = os.path.basename(explicit)
        print(f"[+] Using video: {VIDEO_FILENAME}  (from explicit path)")
        return
    print(f"[!] Video not found: '{name}'")
    sys.exit(1)


def resolve_template(name):
    if not name.lower().endswith('.html'):
        print(f"[!] Template must be an .html file, got: '{name}'"); sys.exit(1)
    folder_path = os.path.join(TEMPLATES_DIR, os.path.basename(name))
    if os.path.isfile(folder_path):
        print(f"[+] Using template: {os.path.basename(name)}  (from templates/)")
        return folder_path
    explicit = os.path.abspath(name)
    if os.path.isfile(explicit):
        print(f"[+] Using template: {os.path.basename(explicit)}  (from explicit path)")
        return explicit
    print(f"[!] Template not found: '{name}'"); sys.exit(1)


def pick_video():
    global VIDEO_PATH, VIDEO_FILENAME
    if not os.path.isdir(RICKROLLS_DIR):
        print(f"[!] Rickrolls folder not found at: {RICKROLLS_DIR}")
        print("   Create a 'rickrolls' folder next to this script and add video files.")
        sys.exit(1)
    video_files = sorted(
        f for f in os.listdir(RICKROLLS_DIR)
        if os.path.splitext(f)[1].lower() in VIDEO_EXTENSIONS
        and os.path.isfile(os.path.join(RICKROLLS_DIR, f))
    )
    if not video_files:
        print(f"[!] No video files found in: {RICKROLLS_DIR}"); sys.exit(1)
    print("\nAvailable videos:")
    for i, name in enumerate(video_files, 1):
        mb = os.path.getsize(os.path.join(RICKROLLS_DIR, name)) / (1024*1024)
        print(f"  {i}. {name}  ({mb:.1f} MB)")
    while True:
        c = input("\nSelect video (number): ").strip()
        if c.isdigit():
            idx = int(c) - 1
            if 0 <= idx < len(video_files):
                VIDEO_FILENAME = video_files[idx]
                VIDEO_PATH     = os.path.join(RICKROLLS_DIR, VIDEO_FILENAME)
                print(f"[+] Using video: {VIDEO_FILENAME}"); return
        print("  Invalid choice, try again.")


def pick_template():
    if not os.path.isdir(TEMPLATES_DIR):
        print(f"[!] Templates folder not found at: {TEMPLATES_DIR}"); sys.exit(1)
    html_files = sorted(
        f for f in os.listdir(TEMPLATES_DIR)
        if f.lower().endswith('.html') and os.path.isfile(os.path.join(TEMPLATES_DIR, f))
    )
    if not html_files:
        print(f"[!] No .html files found in: {TEMPLATES_DIR}"); sys.exit(1)
    print("\nAvailable templates:")
    for i, name in enumerate(html_files, 1): print(f"  {i}. {name}")
    while True:
        c = input("\nSelect template (number): ").strip()
        if c.isdigit():
            idx = int(c) - 1
            if 0 <= idx < len(html_files):
                chosen = os.path.join(TEMPLATES_DIR, html_files[idx])
                print(f"[+] Using template: {html_files[idx]}"); return chosen
        print("  Invalid choice, try again.")


# ── arg parsing ──────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description='RRW - Rickroll Captive Portal',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  sudo python3 RRW.py -s "FREE WIFI" -v rickroll.mp4 -t portal.html -i wlan1
  sudo python3 RRW.py -s "Airport WiFi" -v /tmp/bait.webm -t /tmp/evil.html -i wlan0
  sudo python3 RRW.py -i wlan1 -s "FREE WIFI"
  sudo python3 RRW.py
        """)
    p.add_argument('-s', '--ssid',      metavar='NAME',  help='WiFi SSID name')
    p.add_argument('-v', '--video',     metavar='FILE',  help='Video filename (from rickrolls/) or explicit path')
    p.add_argument('-t', '--template',  metavar='FILE',  help='HTML template (from templates/) or explicit path')
    p.add_argument('-i', '--interface', metavar='IFACE', help='Wireless interface to use as AP')
    return p.parse_args()


# ── main ─────────────────────────────────────────────────────────────────────

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
        SSID = args.ssid; print(f"[+] SSID: {SSID}")
    else:
        custom = input(f"\nEnter WiFi name [{SSID}]: ").strip()
        if custom: SSID = custom

    if args.video:    resolve_video(args.video)
    else:             pick_video()

    if args.template: TEMPLATE_PATH = resolve_template(args.template)
    else:             TEMPLATE_PATH = pick_template()

    interfaces = get_wireless_interfaces()
    if not interfaces:
        print("[!] No wireless interfaces found!"); sys.exit(1)

    if args.interface:
        if args.interface not in interfaces:
            print(f"[!] Interface '{args.interface}' not found.")
            print(f"   Available: {', '.join(interfaces)}"); sys.exit(1)
        AP_IFACE = args.interface
        print(f"[+] Using interface: {AP_IFACE}")
    else:
        print("\nAvailable wireless interfaces:")
        for i, iface in enumerate(interfaces, 1): print(f"  {i}. {iface}")
        while True:
            c = input("\nSelect AP interface (number/name): ").strip()
            if c.isdigit():
                idx = int(c) - 1
                if 0 <= idx < len(interfaces): AP_IFACE = interfaces[idx]; break
            elif c in interfaces: AP_IFACE = c; break
            print("Invalid choice.")

    print(f"\n[*] Unmanaging {AP_IFACE} from NetworkManager ...")
    subprocess.run(f"nmcli device set {AP_IFACE} managed no 2>/dev/null", shell=True)
    try:
        subprocess.run(f"wpa_cli -i {AP_IFACE} terminate", shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=3)
    except subprocess.TimeoutExpired:
        pass

    time.sleep(1)
    if not start_hostapd(): cleanup(); sys.exit(1)
    if not start_dnsmasq(): cleanup(); sys.exit(1)

    generate_self_signed_cert()   # must run before iptables / HTTPS server
    setup_iptables()

    server = ThreadingHTTPServer(('0.0.0.0', 80), RickrollHandler)
    t_http = threading.Thread(target=server.serve_forever, daemon=True)
    t_http.start()

    start_https_server()

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("\n" + "="*60)
    print("  [+] RICKROLL DEPLOYED!")
    print("="*60)
    print(f"  SSID      : {SSID}")
    print(f"  AP iface  : {AP_IFACE}")
    print(f"  Portal    : {PORTAL_URL}")
    print(f"  CAPPORT   : {CAPPORT_URL}  (DHCP option 114)")
    print(f"  HTTPS srv : :{HTTPS_PORT}  (443 DNATed here)")
    print("="*60 + "\n")

    try:
        while True:
            res     = subprocess.run(f"iw dev {AP_IFACE} station dump",
                                     shell=True, capture_output=True, text=True)
            clients = res.stdout.count('Station')
            print(f"\r[+] Connected clients: {clients}    ", end='', flush=True)
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
