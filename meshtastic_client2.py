import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import sys
import time
import argparse


def on_receive(packet, interface):
    """Callback for received messages."""
    try:
        if "decoded" in packet and packet["decoded"].get("portnum") == "TEXT_MESSAGE_APP":
            sender = packet.get("fromId", "unknown")
            message = packet["decoded"]["text"]
            snr = packet.get("rxSnr", "N/A")
            rssi = packet.get("rxRssi", "N/A")
            print(f"\n📩 Message from {sender} (SNR: {snr}, RSSI: {rssi}):")
            print(f"   {message}")
            print("\nEnter message (or 'quit' to exit): ", end="", flush=True)
    except KeyError:
        pass


def on_connection(interface, topic=pub.AUTO_TOPIC):
    """Called when we connect to the radio."""
    node_info = interface.getMyNodeInfo()
    print(f"✅ Connected to node: {node_info['user']['longName']} ({node_info['user']['id']})")
    print(f"   Hardware: {node_info['user'].get('hwModel', 'unknown')}")


def on_disconnect(interface, topic=pub.AUTO_TOPIC):
    """Called when we disconnect from the radio."""
    print("❌ Disconnected from node.")


def send_message(interface, message, destination=None):
    """Send a text message via the mesh network."""
    if destination:
        print(f"📤 Sending to {destination}: {message}")
        interface.sendText(message, destinationId=destination)
    else:
        print(f"📤 Broadcasting: {message}")
        interface.sendText(message)


def list_nodes(interface):
    """List all known nodes in the mesh."""
    print("\n📡 Known nodes:")
    print("-" * 60)
    if interface.nodes:
        for node_id, node in interface.nodes.items():
            user = node.get("user", {})
            name = user.get("longName", "Unknown")
            short_name = user.get("shortName", "???")
            hw = user.get("hwModel", "unknown")
            last_heard = node.get("lastHeard", None)
            if last_heard:
                elapsed = int(time.time() - last_heard)
                last_str = f"{elapsed}s ago"
            else:
                last_str = "never"
            print(f"  {node_id} | {name} ({short_name}) | HW: {hw} | Last heard: {last_str}")
    else:
        print("  No nodes discovered yet.")
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(description="Meshtastic Text Client")
    parser.add_argument(
        "--port",
        type=str,
        default=None,
        help="Serial port (e.g., /dev/ttyUSB0, COM3). Auto-detects if not specified.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=None,
        help="TCP/IP hostname for network-connected node (e.g., 192.168.1.100).",
    )
    args = parser.parse_args()

    # Subscribe to message events
    pub.subscribe(on_receive, "meshtastic.receive")
    pub.subscribe(on_connection, "meshtastic.connection.established")
    pub.subscribe(on_disconnect, "meshtastic.connection.lost")

    # Connect to the device
    try:
        if args.host:
            print(f"🔌 Connecting via TCP to {args.host}...")
            import meshtastic.tcp_interface
            interface = meshtastic.tcp_interface.TCPInterface(hostname=args.host)
        else:
            port_msg = f" on {args.port}" if args.port else " (auto-detect)"
            print(f"🔌 Connecting via serial{port_msg}...")
            interface = meshtastic.serial_interface.SerialInterface(devPath=args.port)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)

    print("\nCommands:")
    print("  Type a message and press Enter to broadcast")
    print("  !dm <node_id> <message>  - Send direct message")
    print("  !nodes                   - List known nodes")
    print("  !info                    - Show current node info")
    print("  quit                     - Exit\n")

    try:
        while True:
            try:
                user_input = input("Enter message (or 'quit' to exit): ").strip()
            except EOFError:
                break

            if not user_input:
                continue

            if user_input.lower() == "quit":
                break

            if user_input.lower() == "!nodes":
                list_nodes(interface)
                continue

            if user_input.lower() == "!info":
                node_info = interface.getMyNodeInfo()
                print(f"  Node: {node_info['user']['longName']} ({node_info['user']['id']})")
                print(f"  Hardware: {node_info['user'].get('hwModel', 'unknown')}")
                continue

            if user_input.startswith("!dm "):
                parts = user_input.split(" ", 2)
                if len(parts) < 3:
                    print("⚠️  Usage: !dm <node_id> <message>")
                    continue
                dest = parts[1]
                msg = parts[2]
                send_message(interface, msg, destination=dest)
                continue

            # Default: broadcast message
            send_message(interface, user_input)

    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user.")
    finally:
        print("Closing connection...")
        interface.close()
        print("Goodbye!")


if __name__ == "__main__":
    main()
