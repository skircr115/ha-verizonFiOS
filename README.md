# Verizon FiOS Router Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/v/release/skircr115/ha-verizonFiOS?include_prereleases)](https://github.com/skircr115/ha-verizonFiOS/releases)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/skircr115/ha-verizonFiOS/blob/main/LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained-Yes-green.svg)](https://github.com/skircr115/ha-verizonFiOS/graphs/commit-activity)

A comprehensive Home Assistant integration for Verizon FiOS CR1000A and CE1000A routers.

## Installation

### HACS (Recommended)
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=https%3A%2F%2Fgithub.com%2Fskircr115%2Fha-verizonFiOS&owner=skircr115&category=Integration)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the 3 dots in the top right
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/skircr115/ha-verizonFiOS`
6. Category: Integration
7. Click "Install"
8. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/verizon_fios` directory to your `config/custom_components` directory
2. Restart Home Assistant

## Configuration

### Via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Verizon FiOS Router"
4. Enter your router details:
   - **Router URL**: `https://192.168.1.1` (default)
   - **Username**: `admin` (default)
   - **Password**: Your router admin password
5. Click **Submit**

### Updating Credentials or Router IP After Installation

If your router's IP address changes (e.g. after a network reconfiguration) or you update your admin password, you can reconfigure the integration without removing and re-adding it:

1. Go to **Settings** → **Devices & Services**
2. Find **Verizon FiOS Router** and click **Configure**
3. Update the Router URL, username, and/or password
4. Click **Submit** — the integration validates the new connection before saving

If the connection test passes, the integration reloads automatically with the new settings. No Home Assistant restart is required. If the test fails, the form stays open with an error so you can correct the details before saving.

> **Note on extenders:** Extender discovery is automatic — the integration finds CE1000A units from the router's topology data. Updating the router URL is all that's needed; there is no separate extender URL to configure.

### Supported Routers

- ✅ Verizon CR1000A (tested)
- ✅ Verizon CE1000A (mesh extender, tested)
- 🔶 Other Verizon FiOS routers (likely compatible)

## Features

### 🎯 **100+ Sensors!**

This integration provides extensive monitoring of your Verizon FiOS network:

**Sensor Count:**
- **Router only:** ~71 sensors
- **Router + 1 extender:** ~117 sensors ✅
- **Router + 2 extenders:** ~163 sensors

**Coverage:**

- **Router Performance**: CPU, memory, temperature, uptime
- **Network Quality**: Signal strength, SNR, retry rates, error rates per band
- **Device Tracking**: Total, active, inactive, by type, by vendor, by OS
- **WiFi Analytics**: Per-band device counts (main/IoT/guest), WiFi standards (4/5/6/6E)
- **Mesh Network**: Full extender monitoring with all the same metrics
- **All SSIDs**: Main, Guest, IoT, IPTV, Backhaul networks

## Update Frequency

The integration updates every **4 hours** by default to avoid overloading the router and ensure stable operation. This can be adjusted in `const.py` if needed (UPDATE_INTERVAL setting).

## Technical Details

### Authentication

This integration uses reverse-engineered Verizon router authentication:
- Custom "ArcMD5" hashing (MD5 → SHA512)
- Dynamic token-based password hashing
- Secure session management with cookies

### Connection Management

- ✅ Proper connection cleanup after each update
- ✅ No unclosed connection warnings
- ✅ Efficient resource management
- ✅ Automatic error recovery

### Data Sources

The integration fetches data from:
- `/cgi/cgi_basic.js` - Router topology and basic info
- `/cgi/cgi_owl.js` - Extended device and station information

### Privacy & Security

- ✅ All communication is local (no cloud required)
- ✅ Passwords are never stored in plain text
- ✅ Uses HTTPS with the router
- ✅ Read-only operations (doesn't change router settings)

## Troubleshooting

### Can't Connect

- Verify router URL (default: `https://192.168.1.1`)
- Confirm username (default: `admin`)
- Check password is correct
- Ensure Home Assistant can reach the router

### Router IP Changed

If your router's IP address changed and the integration is showing unavailable sensors, use **Configure** (see [Updating Credentials or Router IP After Installation](#updating-credentials-or-router-ip-after-installation)) to update the URL without losing your history or automations.

### Missing Sensors

- Some sensors only appear when devices are connected
- Device analytics sensors show type/vendor/OS breakdowns as **attributes** (not individual sensors)
- Extender sensors only appear if extenders are configured
- Network quality sensors (per band) only appear when devices are active on that band

### Enable Debug Logging

Add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.verizon_fios: debug
```

## Changelog

### v1.2.1 (2026-06-28) - Current Release
- ✅ Fixed asyncio blocking call when creating SSL context
- ℹ️ No breaking changes

### v1.2.0 (2026-06-07)
- ✨ Added Options Flow — router URL, username, and password can now be updated post-install via **Configure** without removing and re-adding the integration
- ✅ Integration reloads automatically when options are saved; no Home Assistant restart required
- ✅ Connection is validated before new options are committed — bad credentials or an unreachable URL are caught at save time, not at the next update cycle
- ✅ Updated `strings.json` and `translations/en.json` with options flow labels and error messages
- ℹ️ No breaking changes — all entity IDs, sensor names, and existing configuration entries remain the same

### v1.1.0 (2026-05-28)
- 🚀 Eliminated redundant sensor data reprocessing — coordinator caches processed data, cutting ~200+ passes per update cycle down to one
- ✅ Fixed JavaScript parser string-tracking bug — mismatched quotes (e.g. apostrophes in device names) no longer break bracket matching
- ✅ Replaced quote-conversion regex with a proper character-by-character converter — handles apostrophes, escaped quotes, and embedded double quotes correctly
- ✅ Fixed bare `except:` clauses that could swallow `KeyboardInterrupt`/`SystemExit`
- ✅ Added `SensorStateClass.MEASUREMENT` to all 35 measurement sensors — enables long-term history graphing and statistics
- ✅ Replaced private `ssl._create_unverified_context()` with public API; consolidated to a single reusable SSL context
- ✅ Added `translations/en.json` — config flow labels and error messages now render correctly
- 🧹 Removed unused imports and redundant per-request SSL parameters
- ℹ️ No breaking changes - all entity IDs and sensor names remain the same

### v1.0.8 (2025-01-07)
- ✅ Fixed connection management to prevent unclosed connections
- ✅ Proper cleanup of aiohttp connectors after each update
- ✅ Enhanced error handling in API requests
- 📝 Updated documentation with connection management details
- ℹ️ No breaking changes - all sensors remain the same

### v1.0.7 (2025-11-29)
- 🎨 Improved sensor naming consistency
- ✅ Time sensors now show units: "Uptime (hours)", "Uptime (days)"
- ✅ Quality metrics use clearer format: "2G Signal (Avg)" instead of "2G Avg Signal"
- ✅ Device counts simplified: "2.4G Main Devices" instead of "2.4G Main SSID Devices"
- ✅ Aggregate sensors consistent: "WiFi All Devices" instead of "Total WiFi Devices"
- ✅ WiFi standards properly formatted: "WiFi 4 Devices" instead of "Devices: Wifi 4"
- ℹ️ No breaking changes - entity IDs unchanged, only friendly names updated

### v1.0.6 (2025-11-29)
- ✨ Added missing main SSID device sensors (2.4G, 5G, 6G)
- ✨ Added WiFi total rollup sensor (all WiFi devices, excludes ethernet)
- 🔧 Fixed aggregate sensor calculations (5G and 6G now include backhaul)

### v1.0.5 (2025-11-28)
- 🔧 Fixed unit of measurement for data_rate sensors (Mbps → Mbit/s)
- ✅ Resolved Home Assistant unit validation warnings

---

**⭐ If you find this integration useful, please star the repository!**