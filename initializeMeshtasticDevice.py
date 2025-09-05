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
from dotenv import load_dotenv
import subprocess

# Load environment variables
load_dotenv()

# Lazy import meshtastic to allow graceful error if not installed
try:
        import meshtastic
        from meshtastic import serial_interface, tcp_interface
        try:
                from meshtastic.protobufs import config_pb2  # newer package layout
        except ImportError:
                from meshtastic import config_pb2  # older package layout
except ImportError as e:
        print(f"meshtastic library not installed. Run: pip install meshtastic (ImportError: {e})", file=sys.stderr)

        sys.exit(1)

def env(name: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable or default if unset or empty"""
        value = os.getenv(name, default)
        print(f"loading env(name: {name}, default: {default}) -> '{value}'")
        return value if value not in ("", None) else default

def bool_env(name: str, default: bool = False) -> bool:
        value = env(name)
        if value is None:
                return default
        return value.lower() in ("1", "true", "yes", "on")

def get_interface():
        host = env("MESHTASTIC_HOST")

        if host:
                logging.info(f"Connecting via TCP to {host}")
                return tcp_interface.TCPInterface(hostname=host)

        port = env("MESHTASTIC_SERIAL")

        logging.info(f"Connecting via Serial ({port or 'auto-discover'})")

        return serial_interface.SerialInterface(devPath=port)

def get_config(node):
        """
        Compatibility helper: some versions expose getConfig on the node, others only on the interface.
        """
        if hasattr(node, "getConfig"):
            return node.getConfig()
        iface = getattr(node, "iface", None) or getattr(node, "interface", None)
        if iface and hasattr(iface, "getConfig"):
            return iface.getConfig()
        raise AttributeError("Neither node nor its interface provides getConfig()")

def write_config(node, **sections):
        """
        Compatibility helper mirroring writeConfig similarly.
        """
        print(f"write_config(node: {node}, sections: {list(sections.keys())}")

        if hasattr(node, "writeConfig"):
            return node.writeConfig(**sections)

        iface = getattr(node, "iface", None) or getattr(node, "interface", None)
        if hasattr(iface, "localNode"):
            return iface.localNode.setOwner(long_name, short_name)

def set_owner(node, long_name: Optional[str], short_name: Optional[str]):
        if long_name is None and short_name is None:
            logging.info("No owner specified, skipping owner configuration")
            return

        logging.info(f"Setting owner to {long_name} ({short_name})")
        iface = getattr(node, "iface", None) or getattr(node, "interface", None)
        if iface and hasattr(iface, "localNode"):
            return iface.localNode.setOwner(long_name, short_name)

def set_region(node, desired_region: str):
    if not desired_region:
        logging.info("No region specified; skipping region configuration")
        return

    logging.info(f"Setting region via CLI to {desired_region}")
    try:
        result = subprocess.run(
        ["meshtastic", "--set", "lora.region", desired_region],
        capture_output=True,
        text=True
        )
        if result.returncode != 0:
            logging.error(f"Failed to set region (exit {result.returncode}): {result.stderr.strip()}")
        else:
            logging.info(f"Region set output: {result.stdout.strip() or 'success'}")
    except FileNotFoundError:
        logging.error("meshtastic CLI not found in PATH; cannot set region")
    except Exception as e:
        logging.exception(f"Unexpected error setting region: {e}")

def set_role(node, desired_role: Optional[str]):
    if not desired_role:
        return

    valid_roles = {"CLIENT", "CLIENT_MUTE", "ROUTER", "REPEATER", "TRACKER", "SENSOR"}
    if desired_role not in valid_roles:
        logging.error(f"Invalid role '{desired_role}'. Valid roles: {', '.join(sorted(valid_roles))}")
        return

    logging.info(f"Setting role via CLI to {desired_role}")
    try:
        result = subprocess.run(
        ["meshtastic", "--set", "device.role", desired_role],
        capture_output=True,
        text=True
        )
        if result.returncode != 0:
            logging.error(f"Failed to set role (exit {result.returncode}): {result.stderr.strip()}")
        else:
            logging.info(f"Role set output: {result.stdout.strip() or 'success'}")
    except FileNotFoundError:
        logging.error("meshtastic CLI not found in PATH; cannot set role")
    except Exception as e:
        logging.exception(f"Unexpected error setting role: {e}")

def set_position_broadcast(node, enabled: bool):
    # Configure smart position broadcast flag via CLI
    logging.info(f"Setting position broadcast {'ON' if enabled else 'OFF'}")
    try:
        result = subprocess.run(
        ["meshtastic", "--set", "position.position_broadcast_smart_enabled", enabled],
        capture_output=True,
        text=True
        )
        if result.returncode != 0:
            logging.error(f"Failed to set position.position_broadcast_smart_enabled={enabled}: {result.stderr.strip()}")
        else:
            logging.info(f"Set position.position_broadcast_smart_enabled={enabled}: {result.stdout.strip() or 'success'}")
    except FileNotFoundError:
        logging.error("meshtastic CLI not found; cannot set position.position_broadcast_smart_enabled")
    except Exception as e:
        logging.exception(f"Error setting position.position_broadcast_smart_enabled: {e}")

def set_wifi(node, ssid: Optional[str], psk: Optional[str]):
    if not ssid:
        logging.info("No Wi-Fi SSID provided; disabling Wi-Fi configuration")
        try:
            cmd = [
                "meshtastic", "--set", "network.wifi_enabled", "false",
            ]

            return subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            logging.exception(f"Error disabling Wi-Fi: {e}")

    logging.info(f"Configuring Wi-Fi SSID={ssid} psk={'(provided)' if psk else '(none)'}")
    try:
        cmd = [
            "meshtastic",
            "--set", "network.wifi_enabled", "true",
            "--set", "network.wifi_ssid", ssid,
        ]
        if psk:
            cmd += ["--set", "network.wifi_psk", psk]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Failed to configure Wi-Fi (exit {result.returncode}): {result.stderr.strip()}")
        else:
            logging.info(f"Wi-Fi configured: {result.stdout.strip() or 'success'}")
    except FileNotFoundError:
        logging.error("meshtastic CLI not found; cannot configure Wi-Fi")
    except Exception as e:
        logging.exception(f"Error configuring Wi-Fi: {e}")

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

        # iface = meshtastic.serial_interface.SerialInterface()
        if iface.nodes:
            for n in iface.nodes.values():
                 if n["num"] == iface.myInfo.my_node_num:
                      print(f"hwModel: {n['user']['hwModel']}")

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
