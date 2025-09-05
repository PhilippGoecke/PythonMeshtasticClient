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
        self.current_channel = "Unnamed channel 0"
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

    def send_message(self, message, channel_name="Unnamed channel 0"):
        """Send a message to a specific channel."""
        if not self.connected:
            print("Not connected to any device")
            return False
        
        try:
            # Find the channel index by name
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

    def add_channel(self, name, psk, uplink_enabled, downlink_enabled):
        """Add or update a channel with the given settings."""
        if not self.connected:
            print("Not connected to any device")
            return

        try:
            print(f"Configuring channel '{name}'...")
            # The addChannel method finds an empty slot and configures it
            ch_index = self.interface.localNode.addChannel(name, psk.encode('utf-8'))
            
            # Now set the additional properties
            ch = self.interface.localNode.channels[ch_index]
            ch.settings.uplink_enabled = uplink_enabled
            ch.settings.downlink_enabled = downlink_enabled
            
            # Write the updated settings to the device
            self.interface.localNode.writeChannelSettings(ch_index)
            
            print(f"Successfully configured channel '{name}' at index {ch_index}.")
            print(f"  PSK: {'*' * len(psk)}")
            print(f"  Uplink: {'Enabled' if uplink_enabled else 'Disabled'}")
            print(f"  Downlink: {'Enabled' if downlink_enabled else 'Disabled'}")
            
        except Exception as e:
            print(f"Failed to add/configure channel: {e}")

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
        print("  send <message> - Send a message to the current channel")
        print("  set_channel <channel_name> - Set the default channel for sending messages")
        print("  add_channel <name> <psk> <uplink_on|off> <downlink_on|off> - Add/configure a channel")
        print("  list - List available channels")
        print("  exit - Exit the client")
        print(f"\nDefault channel is currently '{client.current_channel}'")
        
        while True:
            command = input("> ").strip()
            
            if command == "exit":
                break
            elif command == "list":
                client.list_channels()
            elif command.startswith("set_channel "):
                client.current_channel = command[12:]
                print(f"Default channel set to '{client.current_channel}'")
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
