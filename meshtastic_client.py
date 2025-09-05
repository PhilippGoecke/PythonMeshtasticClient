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
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                print(f"Loading {key} from {path}: {value}")
                os.environ[key] = value

class MeshtasticClient:
    def __init__(self, port=None, host=None):
        self.interface = None
        self.port = port
        self.host = host
        self.current_channel = None
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

    def current_channel(self):
        if self.current_channel is not None:
            return self.current_channel
        else:
            self.current_channel = os.getenv("CURRENT_CHANNEL_NAME", "Unnamed channel 0")
            return self.current_channel

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

    def send_message(self, message):
        if not self.connected:
            print("Not connected to any device")
            return False
        try:
            self.interface.sendText(message)
            print(f"Message sent: {message}")
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

    try:
        if client.interface.nodes:
            for n in client.interface.nodes.values():
                 if n["num"] == client.interface.myInfo.my_node_num:
                      print(f"hwModel: {n['user']['hwModel']}")

        client.list_channels()
        print("\nMeshtastic Client Commands:")
        print("  send <message> - Send a message to the current channel")
        print("  list - List available channels")
        print("  history - Show recently received messages")
        print("  exit - Exit the client")
        print(f"\nDefault channel is currently '{client.current_channel}'")

        # Keep a local log of received text messages
        received_messages = []

        # Subscribe to capture messages for history (printing already handled in client.on_message_received)
        def _log_message(packet, interface):
            try:
                if packet.get('decoded', {}).get('portnum') == 'TEXT_MESSAGE_APP':
                    sender = packet.get('fromId', 'Unknown')
                    message = packet.get('decoded', {}).get('text', '')
                    channel_index = packet.get('channel', 0)
                    channel_name = "Unknown"
                    if client.interface.localNode.channels and channel_index < len(client.interface.localNode.channels):
                        channel_name = client.interface.localNode.channels[channel_index].settings.name or f"Channel {channel_index}"
                        ts = time.strftime("%H:%M:%S")
                        received_messages.append(f"[{ts}] {channel_name} {sender}: {message}")
                        # Optional: limit history size
                        if len(received_messages) > 200:
                            received_messages.pop(0)
            except Exception as e:
                print(f"Error logging message {packet}: {e}")

        pub.subscribe(_log_message, "meshtastic.receive.data")

        while True:
            command = input("> ").strip()
            if command == "exit":
                break
            elif command == "list":
                client.list_channels()
            elif command.startswith("send "):
                message = command[5:]
                client.send_message(message)
            elif command == "history":
                if not received_messages:
                    print("No messages received yet.")
                else:
                    print("Received messages:")
                    for line in received_messages[-50:]:
                        print("  " + line)
            else:
                print("Commands: send <msg>, list, history, exit")
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
