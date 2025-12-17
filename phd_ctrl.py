import socket
import json
import time
import logging
import re


# Configuration for the PHD2 server
PHD2_HOST = 'localhost'
PHD2_PORT = 4400
TIMEOUT = 5  # seconds


def stream_json(s):
    dec = json.JSONDecoder()
    buf = ""
    while True:
        response_bytes = s.recv(128)
        buf += response_bytes.decode('utf-8')
        buf = buf.lstrip()
        try:
            obj, idx = dec.raw_decode(buf, idx=0)
            if obj is not None:
                print(obj)
                yield obj
                buf = buf[idx:]
        except json.JSONDecodeError as err:
            # logging.error(f"JSON decode error: {err}")
            continue


def send_phd2_command(command, endon, timeout=60, host=PHD2_HOST, port=PHD2_PORT):
    """
    Sends a JSON command to the PHD2 server and returns the response.
    
    Args:
        command (dict): The command to send as a Python dictionary.
        host (str): The hostname or IP address of the machine running PHD2.
        port (int): The port number of the PHD2 server.

    Returns:
        1: Completed
        -1: Err - no PHD
        -2: Err - timeout
        -3: Err - unexpected
    """
    try:
        # Create a TCP/IP socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(TIMEOUT)
            logging.info(f"Connecting to PHD2 server at {host}:{port}...")
            s.connect((host, port))
            logging.info("Connection successful.")

            # The PHD2 protocol requires messages to be terminated with a newline
            message_str = json.dumps(command) + '\n'
            message_bytes = message_str.encode('utf-8')

            logging.info(f"Sending command: {message_str.strip()}")
            s.sendall(message_bytes)

            start_time = time.time()
            
            for obj in stream_json(s):
                if time.time() - start_time > timeout:
                    return -2
                if 'Event' in obj:
                    event = obj['Event']
                    logging.info(f"Received event: {event}")
                    if event in endon:
                        return 1

    except ConnectionRefusedError:
        logging.error(f"Error: Connection refused. Is PHD2 running and is the server enabled on port {port}?")
        return -1
    except socket.timeout:
        logging.error(f"Error: Connection to PHD2 timed out after {TIMEOUT} seconds.")
        return -2
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return -3


def stop_guiding():
    """Sends the 'stop' command to PHD2."""
    logging.info("Attempting to stop guiding...")
    return send_phd2_command({"method": "stop_capture"}, endon=["GuidingStopped"])


def pause_guiding():
    """Sends the 'pause' command to PHD2."""
    logging.info("Attempting to pause guiding...")
    return send_phd2_command({"method": "loop"}, endon=["GuidingStopped", "LoopingExposures"])

def start_guiding():
    """Sends the 'guide' command to PHD2."""
    logging.info("Attempting to start guiding...")
    command = {"method": "guide", "params": {"settle": {"pixels": 1.5, "time": 8, "timeout": 40}}, "id": 42}
    while (err := send_phd2_command(command, endon=["SettleDone"])) in [-2, -3]:
        pause_guiding()
    return err


if __name__ == "__main__":
    print("--- PHD2 Guiding Control Script ---")

    # --- RESTART GUIDING ---
    err = start_guiding()
    print(err)

    time.sleep(10)

    err = pause_guiding()
    print(err)

    time.sleep(5)

    err = start_guiding()
    print(err)

