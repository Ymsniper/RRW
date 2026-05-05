# RRW — Rick Roll Wifi

RRW is a Wi‑Fi captive portal demo for authorized security labs, classroom exercises, and harmless pranks done with clear permission.
<img width="1239" height="844" alt="Screenshot_20260505_005838" src="https://github.com/user-attachments/assets/4c95b639-a659-4b95-8fd7-4e532b302b3e" />
<img width="1239" height="844" alt="Screenshot_20260505_005908" src="https://github.com/user-attachments/assets/5275fa96-c78e-4862-a888-4375ddd77ce5" />


## Overview

This project presents a network login page and then displays a fullscreen Rick Astley video after the user interacts with the page. It is intended only for controlled environments where you have explicit authorization to test or demonstrate captive portal behavior.

## Educational & Authorized Use Only

Use this project only in environments you own or are permitted to test.

Do not use it to:
- intercept traffic without consent
- impersonate public or private networks
- collect credentials or personal data
- disrupt third-party devices or networks

## Features

- Custom captive portal-style login page
- Mobile-friendly layout
- Configurable SSID and channel
- Local logging for lab use
- Easy cleanup on exit

## Requirements

### System packages
Debian / Ubuntu / Kali:
```bash
sudo apt update
sudo apt install hostapd dnsmasq iptables python3 iw
```

### Hardware
A Wi‑Fi adapter that supports Access Point mode.

Check support with:
```bash
iw list | grep -A 10 "Supported interface modes"
```
Look for `* AP` in the output.

## Usage

1. Clone the repository:
```bash
git clone https://github.com/YOUR_USERNAME/RRW.git
cd RRW
```

2. Configure the video path:
Set `VIDEO_PATH` in `RRW.py` to the location of your `rickroll.mp4` file.

3. Run the script as root:
```bash
sudo python3 RRW.py
```

4. Follow the prompts:
- Enter the Wi‑Fi name
- Select the adapter
- Start the demo

5. Stop the demo:
Press `Ctrl+C` to clean up background services and restore the system state.

## Configuration

Common settings in `RRE.py`:
- `VIDEO_PATH`: path to the Rick Roll video
- `SSID`: default Wi‑Fi name
- `CHANNEL`: Wi‑Fi channel

## Notes

- Some devices may show connection warnings in captive portal demos.
- On iOS / Safari, media playback may require a direct user gesture.
- Logs, if enabled, are stored locally for lab use.

## License

MIT License. See the `LICENSE` file for details.

## Requirements File

This project uses standard Python 3 libraries plus system dependencies listed above.
