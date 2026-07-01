# Installation guide

## Install the packaged add-on

1. Obtain `SarvamAIassistant-x.y.z.nvda-addon` (from the Releases page or by
   building it — see below).
2. In NVDA, press `NVDA+N` to open the menu, then **Tools → Add-on Store**
   (NVDA 2023.2+) or **Tools → Manage add-ons** (older).
3. Choose **Install from external file…**, select the `.nvda-addon`, and
   confirm.
4. Restart NVDA when prompted.

## Configure your API key

1. **NVDA menu → Tools → Sarvam AI → Settings…** (or NVDA **Preferences →
   Settings → Sarvam AI**).
2. Paste your Sarvam API key (from <https://dashboard.sarvam.ai/>).
3. Press **Validate key / Test connection**.
   - *"Connection OK…"* → you're ready.
   - *"…no credits available"* → the key is valid but the account needs credits.
   - *"Authentication failed"* → the key is incorrect.
4. Set your defaults and press **OK**.

## Build from source

No third-party tools are required (a `.nvda-addon` is a ZIP archive).

```bash
python build.py            # build + copy to Downloads
python build.py --no-copy  # build only
python build.py --pot      # regenerate translation template only
```

The package is written to the repository root and copied to your `Downloads`
folder by default.

## Requirements

- NVDA 2021.1 or newer (tested to 2025.1), Windows 10/11.
- A funded Sarvam API key.
- For Windows OCR: a Windows OCR language pack (English is usually preinstalled).

## Uninstall

**Tools → Add-on Store → Installed add-ons →** select *Sarvam AI assistant* **→
Remove**, then restart NVDA.
