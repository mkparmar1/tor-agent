# Tor Traffic Generation Script

This Python script generates simulated website traffic by sending requests to a specified URL using the **Tor network**. The requests are routed through **random IP addresses** and **user-agents** to mimic real human traffic. It is built to be **anonymous** and **undetectable** through the Tor network.

## Features

- **Dynamic User-Agent**: Generates random user-agents using the `fake_useragent` library. If the dynamic user-agent fails, it falls back to a **static user-agent**.
- **Tor IP Rotation**: Changes IP addresses with every request using the **Tor network** (via **SOCKS5 proxy** and **ControlPort**).
- **Concurrency**: Supports concurrent requests to simulate high website traffic.
- **Logging**: Logs every request with its status, user-agent, IP address, and response time to a JSON log file.

---

## Concept Overview

The goal of this project is to simulate website traffic by mimicking legitimate user behavior, such as randomizing **user-agents** and **IP addresses**. The traffic is routed through the **Tor network** for anonymity, ensuring that the origin of the traffic is difficult to trace.

Here’s how the process works step-by-step:

1. **Tor Network Setup**: The script uses the **Tor network** to route HTTP requests through random IP addresses. Each request uses a new IP, making it harder for the target website to detect the source of the traffic.
2. **IP Rotation**: Tor's **ControlPort** allows us to signal Tor to change its IP address using the `NEWNYM` command. This ensures each request comes from a unique IP.

3. **User-Agent Randomization**: The script generates random **user-agents** using the `fake_useragent` library. This simulates traffic from different browsers and devices. If it fails to generate a random user-agent, the script falls back to a **static user-agent** to ensure compatibility.

4. **Concurrency**: Using **multi-threading**, the script can generate multiple concurrent requests to simulate heavy website traffic.

5. **Logging**: Every request is logged in a **JSON format** with detailed information, such as the **status**, **user-agent**, **IP address**, **timestamp**, and **response time**.

---

## Prerequisites

### 1. **Install Python**

This script works with Python 3.8 and later. Make sure you have **Python 3.8+** installed on your system.

- Install Python from [here](https://www.python.org/downloads/).

### 2. **Install Required Libraries**

This script requires the following libraries:

- `requests[socks]`: For making HTTP requests through the SOCKS proxy (Tor).
- `stem`: To control the Tor process and change IP addresses.
- `fake_useragent`: To generate random user-agent strings.

You can install them using the following command:

```bash
pip install requests[socks] stem fake-useragent
```
