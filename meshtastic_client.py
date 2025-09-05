#!/usr/bin/env python3

import os
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
import argparse
from pubsub import pub
import readline
from meshtastic import RegionCode

# --- NEW: simple .env loader (no external dependency) ---
def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v

class MeshtasticClient:
    def __init__(self, port=None, host=None):
        self.interface = None
        self.port = port
        self.host = host
        self.current_channel = "Unnamed channel 0"
        self.connected = False

    def connect(self):
        try:
            if self.host:
                self.interface = meshtastic.tcp_interface.TCPInterface(hostname=self.host)
            else:
                self.interface = meshtastic.serial_interface.SerialInterface(devPath=self.port)
            pub.subscribe(self.on_message_received, "meshtastic.receive.data")
            pub.subscribe(self.on_connection_established, "meshtastic.connection.established")
            self.connected = True
            print("Connected to Meshtastic device")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    # --- NEW: bootstrap region from env if provided ---
    def bootstrap_region_from_env(self):
        region_code = os.getenv("MESHTASTIC_REGION")
        if not region_code:
            return
        region_code = region_code.strip()
        # Check existing region to avoid unnecessary write
        try:
            current_region_val = self.interface.localNode.radioConfig.preferences.region
            # Map numeric to name if possible
            current_region_name = None
            try:
                for name, enum_val in RegionCode.items():
                    if enum_val == current_region_val:
                        current_region_name = name
                        break
            except AttributeError:
                # Fallback if RegionCode is an Enum
                for name in RegionCode.__members__:
                    if RegionCode[name].value == current_region_val:
                        current_region_name = name
                        break
            if current_region_name == region_code:
                print(f"Region already set to {region_code}, skipping.")
                return
        except Exception:
            pass
        print(f"Bootstrapping region from env: {region_code}")
        self.set_region(region_code)

    def disconnect(self):
        if self.interface:
            self.interface.close()
            self.connected = False
            print("Disconnected from Meshtastic device")

    def on_connection_established(self, interface, topic=pub.AUTO_TOPIC):
        print(f"Connection established: {interface}")

    def on_message_received(self, packet, interface):
        try:
            if packet.get('decoded', {}).get('portnum') == 'TEXT_MESSAGE_APP':
                sender = packet.get('fromId', 'Unknown')
                message = packet.get('decoded', {}).get('text', '')
                channel_index = packet.get('channel', 0)
                channel_name = "Unknown"
                if self.interface.localNode.channels and channel_index < len(self.interface.localNode.channels):
                    channel_name = self.interface.localNode.channels[channel_index].settings.name or f"Channel {channel_index}"
                print(f"\r{' ' * (len(readline.get_line_buffer()) + 2)}\r", end='')
                print(f"Message from {sender} on channel {channel_name}: {message}")
                print(f"> {readline.get_line_buffer()}", end='', flush=True)
        except Exception as e:
            print(f"\rError processing message: {e}")
            print(f"> {readline.get_line_buffer()}", end='', flush=True)

    def send_message(self, message, channel_name="Unnamed channel 0"):
        if not self.connected:
            print("Not connected to any device")
            return False
        try:
            channel_index = None
            for ch in self.interface.localNode.channels:
                ch_name = ch.settings.name or f"Unnamed channel {ch.index}"
                if ch_name == channel_name:
                    channel_index = ch.index
                    break
            if channel_index is None:
                print(f"Channel '{channel_name}' not found")
                return False
            self.interface.sendText(message, channelIndex=channel_index)
            print(f"Message sent on channel {channel_name}: {message}")
            return True
        except Exception as e:
            print(f"Failed to send message: {e}")
            return False

    def list_channels(self):
        if not self.connected:
            print("Not connected to any device")
            return
        print("Available channels:")
        if not self.interface.localNode.channels:
            print("  No channels found.")
            return
        for ch in self.interface.localNode.channels:
            channel_name = ch.settings.name or f"Unnamed channel {ch.index}"
            print(f"  Index {ch.index}: {channel_name}")

    def add_channel(self, name, psk, uplink_enabled, downlink_enabled):
        if not self.connected:
            print("Not connected to any device")
            return
        try:
            print(f"Configuring channel '{name}'...")
            ch_index = self.interface.localNode.addChannel(name, psk.encode('utf-8'))
            ch = self.interface.localNode.channels[ch_index]
            ch.settings.uplink_enabled = uplink_enabled
            ch.settings.downlink_enabled = downlink_enabled
            self.interface.localNode.writeChannelSettings(ch_index)
            print(f"Successfully configured channel '{name}' at index {ch_index}.")
            print(f"  PSK: {'*' * len(psk)}")
            print(f"  Uplink: {'Enabled' if uplink_enabled else 'Disabled'}")
            print(f"  Downlink: {'Enabled' if downlink_enabled else 'Disabled'}")
        except Exception as e:
            print(f"Failed to add/configure channel: {e}")

    def set_region(self, region_code):
        if not self.connected:
            print("Not connected to any device")
            return
        try:
            valid_names = []
            try:
                valid_names = list(RegionCode.keys())
            except AttributeError:
                valid_names = list(RegionCode.__members__.keys())
            if region_code not in valid_names:
                print(f"Invalid region code '{region_code}'. Use 'list_regions' to see available codes.")
                return
            print(f"Setting region to {region_code}...")
            self.interface.localNode.setRegion(region_code)
            print(f"Region successfully set to {region_code}. The device may reboot.")
        except Exception as e:
            print(f"Failed to set region: {e}")

    def list_regions(self):
        print("Available region codes:")
        try:
            names = list(RegionCode.keys())
        except AttributeError:
            names = list(RegionCode.__members__.keys())
        for region_name in names:
            if region_name != "UNSET":
                print(f"  {region_name}")

def main():
    # Load environment file first
    load_env()
    parser = argparse.ArgumentParser(description='Meshtastic Serial Client')
    parser.add_argument('--port', help='Serial port for the Meshtastic device')
    parser.add_argument('--host', help='Hostname/IP for TCP connection')
    args = parser.parse_args()

    client = MeshtasticClient(port=args.port, host=args.host)

    if not client.connect():
        print("Failed to connect to Meshtastic device")
        return

    # NEW: bootstrap region if MESHTASTIC_REGION is set
    client.bootstrap_region_from_env()

    try:
        client.list_channels()
        print("\nMeshtastic Client Commands:")
        print("  send <message> - Send a message to the current channel")
        print("  set_channel <channel_name> - Set the default channel for sending messages")
        print("  add_channel <name> <psk> <uplink_on|off> <downlink_on|off> - Add/configure a channel")
        print("  list - List available channels")
        print("  set_region <region_code> - Set the device region (e.g., US, EU_868)")
        print("  list_regions - List available region codes")
        print("  exit - Exit the client")
        print(f"\nDefault channel is currently '{client.current_channel}'")
        env_region = os.getenv("MESHTASTIC_REGION")
        if env_region:
            print(f"(Region bootstrapped from env: {env_region})")
        while True:
            command = input("> ").strip()
            if command == "exit":
                break
            elif command == "list":
                client.list_channels()
            elif command == "list_regions":
                client.list_regions()
            elif command.startswith("set_channel "):
                client.current_channel = command[12:]
                print(f"Default channel set to '{client.current_channel}'")
            elif command.startswith("set_region "):
                parts = command.split()
                if len(parts) == 2:
                    region_code = parts[1]
                    client.set_region(region_code)
                else:
                    print("Usage: set_region <region_code>")
            elif command.startswith("send "):
                message = command[5:]
                client.send_message(message, client.current_channel)
            elif command.startswith("add_channel "):
                parts = command.split()
                if len(parts) == 5:
                    name, psk, uplink, downlink = parts[1], parts[2], parts[3], parts[4]
                    uplink_enabled = uplink.lower() == 'on'
                    downlink_enabled = downlink.lower() == 'on'
                    client.add_channel(name, psk, uplink_enabled, downlink_enabled)
                else:
                    print("Usage: add_channel <name> <psk> <uplink_on|off> <downlink_on|off>")
            else:
                print("Unknown command. Type 'list' for commands.")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
