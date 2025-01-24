import json
import paho.mqtt.client as mqtt
import csv
import os
from datetime import datetime

# Function to write time, temperature, TDS, and pH values to CSV
def log_to_csv(temperature, tds_value, ph_value):
    file_exists = os.path.isfile('sensor_data_log.csv')
    
    with open('sensor_data_log.csv', mode='a', newline='') as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(['Timestamp', 'Temperature', 'TDS', 'PH'])
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow([current_time, temperature, tds_value, ph_value])

# Save data to a shared JSON file
def save_to_shared_file(data):
    with open("shared_data.json", "w") as file:
        json.dump(data, file)

def on_message(client, userdata, message):
    payload = message.payload.decode()
    try:
        data = json.loads(payload)
        temperature = data.get('temperature')
        tds_value = data.get('TDS')
        ph_value = data.get('PH')

        if temperature is not None and tds_value is not None and ph_value is not None:
            log_to_csv(temperature, tds_value, ph_value)
            save_to_shared_file({
                "temperature": temperature,
                "TDS": tds_value,
                "PH": ph_value
            })
    except json.JSONDecodeError:
        print("Error decoding JSON")

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe([("esp/sensor1", 0), ("esp/sensor2", 0)])
client.loop_forever()
