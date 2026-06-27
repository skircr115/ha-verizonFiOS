"""Sensor platform for Verizon FiOS Router."""

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VerizonRouterCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Verizon FiOS Router sensors."""
    coordinator: VerizonRouterCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []

    # Process the data and create sensors
    if coordinator.data:
        processed_data = await hass.async_add_executor_job(
            _process_router_data, coordinator.data
        )
        # Seed the coordinator cache so the initial native_value reads on every
        # sensor don't each trigger an independent reprocessing pass.
        coordinator.processed_data = processed_data

        for sensor_id, sensor_data in processed_data.items():
            sensors.append(
                VerizonRouterSensor(
                    coordinator,
                    entry,
                    sensor_id,
                    sensor_data.get("name"),
                    sensor_data.get("unit"),
                    sensor_data.get("device_class"),
                    sensor_data.get("icon"),
                    sensor_data.get("device_key"),
                    sensor_data.get("state_class"),
                )
            )

    async_add_entities(sensors)


def _get_device_info(
    device_key: str, device_name: str, model: str, entry: ConfigEntry
) -> DeviceInfo:
    """Create device info for a device."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{device_key}")},
        name=device_name,
        manufacturer="Verizon",
        model=model,
        via_device=(DOMAIN, entry.entry_id) if device_key != "router" else None,
    )


def _process_router_data(data: dict[str, Any]) -> dict[str, dict]:
    """Process router data into sensor definitions."""
    sensors = {}

    topology = data.get("topology", {})
    known_devices = data.get("known_devices", {})
    station_info = data.get("station_info", {})

    # Router basic info (string-state sensors — no state_class)
    if data.get("router_name"):
        sensors["router_name"] = {
            "name": "Router Name",
            "value": data["router_name"],
            "unit": None,
            "device_class": None,
            "state_class": None,
            "icon": "mdi:router-wireless",
            "device_key": "router",
        }

    if data.get("hardware_model"):
        sensors["router_model"] = {
            "name": "Router Model",
            "value": data["hardware_model"],
            "unit": None,
            "device_class": None,
            "state_class": None,
            "icon": "mdi:router-wireless",
            "device_key": "router",
        }

    # Process topology
    if topology and "nodes" in topology:
        main_node = topology["nodes"][0]

        # Router metrics
        _process_node_metrics(sensors, main_node, "router", "router")

        # WiFi SSIDs
        _process_ssids(sensors, main_node, "router", "router")

        # Mesh extenders
        extender_count = len(topology["nodes"]) - 1
        sensors["router_mesh_extenders"] = {
            "name": "Mesh Extenders",
            "value": extender_count,
            "unit": "devices",
            "device_class": None,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:access-point-network",
            "device_key": "router",
        }

        # Total devices
        total_devices = sum(int(node.get("sta_num", 0)) for node in topology["nodes"])
        sensors["router_total_connected_devices"] = {
            "name": "Total Connected Devices",
            "value": total_devices,
            "unit": "devices",
            "device_class": None,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:devices",
            "device_key": "router",
        }

        # Process extenders
        for i, node in enumerate(topology["nodes"][1:], 1):
            device_key = f"extender_{i}"
            _process_node_metrics(sensors, node, f"extender_{i}", device_key)
            _process_extender_connection(sensors, node, i, device_key)

    # Process known devices - all under router
    if known_devices and "known_devices" in known_devices:
        _process_known_devices(sensors, known_devices["known_devices"], "router")

    # Process station info for detailed metrics
    if station_info and "stations" in station_info and topology and "nodes" in topology:
        _process_station_info(sensors, station_info["stations"], topology["nodes"])

    return sensors


def _process_node_metrics(
    sensors: dict, node: dict, prefix: str, device_key: str
) -> None:
    """Process metrics for a node (router or extender)."""
    # Uptime
    uptime_seconds = int(node.get("uptime", 0))
    sensors[f"{prefix}_uptime_hours"] = {
        "name": "Uptime (hours)",
        "value": uptime_seconds // 3600,
        "unit": "h",
        "device_class": "duration",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:clock-outline",
        "device_key": device_key,
    }

    sensors[f"{prefix}_uptime_days"] = {
        "name": "Uptime (days)",
        "value": round(uptime_seconds / 86400, 1),
        "unit": "d",
        "device_class": "duration",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:calendar-clock",
        "device_key": device_key,
    }

    # CPU metrics
    cpu_user = int(node.get("cpuU", 0))
    cpu_system = int(node.get("cpuS", 0))
    cpu_idle = int(node.get("cpuI", 0))

    sensors[f"{prefix}_cpu_usage"] = {
        "name": "CPU Usage",
        "value": cpu_user + cpu_system,
        "unit": "%",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:chip",
        "device_key": device_key,
    }

    sensors[f"{prefix}_cpu_user"] = {
        "name": "CPU User",
        "value": cpu_user,
        "unit": "%",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:chip",
        "device_key": device_key,
    }

    sensors[f"{prefix}_cpu_system"] = {
        "name": "CPU System",
        "value": cpu_system,
        "unit": "%",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:chip",
        "device_key": device_key,
    }

    sensors[f"{prefix}_cpu_idle"] = {
        "name": "CPU Idle",
        "value": cpu_idle,
        "unit": "%",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:chip",
        "device_key": device_key,
    }

    # Temperature
    sensors[f"{prefix}_temperature"] = {
        "name": "Temperature",
        "value": int(node.get("cpuT", 0)),
        "unit": "°C",
        "device_class": "temperature",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer",
        "device_key": device_key,
    }

    # Memory
    mem_total = int(node.get("memT", 0))
    mem_used = int(node.get("memU", 0))
    mem_free = int(node.get("memF", 0))

    if mem_total > 0:
        sensors[f"{prefix}_memory_usage_pct"] = {
            "name": "Memory Usage",
            "value": round((mem_used / mem_total * 100), 1),
            "unit": "%",
            "device_class": None,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:memory",
            "device_key": device_key,
        }

    sensors[f"{prefix}_memory_used_mb"] = {
        "name": "Memory Used",
        "value": round(mem_used / 1024, 1),
        "unit": "MB",
        "device_class": "data_size",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "device_key": device_key,
    }

    sensors[f"{prefix}_memory_free_mb"] = {
        "name": "Memory Free",
        "value": round(mem_free / 1024, 1),
        "unit": "MB",
        "device_class": "data_size",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "device_key": device_key,
    }

    sensors[f"{prefix}_memory_total_mb"] = {
        "name": "Memory Total",
        "value": round(mem_total / 1024, 1),
        "unit": "MB",
        "device_class": "data_size",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:memory",
        "device_key": device_key,
    }

    # Connected devices
    sensors[f"{prefix}_connected_devices"] = {
        "name": "Connected Devices",
        "value": int(node.get("sta_num", 0)),
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:devices",
        "device_key": device_key,
    }

    # Firmware (string state — no state_class)
    if node.get("sw_ver"):
        sensors[f"{prefix}_firmware"] = {
            "name": "Firmware Version",
            "value": node["sw_ver"],
            "unit": None,
            "device_class": None,
            "state_class": None,
            "icon": "mdi:chip",
            "device_key": device_key,
        }


def _process_ssids(sensors: dict, node: dict, prefix: str, device_key: str) -> None:
    """Process SSID information."""
    ssid_map = {
        "wifi_2g_ssid": ("essid_2g", "2.4GHz Main SSID"),
        "wifi_2g_guest_ssid": ("essid_2g_gst", "2.4GHz Guest SSID"),
        "wifi_2g_iot_ssid": ("essid_2g_iot", "2.4GHz IoT SSID"),
        "wifi_5g_ssid": ("essid_5g", "5GHz Main SSID"),
        "wifi_5g_iptv_ssid": ("essid_5g_iptv", "5GHz IPTV SSID"),
        "wifi_5g_backhaul_ssid": ("essid_5g_bh", "5GHz Backhaul SSID"),
        "wifi_6g_ssid": ("essid_6g", "6GHz Main SSID"),
        "wifi_6g_backhaul_ssid": ("essid_6g_bh", "6GHz Backhaul SSID"),
    }

    for sensor_key, (node_key, display_name) in ssid_map.items():
        if node.get(node_key):
            sensors[f"{prefix}_{sensor_key}"] = {
                "name": display_name,
                "value": node[node_key],
                "unit": None,
                "device_class": None,
                "state_class": None,
                "icon": "mdi:wifi",
                "device_key": device_key,
            }


def _process_extender_connection(
    sensors: dict, node: dict, index: int, device_key: str
) -> None:
    """Process extender connection details."""
    prefix = f"extender_{index}"

    # Name and model are string states — no state_class
    if node.get("device_name"):
        sensors[f"{prefix}_name"] = {
            "name": "Name",
            "value": node["device_name"],
            "unit": None,
            "device_class": None,
            "state_class": None,
            "icon": "mdi:access-point-network",
            "device_key": device_key,
        }

    if node.get("model_name"):
        sensors[f"{prefix}_model"] = {
            "name": "Model",
            "value": node["model_name"],
            "unit": None,
            "device_class": None,
            "state_class": None,
            "icon": "mdi:access-point-network",
            "device_key": device_key,
        }

    # Parse signal strength - ensure it's numeric
    signal_raw = node.get("connect_rssi", "0")
    if isinstance(signal_raw, str):
        signal_value = signal_raw.replace("dBm", "").replace("dbm", "").strip()
        try:
            signal_value = int(signal_value)
        except ValueError:
            signal_value = 0
    else:
        signal_value = signal_raw

    sensors[f"{prefix}_signal"] = {
        "name": "Signal Strength",
        "value": signal_value,
        "unit": "dBm",
        "device_class": "signal_strength",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:wifi-strength-3",
        "device_key": device_key,
    }

    # Connection type is a string state — no state_class
    sensors[f"{prefix}_connection_type"] = {
        "name": "Connection Type",
        "value": node.get("connect_type", "Unknown"),
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:connection",
        "device_key": device_key,
    }

    # Parse link rate - strip 'Mbps' suffix if present
    link_rate_raw = node.get("linkrate", "0")
    if isinstance(link_rate_raw, str):
        link_rate_value = link_rate_raw.replace("Mbps", "").replace("mbps", "").strip()
        try:
            link_rate_value = int(link_rate_value)
        except ValueError:
            link_rate_value = 0
    else:
        link_rate_value = link_rate_raw

    sensors[f"{prefix}_link_rate"] = {
        "name": "Link Rate",
        "value": link_rate_value,
        "unit": "Mbit/s",
        "device_class": "data_rate",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:speedometer",
        "device_key": device_key,
    }


def _process_known_devices(sensors: dict, devices: list, device_key: str) -> None:
    """Process known devices for statistics."""
    total_known = len(devices)
    active_devices = 0

    device_types = {}
    device_vendors = {}
    devices_by_os = {}

    for device in devices:
        if device.get("activity") == 1:
            active_devices += 1

        # Device type
        dev_class = device.get("dev_class", "Unknown")
        if dev_class and dev_class != "(null)" and dev_class != "":
            device_types[dev_class] = device_types.get(dev_class, 0) + 1

        # Vendor
        vendor = device.get("mac_vendor", "Unknown")
        if vendor and vendor != "":
            device_vendors[vendor] = device_vendors.get(vendor, 0) + 1

        # OS
        device_os = device.get("device_os", "Unknown")
        if device_os and device_os != "(null)" and device_os != "":
            devices_by_os[device_os] = devices_by_os.get(device_os, 0) + 1

    sensors["router_total_known_devices"] = {
        "name": "Total Known Devices",
        "value": total_known,
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:database",
        "device_key": device_key,
    }

    sensors["router_active_devices"] = {
        "name": "Active Devices",
        "value": active_devices,
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:check-network",
        "device_key": device_key,
    }

    sensors["router_inactive_devices"] = {
        "name": "Inactive Devices",
        "value": total_known - active_devices,
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:network-off",
        "device_key": device_key,
    }

    # Device breakdown by type (as attributes)
    sensors["router_device_types"] = {
        "name": "Device Types",
        "value": len(device_types),
        "unit": "types",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:devices",
        "device_key": device_key,
        "attributes": device_types,
    }

    # Device breakdown by vendor (as attributes)
    sensors["router_device_vendors"] = {
        "name": "Device Vendors",
        "value": len(device_vendors),
        "unit": "vendors",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:factory",
        "device_key": device_key,
        "attributes": device_vendors,
    }

    # Device breakdown by OS (as attributes)
    sensors["router_device_os"] = {
        "name": "Device Operating Systems",
        "value": len(devices_by_os),
        "unit": "OSes",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:devices",
        "device_key": device_key,
        "attributes": devices_by_os,
    }


def _process_station_info(sensors: dict, stations: list, nodes: list) -> None:
    """Process station information for detailed per-band metrics."""
    main_router_mac = nodes[0].get("device_mac", "")

    # Initialize band counters
    router_bands = {
        "2g": 0,
        "2g_guest": 0,
        "2g_iot": 0,
        "5g": 0,
        "5g_iptv": 0,
        "5g_backhaul": 0,
        "6g": 0,
        "6g_backhaul": 0,
        "ethernet": 0,
    }

    extender_bands = {}
    for i, node in enumerate(nodes[1:], 1):
        extender_mac = node.get("device_mac", "")
        extender_bands[extender_mac] = {
            "2g": 0,
            "2g_guest": 0,
            "2g_iot": 0,
            "5g": 0,
            "5g_iptv": 0,
            "5g_backhaul": 0,
            "6g": 0,
            "6g_backhaul": 0,
            "ethernet": 0,
        }

    # Quality metrics per band
    band_metrics = {
        "2g": {"signals": [], "snr": [], "retries": [], "errors": [], "rates": []},
        "5g": {"signals": [], "snr": [], "retries": [], "errors": [], "rates": []},
        "6g": {"signals": [], "snr": [], "retries": [], "errors": [], "rates": []},
    }

    wifi_standards = {"wifi_4": 0, "wifi_5": 0, "wifi_6": 0, "wifi_6e": 0}

    for station in stations:
        parent_mac = station.get("parent_mac", "")
        connect_type = station.get("connect_type", "")

        # Determine target (router or extender)
        if parent_mac == main_router_mac:
            target = router_bands
        elif parent_mac in extender_bands:
            target = extender_bands[parent_mac]
        else:
            continue

        # Count by connection type
        if connect_type == "2.4G":
            target["2g"] += 1
        elif connect_type == "2.4G_iot":
            target["2g_iot"] += 1
        elif connect_type == "2.4G_guest":
            target["2g_guest"] += 1
        elif connect_type == "5G":
            target["5g"] += 1
        elif connect_type == "5G_iptv":
            target["5g_iptv"] += 1
        elif connect_type == "5G_backhaul":
            target["5g_backhaul"] += 1
        elif connect_type == "6G":
            target["6g"] += 1
        elif connect_type == "6G_backhaul":
            target["6g_backhaul"] += 1
        elif connect_type == "Ether":
            target["ethernet"] += 1

        # Collect quality metrics
        if "2.4G" in connect_type or "2G" in connect_type:
            band = "2g"
        elif "5G" in connect_type:
            band = "5g"
        elif "6G" in connect_type:
            band = "6g"
        else:
            continue

        # Parse numeric station metrics; skip the whole station on bad data
        # rather than silently swallowing SystemExit or KeyboardInterrupt
        try:
            signal = int(station.get("signal_strength", 0))
            if signal < 0:
                band_metrics[band]["signals"].append(signal)

            snr = int(station.get("snr", 0))
            if snr > 0:
                band_metrics[band]["snr"].append(snr)

            retries = int(station.get("rtc", 0))
            band_metrics[band]["retries"].append(retries)

            errors = int(station.get("es", 0))
            band_metrics[band]["errors"].append(errors)

            link_rate = station.get("link_rate", "0Mbps").replace("Mbps", "")
            try:
                rate_val = int(link_rate)
                band_metrics[band]["rates"].append(rate_val)
            except (ValueError, TypeError):
                pass
        except (ValueError, TypeError):
            pass

        # WiFi standard
        mode = station.get("mode", "")
        if mode in ["2", "5"]:
            wifi_standards["wifi_4"] += 1
        elif mode in ["6", "7", "8", "9"]:
            wifi_standards["wifi_5"] += 1
        elif mode == "11":
            if "6G" in connect_type:
                wifi_standards["wifi_6e"] += 1
            else:
                wifi_standards["wifi_6"] += 1

    # Create router band sensors
    _create_band_sensors(sensors, router_bands, "router", "router")

    # Create extender band sensors
    for i, node in enumerate(nodes[1:], 1):
        extender_mac = node.get("device_mac", "")
        if extender_mac in extender_bands:
            _create_band_sensors(
                sensors, extender_bands[extender_mac], f"extender_{i}", f"extender_{i}"
            )

    # Create quality metric sensors - all under router device
    for band_name, metrics in band_metrics.items():
        if metrics["signals"]:
            avg_signal = sum(metrics["signals"]) / len(metrics["signals"])
            sensors[f"router_{band_name}_avg_signal"] = {
                "name": f"{band_name.upper()} Signal (Avg)",
                "value": round(avg_signal, 1),
                "unit": "dBm",
                "device_class": "signal_strength",
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:wifi",
                "device_key": "router",
            }

            sensors[f"router_{band_name}_min_signal"] = {
                "name": f"{band_name.upper()} Signal (Min)",
                "value": min(metrics["signals"]),
                "unit": "dBm",
                "device_class": "signal_strength",
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:wifi-strength-1",
                "device_key": "router",
            }

            sensors[f"router_{band_name}_max_signal"] = {
                "name": f"{band_name.upper()} Signal (Max)",
                "value": max(metrics["signals"]),
                "unit": "dBm",
                "device_class": "signal_strength",
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:wifi-strength-4",
                "device_key": "router",
            }

        if metrics["snr"]:
            avg_snr = sum(metrics["snr"]) / len(metrics["snr"])
            sensors[f"router_{band_name}_avg_snr"] = {
                "name": f"{band_name.upper()} SNR (Avg)",
                "value": round(avg_snr, 1),
                "unit": "dB",
                "device_class": None,
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:signal",
                "device_key": "router",
            }

        if metrics["retries"]:
            sensors[f"router_{band_name}_total_retries"] = {
                "name": f"{band_name.upper()} Retries",
                "value": sum(metrics["retries"]),
                "unit": "count",
                "device_class": None,
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:refresh",
                "device_key": "router",
            }

        if metrics["errors"]:
            sensors[f"router_{band_name}_total_errors"] = {
                "name": f"{band_name.upper()} Errors",
                "value": sum(metrics["errors"]),
                "unit": "count",
                "device_class": None,
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:alert-circle",
                "device_key": "router",
            }

        if metrics["rates"]:
            avg_rate = sum(metrics["rates"]) / len(metrics["rates"])
            sensors[f"router_{band_name}_avg_link_rate"] = {
                "name": f"{band_name.upper()} Link Rate (Avg)",
                "value": round(avg_rate, 0),
                "unit": "Mbit/s",
                "device_class": "data_rate",
                "state_class": SensorStateClass.MEASUREMENT,
                "icon": "mdi:speedometer",
                "device_key": "router",
            }

    # WiFi standard sensors - under router
    for standard, count in wifi_standards.items():
        # Convert wifi_4 to "WiFi 4", wifi_6e to "WiFi 6E"
        display_name = standard.replace("_", " ").title().replace("Wifi", "WiFi")
        if standard == "wifi_6e":
            display_name = "WiFi 6E"

        sensors[f"router_devices_{standard}"] = {
            "name": f"{display_name} Devices",
            "value": count,
            "unit": "devices",
            "device_class": None,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": "mdi:wifi",
            "device_key": "router",
        }


def _create_band_sensors(
    sensors: dict, bands: dict, prefix: str, device_key: str
) -> None:
    """Create per-band device count sensors."""
    band_mapping = {
        "2g": ("2.4G Main", "mdi:wifi"),
        "2g_iot": ("2.4G IoT", "mdi:home-automation"),
        "2g_guest": ("2.4G Guest", "mdi:account-multiple"),
        "5g": ("5G Main", "mdi:wifi"),
        "5g_iptv": ("5G IPTV", "mdi:television"),
        "5g_backhaul": ("5G Backhaul", "mdi:access-point-network"),
        "6g": ("6G Main", "mdi:wifi-star"),
        "6g_backhaul": ("6G Backhaul", "mdi:access-point-network"),
        "ethernet": ("Ethernet", "mdi:ethernet"),
    }

    for band_key, (band_name, icon) in band_mapping.items():
        sensors[f"{prefix}_devices_{band_key}"] = {
            "name": f"{band_name} Devices",
            "value": bands[band_key],
            "unit": "devices",
            "device_class": None,
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": icon,
            "device_key": device_key,
        }

    # Aggregate sensors for each band
    sensors[f"{prefix}_devices_2g_total"] = {
        "name": "2.4G All Devices",
        "value": bands["2g"] + bands["2g_iot"] + bands["2g_guest"],
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:wifi",
        "device_key": device_key,
    }

    sensors[f"{prefix}_devices_5g_total"] = {
        "name": "5G All Devices",
        "value": bands["5g"] + bands["5g_iptv"] + bands["5g_backhaul"],
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:wifi",
        "device_key": device_key,
    }

    sensors[f"{prefix}_devices_6g_total"] = {
        "name": "6G All Devices",
        "value": bands["6g"] + bands["6g_backhaul"],
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:wifi-star",
        "device_key": device_key,
    }

    # Total WiFi devices (excludes ethernet)
    total_wifi = (
        bands["2g"]
        + bands["2g_iot"]
        + bands["2g_guest"]
        + bands["5g"]
        + bands["5g_iptv"]
        + bands["5g_backhaul"]
        + bands["6g"]
        + bands["6g_backhaul"]
    )
    sensors[f"{prefix}_devices_wifi_total"] = {
        "name": "WiFi All Devices",
        "value": total_wifi,
        "unit": "devices",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:wifi-check",
        "device_key": device_key,
    }


class VerizonRouterSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Verizon Router sensor."""

    def __init__(
        self,
        coordinator: VerizonRouterCoordinator,
        entry: ConfigEntry,
        sensor_id: str,
        name: str,
        unit: str | None,
        device_class: str | None,
        icon: str | None,
        device_key: str,
        state_class: SensorStateClass | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_id = sensor_id
        self._device_key = device_key
        self._attr_name = name
        self._attr_unique_id = f"verizon_fios_{entry.entry_id}_{sensor_id}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_state_class = state_class

    def _get_processed_data(self) -> dict[str, dict]:
        """Return processed sensor data, populating the coordinator cache if needed.

        The coordinator invalidates processed_data each time fresh raw data
        arrives.  The first sensor to read after an update reprocesses and
        caches the result; every subsequent sensor in that cycle hits the cache.
        """
        if self.coordinator.processed_data is None and self.coordinator.data:
            self.coordinator.processed_data = _process_router_data(
                self.coordinator.data
            )
        return self.coordinator.processed_data or {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for this sensor."""
        # Get device info from coordinator data
        topology = self.coordinator.data.get("topology", {})
        router_model = self.coordinator.data.get("hardware_model", "CR1000A")
        router_name = self.coordinator.data.get("router_name", "Verizon Router")

        if self._device_key == "router":
            return DeviceInfo(
                identifiers={(DOMAIN, self._entry.entry_id)},
                name=router_name,
                manufacturer="Verizon",
                model=router_model,
                sw_version=(
                    topology.get("nodes", [{}])[0].get("sw_ver")
                    if topology and "nodes" in topology
                    else None
                ),
            )

        # Extender device
        if topology and "nodes" in topology:
            extender_index = int(self._device_key.split("_")[1])
            if len(topology["nodes"]) > extender_index:
                node = topology["nodes"][extender_index]
                return DeviceInfo(
                    identifiers={
                        (DOMAIN, f"{self._entry.entry_id}_{self._device_key}")
                    },
                    name=node.get("device_name", f"Extender {extender_index}"),
                    manufacturer="Verizon",
                    model=node.get("model_name", "CE1000A"),
                    sw_version=node.get("sw_ver"),
                    via_device=(DOMAIN, self._entry.entry_id),
                )

        # Fallback
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._device_key}")},
            name=f"Extender {self._device_key.split('_')[1]}",
            manufacturer="Verizon",
            model="CE1000A",
            via_device=(DOMAIN, self._entry.entry_id),
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        sensor_data = self._get_processed_data().get(self._sensor_id, {})
        return sensor_data.get("value")

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        sensor_data = self._get_processed_data().get(self._sensor_id, {})
        return sensor_data.get("attributes")
