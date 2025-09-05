import meshtastic
import meshtastic.serial_interface
from pubsub import pub
import time
import sys

def on_receive(packet, interface):
    """Callback function called when a packet is received"""
    try:
        if packet and 'decoded' in packet and 'text' in packet['decoded']:
            sender = packet.get('fromId', 'N/A')
            message_text = packet['decoded']['text']
            print(f"Received from {sender}: {message_text}")
        else:
            print(f"Received a non-text packet: {packet}")
    except Exception as e:
        print(f"Error processing received packet: {e}")

def on_connection(interface, topic=pub.AUTO_TOPIC):
    """Callback function called when a connection is established"""
    my_node_num = interface.myInfo.my_node_num
    print(f"Connection established to node {my_node_num}.")
    print("You can now send messages.")
    # Set the channel to LongFast
    print("Setting channel to LongFast...")
    interface.localNode.set_config(lora={'modem_preset': 'LONG_FAST'})
    print("Channel set to LongFast.")

def main():
    """Main function to run the serial client"""
    interface = None
    try:
        # By default, SerialInterface will try to find the first Meshtastic device
        # You can specify a port like this: meshtastic.serial_interface.SerialInterface(port='/dev/ttyUSB0')
        print("Connecting to Meshtastic device...")
        interface = meshtastic.serial_interface.SerialInterface()

        # Subscribe to receive events
        pub.subscribe(on_receive, "meshtastic.receive")
        pub.subscribe(on_connection, "meshtastic.connection.established")

        print("Listening for messages... (Press Ctrl+C to send a message or exit)")

        # Keep the script running to listen for incoming messages
        while True:
            try:
                # The script will block here until Ctrl+C is pressed
                time.sleep(86400) # Sleep for a long time
            except KeyboardInterrupt:
                # Handle Ctrl+C to allow sending a message
                try:
                    message = input("\nEnter message to send (or type 'exit' to quit): ")
                    if message.lower() == 'exit':
                        break
                    if message:
                        print(f"Sending message: {message}")
                        interface.sendText(message)
                except EOFError:
                    # Handle Ctrl+D
                    print("\nExiting...")
                    break

    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
    finally:
        if interface:
            print("Closing serial interface.")
            interface.close()

if __name__ == "__main__":
    main()
