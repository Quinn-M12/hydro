import json
import paho.mqtt.client as mqtt
import time
from datetime import datetime

client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to MQTT broker")
        client.subscribe("rpi/commands")
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

client.on_connect = on_connect
client.on_disconnect = on_disconnect

client.connect("localhost", 1883, 60)

MainFlowON = 0
AuxFlowON = 0
lights = [0, 0, 0, 0]   # Initial state for lights (4 lights)
dosing = [0, 0, 0, 0]   # Initial state for dosing pumps (4 dosing pumps)

tds = None
temp = None
ph = None

previous_state = {
    "MainFlowON": MainFlowON,
    "AuxFlowON": AuxFlowON,
    "lights": lights.copy(),
    "dosing": dosing.copy(),
    "tds": tds,
    "temp": temp,
    "ph": ph,
}

# Store the last time the loop ran
last_loop_time = time.time()

last_dosing1_on_time = 0  # Track the last time dosing pump 1 was turned on
dosing1_active = False    # Track if dosing pump 1 is currently active

last_main_pump_off_time = 0
nutrient_dosing_done = True

# Counter to control the aux pump 75% of the time
aux_cycle_counter = 0

# Manual control flag
manual_control = False

# Store the last time an update was published
last_publish_time = time.time()

def publish_if_changed():
    global previous_state, last_publish_time
    current_state = {
        "MainFlowON": MainFlowON,
        "AuxFlowON": AuxFlowON,
        "lights": lights.copy(),
        "dosing": dosing.copy(),
        "tds": tds,
        "temp": temp,
        "ph": ph,
    }
    current_time = time.time()
    if current_state != previous_state or (current_time - last_publish_time) >= 60:
        print(f"State changed or timeout reached. Publishing: {current_state}")  # Debugging statement
        client.publish("rpi/broadcast", json.dumps(current_state))
        previous_state = current_state
        last_publish_time = current_time

def controlMainPump():
    global MainFlowON, last_main_pump_off_time, nutrient_dosing_done
    
    # Get the current time
    current_time = datetime.now()
    current_minute = current_time.minute
    
    # Control the main flow for the first 10 minutes of each hour
    if 0 <= current_minute < 10:
        MainFlowON = 1
    else:
        if MainFlowON == 1:  # If the pump was ON and now turning OFF
            last_main_pump_off_time = time.time()  # Record the off time
            nutrient_dosing_done = False  # Reset nutrient dosing flag for the next cycle

    MainFlowON = 0


def controlShittyAuxPump():
    global AuxFlowON
    global aux_cycle_counter
    
    AuxFlowON = 0


def controlLights():
    global lights, light_index, direction
    
    # Get the current time
    current_time = datetime.now()
    current_minute = current_time.minute
    current_hour = current_time.hour
    
    # Control lights based on time
    if 5 <= current_hour <= 23:
        for i in range(4):
            lights[i] = 1
    else:
        for i in range(4):
            lights[i] = 0


def controlDosing():
    global dosing, previous_dosing, tds, last_dosing1_on_time, dosing1_active, nutrient_dosing_done, last_main_pump_off_time
    current_time = time.time()  # Get the current time as seconds since epoch
    
    # Control fresh water pump (Pump 0)
    if tds is not None and tds < 90:
        dosing[0] = 1
    else:
        dosing[0] = 0

    # Control nutrient pump (Pump 1)
    if not nutrient_dosing_done and MainFlowON == 0 and (current_time - last_main_pump_off_time) >= 300 and tds < 700:  # 5 minutes
        if not dosing1_active:
            # Turn on the pump for 2 seconds
            dosing[1] = 1
            dosing1_active = True
            last_dosing1_on_time = current_time
            print(current_time)
        elif dosing1_active and (current_time - last_dosing1_on_time >= 1):  # Change 30 to 2 for 2 seconds
            # Turn off the pump after 2 seconds
            dosing[1] = 0
            dosing1_active = False
            nutrient_dosing_done = True  # Mark nutrient dosing as completed for this cycle
            print(current_time)
    
    dosing[1] = 0  # If Pump 1 has no active logic, keep it off
    dosing[0] = 0


def read_shared_file():
    try:
        with open("shared_data.json", "r") as file:
            data = json.load(file)
            temperature = data.get("temperature")
            tds = data.get("TDS")
            ph = data.get("PH")
            return temperature, tds, ph
    except FileNotFoundError:
        print("File not found. Using default values.")
        return None, None, None
    except json.JSONDecodeError:
        print("Invalid JSON in shared file. Using default values.")
        return None, None, None

def on_command_message(client, userdata, message):
    global MainFlowON, AuxFlowON, lights, dosing, tds, temp, ph, manual_control
    payload = message.payload.decode()
    print("Received command message:", payload)  # Debugging statement
    try:
        command_data = json.loads(payload)
        MainFlowON = command_data.get("MainFlowON", MainFlowON)
        AuxFlowON = command_data.get("AuxFlowON", AuxFlowON)
        lights = command_data.get("lights", lights)
        dosing = command_data.get("dosing", dosing)
        tds = command_data.get("tds", tds)
        temp = command_data.get("temp", temp)
        ph = command_data.get("ph", ph)
        manual_control = command_data.get("manual_control", manual_control)
        print("Updated variables based on command message:", command_data)  # Debugging statement

    except json.JSONDecodeError:
        print("Error decoding JSON command")

client.message_callback_add("rpi/commands", on_command_message)

print("Starting main loop...")  # Debugging statement
while True:
    # Get the current time
    current_time = time.time()

    if not manual_control:
        controlMainPump()
        controlShittyAuxPump()
        controlLights()
        controlDosing()

    publish_if_changed()

     # Read sensor data from the shared file periodically
    if current_time - last_loop_time >= 1:  # Adjust the interval as needed
        temp, tds, ph = read_shared_file()
        last_loop_time = current_time
    
    # Perform other non-blocking tasks here if necessary
    # Example: Check MQTT client loop for messages
    client.loop(timeout=0.01)  # Adjust timeout as needed
