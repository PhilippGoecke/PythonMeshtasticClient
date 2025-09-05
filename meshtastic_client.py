#!/usr/bin/env python3

import os
import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
import argparse
from pubsub import pub
import readline

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
            print(f"Failed to connect: {e}")
            return False

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

def main():
    load_env()
    parser = argparse.ArgumentParser(description="Meshtastic client")
    parser.add_argument("--port", help="Serial port of Meshtastic device")
    parser.add_argument("--host", help="TCP host/IP of Meshtastic device")
    args = parser.parse_args()
    client = MeshtasticClient(port=args.port, host=args.host)
    if not client.connect():
        print("Failed to connect to Meshtastic device")
        return

def main():
    if not client.connect():
        print("Failed to connect to Meshtastic device")
        return

    try:
        client.list_channels()
        print("\nMeshtastic Client Commands:")
        print("  send <message> - Send a message to the current channel")
        print("  list - List available channels")
        print("  exit - Exit the client")
        print(f"\nDefault channel is currently '{client.current_channel}'")

        while True:
            command = input("> ").strip()
            if command == "exit":
                break
            elif command == "list":
                client.list_channels()
            elif command.startswith("send "):
                message = command[5:]
                client.send_message(message, client.current_channel)
            else:
                print("Unknown command. Type 'list' for commands.")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
