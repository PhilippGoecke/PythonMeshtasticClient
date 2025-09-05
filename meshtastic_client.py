#!/usr/bin/env python3

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface
import time
import argparse
from pubsub import pub

class MeshtasticClient:
    def __init__(self, port=None, host=None):
        """Initialize the Meshtastic client."""
        self.interface = None
        self.port = port
        self.host = host
        self.connected = False

    def connect(self):
        """Connect to a Meshtastic device via serial or TCP."""
        try:
            if self.host:
                self.interface = meshtastic.tcp_interface.TCPInterface(hostname=self.host)
            else:
                self.interface = meshtastic.serial_interface.SerialInterface(devPath=self.port)
            
            # Subscribe to receive messages
            pub.subscribe(self.on_message_received, "meshtastic.receive.data")
            pub.subscribe(self.on_connection_established, "meshtastic.connection.established")
            
            self.connected = True
            print("Connected to Meshtastic device")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Disconnect from the Meshtastic device."""
        if self.interface:
            self.interface.close()
            self.connected = False
            print("Disconnected from Meshtastic device")

    def on_connection_established(self, interface, topic=pub.AUTO_TOPIC):
        """Callback when connection is established."""
        print(f"Connection established: {interface}")

    def on_message_received(self, packet, interface):
        """Callback when a message is received."""
        try:
            if packet.get('decoded', {}).get('portnum') == 'TEXT_MESSAGE_APP':
                sender = packet.get('fromId', 'Unknown')
                message = packet.get('decoded', {}).get('text', '')
                channel_index = packet.get('channel', 0)
                
                channel_name = "Unknown"
                if self.interface.localNode.channels and channel_index < len(self.interface.localNode.channels):
                    channel_name = self.interface.localNode.channels[channel_index].settings.name or f"Channel {channel_index}"

                print(f"Message from {sender} on channel {channel_name}: {message}")
        except Exception as e:
            print(f"Error processing message: {e}")

    def send_message(self, message, channel_name="LongFast"):
        """Send a message to a specific channel."""
        if not self.connected:
            print("Not connected to any device")
            return False
        
        try:
            # Find the channel index by name
            channel_index = None
            for idx, channel in enumerate(self.interface.localNode.channels):
                if channel.settings.name == channel_name:
                    channel_index = idx
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
        """List available channels on the device."""
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

def main():
    parser = argparse.ArgumentParser(description='Meshtastic Serial Client')
    parser.add_argument('--port', help='Serial port for the Meshtastic device')
    parser.add_argument('--host', help='Hostname/IP for TCP connection')
    args = parser.parse_args()
    
    client = MeshtasticClient(port=args.port, host=args.host)
    
    if not client.connect():
        print("Failed to connect to Meshtastic device")
        return
    
    try:
        client.list_channels()
        
        print("\nMeshtastic Client Commands:")
        print("  send <message> - Send a message to LongFast channel")
        print("  list - List available channels")
        print("  exit - Exit the client")
        
        while True:
            command = input("> ").strip()
            
            if command == "exit":
                break
            elif command == "list":
                client.list_channels()
            elif command.startswith("send "):
                message = command[5:]
                client.send_message(message, "LongFast")
            else:
                print("Unknown command. Available commands: send, list, exit")
                
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
