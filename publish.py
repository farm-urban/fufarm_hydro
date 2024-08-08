import json
import time
import paho.mqtt.client as mqtt

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
#host = "homeassistant.local"
host = "localhost"
port = 1883
username = "hamqtt"
password = "UbT4Rn3oY7!S9L"
client.username_pw_set(username, password)
ret = client.connect(host, port=port)
client.loop()

SEPARATOR = "/"
CALIBRATE = "calibrate"
CONTROL = "control"
EC = "ec"
PARAMETERS = "parameters"
TOPIC_PREFIX = "hydro"
TOPICS = {
    CONTROL: SEPARATOR.join([TOPIC_PREFIX, CONTROL]),
    CALIBRATE: SEPARATOR.join([TOPIC_PREFIX, CALIBRATE]),
    EC: SEPARATOR.join([TOPIC_PREFIX, EC]),
    PARAMETERS: SEPARATOR.join([TOPIC_PREFIX, PARAMETERS]),
}

print(TOPICS)

while not client.is_connected():
    print("mqtt_client not connected")
    ret = client.reconnect()
    time.sleep(2)

params = {
    "dose_duration": 10,
    "equilibration_time": 30,
    "target_ec": 2.2,
}

#client.publish(TOPICS[PARAMETERS], json.dumps(params))
client.publish(TOPICS[CONTROL], 1)
# client.publish(TOPICS[EC], 1.2)
