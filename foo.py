"""FOO"""

import yaml
import time
import statistics

import mqtt_io.modules.sensor.dfr0300 as dfr0300
from mqtt_io.server import _init_module
from mqtt_io.__main__ import load_config

config_file = "mqtt-io.yml"

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

module = _init_module(module_config, "sensor", False)
# Need to remove the temperature sensor config
# so we don't try and access the event bus
del sensor_config[dfr0300.TEMPSENSOR_ID]

module.setup_sensor(sensor_config, None)
calibrator = dfr0300.Calibrator()
temperature = 25.0


def get_ec():
    voltage = module.board.get_adc_value(module.channel)
    ec = module.ec_from_voltage(voltage, temperature)
    #value = module.get_value(sensor_config)
    return ec

ntries = 20  # Number of calibration attempts
values = []
for i in range(ntries):
    ec = get_ec()
    values.append(ec)
    print(ec)
    #if calibrator.calibrate(value):
    #    break
    time.sleep(1)

variance = statistics.variance(values)
print(variance)
if variance > 0.05:
   print("Cannot calibrate - variance of readings is > 0.05")

voltage = statistics.fmean(values)
print("Voltage: ",voltage)



# self.current_state.should_calibrate_ec = False
