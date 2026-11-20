# Proxy listening settings
PROXY_HOST = "127.0.0.1" 
PROXY_PORT = 8080

# List of backend servers
BACKEND_SERVERS = [
    ("127.0.0.1", 9001),
    ("127.0.0.1", 9002),
    ("127.0.0.1", 9003),
]

# Default load-balancing algorithm : round_robin
DEFAULT_ALGORITHM = "round_robin"

# Max seconds to wait when connecting to a backend server
CONNECT_TIMEOUT = 2.0

# Health check settings 
HEALTH_CHECK_INTERVAL = 1.0
PROBE_TIMEOUT = 1.0
FAILURE_THRESHOLD = 2
RECOVERY_THRESHOLD = 2