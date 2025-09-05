# 🐍 Python Meshtastic Client

[![Python Version](https://img.shields.io/badge/python-3.x-blue.svg)](https://www.python.org/)
[![PyPI version](https://badge.fury.io/py/meshtastic.svg)](https://badge.fury.io/py/meshtastic)
[![Meshtastic](https://img.shields.io/badge/meshtastic-powered-brightgreen.svg)](https://meshtastic.org/)

A simple Python client to interact with [Meshtastic](https://meshtastic.org/) devices.

---

## 📋 Prerequisites

Before running the client, you need to ensure your user has the correct permissions to access the serial port where your Meshtastic device is connected (e.g., `/dev/ttyUSB0`).

1.  **Add user to the `dialout` group:** This group typically has ownership of serial ports.
    ```bash
    sudo usermod -a -G dialout $USER
    ```
    > **Note:** You may need to log out and log back in for this change to take effect.

2.  **Set permissions for the device (optional):** If the above doesn't work, you can temporarily change the device permissions.
    ```bash
    sudo chmod a+rw /dev/ttyUSB0
    ```

---

## 🚀 Installation

Follow these steps to set up your environment and install the necessary dependencies.

1.  **Create and activate a Python virtual environment:**
    ```bash
    python3 -m venv .
    source bin/activate
    ```

2.  **Install the `meshtastic` library from PyPI:**
    ```bash
    pip install dotenv meshtastic
    ```

---

## ▶️ Usage

With your environment set up and your device connected, run the client script:

```bash
python3 meshtastic_client.py
```

---

### 🔗 Useful Links

-   [Official Meshtastic Project Website](https://meshtastic.org/)
-   [`meshtastic` on PyPI](https://pypi.org/project/meshtastic/)
-   [Meshtastic GitHub Repository](https://github.com/meshtastic/python)
-   https://github.com/probsJustin/meshtastic_client.git
