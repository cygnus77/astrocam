import socket
import json
import time

# Configuration for the PHD2 server
PHD2_HOST = 'localhost'
PHD2_PORT = 4400
TIMEOUT = 5  # seconds

def send_phd2_command(command, endon, host=PHD2_HOST, port=PHD2_PORT):
    """
    Sends a JSON command to the PHD2 server and returns the response.
    
    Args:
        command (dict): The command to send as a Python dictionary.
        host (str): The hostname or IP address of the machine running PHD2.
        port (int): The port number of the PHD2 server.

    Returns:
        list of dict: A list of JSON responses from the server, or None on error.
    """
    try:
        # Create a TCP/IP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            print(f"Connecting to PHD2 server at {host}:{port}...")
            s.connect((host, port))
            print("Connection successful.")

            # The PHD2 protocol requires messages to be terminated with a newline
            message_str = json.dumps(command) + '\n'
            message_bytes = message_str.encode('utf-8')

            print(f"Sending command: {message_str.strip()}")
            s.sendall(message_bytes)

            while True:

                # Receive the response from the server
                response_bytes = s.recv(4096)
                response_str = response_bytes.decode('utf-8').strip()

                response_str = prev_data + response_str
                lines = response_str.split('\n')
                prev_data = lines.pop()  # Save incomplete line for next read
                
                # The server can send multiple JSON objects, so we split by newline
                responses = [json.loads(line) for line in lines if line]

                for resp in responses:
                    if 'Event' in resp and resp['Event'] in endon:
                        return

    except ConnectionRefusedError:
        print(f"Error: Connection refused. Is PHD2 running and is the server enabled on port {port}?")
        return None
    except socket.timeout:
        print(f"Error: Connection to PHD2 timed out after {TIMEOUT} seconds.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def stop_guiding():
    """Sends the 'stop' command to PHD2."""
    print("Attempting to stop guiding...")
    send_phd2_command({"method": "stop_capture"}, endon=["GuidingStopped"])

def start_guiding():
    """Sends the 'guide' command to PHD2."""
    print("Attempting to start guiding...")
    command = {"method": "guide", "params": {"settle": {"pixels": 1.5, "time": 8, "timeout": 40}}, "id": 42}
    send_phd2_command(command, endon=["SettleDone"])


if __name__ == "__main__":
    print("--- PHD2 Guiding Control Script ---")

     # --- RESTART GUIDING ---
    # start_response = start_guiding()

    stop_guiding()


