"""Calibrate the EC sensor"""

import dataclasses
import json
import logging
import os
import statistics
import time


import yaml

import mqtt_io.modules.sensor.dfr0300 as dfr0300
from mqtt_io.server import _init_module

INITIAL_KVALUE = 1.0
CALIBRATION_FILE_ENCODING = "ascii"
CALIBRATION_FILENAME = "ec_calibration.json"


_LOG = logging.getLogger(__name__)


@dataclasses.dataclass
class CalibrationData:
    """Class to handle calibration data"""

    kvalue_low: float = INITIAL_KVALUE
    kvalue_mid: float = INITIAL_KVALUE
    kvalue_high: float = INITIAL_KVALUE
    buffer_solution: float
    voltage: float
    temperature: float
    calibration_time: int
    calibration_status: int
    calibration_message: str


def read_calibration(calibration_file) -> CalibrationData:
    """Read calibrated values from json file."""
    if os.path.exists(calibration_file):
        with open(
            calibration_file, "r", encoding=CALIBRATION_FILE_ENCODING
        ) as file_handle:
            data = json.load(file_handle)
        return CalibrationData(**data)
    raise FileNotFoundError(f"Calibration file ${calibration_file} not found")


def write_calibration(calibration_data, calibration_file) -> None:
    """Write calibrated values to json file."""
    try:
        with open(
            calibration_file, "w", encoding=CALIBRATION_FILE_ENCODING
        ) as file_handle:
            data = dataclasses.asdict(calibration_data)
            json.dump(data, file_handle, indent=2, encoding=CALIBRATION_FILE_ENCODING)
    except IOError as exc:
        _LOG.warning("Failed to write calibration data: %s", exc)


def calc_calibration_voltage_and_temperature(self, temperature):
    """Calculate calibration voltage and temperature"""
    num_samples = 20
    sample_interval = 1
    voltages = []
    temperatures = []  # for when using a temp sensor
    for _ in range(num_samples):
        voltage = self.dfr0300_module.board.get_adc_value(self.dfr0300_module.channel)
        voltages.append(voltage)
        temperatures.append(temperature)
        time.sleep(sample_interval)

    _LOG.debug(
        "Calibration got voltages: %s\n temperatures: %s", voltages, temperatures
    )
    stdev = statistics.stdev(voltages)
    max_stdev = 10  # Arbitrary value - need to determine a sensible parameter
    if stdev > max_stdev:
        raise RuntimeError(f"Cannot calibrate - stdev of voltages is > {max_stdev}")

    voltage = statistics.fmean(voltages)
    temperature = statistics.fmean(temperatures)
    _LOG.debug("Calibration voltage: %s, temperature: %s", voltage, temperature)
    return voltage, temperature


@staticmethod
def calc_raw_ec(voltage: float) -> float:
    """Convert voltage to raw EC"""
    return 1000 * voltage / 820.0 / 200.0


def calibrate(voltage: float, temperature: float) -> CalibrationData:
    """Set the calibration values and write out to file."""

    def calc_kvalue(ec_solution: float, voltage: float, temperature: float) -> float:
        comp_ec_solution = ec_solution * (1.0 + 0.0185 * (temperature - 25.0))
        return round(820.0 * 200.0 * comp_ec_solution / 1000.0 / voltage, 2)

    cd = CalibrationData()
    cd.voltage = voltage
    cd.temperature = temperature

    raw_ec = calc_raw_ec(voltage)
    if 0.9 < raw_ec < 1.9:
        cd.buffer_solution = 1.413
        cd.kvalue_low = calc_kvalue(1.413, voltage, temperature)
        _LOG.info(
            ">>>Buffer Solution: %fus/cm kvalue_low: %f",
            cd.buffer_solution,
            cd.kvalue_low,
        )
    elif 1.9 <= raw_ec < 4:
        cd.buffer_solution = 2.76
        cd.kvalue_mid = calc_kvalue(2.8, voltage, temperature)
        _LOG.info(">>>EC: %fms/cm kvalue_mid: %f", cd.buffer_solution, cd.kvalue_mid)
    elif 9 < raw_ec < 16.8:
        cd.buffer_solution = 12.88
        cd.kvalue_high = calc_kvalue(12.88, voltage, temperature)
        _LOG.info(
            ">>>Buffer Solution:%fms/cm kvalue_high:%f ",
            cd.buffer_solution,
            cd.kvalue_high,
        )
    else:
        # raise ValueError(">>>Buffer Solution Error Try Again<<<")
        cd.calibration_status = 1
        cd.calibration_message = ">>>Buffer Solution Error Try Again<<<"
    cd.calibration_time = time.time()
    cd.calibration_status = 0
    cd.calibration_message = "Calibration Successful"
    return cd


def parse_config(config_file, module_name="dfr0300"):
    """Parse MQTT-IO config file for sensor module and sensor input"""
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


def reset_calibration(module):
    """Very hacky way to reset calibration"""
    module.kvalue_low = 1.0
    module.kvalue_mid = 1.0
    module.kvalue_high = 1.0
    calibration_file = module.calibrator.calibration_file
    if os.path.isfile(calibration_file):
        _LOG.info("Resetting EC calibration file: %s", calibration_file)
        calibration_file_bak = calibration_file + ".bak"
        os.rename(calibration_file, calibration_file_bak)
    return


def run_calibration(config_file, temperature=25.0) -> tuple[bool, str]:
    """Run the calibration process"""
    try:
        module_config, sensor_config = parse_config(config_file)
        dfr0300_module = _init_module(module_config, "sensor", False)
        reset_calibration(dfr0300_module)
        dfr0300_module.setup_sensor(sensor_config, None)
        voltage, temperature = calc_calibration_voltage_and_temperature(
            dfr0300_module, temperature
        )
        calibration_data = calibrate(voltage, temperature)
        _LOG.info("Calibrating sensor with values: %s", calibration_data)
        write_calibration(calibration_data, dfr0300_module.calibration_file)
    except RuntimeError as e:
        error_msg = f"Error calibrating sensor: {e}"
        _LOG.error(error_msg)
        return (False, error_msg)
    return (True, f"Calibrated at: {time.asctime(time.localtime())}")
