from flask import Flask, jsonify, render_template_string, request
import json
import os

app = Flask(__name__)

# --- GPIO Setup ---
# Uncomment the block below when running on a real Raspberry Pi 5
from gpiozero import OutputDevice, Device
from gpiozero.pins.lgpio import LGPIOFactory

# Force a fresh pin factory so stale claims from a previous run are cleared
Device.pin_factory = LGPIOFactory()

ACTUATORS_PINS = {
    "actuator_1": OutputDevice(17, initial_value=False),
    "actuator_2": OutputDevice(27, initial_value=False),
    "actuator_3": OutputDevice(22, initial_value=False),
    "actuator_4": OutputDevice(23, initial_value=False),
}

import atexit
atexit.register(lambda: [p.close() for p in ACTUATORS_PINS.values()])

# --- Mock GPIO for development/testing off-Pi ---
# class MockPin:
#     def __init__(self, pin):
#         self.pin = pin
#         self._active = False
#     def on(self):
#         self._active = True
#         print(f"[GPIO] Pin {self.pin} → ON")
#     def off(self):
#         self._active = False
#         print(f"[GPIO] Pin {self.pin} → OFF")
#     @property
#     def is_active(self):
#         return self._active

# ACTUATORS_PINS = {
#     "actuator_1": MockPin(17),
#     "actuator_2": MockPin(27),
#     "actuator_3": MockPin(22),
#     "actuator_4": MockPin(23),
# }

ACTUATOR_LABELS = {
    "actuator_1": "Relay 1",
    "actuator_2": "Relay 2",
    "actuator_3": "Relay 3",
    "actuator_4": "Relay 4",
}

# --- Routes ---

@app.route("/")
def index():
    with open(os.path.join(os.path.dirname(__file__), "index.html")) as f:
        return f.read()

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({
        key: {
            "active": pin.is_active,
            "label": ACTUATOR_LABELS[key]
        }
        for key, pin in ACTUATORS_PINS.items()
    })

@app.route("/api/toggle/<actuator_id>", methods=["POST"])
def toggle(actuator_id):
    if actuator_id not in ACTUATORS_PINS:
        return jsonify({"error": "Unknown actuator"}), 404

    pin = ACTUATORS_PINS[actuator_id]
    if pin.is_active:
        pin.off()
    else:
        pin.on()

    return jsonify({
        "id": actuator_id,
        "active": pin.is_active,
        "label": ACTUATOR_LABELS[actuator_id]
    })

@app.route("/api/set/<actuator_id>", methods=["POST"])
def set_state(actuator_id):
    if actuator_id not in ACTUATORS_PINS:
        return jsonify({"error": "Unknown actuator"}), 404

    data = request.get_json()
    state = data.get("state", False)
    pin = ACTUATORS_PINS[actuator_id]

    if state:
        pin.on()
    else:
        pin.off()

    return jsonify({
        "id": actuator_id,
        "active": pin.is_active,
        "label": ACTUATOR_LABELS[actuator_id]
    })

@app.route("/api/all_off", methods=["POST"])
def all_off():
    for pin in ACTUATORS_PINS.values():
        pin.off()
    return jsonify({"status": "all off"})

if __name__ == "__main__":
    # host="0.0.0.0" makes it accessible on your local network
    app.run(host="0.0.0.0", port=5000, debug=True)
