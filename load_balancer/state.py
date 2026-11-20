import threading
from config import BACKEND_SERVERS

# List of all backend servers: [("127.0.0.1", 9001), ...]
servers = list(BACKEND_SERVERS)

# Counts how many clients are currently using each server: {9001: 0, 9002: 0, 9003: 0}
active_connections = {port: 0 for _, port in servers}

# Tracks if each server is healthy (True) or dead (False)
server_health = {port: True for _, port in servers}
# Counts total requests sent to each server, helpful for traffic distribution stats
total_requests = {port: 0 for _, port in servers}

state_lock = threading.Lock()


def get_healthy_servers():
    """Returns a list of (host, port) for servers that are currently healthy."""
    with state_lock:
        return [(host, port) for host, port in servers if server_health[port]]


def increment_connections(port):
    """Adds 1 when a client starts using a backend server."""
    with state_lock:
        active_connections[port] += 1
        total_requests[port] += 1


def decrement_connections(port):
    """Subtracts 1 when a client finishes and disconnects."""
    with state_lock:
        if active_connections[port] > 0:
            active_connections[port] -= 1