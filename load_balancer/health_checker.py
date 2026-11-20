import logging
import socket
import threading
import time


# function 1: single-server tcp handshake probe
def probe_server(ip, port, timeout):
    # create a fresh tcp ipv4 socket for every check
    probe_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe_socket.settimeout(timeout)

    try:
        # attempt tcp 3-way handshake
        probe_socket.connect((ip, port))
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        # return false cleanly if server is down, unreachable, or times out
        return False
    finally:
        # always close the probe socket so file descriptors do not leak
        probe_socket.close()


# function 2: background daemon loop to check all servers periodically
def health_check_loop(servers, server_health, state_lock, interval, timeout, stop_event=None):
    while stop_event is None or not stop_event.is_set():
        try:
            # take a quick snapshot of the server list outside the lock
            server_list = list(servers)

            for ip, port in server_list:
                # probe over network without holding the lock so proxy threads never freeze
                is_alive = probe_server(ip, port, timeout)

                # acquire lock only for the brief in-memory read and update
                with state_lock:
                    old_status = server_health.get(port)
                    server_health[port] = is_alive

                # log only when a server changes state
                if old_status is True and is_alive is False:
                    logging.warning(f"Backend server {ip}:{port} became unreachable (DOWN)")
                elif old_status is False and is_alive is True:
                    logging.info(f"Backend server {ip}:{port} is reachable again (UP)")

        except Exception as err:
            # prevent unexpected errors from killing the background daemon
            logging.error(f"Unexpected error in health_check_loop: {err}")

        # wait for the next check cycle
        if stop_event is not None:
            stop_event.wait(interval)
        else:
            time.sleep(interval)


# function 3: launch the health-checker thread in the background
def start_health_checker(servers, server_health, state_lock, interval=1.0, timeout=1.0, stop_event=None):
    checker_thread = threading.Thread(
        target=health_check_loop,
        args=(servers, server_health, state_lock, interval, timeout, stop_event),
        daemon=True
    )
    checker_thread.start()
    logging.info(f"Health-checker daemon started (interval: {interval}s, timeout: {timeout}s)")
    return checker_thread


# standalone test block
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    )

    # try reading settings from config.py if it exists, else use default values
    try:
        import config
        interval = getattr(config, "HEALTH_CHECK_INTERVAL", 1.0)
        timeout = getattr(config, "PROBE_TIMEOUT", 1.0)
        servers = getattr(config, "BACKEND_SERVERS", [("127.0.0.1", 9001), ("127.0.0.1", 9002), ("127.0.0.1", 9003)])
    except ImportError:
        interval = 1.0
        timeout = 1.0
        servers = [("127.0.0.1", 9001), ("127.0.0.1", 9002), ("127.0.0.1", 9003)]

    server_health = {port: True for _, port in servers}
    state_lock = threading.Lock()
    stop_event = threading.Event()

    start_health_checker(servers, server_health, state_lock, interval, timeout, stop_event)

    try:
        while True:
            time.sleep(2.0)
            with state_lock:
                # copy dict under lock before printing
                current_health = dict(server_health)
            print(f"Current server health: {current_health}")
    except KeyboardInterrupt:
        logging.info("Stopping standalone health-checker test...")
        stop_event.set()