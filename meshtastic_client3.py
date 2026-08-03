#!/usr/bin/env python3
"""Simple Meshtastic client: send and receive text messages over USB serial.

Requires: pip install meshtastic pypubsub
"""

import sys

import meshtastic.serial_interface
from pubsub import pub


def on_receive(packet, interface):
    """Called when a packet arrives."""
    decoded = packet.get("decoded", {})
    if decoded.get("portnum") == "TEXT_MESSAGE_APP":
        sender = packet.get("fromId", "unknown")
        text = decoded.get("text", "")
        print(f"\n[RX] {sender}: {text}")
        print("> ", end="", flush=True)


def on_connection(interface, topic=pub.AUTO_TOPIC):
    """Called when we (re)connect to the radio."""
    print("[INFO] Connected to Meshtastic device")


def main():
    # Optionally pass a serial port as argument, e.g. /dev/ttyUSB0 or COM3
    dev_path = sys.argv[1] if len(sys.argv) > 1 else None

    pub.subscribe(on_receive, "meshtastic.receive")
    pub.subscribe(on_connection, "meshtastic.connection.established")

    try:
        interface = meshtastic.serial_interface.SerialInterface(devPath=dev_path)
    except Exception as e:
        print(f"[ERROR] Could not open Meshtastic device: {e}")
        sys.exit(1)

    print("Type a message and press Enter to send (broadcast).")
    print("Commands: /quit to exit, /nodes to list nodes.")

    try:
        while True:
            msg = input("> ").strip()
            if not msg:
                continue
            if msg == "/quit":
                break
            if msg == "/nodes":
                for node_id, node in (interface.nodes or {}).items():
                    name = node.get("user", {}).get("longName", "?")
                    print(f"  {node_id}: {name}")
                continue
            interface.sendText(msg)
            print("[TX] Message sent")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        interface.close()
        print("\n[INFO] Disconnected")


if __name__ == "__main__":
    main()
