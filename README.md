# RRW — Rick Roll WiFi

RRW spins up a rogue access point that intercepts OS captive portal probes and serves a fake Wi-Fi login page. Once a connected device opens the portal, it gets rickrolled — no credentials collected, no traffic intercepted, no MitM. It's a prank tool, not a credential harvester.

<img width="1239" height="844" alt="Screenshot_20260505_005838" src="https://github.com/user-attachments/assets/4c95b639-a659-4b95-8fd7-4e532b302b3e" />
<img width="1239" height="844" alt="Screenshot_20260505_005908" src="https://github.com/user-attachments/assets/5275fa96-c78e-4862-a888-4375ddd77ce5" />

## How It Works

1. `hostapd` broadcasts an open AP with your chosen SSID.
2. `dnsmasq` answers all DNS queries with the AP's IP (`10.0.0.1`) and hands out DHCP leases.
3. `iptables` redirects all TCP 80/443 traffic to the local HTTP server on port 80.
4. When a device connects, its OS fires a captive portal probe (e.g. `connectivitycheck.gstatic.com`, `captive.apple.com`). The server catches that probe and issues a `302` redirect to the portal page.
5. The device pops the portal. The victim hits "Accept" (or whatever your template says). The page swaps to a fullscreen rickroll video served directly from the AP.
6. Each unique IP is logged once to `rickroll_victims.txt`.

Nothing beyond that. No SSL stripping, no packet sniffing, no form data capture.

## Authorized Use Only

Only run this on networks and devices you own or have explicit written permission to test on.

## Requirements

### System packages

**Debian / Ubuntu / Kali / Parrot**
```bash
sudo apt update
sudo apt install hostapd dnsmasq iptables python3 iw
```

**Arch Linux / Manjaro / EndeavourOS**
```bash
sudo pacman -Sy hostapd dnsmasq iptables iw python
```
> `python` is Python 3 on Arch. `iptables` may already be installed; if you're on a system using `nftables` by default install `iptables-nft` instead.

**Fedora**
```bash
sudo dnf install hostapd dnsmasq iptables iw python3
```

**RHEL / CentOS Stream / AlmaLinux / Rocky Linux**
```bash
sudo dnf install epel-release
sudo dnf install hostapd dnsmasq iptables iw python3
```
> `hostapd` lives in EPEL on RHEL-based distros — the first line enables that repo.

**openSUSE Tumbleweed / Leap**
```bash
sudo zypper addrepo https://download.opensuse.org/repositories/home:mnhauke:network/openSUSE_Tumbleweed/home:mnhauke:network.repo
sudo zypper refresh
sudo zypper install hostapd dnsmasq iptables iw python3
```
> `hostapd` is not in the default openSUSE repos; the command above adds the community repo that carries it. For Leap, replace `openSUSE_Tumbleweed` in the URL with your Leap version (e.g. `15.6`).

**Gentoo**
```bash
sudo emerge --ask net-wireless/hostapd net-dns/dnsmasq net-firewall/iptables net-wireless/iw
```
> Python 3 is a Gentoo base dependency and will already be present.

**Void Linux**
```bash
sudo xbps-install -S hostapd dnsmasq iptables iw python3
```

### Hardware

A Wi-Fi adapter that supports AP mode:

```bash
iw list | grep -A 10 "Supported interface modes"
# look for "* AP" in the output
```

## Project Structure

```
RRW/
├── RRW.py
├── rickrolls/          # drop your video files here
│   └── rickroll.mp4
└── templates/          # drop your HTML portal pages here
    └── portal.html
```

### Supported video formats

`.mp4` `.m4v` `.webm` `.mkv` `.avi` `.mov` `.ogv` `.flv` `.wmv` `.ts` `.3gp`

### HTML templates

Any `.html` file. Use `{SSID}` anywhere in the markup and it gets replaced with the live SSID at runtime.

## Usage

### Interactive (prompted)

```bash
sudo python3 RRW.py
```

You'll be prompted for SSID, video, template, and interface in order.

### Flag-driven (no prompts)

```bash
sudo python3 RRW.py -s "FREE WIFI" -v rickroll.mp4 -t portal.html -i wlan1
```

| Flag | Long form | What it does |
|------|-----------|--------------|
| `-s` | `--ssid` | SSID to broadcast |
| `-v` | `--video` | Video filename from `rickrolls/` **or** an explicit path |
| `-t` | `--template` | HTML filename from `templates/` **or** an explicit path |
| `-i` | `--interface` | Wireless interface to use as AP |

All flags are optional — omit any one and you'll be prompted for that value interactively.

### Using files outside the project folders

Pass a full or relative path and RRW will use it directly:

```bash
sudo python3 RRW.py -v /tmp/other.webm -t /tmp/custom.html -i wlan0 -s "Airport WiFi"
```

### Stop

`Ctrl+C` — kills `hostapd` and `dnsmasq`, flushes the IP, removes the `iptables` rules, and hands the interface back to NetworkManager.

## Logging

Each rickrolled IP is written once to `rickroll_victims.txt` in the working directory:

```
Mon May  5 00:59:12 2026,192.168.0.42
```
