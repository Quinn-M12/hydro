from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
import json
import paho.mqtt.client as mqtt
import threading

app = Flask(__name__)
socketio = SocketIO(app)

mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe("rpi/broadcast")
    else:
        print(f"Failed to connect, return code {rc}")

def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT broker")
    if rc != 0:
        print("Unexpected disconnection. Reconnecting...")
        try:
            client.reconnect()
        except Exception as e:
            print(f"Reconnection failed: {e}")

def on_message(client, userdata, message):
    global state
    payload = message.payload.decode()
    print("Received broadcast message:", payload)  # Debugging statement
    try:
        broadcast_data = json.loads(payload)
        state.update(broadcast_data)
        print("Updated state based on broadcast message:", state)  # Debugging statement
        socketio.emit('sensor_data', {
            "temp": state["temp"],
            "tds": state["tds"],
            "ph": state["ph"]
        })
    except json.JSONDecodeError:
        print("Error decoding JSON broadcast")

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message

def start_mqtt_loop():
    mqtt_client.loop_forever()

mqtt_client.connect("localhost", 1883, 60)
mqtt_thread = threading.Thread(target=start_mqtt_loop)
mqtt_thread.start()

# Initial state of the variables
state = {
    "MainFlowON": 0,
    "AuxFlowON": 0,
    "lights": [0, 0, 0, 0],
    "dosing": [0, 0, 0, 0],
    "tds": 0,
    "temp": 0,
    "ph": 0,
    "manual_control": False
}

@app.route('/')
def index():
    print("Rendering index page with state:", state)  # Debugging statement
    return render_template('index.html', state=state)

@app.route('/update', methods=['POST'])
def update():
    global state
    state["MainFlowON"] = int(request.form.get("MainFlowON", 0))
    state["AuxFlowON"] = int(request.form.get("AuxFlowON", 0))
    state["lights"] = [int(request.form.get(f"light{i}", 0)) for i in range(4)]
    state["dosing"] = [int(request.form.get(f"dosing{i}", 0)) for i in range(4)]
    state["tds"] = float(request.form.get("tds", 0))
    state["temp"] = float(request.form.get("temp", 0))
    state["ph"] = float(request.form.get("ph", 0))
    state["manual_control"] = request.form.get("manual_control") == "on"

    print("Sending command message:", state)  # Debugging statement
    result = mqtt_client.publish("rpi/commands", json.dumps(state))

    # Check if the message was published successfully
    status = result.rc
    if status == 0:
        print(f"Message sent to topic rpi/commands")
    else:
        print(f"Failed to send message to topic rpi/commands, return code {status}")

    return redirect(url_for('index'))

@socketio.on('request_initial_data')
def handle_initial_data_request():
    emit('sensor_data', {
        "temp": state["temp"],
        "tds": state["tds"],
        "ph": state["ph"]
    })

if __name__ == '__main__':
    print("Starting Flask app...")  # Debugging statement
    socketio.run(app, host='0.0.0.0', port=5000)