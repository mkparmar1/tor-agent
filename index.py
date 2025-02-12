import socks
import socket
from stem import Signal
from stem.control import Controller
import requests
from fake_useragent import UserAgent
import threading
import queue
import time
import json
import logging


# Configure logging to print in JSON format
logging.basicConfig(filename='traffic_log.json', level=logging.INFO)

# Configure the Tor proxy and connection settings
TOR_PROXY = "127.0.0.1"
TOR_PORT = 9050
TOR_CONTROL_PORT = 9051
TOR_PASSWORD = "password12@12@12"  # Set this in your Tor config

# Create a queue for requests
request_queue = queue.Queue()

# Set a timeout for the Tor connection
TOR_CONNECTION_TIMEOUT = 30  # seconds

def change_ip():
    """Signal Tor to change the IP. If not connected in 30s, skip the request."""
    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            controller.authenticate(password=TOR_PASSWORD)
            controller.signal(Signal.NEWNYM)
            time.sleep(2)  # Allow time for the IP change to take effect
    except Exception as e:
        logging.error(json.dumps({
            'error': f"Tor IP change failed: {e}"
        }))
        return False  # Return False if Tor connection fails
    return True  # Return True if Tor connection succeeds

def get_session():
    """Create a new requests session using the Tor proxy."""
    session = requests.Session()
    session.proxies = {
        'http': f'socks5h://{TOR_PROXY}:{TOR_PORT}',
        'https': f'socks5h://{TOR_PROXY}:{TOR_PORT}'
    }
    return session

def log_request(request_id, status, url, user_agent, ip, request_time, status_code, response_time):
    """Log the request details in JSON format."""
    log_entry = {
        'request_id': request_id,
        'status': status,
        'url': url,
        'user_agent': user_agent,
        'ip': ip,
        'timestamp': request_time,
        'status_code': status_code,
        'response_time': response_time
    }
    logging.info(json.dumps(log_entry))

def worker():
    """Thread worker that processes requests from the queue."""
    request_id = 1  # Start request ID from 1 and increment
    while not request_queue.empty():
        url = request_queue.get()
        try:
            # Attempt to change IP via Tor with a timeout mechanism
            start_time = time.time()
            if not change_ip():
                log_request(
                    request_id, 'skipped', url, None, None, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(start_time)), None, None
                )
                request_id += 1  # Increment the request ID
                continue  # Skip to the next URL if Tor connection fails

            session = get_session()

            # Generate a random User-Agent for the request
            try:
                ua = UserAgent(use_cache_server=True)  # Set to use the cache server
                user_agent = ua.random  # Try to get a random user-agent
                print(f"Generated User-Agent: {user_agent}")
            except Exception as e:
                print(f"Error generating random User-Agent: {e}")
                # Fall back to a static user-agent if the random one fails
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                print(f"Using static User-Agent: {user_agent}")

            # Use the generated or static user-agent in the headers
            headers = {'User-Agent': user_agent}

            # Send the request
            request_start_time = time.time()
            response = session.get(url, headers=headers, timeout=10)
            request_end_time = time.time()

            ip = session.get('http://httpbin.org/ip').json()['origin']
            response_time = round(request_end_time - request_start_time, 2)

            # Log the result
            if response.status_code == 200:
                log_request(
                    request_id, 'success', url, user_agent, ip, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(request_start_time)),
                    response.status_code, response_time
                )
                print(f"[SUCCESS] {url} visited with IP: {ip}")
            else:
                log_request(
                    request_id, 'failed', url, user_agent, ip, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(request_start_time)),
                    response.status_code, response_time
                )
                print(f"[ERROR] Failed to visit {url} (Status: {response.status_code})")

        except Exception as e:
            # If an exception occurs, log the details
            log_request(
                request_id, 'exception', url, user_agent, None, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time())),
                None, None
            )
            print(f"[EXCEPTION] {e}")
        
        finally:
            # Increment the request ID for the next request
            request_id += 1
            # Mark the task as done
            request_queue.task_done()

if __name__ == "__main__":
    url = input("Enter the URL to generate traffic: ")
    num_requests = int(input("Enter the number of requests to simulate: "))

    # Populate the queue with requests
    for _ in range(num_requests):
        request_queue.put(url)
    
    # Create and start worker threads
    num_threads = 5  # Number of concurrent threads
    threads = []
    for _ in range(num_threads):
        thread = threading.Thread(target=worker)
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All requests have been processed.")
