import argparse
import socket
import threading
import time


# function 1: simulate a single client sending one tcp request and measuring latency
def send_single_request(host, port, request_id, results, results_lock, timeout=5.0):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.settimeout(timeout)

    try:
        # start high-resolution timer before connecting
        start = time.perf_counter()
        client_socket.connect((host, port))

        # send ping request and read server reply
        client_socket.sendall(b"PING")
        data = client_socket.recv(1024)

        # if server closed without sending data, treat as dropped connection
        if not data:
            with results_lock:
                results.append((False, None, "empty response from server"))
            return

        end = time.perf_counter()
        latency_ms = (end - start) * 1000.0
        response_text = data.decode("utf-8", errors="replace").strip()

        # safely record successful request and response text
        with results_lock:
            results.append((True, latency_ms, response_text))

    except (socket.timeout, ConnectionRefusedError, ConnectionResetError, OSError) as err:
        # safely record failed or dropped connection
        with results_lock:
            results.append((False, None, str(err)))

    finally:
        # always close socket so file descriptors never leak
        client_socket.close()


# function 2: run concurrent client threads and summarize performance metrics
def run_load_test(host, port, num_connections, timeout=5.0):
    results = []
    results_lock = threading.Lock()
    threads = []

    batch_start = time.perf_counter()

    # spawn and start all concurrent worker threads
    for req_id in range(num_connections):
        thread = threading.Thread(
            target=send_single_request,
            args=(host, port, req_id, results, results_lock, timeout)
        )
        threads.append(thread)
        thread.start()

    # wait for every worker thread to complete
    for thread in threads:
        thread.join()

    batch_end = time.perf_counter()
    total_duration = batch_end - batch_start

    # calculate connection counts and drop rate
    total = len(results)
    latencies = [lat for ok, lat, _ in results if ok]
    successful = len(latencies)
    dropped = total - successful
    drop_rate = (dropped / total) * 100.0 if total > 0 else 0.0

    # calculate latency metrics only when at least one request succeeded
    if successful > 0:
        avg_latency = sum(latencies) / successful
        min_latency = min(latencies)
        max_latency = max(latencies)
    else:
        avg_latency = None
        min_latency = None
        max_latency = None

    throughput = (successful / total_duration) if total_duration > 0 else 0.0

    # print summary report
    print(f"\nLoad Test Results ({host}:{port})")
    print(f"Total: {total} | Successful: {successful} | Dropped: {dropped} | Drop Rate: {drop_rate:.2f}%")

    if successful > 0:
        print(f"Latency (ms) -> Avg: {avg_latency:.2f} ms | Min: {min_latency:.2f} ms | Max: {max_latency:.2f} ms")
    else:
        print("Latency (ms) -> N/A (0 successful connections)")

    print(f"Throughput: {throughput:.2f} requests/sec (total time: {total_duration:.3f}s)")

    return {
        "total": total,
        "successful": successful,
        "dropped": dropped,
        "drop_rate": drop_rate,
        "avg_latency_ms": avg_latency,
        "min_latency_ms": min_latency,
        "max_latency_ms": max_latency,
        "throughput_rps": throughput,
    }


# function 3: parse command line arguments and launch test
def main():
    parser = argparse.ArgumentParser(description="concurrent tcp load generator")
    parser.add_argument("--host", default="127.0.0.1", help="target server host")
    parser.add_argument("--port", type=int, default=9001, help="target server port")
    parser.add_argument("-n", "--connections", type=int, default=10, help="number of concurrent connections")
    parser.add_argument("--timeout", type=float, default=5.0, help="socket timeout in seconds")
    args = parser.parse_args()

    run_load_test(args.host, args.port, args.connections, args.timeout)


if __name__ == "__main__":
    main()