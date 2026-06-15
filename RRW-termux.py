#!/usr/bin/env python3
"""
RRW - RICKROLL CAPTIVE PORTAL  [Termux / Rooted Android Edition]

Changes from desktop version:
  - No airmon-ng / monitor mode
  - No victim logging / captures
  - Uses $TMPDIR instead of /tmp  (Termux has no /tmp)
  - Uses 'svc wifi' instead of NetworkManager/systemctl
  - Kills wpa_supplicant directly instead of airmon-ng check kill
  - Auto root-check with clear Termux instructions
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
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_PATH = os.path.join(SCRIPT_DIR, "rickroll.mp4")

SSID    = "FREE_WIFI"
CHANNEL = 6
AP_IFACE = None

# Termux sets $TMPDIR; fall back to /data/local/tmp if missing
TMPDIR = os.environ.get("TMPDIR", "/data/local/tmp")

HOSTAPD_CONF = os.path.join(TMPDIR, "rrw_hostapd.conf")
DNSMASQ_CONF = os.path.join(TMPDIR, "rrw_dnsmasq.conf")
DNSMASQ_PID  = os.path.join(TMPDIR, "rrw_dnsmasq.pid")

server = None

# ============ HELPERS ============
def run(cmd, silent=True):
    """Run a shell command. Returns the CompletedProcess."""
    kw = dict(shell=True)
    if silent:
        kw["stdout"] = subprocess.DEVNULL
        kw["stderr"] = subprocess.DEVNULL
    return subprocess.run(cmd, **kw)

def run_out(cmd):
    """Run a shell command and return stdout as a string."""
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return r.stdout.strip()

# ============ DEPENDENCY CHECK ============
def check_dependencies():
    missing = []
    for dep in ["hostapd", "dnsmasq", "iw", "ip", "iptables"]:
        if not run_out(f"which {dep}"):
            missing.append(dep)
    if missing:
        print(f"\n❌  Missing binaries: {', '.join(missing)}")
        print("    Install in Termux:\n")
        print("      pkg install hostapd dnsmasq iw iproute2 iptables\n")
        sys.exit(1)

# ============ INTERFACE DETECTION ============
def get_wireless_interfaces():
    # Try iw first
    raw = run_out("iw dev | grep Interface | awk '{print $2}'")
    ifaces = [i for i in raw.split("\n") if i]

    # Fallback: common Android names
    if not ifaces:
        for name in ["wlan0", "wlan1", "ap0"]:
            if run_out(f"ip link show {name} 2>/dev/null"):
                ifaces.append(name)
    return ifaces

# ============ HTTP HANDLER ============
class RickrollHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/rickroll.mp4":
            self.serve_video()
        else:
            self.serve_html()

    # --- video with range support (needed for mobile seek) ---
    def serve_video(self):
        try:
            if not os.path.exists(VIDEO_PATH):
                self.send_error(404, "Video not found")
                return
            size = os.path.getsize(VIDEO_PATH)
            rng  = self.headers.get("Range")

            if rng:
                m = re.search(r"bytes=(\d+)-(\d*)", rng)
                if m:
                    start  = int(m.group(1))
                    end    = int(m.group(2)) if m.group(2) else size - 1
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type",   "video/mp4")
                    self.send_header("Content-Range",  f"bytes {start}-{end}/{size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges",  "bytes")
                    self.end_headers()
                    with open(VIDEO_PATH, "rb") as f:
                        f.seek(start)
                        left = length
                        while left > 0:
                            chunk = f.read(min(65536, left))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            left -= len(chunk)
                    return

            self.send_response(200)
            self.send_header("Content-Type",   "video/mp4")
            self.send_header("Content-Length", str(size))
            self.send_header("Accept-Ranges",  "bytes")
            self.end_headers()
            with open(VIDEO_PATH, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception:
            pass

    # --- captive portal HTML ---
    def serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wi-Fi Login</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                   Helvetica, Arial, sans-serif;
      background: #f4f5f7; margin: 0; padding: 0;
      display: flex; justify-content: center; align-items: center;
      min-height: 100vh;
    }}
    .card {{
      background: #fff; width: 90%; max-width: 400px;
      border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,.1);
      padding: 30px 20px; text-align: center;
    }}
    .wifi-icon {{ width: 40px; height: 40px; margin-bottom: 15px; fill: #333; }}
    h2 {{ margin: 0 0 5px; color: #1a1a1a; font-size: 22px; }}
    .sub {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
    .tos {{
      text-align: left; background: #f9f9f9;
      border: 1px solid #e0e0e0; border-radius: 4px;
      padding: 15px; height: 180px; overflow-y: auto;
      font-size: 13px; color: #444; line-height: 1.5; margin-bottom: 25px;
    }}
    .tos h4 {{ margin: 0 0 8px; font-size: 13px; color: #222; }}
    .tos p  {{ margin: 0 0 10px; }}
    .btn {{
      background: #0066cc; color: #fff; border: none;
      padding: 14px; width: 100%; border-radius: 4px;
      font-size: 16px; font-weight: 500; cursor: pointer;
      transition: background .2s;
    }}
    .btn:hover {{ background: #0052a3; }}
    #vl {{
      display: none; position: fixed; top: 0; left: 0;
      width: 100vw; height: 100vh; background: #000; z-index: 9999;
    }}
    video {{ width: 100%; height: 100%; object-fit: cover; }}
    #fu  {{
      display: none; position: fixed; top: 0; left: 0;
      width: 100%; height: 100%; z-index: 10000;
    }}
  </style>
</head>
<body>
  <div class="card" id="ui">
    <svg class="wifi-icon" viewBox="0 0 24 24">
      <path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9z
               m8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0z
               m-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/>
    </svg>
    <h2>{SSID}</h2>
    <p class="sub">Network Login Required</p>
    <div class="tos">
      <h4>Terms of Service</h4>
      <p><strong>Welcome to {SSID}</strong></p>
      <p>To continue browsing, please review and accept our network terms:</p>
      <p><strong>1. Data Allowance</strong><br>
         This network is limited to 20 GB per 24-hour period per device.</p>
      <p><strong>2. Acceptable Use</strong><br>
         You agree to use this network for lawful purposes only.</p>
      <p><strong>3. Privacy &amp; Security</strong><br>
         We do not monitor or log your personal browsing data. As with any
         public Wi-Fi, we recommend using a VPN for sensitive activity.</p>
      <p><strong>4. Service Availability</strong><br>
         We do not guarantee uninterrupted service or bandwidth.</p>
      <p>By clicking below you acknowledge that you have read and agree to
         these terms.</p>
    </div>
    <button class="btn" id="btn">I Accept &amp; Connect</button>
  </div>

  <div id="vl">
    <div id="fu"></div>
    <video id="rv" autoplay loop playsinline>
      <source src="/rickroll.mp4" type="video/mp4">
    </video>
  </div>

  <script>
    var rv  = document.getElementById('rv');
    var ui  = document.getElementById('ui');
    var vl  = document.getElementById('vl');
    var btn = document.getElementById('btn');
    var fu  = document.getElementById('fu');

    btn.addEventListener('click', function () {{
      ui.style.display  = 'none';
      vl.style.display  = 'block';
      rv.muted = false;
      var p = rv.play();
      if (p !== undefined) {{
        p.catch(function () {{
          rv.muted = true;
          rv.play();
          fu.style.display = 'block';   // tap-to-unmute fallback (iOS)
        }});
      }}
    }});

    fu.addEventListener('click', function () {{
      rv.muted = false;
      rv.play();
      fu.style.display = 'none';
    }});
  </script>
</body>
</html>"""
        self.wfile.write(html.encode())
        print(f"[🎵] Rickroll delivered to {self.client_address[0]}")

    def log_request(self, code="-", size="-"):
        if code == 400:
            return
        super().log_request(code, size)

    def log_message(self, fmt, *args):
        print(f"   [HTTP] {fmt % args}")

# ============ NETWORK SETUP ============
def kill_interfering():
    """
    On Android we stop wpa_supplicant (WiFi client daemon) so the
    adapter is free for hostapd (AP mode).
    No airmon-ng needed.
    """
    print("[*] Disabling Android WiFi client...")
    run("svc wifi disable")                      # Android system command
    run("killall -9 wpa_supplicant 2>/dev/null") # belt-and-suspenders
    time.sleep(2)

def start_hostapd():
    global AP_IFACE, SSID, CHANNEL
    cfg = (
        f"interface={AP_IFACE}\n"
        f"driver=nl80211\n"
        f"ssid={SSID}\n"
        f"hw_mode=g\n"
        f"channel={CHANNEL}\n"
        f"ieee80211n=1\n"
        f"wmm_enabled=1\n"
        f"auth_algs=1\n"
        f"ignore_broadcast_ssid=0\n"
    )
    with open(HOSTAPD_CONF, "w") as f:
        f.write(cfg)

    run("killall -9 hostapd 2>/dev/null")
    time.sleep(1)
    run(f"ip addr flush dev {AP_IFACE}")
    run(f"ip link set {AP_IFACE} up")

    r = subprocess.run(
        f"hostapd {HOSTAPD_CONF} -B",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if r.returncode != 0:
        print("[-] hostapd failed to start. Does your adapter support AP mode?")
        print(f"    Debug: hostapd {HOSTAPD_CONF}  (run without -B to see errors)")
        return False

    time.sleep(2)
    alive = run_out(f"pgrep -f 'hostapd {HOSTAPD_CONF}'")
    if not alive:
        print("[-] hostapd died immediately. Check driver support.")
        return False

    print(f"[+] AP up  →  SSID: {SSID}  |  interface: {AP_IFACE}")
    return True

def start_dnsmasq():
    cfg = (
        f"interface={AP_IFACE}\n"
        f"listen-address=10.0.0.1\n"
        f"bind-interfaces\n"
        f"dhcp-range=10.0.0.10,10.0.0.100,255.255.255.0,12h\n"
        f"dhcp-option=3,10.0.0.1\n"
        f"address=/#/10.0.0.1\n"   # captive-portal: all DNS → us
        f"no-resolv\n"
        f"pid-file={DNSMASQ_PID}\n"
    )
    with open(DNSMASQ_CONF, "w") as f:
        f.write(cfg)

    run("killall -9 dnsmasq 2>/dev/null")
    run(f"rm -f {DNSMASQ_PID}")
    time.sleep(1)
    run(f"ip addr add 10.0.0.1/24 dev {AP_IFACE}")

    r = subprocess.run(
        f"dnsmasq -C {DNSMASQ_CONF}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if r.returncode != 0:
        print("[-] dnsmasq failed.")
        return False

    alive = run_out(f"pgrep -f 'dnsmasq -C {DNSMASQ_CONF}'")
    if not alive:
        print("[-] dnsmasq died silently.")
        return False

    print("[+] dnsmasq started  →  DHCP + captive-DNS active")
    return True

def setup_iptables():
    iface = AP_IFACE
    rules = [
        # Allow DHCP and DNS in
        f"iptables -I INPUT -i {iface} -p udp --dport 67:68 -j ACCEPT",
        f"iptables -I INPUT -i {iface} -p udp --dport 53   -j ACCEPT",
        # Allow HTTP/HTTPS in
        f"iptables -I INPUT -i {iface} -p tcp --dport 80  -j ACCEPT",
        f"iptables -I INPUT -i {iface} -p tcp --dport 443 -j ACCEPT",
        # Redirect all HTTP/HTTPS to our portal
        f"iptables -t nat -A PREROUTING -i {iface} -p tcp --dport 80  -j DNAT --to-destination 10.0.0.1:80",
        f"iptables -t nat -A PREROUTING -i {iface} -p tcp --dport 443 -j DNAT --to-destination 10.0.0.1:80",
    ]
    for cmd in rules:
        run(cmd)
    print("[+] iptables  →  all traffic redirected to portal")

# ============ CLEANUP ============
def cleanup():
    global AP_IFACE
    print("\n[*] Cleaning up...")
    run("killall -9 hostapd dnsmasq 2>/dev/null")
    time.sleep(1)
    if AP_IFACE:
        run(f"ip addr flush dev {AP_IFACE}")
        run(f"ip link set {AP_IFACE} down")
        # Remove our iptables rules
        iface = AP_IFACE
        run(f"iptables -D INPUT -i {iface} -p udp --dport 67:68 -j ACCEPT 2>/dev/null")
        run(f"iptables -D INPUT -i {iface} -p udp --dport 53   -j ACCEPT 2>/dev/null")
        run(f"iptables -D INPUT -i {iface} -p tcp --dport 80  -j ACCEPT 2>/dev/null")
        run(f"iptables -D INPUT -i {iface} -p tcp --dport 443 -j ACCEPT 2>/dev/null")
        run(f"iptables -t nat -D PREROUTING -i {iface} -p tcp --dport 80  -j DNAT --to-destination 10.0.0.1:80 2>/dev/null")
        run(f"iptables -t nat -D PREROUTING -i {iface} -p tcp --dport 443 -j DNAT --to-destination 10.0.0.1:80 2>/dev/null")
    # Re-enable Android WiFi
    run("svc wifi enable")
    print("[+] Done. Android WiFi re-enabled.")

def signal_handler(sig, frame):
    if server:
        server.shutdown()
    cleanup()
    sys.exit(0)

# ============ MAIN ============
def main():
    global AP_IFACE, SSID, server

    print("\n" + "=" * 56)
    print("  🎵  RRW — RICKROLL PORTAL  [Termux / Android]")
    print("=" * 56)

    # Root check — on Termux, run via:  su  then  python3 RRW.py
    if os.geteuid() != 0:
        print("\n❌  This script needs root.")
        print("    In Termux:")
        print("      su                   ← open a root shell")
        print("      python3 RRW.py       ← then run this script")
        print("    Or:  tsu -c 'python3 RRW.py'")
        sys.exit(1)

    check_dependencies()

    if not os.path.exists(VIDEO_PATH):
        print(f"\n❌  rickroll.mp4 not found at:\n    {VIDEO_PATH}")
        print("    Put rickroll.mp4 in the same folder as RRW.py")
        sys.exit(1)

    # SSID prompt
    custom = input("\n📶  WiFi name [FREE_WIFI]: ").strip()
    if custom:
        SSID = custom

    # Interface selection
    ifaces = get_wireless_interfaces()
    if not ifaces:
        print("\n❌  No wireless interfaces found.")
        print("    Make sure WiFi is on, then re-run.")
        sys.exit(1)

    if len(ifaces) == 1:
        AP_IFACE = ifaces[0]
        print(f"[+] Using interface: {AP_IFACE}")
    else:
        print("\nWireless interfaces:")
        for i, iface in enumerate(ifaces, 1):
            print(f"  {i}. {iface}")
        while True:
            choice = input("\nSelect AP interface (number or name): ").strip()
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(ifaces):
                    AP_IFACE = ifaces[idx]
                    break
            elif choice in ifaces:
                AP_IFACE = choice
                break
            print("  Invalid — try again.")

    kill_interfering()

    if not start_hostapd():
        cleanup()
        sys.exit(1)

    if not start_dnsmasq():
        cleanup()
        sys.exit(1)

    setup_iptables()

    # Start HTTP portal
    server = HTTPServer(("0.0.0.0", 80), RickrollHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    signal.signal(signal.SIGINT,  signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("\n" + "=" * 56)
    print("  ✅  RICKROLL DEPLOYED!")
    print("=" * 56)
    print(f"  SSID   : {SSID}")
    print(f"  AP     : {AP_IFACE}")
    print(f"  Portal : http://10.0.0.1")
    print("  Stop   : Ctrl+C")
    print("=" * 56 + "\n")

    try:
        while True:
            out = run_out(f"iw dev {AP_IFACE} station dump")
            clients = out.count("Station")
            print(f"\r[+] Connected clients: {clients}    ", end="", flush=True)
            time.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
