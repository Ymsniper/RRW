
================================================================================
                    RRW - Rick Roll Wifi
================================================================================

RRW is a professional-looking Wi-Fi captive portal designed for harmless pranks 
and penetration testing labs. It broadcasts a fake Wi-Fi network and serves a 
highly convincing "Terms of Service" login page. Once the victim clicks 
"Accept", they are seamlessly Rick-Rolled in fullscreen with audio.

Built natively in Python 3, utilizing hostapd and dnsmasq for Rogue AP creation.

--------------------------------------------------------------------------------
WARNING: EDUCATIONAL & PRANK USE ONLY
--------------------------------------------------------------------------------
RRW creates a Rogue Access Point. Intercepting or redirecting network traffic 
without explicit, documented consent is illegal. This tool is intended strictly 
for authorized security audits, CTF events, and pranking friends (with 
permission). The author assumes no liability for misuse.


================================================================================
HOW IT WORKS
================================================================================

1. Rogue AP: Uses hostapd to broadcast a fake SSID (default: FREE_WIFI).
2. DHCP/DNS: Uses dnsmasq to assign IPs to victims and force all DNS requests 
   to the host machine.
3. Traffic Redirection: Uses iptables to hijack HTTP/HTTPS traffic, sending it 
   to a local Python web server.
4. The Trap: Serves a realistic, mobile-responsive network login UI.
5. The Payload: Hides the UI and drops the victim into an inescapable fullscreen 
   Rick Astley music video.


================================================================================
PREREQUISITES
================================================================================

SYSTEM PACKAGES (Debian/Ubuntu/Kali):
-------------------------------------
sudo apt update
sudo apt install hostapd dnsmasq iptables python3 iw

HARDWARE:
---------
A Wi-Fi adapter that supports AP (Access Point) mode. 
Check your adapter with: 
    iw list | grep -A 10 "Supported interface modes"
(Look for "* AP" in the output).


================================================================================
USAGE
================================================================================

1. CLONE THE REPOSITORY:
   git clone https://github.com/YOUR_USERNAME/RRW.git
   cd RRW

   NOTE: RRW uses only Python standard libraries, so no "pip install" is 
   needed. See requirements.txt for details.

2. PROVIDE THE VIDEO:
   By default, RRW looks for: 
   /home/sinstriker/FINALRICKROLL/rickroll_video/rickroll.mp4
   
   Change the VIDEO_PATH variable at the top of rrw.py to match where your 
   rickroll.mp4 is actually located.

3. RUN RRW (REQUIRES ROOT):
   sudo python3 rrw.py

4. FOLLOW THE PROMPTS:
   - Enter your desired Wi-Fi name.
   - Select your Wi-Fi adapter.
   - Wait for victims to connect!

5. STOP RRW:
   Press Ctrl+C. The script automatically cleans up iptables, kills 
   background processes, and restores your network.


================================================================================
CONFIGURATION
================================================================================

Easily tweak the variables inside rrw.py:

- VIDEO_PATH: Absolute path to your Rick Roll video.
- SSID: Default Wi-Fi name (e.g., FREE_WIFI, Airport_WiFi).
- CHANNEL: Wi-Fi channel (default: 6).


================================================================================
NOTES
================================================================================

- HTTPS WARNINGS: Victims may see a "Connection is not private" warning 
  because HTTPS traffic is being forcibly redirected. The realistic TOS UI 
  usually encourages them to click "Advanced -> Proceed anyway".

- iOS AUDIO FIX: Includes a specific JavaScript fallback to unmute audio on 
  Safari/iOS, as Apple requires a direct user gesture to trigger sound.

- LOGGING: Victim IPs and timestamps are saved locally to 
  rickroll_victims.txt (this file is git-ignored for privacy).


================================================================================
LICENSE & REQUIREMENTS
================================================================================

- License: This project is licensed under the MIT License. Please see the 
  included LICENSE file for full details.
  
- Requirements: See the included requirements.txt file for system dependency 
  information (no Python pip packages are required).

================================================================================
```
