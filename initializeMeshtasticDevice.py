#!/usr/bin/env python3
"""
Initialize a Meshtastic device from environment variables.

Environment variables (all optional unless noted):
    MESHTASTIC_SERIAL             Serial port (e.g. /dev/ttyUSB0)
    MESHTASTIC_HOST               Host:port for TCP (if using Meshtastic TCP service)
    MESHTASTIC_REGION             Region code (e.g. US, EU433, EU868, CN, JP, ANZ, KR, TW, RU, IN, NZ865, TH, LORA_24, UA)
    MESHTASTIC_OWNER_LONG         Owner long name
    MESHTASTIC_OWNER_SHORT        Owner short name (max 4 chars recommended)
    MESHTASTIC_CHANNEL_NAME       Primary channel name
    MESHTASTIC_CHANNEL_PSK        Base64 or cleartext PSK (16 chars -> will be hashed). If literally "random" a random key is generated.
    MESHTASTIC_CHANNEL_INDEX      Channel index (default 0)
    MESHTASTIC_DEVICE_ROLE        Client, Router, Repeater, Tracker, Sensor, TA (if supported)
    MESHTASTIC_POSITION_BROADCAST true/false to enable position broadcast (if supported)
    MESHTASTIC_WIFI_SSID          (optional, ESP32 class devices)
    MESHTASTIC_WIFI_PSK           (optional)
    MESHTASTIC_VERBOSE            1 for debug logs

Requires: pip install meshtastic
"""

import os
import sys
import base64
import secrets
import logging
from typing import Optional

# Lazy import meshtastic to allow graceful error if not installed
try:
        import meshtastic
        from meshtastic import serial_interface, tcp_interface
        from meshtastic.protobufs import config_pb2
except ImportError as e:
        print(f"meshtastic library not installed. Run: pip install meshtastic (ImportError: {e})", file=sys.stderr)

        sys.exit(1)

def env(name: str, default: Optional[str] = None) -> Optional[str]:
        v = os.getenv(name, default)
        return v if v not in ("", None) else default

def bool_env(name: str, default: bool = False) -> bool:
        v = os.getenv(name)
        if v is None:
                return default
        return v.lower() in ("1", "true", "yes", "on")

def get_interface():
        host = env("MESHTASTIC_HOST")
        if host:
                logging.info(f"Connecting via TCP to {host}")
                return tcp_interface.TCPInterface(hostname=host)
        port = env("MESHTASTIC_SERIAL")
        logging.info(f"Connecting via Serial ({port or 'auto-discover'})")
        return serial_interface.SerialInterface(port=port)

REGION_ALIASES = {
        "US": "US",
        "EU": "EU868",
        "EU868": "EU868",
        "EU433": "EU433",
        "AU": "ANZ",
        "ANZ": "ANZ",
        "CN": "CN",
        "JP": "JP",
        "KR": "KR",
        "TW": "TW",
        "RU": "RU",
        "IN": "IN",
        "NZ865": "NZ865",
        "TH": "TH",
        "UA": "UA",
        "LORA_24": "LORA_24",
}

def normalize_region(r: Optional[str]) -> Optional[str]:
        if not r:
                return None
        r = r.upper().strip()
        return REGION_ALIASES.get(r, r)

def resolve_psk(raw: Optional[str]) -> Optional[str]:
        if not raw:
                return None
        if raw.lower() == "random":
                key = secrets.token_bytes(16)
                return base64.b64encode(key).decode()
        # If it's exactly 16 chars (likely passphrase), Meshtastic will hash internally; just return as-is.
        # If it decodes as base64 cleanly, keep it.
        try:
                base64.b64decode(raw, validate=True)
                return raw
        except Exception:
                return raw  # treat as plain text passphrase
        # Meshtastic Python API expects setChannel(psk=string)

def set_region(node, desired_region: str):
        if not desired_region:
                logging.info("No region specified, skipping region configuration")
                return
        desired_region = normalize_region(desired_region)
        if not desired_region:
                logging.warning("Region value not recognized, skipping")
                return
        try:
                current = node.getConfig().lora.region
        except Exception:
                current = None
        if current and current.name == desired_region:
                logging.info(f"Region already set to {desired_region}")
                return
        logging.info(f"Setting region to {desired_region}")
        # Shorthand dict form supported by library
        node.writeConfig(lora={"region": desired_region})

def set_owner(node, long_name: Optional[str], short_name: Optional[str]):
        if not long_name and not short_name:
                return
        logging.info(f"Setting owner long='{long_name}' short='{short_name}'")
        node.setOwner(longName=long_name, shortName=short_name)

def set_role(node, role: Optional[str]):
        if not role:
                return
        role_enum = getattr(config_pb2.Config.DeviceConfig.Role, role.upper(), None)
        if role_enum is None:
                logging.warning(f"Role '{role}' not valid, skipping")
                return
        cfg = node.getConfig()
        if cfg.device.role == role_enum:
                logging.info(f"Device role already {role}")
                return
        cfg.device.role = role_enum
        logging.info(f"Setting device role to {role}")
        node.writeConfig(device={"role": role})

def set_position_broadcast(node, enabled: bool):
        cfg = node.getConfig()
        cur = cfg.position.position_broadcast_secs
        want = 15 if enabled else 0
        if (enabled and cur > 0) or (not enabled and cur == 0):
                logging.info("Position broadcast already desired state")
                return
        # 0 disables; small positive enables
        logging.info(f"Setting position broadcast {'ON' if enabled else 'OFF'}")
        node.writeConfig(position={"position_broadcast_secs": want})

def set_wifi(node, ssid: Optional[str], psk: Optional[str]):
        if not ssid:
                return
        logging.info("Configuring Wi-Fi credentials")
        node.writeConfig(wifi={"ssid": ssid, "psk": psk or ""})

def set_channel(node, index: int, name: Optional[str], psk: Optional[str]):
        if name or psk:
                logging.info(f"Configuring channel index={index} name={name} psk={'(provided)' if psk else '(none)'}")
                node.setChannel(channelIndex=index, name=name, psk=psk)

def main():
        if bool_env("MESHTASTIC_VERBOSE"):
                logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(message)s")
        else:
                logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

        try:
                iface = get_interface()
        except Exception as e:
                logging.error(f"Failed to connect to device: {e}")
                sys.exit(2)

        node = iface.localNode

        try:
                set_owner(node, env("MESHTASTIC_OWNER_LONG"), env("MESHTASTIC_OWNER_SHORT"))
                set_region(node, env("MESHTASTIC_REGION"))
                set_role(node, env("MESHTASTIC_DEVICE_ROLE"))
                set_position_broadcast(node, bool_env("MESHTASTIC_POSITION_BROADCAST", False))
                set_wifi(node, env("MESHTASTIC_WIFI_SSID"), env("MESHTASTIC_WIFI_PSK"))

                channel_index = int(env("MESHTASTIC_CHANNEL_INDEX", "0"))
                psk = resolve_psk(env("MESHTASTIC_CHANNEL_PSK"))
                set_channel(node, channel_index, env("MESHTASTIC_CHANNEL_NAME"), psk)

                logging.info("Waiting for config to flush to device...")
                iface.waitForConfig()
                logging.info("Initialization complete.")
        except KeyboardInterrupt:
                logging.warning("Interrupted by user")
        except Exception as e:
                logging.exception(f"Initialization failed: {e}")
                sys.exit(3)
        finally:
                try:
                        iface.close()
                except Exception:
                        pass

if __name__ == "__main__":
        main()
