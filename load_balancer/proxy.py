import logging
import socket
import threading

from config import CONNECT_TIMEOUT, PROXY_HOST, PROXY_PORT
from load_balancer import state


def forward_bytes(source, destination, half_close=False):
    """Continuously copy raw bytes from source socket to destination socket."""
    try:
        while True:
            data = source.recv(4096)
            if not data:
                # Source finished sending cleanly
                if half_close:
                    try:
                        destination.shutdown(socket.SHUT_WR)
                    except OSError:
                        pass
                break
            destination.sendall(data)
    except OSError:
        # Connection reset or closed unexpectedly; close destination so other thread exits
        try:
            destination.close()
        except OSError:
            pass
    finally:
        if not half_close:
            try:
                destination.close()
            except OSError:
                pass


def handle_client(client_socket, client_address):
    """Handle one client session: pick a backend, connect, forward both ways, clean up."""
    backend_socket = None
    connected_port = None

    try:
        
        healthy_servers = state.get_healthy_servers()
        if not healthy_servers:
            logging.error("No healthy backend servers available. Closing client.")
            return

        backend_host, backend_port = healthy_servers[0]

        # Open a TCP connection to the backend server with a timeout
        backend_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        backend_socket.settimeout(CONNECT_TIMEOUT)
        backend_socket.connect((backend_host, backend_port))
        backend_socket.settimeout(None)  # Normal mode after connecting

        # Record the active connection in shared state
        state.increment_connections(backend_port)
        connected_port = backend_port

        logging.info(
            f"Routed client {client_address[0]}:{client_address[1]} -> {backend_host}:{backend_port}"
        )

        # Two threads: one sends client -> backend, the other sends backend -> client
        t_client_to_backend = threading.Thread(
            target=forward_bytes,
            args=(client_socket, backend_socket, True),
            daemon=True,
        )
        t_backend_to_client = threading.Thread(
            target=forward_bytes,
            args=(backend_socket, client_socket, False),
            daemon=True,
        )

        t_client_to_backend.start()
        t_backend_to_client.start()
        t_client_to_backend.join()
        t_backend_to_client.join()

    except (OSError, socket.timeout) as err:
        logging.error(
            f"Connection failed for client {client_address[0]}:{client_address[1]}: {err}"
        )
    finally:
        #always decrement count and close both sockets
        if connected_port is not None:
            state.decrement_connections(connected_port)
        if backend_socket is not None:
            try:
                backend_socket.close()
            except OSError:
                pass
        try:
            client_socket.close()
        except OSError:
            pass


def start_proxy():
    """Start the main TCP listening socket on port 8080."""
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((PROXY_HOST, PROXY_PORT))
        server_socket.listen(128)
        logging.info(f"Load Balancer listening on {PROXY_HOST}:{PROXY_PORT}")

        while True:
            client_socket, client_address = server_socket.accept()
            # Spawn a new thread for each client so multiple clients work at the same time
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=True,
            )
            client_thread.start()

    except KeyboardInterrupt:
        logging.info("Shutting down Load Balancer...")
    finally:
        server_socket.close()


if __name__ == "__main__":
    start_proxy()