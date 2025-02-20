import socks
import socket
from stem import Signal
from stem.control import Controller
import requests
from random_user_agent.user_agent import UserAgent
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

# Add this at the top with other global variables
request_id_lock = threading.Lock()
global_request_id = 0

def get_next_request_id():
    """Thread-safe way to get the next request ID."""
    global global_request_id
    with request_id_lock:
        global_request_id += 1
        return global_request_id

def verify_ip_changed(session, previous_ip):
    """Verify that the IP has actually changed with retries."""
    max_verify_attempts = 3
    verify_wait = 2
    
    for attempt in range(max_verify_attempts):
        try:
            # Create a new session for each verification attempt
            if attempt > 0:
                session.close()
                session = get_session()
            
            current_ip = session.get('http://httpbin.org/ip', timeout=10).json()['origin']
            
            if current_ip != previous_ip:
                return True, current_ip
                
            logging.warning(f"IP hasn't changed (attempt {attempt + 1}/{max_verify_attempts}): {current_ip}")
            time.sleep(verify_wait)
            
        except Exception as e:
            logging.error(f"Error verifying IP change (attempt {attempt + 1}/{max_verify_attempts}): {e}")
            time.sleep(verify_wait)
    
    return False, None

def change_ip():
    """Signal Tor to change the IP with verification and proper timing."""
    max_attempts = 3
    controller = None
    
    for attempt in range(max_attempts):
        try:
            # Close any existing controller connection
            if controller:
                try:
                    controller.close()
                except:
                    pass
            
            # Create a new controller connection
            controller = Controller.from_port(port=TOR_CONTROL_PORT)
            
            # Check if controller is authenticated
            if not controller.is_authenticated():
                controller.authenticate(password=TOR_PASSWORD)
            
            # Check how long ago the last IP change was requested
            if hasattr(change_ip, 'last_change'):
                time_since_change = time.time() - change_ip.last_change
                if time_since_change < 10:
                    time.sleep(10 - time_since_change)
            
            # Send NEWNYM signal and wait for confirmation
            if controller.is_newnym_available():
                controller.signal(Signal.NEWNYM)
                change_ip.last_change = time.time()
                
                # Wait for the new circuit to be established
                time.sleep(controller.get_newnym_wait())
                
                return True
            else:
                wait_time = controller.get_newnym_wait()
                logging.warning(f"Waiting {wait_time} seconds for new circuit to become available")
                time.sleep(wait_time)
                continue
                
        except Exception as e:
            logging.error(json.dumps({
                'error': f"Tor IP change failed (attempt {attempt + 1}/{max_attempts}): {str(e)}"
            }))
            if attempt < max_attempts - 1:
                time.sleep(5)  # Longer wait between retries
        finally:
            # Always close the controller in the finally block
            if controller:
                try:
                    controller.close()
                except:
                    pass
    
    return False

# Initialize the last change time
change_ip.last_change = 0

def get_session():
    """Create a new requests session using the Tor proxy."""
    session = requests.Session()
    session.proxies = {
        'http': f'socks5h://{TOR_PROXY}:{TOR_PORT}',
        'https': f'socks5h://{TOR_PROXY}:{TOR_PORT}'
    }
    # Set longer timeouts
    session.timeout = 30
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
    previous_ip = None
    while not request_queue.empty():
        url = request_queue.get()
        session = None
        try:
            request_id = get_next_request_id()
            
            # Create new session for each request
            session = get_session()

            # Attempt to change IP and verify it's different
            max_ip_change_attempts = 3
            ip_changed = False
            
            for attempt in range(max_ip_change_attempts):
                if not change_ip():
                    time.sleep(5)  # Wait before retry
                    continue
                
                ip_changed, current_ip = verify_ip_changed(session, previous_ip)
                if ip_changed:
                    previous_ip = current_ip
                    logging.info(f"Successfully changed IP to: {current_ip}")
                    break
                
                session.close()
                session = get_session()
                time.sleep(2)  # Wait before next attempt
            
            if not ip_changed:
                log_request(
                    request_id, 'skipped', url, None, None,
                    time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time())),
                    None, None
                )
                logging.warning(f"Failed to get new IP after {max_ip_change_attempts} attempts")
                continue

            # Generate a random User-Agent
            try:
                ua = UserAgent()
                user_agent = ua.get_random_user_agent()
            except Exception as e:
                logging.warning(f"Error generating random User-Agent: {e}")
                user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

            headers = {'User-Agent': user_agent}

            # Send the request
            request_start_time = time.time()
            response = session.get(url, headers=headers, timeout=10)
            request_end_time = time.time()
            response_time = round(request_end_time - request_start_time, 2)

            # Log the result
            if response.status_code == 200:
                log_request(
                    request_id, 'success', url, user_agent, current_ip,
                    time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(request_start_time)),
                    response.status_code, response_time
                )
                print(f"[SUCCESS] {url} visited with IP: {current_ip}")
            else:
                log_request(
                    request_id, 'failed', url, user_agent, current_ip,
                    time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(request_start_time)),
                    response.status_code, response_time
                )
                print(f"[ERROR] Failed to visit {url} (Status: {response.status_code})")

        except requests.exceptions.RequestException as e:
            logging.error(f"Request error: {e}")
            log_request(
                request_id, 'exception', url, user_agent if 'user_agent' in locals() else None,
                None, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time())),
                None, None
            )
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            log_request(
                request_id, 'exception', url, user_agent if 'user_agent' in locals() else None,
                None, time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(time.time())),
                None, None
            )
        finally:
            if session:
                session.close()
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
