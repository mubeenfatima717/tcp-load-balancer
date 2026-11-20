import argparse
import logging
import os
import socket
import threading
import time

# function 1: handle communication with a single connected client
def handle_client(client_socket, client_address, port, delay):
    try:
        # loop to handle stream data until client disconnects
        while True:
            data = client_socket.recv(1024)

            # if no data received, client or health probe closed connection
            if not data:
                break

            # optional delay to simulate slow processing
            if delay > 0:
                time.sleep(delay)

            # prepare and send ack response
            response = f"ACK from {port}".encode("utf-8")
            client_socket.sendall(response)

            logging.info(f"[{port}] Handled request from {client_address[0]}:{client_address[1]} -> sent ACK from {port}")

    except (ConnectionResetError, BrokenPipeError, OSError):
        # handle unexpected client disconnect without crashing server
        pass
    finally:
        # always close client socket to prevent resource leaks
        client_socket.close()

# function 2: main listening loop for accepting incoming connections
def start_server(host, port, delay):
    # create ipv4 tcp socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # allow immediate reuse of port after restart
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        # backlog of 128 to queue concurrent connections
        server_socket.listen(128)
        logging.info(f"Backend server listening on {host}:{port} (PID: {os.getpid()})")

        while True:
            # accept incoming connection
            client_socket, client_address = server_socket.accept()

            # spawn daemon thread so main thread never blocks
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address, port, delay),
                daemon=True
            )
            client_thread.start()

    except KeyboardInterrupt:
        logging.info(f"Shutting down backend server on port {port}...")
    finally:
        # close listening socket on exit
        server_socket.close()

# function 3: argument parsing and entry point
def main():
    parser = argparse.ArgumentParser(description="tcp backend server")
    parser.add_argument("--host", default="127.0.0.1", help="host address")
    parser.add_argument("--port", type=int, required=True, help="port number to bind")
    parser.add_argument("--delay", type=float, default=0.0, help="response delay in seconds")
    args = parser.parse_args()

    # configure log format [HH:MM:SS] [LEVEL] message
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    start_server(args.host, args.port, args.delay)

if __name__ == "__main__":
    main()