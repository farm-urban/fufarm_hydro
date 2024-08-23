"""Calibrate the EC sensor"""

import logging
import os
import statistics
import time


import yaml

import mqtt_io.modules.sensor.dfr0300 as dfr0300
from mqtt_io.server import _init_module

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
        voltages.append(voltage)
        temperatures.append(temperature)
        time.sleep(sample_interval)

    _LOG.debug(
        "Calibration got voltages: %s\n temperatures: %s", voltages, temperatures
    )
    stdev = statistics.stdev(voltages)
    if stdev > 10:  # Completely arbitrary value - need to determine a sensible value
        raise RuntimeError("Cannot calibrate - stdev of voltages is > 10")

    voltage = statistics.fmean(voltages)
    temperature = statistics.fmean(temperatures)
    _LOG.debug("Calibration voltage: %s, temperature: %s", voltage, temperature)
    return voltage, temperature


def reset_calibration(module):
    """Very hacky way to reset calibration"""
    calibration_file = module.calibrator.calibration_file
    module.kvalue_low = 1.0
    module.kvalue_mid = 1.0
    module.kvalue_high = 1.0
    calibration_file_bak = calibration_file + ".bak"
    os.rename(calibration_file, calibration_file_bak)
    return


def calibrate(config_file, temperature=25.0) -> tuple[bool, str]:
    try:
        module_config, sensor_config = parse_config(config_file)
        dfr0300_module = _init_module(module_config, "sensor", False)
        reset_calibration(dfr0300_module)
        dfr0300_module.setup_sensor(sensor_config, None)
        voltage, temperature = calc_calibration_voltage_and_temperature(
            dfr0300_module, temperature
        )
        calibrator = dfr0300.Calibrator()
        _LOG.info(
            "Calibrating sensor with voltage: %f, temperature: %f", voltage, temperature
        )
        # Should check return code
        calibrator.calibrate(voltage, temperature)
    except RuntimeError as e:
        error_msg = f"Error calibrating sensor: {e}"
        _LOG.error(error_msg)
        return (False, error_msg)
    return (True, f"Calibrated at: {time.asctime(time.localtime())}")
