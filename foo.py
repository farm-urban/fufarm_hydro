"""FOO"""

import yaml
import time
import statistics

import mqtt_io.modules.sensor.dfr0300 as dfr0300
from mqtt_io.server import _init_module
from mqtt_io.__main__ import load_config


def parse_config(config_file):
    with open(config_file, "r", encoding="utf8") as stream:
        config = yaml.safe_load(stream)

    sensor_module_config = config["sensor_modules"]
    sensor_input_config = config["sensor_inputs"]

    module_config = None
    for s in sensor_module_config:
        if s["module"] == "dfr0300":
            module_config = s
            break
    if not module_config:
        raise ValueError("Module not found")

    sensor_config = None
    for s in sensor_input_config:
        if s["module"] == module_config["name"]:
            sensor_config = s
            break
    if not sensor_config:
        raise ValueError("Sensor not found")

    # Remove the temperature sensor config so we don't try and
    # access the event bus
    del sensor_config[dfr0300.TEMPSENSOR_ID]

    return module_config, sensor_config


config_file = "mqtt-io.yml"
module_config, sensor_config = parse_config(config_file)
module = _init_module(module_config, "sensor", False)
module.setup_sensor(sensor_config, None)
calibrator = dfr0300.Calibrator()
temperature = 25.0


NUM_SAMPLES = 20
SAMPLE_INTERVAL = 1
voltages = []
temperatures = []  # for when using a temp sensor
for _ in range(NUM_SAMPLES):
    voltage = module.board.get_adc_value(module.channel)
    voltages.append(voltage)
    temperatures.append(temperature)
    print(voltage)
    time.sleep(SAMPLE_INTERVAL)

variance = statistics.variance(voltages)
print(variance)
if variance > 0.05:
    print("Cannot calibrate - variance of voltages is > 0.05")

voltage = statistics.fmean(voltages)
temperature = statistics.fmean(temperatures)
print("Calibrating sensor with voltage, temperature: ", voltage, temperature)
calibrator.calibrate(voltage, temperature)


# self.current_state.should_calibrate_ec = False
