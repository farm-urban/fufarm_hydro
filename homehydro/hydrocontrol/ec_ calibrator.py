"""FOO"""

import logging
import yaml
import time
import statistics

import mqtt_io.modules.sensor.dfr0300 as dfr0300
from mqtt_io.server import _init_module
from mqtt_io.__main__ import load_config

_LOG = logging.getLogger(__name__)


def parse_config(config_file, module_name="dfr0300"):
    with open(config_file, "r", encoding="utf8") as stream:
        config = yaml.safe_load(stream)

    sensor_module_config = config["sensor_modules"]
    sensor_input_config = config["sensor_inputs"]

    module_config = None
    for s in sensor_module_config:
        if s["module"] == module_name:
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
    if dfr0300.TEMPSENSOR_ID in sensor_config:
        del sensor_config[dfr0300.TEMPSENSOR_ID]

    return module_config, sensor_config


def calc_calibration_voltage_and_temperature(dfr0300_module, temperature):
    num_samples = 20
    sample_interval = 1
    voltages = []
    temperatures = []  # for when using a temp sensor
    for _ in range(num_samples):
        voltage = dfr0300_module.board.get_adc_value(dfr0300_module.channel)
        _LOG.debug("Voltage: %s", voltage)
        voltages.append(voltage)
        temperatures.append(temperature)
        time.sleep(sample_interval)

    variance = statistics.variance(voltages)
    if variance > 0.05:
        raise RuntimeError("Cannot calibrate - variance of voltages is > 0.05")

    voltage = statistics.fmean(voltages)
    temperature = statistics.fmean(temperatures)
    _LOG.debug("Calibration voltage: %s, temperature: %s", voltage, temperature)
    return voltage, temperature


def calibrate(config_file, temperature=25.0):
    module_config, sensor_config = parse_config(config_file)
    dfr0300_module = _init_module(module_config, "sensor", False)
    dfr0300_module.setup_sensor(sensor_config, None)
    try:
        voltage, temperature = calc_calibration_voltage_and_temperature(
            dfr0300_module, temperature
        )
    except RuntimeError as e:
        _LOG.error("Error calibrating sensor: %s", e)
        return False
    calibrator = dfr0300.Calibrator()
    _LOG.info(
        "Calibrating sensor with voltage: %f, temperature: %f", voltage, temperature
    )
    # Should check return code
    calibrator.calibrate(voltage, temperature)
    return True


# self.current_state.should_calibrate_ec = False
