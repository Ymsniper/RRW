# HTML Template Guide

You can design login pages that look like coffee shops, airports, hotels, or anything else. The script handles injecting the Wi-Fi name and video at serve time — you just need to use the right placeholders and IDs.

---

## 1. Placeholders

Three placeholders get replaced automatically when the script serves your page.

### `{SSID}`
Replaced with the Wi-Fi name chosen at startup.

```html
<title>{SSID} Login</title>
<h1>Welcome to {SSID}</h1>
<p>Connect to {SSID} for free internet.</p>
```

### `{VIDEO_SRC}` and `{VIDEO_MIME}`
Replaced with the URL path and MIME type of whichever video file you picked at startup. Use both together in the `<source>` tag inside the video block — this is what makes the script work with any video format, not just `.mp4`.

```html
<source src="{VIDEO_SRC}" type="{VIDEO_MIME}">
```

Do not hardcode `/rickroll.mp4` or `video/mp4` — use these placeholders instead.

---

## 2. Required IDs

The script's JavaScript needs to find these elements by ID. Do not rename them.

- **`id="tos-ui"`** — wrap your entire visible login UI in this. It gets hidden when the user clicks connect.
- **`id="accept-btn"`** — put this on your connect button. Clicking it triggers the video.

---

## 3. Mandatory Video Block

This block must appear at the bottom of `<body>`, untouched. It is what plays the video after the button is clicked.

```html
<div id="video-layer" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: #000; z-index: 9999;">
    <div id="ios-unmute-fallback" style="display: none; position: fixed; top:0; left:0; width:100%; height:100%; z-index: 10000;"></div>
    <video id="rickroll-video" autoplay loop playsinline style="width: 100%; height: 100%; object-fit: cover;">
        <source src="{VIDEO_SRC}" type="{VIDEO_MIME}">
    </video>
</div>

<script>
    var video = document.getElementById('rickroll-video');
    var tosUI = document.getElementById('tos-ui');
    var videoLayer = document.getElementById('video-layer');
    var acceptBtn = document.getElementById('accept-btn');
    var iosFallback = document.getElementById('ios-unmute-fallback');

    if (acceptBtn) {
        acceptBtn.addEventListener('click', function() {
            tosUI.style.display = 'none';
            videoLayer.style.display = 'block';
            video.muted = false;
            var playPromise = video.play();
            if (playPromise !== undefined) {
                playPromise.then(_ => { iosFallback.style.display = 'none'; })
                .catch(error => {
                    video.muted = true; video.play();
                    iosFallback.style.display = 'block';
                });
            }
        });
    }
    if (iosFallback) {
        iosFallback.addEventListener('click', function() {
            video.muted = false; video.play();
            iosFallback.style.display = 'none';
        });
    }
</script>
```

---

## 4. Master Template

Copy this, save it as something like `my-portal.html`, then edit the CSS and UI section. Leave the video block and script alone.

```html
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{SSID} Guest Login</title>
    <style>
        /* edit styles here */
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #1a1a1a;
            margin: 0; padding: 0;
            display: flex; justify-content: center; align-items: center;
            min-height: 100vh;
        }
        .card {
            background: #ffffff;
            width: 90%; max-width: 400px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.2);
            padding: 40px 30px;
            text-align: center;
        }
        h2 { margin: 0 0 10px 0; color: #1a1a1a; font-size: 24px; }
        .subtitle { color: #666; font-size: 14px; margin-bottom: 25px; }
        .accept-btn {
            background-color: #0066cc;
            color: white;
            border: none;
            padding: 14px;
            width: 100%;
            border-radius: 4px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
        }
    </style>
</head>
<body>

    <!-- edit visible UI here — keep id="tos-ui" on the wrapper and id="accept-btn" on the button -->
    <div class="card" id="tos-ui">
        <h2>{SSID}</h2>
        <p class="subtitle">Free guest Wi-Fi</p>
        <p style="font-size: 13px; color: #444; margin-bottom: 20px;">
            By connecting you agree to use this network responsibly.
        </p>
        <button class="accept-btn" id="accept-btn">Accept &amp; Connect</button>
    </div>

    <!-- do not edit below this line -->
    <div id="video-layer" style="display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background-color: #000; z-index: 9999;">
        <div id="ios-unmute-fallback" style="display: none; position: fixed; top:0; left:0; width:100%; height:100%; z-index: 10000;"></div>
        <video id="rickroll-video" autoplay loop playsinline style="width: 100%; height: 100%; object-fit: cover;">
            <source src="{VIDEO_SRC}" type="{VIDEO_MIME}">
        </video>
    </div>

    <script>
        var video = document.getElementById('rickroll-video');
        var tosUI = document.getElementById('tos-ui');
        var videoLayer = document.getElementById('video-layer');
        var acceptBtn = document.getElementById('accept-btn');
        var iosFallback = document.getElementById('ios-unmute-fallback');

        if (acceptBtn) {
            acceptBtn.addEventListener('click', function() {
                tosUI.style.display = 'none';
                videoLayer.style.display = 'block';
                video.muted = false;
                var playPromise = video.play();
                if (playPromise !== undefined) {
                    playPromise.then(_ => { iosFallback.style.display = 'none'; })
                    .catch(error => {
                        video.muted = true; video.play();
                        iosFallback.style.display = 'block';
                    });
                }
            });
        }
        if (iosFallback) {
            iosFallback.addEventListener('click', function() {
                video.muted = false; video.play();
                iosFallback.style.display = 'none';
            });
        }
    </script>
</body>
</html>
```
