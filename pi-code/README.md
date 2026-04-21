# Pi Actuator Control Panel

A lightweight Flask webserver for Raspberry Pi 5 that lets you toggle GPIO actuators from any browser on your network.

---

## Files

```
app.py        — Flask backend + GPIO logic
index.html    — Control panel UI (served by Flask)
requirements.txt
```

---

## Install & Run

### 1. Install dependencies

```bash
pip install flask gpiozero
```

### 2. Put files on your Pi

Copy `app.py` and `index.html` into the same folder, e.g. `/home/pi/control/`

### 3. Enable real GPIO

In `app.py`, comment out the **Mock GPIO** block and uncomment the **GPIO Setup** block at the top:

```python
from gpiozero import OutputDevice

ACTUATORS_PINS = {
    "actuator_1": OutputDevice(17),
    "actuator_2": OutputDevice(27),
    "actuator_3": OutputDevice(22),
    "actuator_4": OutputDevice(23),
}
```

Adjust the pin numbers to match your wiring.

### 4. Run

```bash
python app.py
```

Server starts on `0.0.0.0:5000` — accessible from any device on your local network.

### 5. Open in browser

```
http://raspberrypi.local:5000
```

Or use the Pi's IP address:

```
http://192.168.x.x:5000
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/status` | Get state of all actuators |
| POST | `/api/toggle/<id>` | Toggle one actuator |
| POST | `/api/set/<id>` | Set state `{"state": true/false}` |
| POST | `/api/all_off` | Turn everything off |

---

## Customize

**Add more actuators** — extend both dicts in `app.py`:

```python
ACTUATORS_PINS = {
    ...
    "actuator_5": OutputDevice(24),
}
ACTUATOR_LABELS = {
    ...
    "actuator_5": "Pump",
}
```

**Auto-start on boot** — create `/etc/systemd/system/control-panel.service`:

```ini
[Unit]
Description=GPIO Control Panel
After=network.target

[Service]
ExecStart=/usr/bin/python3 /home/pi/control/app.py
WorkingDirectory=/home/pi/control
Restart=always
User=pi

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl enable control-panel
sudo systemctl start control-panel
```

---

## GPIO Pinout Reference (Pi 5)

```
Pin 17 → actuator_1
Pin 27 → actuator_2
Pin 22 → actuator_3
Pin 23 → actuator_4
```

Use a relay module between the Pi GPIO and your actual actuators — never connect high-current loads directly to GPIO pins!
