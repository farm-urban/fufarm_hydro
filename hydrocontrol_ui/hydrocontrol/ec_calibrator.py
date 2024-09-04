"""Calibrate the EC sensor"""

import dataclasses
from enum import IntEnum
import json
import logging
import os
import statistics
import time


import yaml

import mqtt_io.modules.sensor.dfr0300 as dfr0300
from mqtt_io.server import _init_module

MQTTIO_CONFIG_FILE = "./mqtt-io.yml"
INITIAL_KVALUE = 1.0
CALIBRATION_FILE_ENCODING = "ascii"
CALIBRATION_TEMPERATURE = 25.0
CALIBRATION_FILE = "./ec_config.json"
LOW_BUFFER_SOLUTION=1.413
HIGH_BUFFER_SOLUTION=12.88
RES2=820.0
ECREF=200.0

class CalibrationStatus(IntEnum):
    """Enum for calibration status."""

    NOT_CALIBRATED = 0
    CALIBRATING = 1
    CALIBRATED = 2
    ERROR = 3

_LOG = logging.getLogger(__name__)


@dataclasses.dataclass
class CalibrationData:
    """Class to handle calibration data"""

    kvalue_low: float = INITIAL_KVALUE
    kvalue_high: float = INITIAL_KVALUE
    buffer_solution: float = -1.0
    voltage: float = -1.0
    temperature: float = -1.0
    calibration_time: int = 0
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    calibration_message: str = "Uknown Status"

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
            json.dump(data, file_handle, indent=2)
    except IOError as exc:
        _LOG.warning("Failed to write calibration data: %s", exc)


def calc_calibration_voltage_and_temperature(
    dfr0300_module, temperature, calibration_data
):
    """Calculate calibration voltage and temperature"""
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
    max_stdev = 10  # Arbitrary value - need to determine a sensible parameter
    if stdev > max_stdev:
        calibration_data.calibration_status = CalibrationStatus.ERROR
        message = f"Cannot calibrate - stdev of voltages is > {max_stdev}"
        calibration_data.calibration_message = message
        calibration_data.time = time.time()
        _LOG.debug(message)
        return calibration_data

    calibration_data.voltage = statistics.fmean(voltages)
    calibration_data.temperature = statistics.fmean(temperatures)
    _LOG.debug(
        "Calibration voltage: %s, temperature: %s",
        calibration_data.voltage,
        calibration_data.temperature,
    )
    return calibration_data


@staticmethod
def calc_raw_ec(voltage: float) -> float:
    """Convert voltage to raw EC
    """
    return 1000 * voltage / RES2 / ECREF

def calibrate(calibration_data: CalibrationData) -> None:
    """Calculate the calibration parameters"""

    def calc_kvalue(ec_solution: float, voltage: float, temperature: float) -> float:
        comp_ec_solution = ec_solution * (1.0 + 0.0185 * (temperature - 25.0))
        return round(RES2 * ECREF * comp_ec_solution / 1000.0 / voltage, 2)

    cd = calibration_data
    cd.calibration_status = CalibrationStatus.CALIBRATED
    cd.calibration_message = "Calibration Successful"

    raw_ec = calc_raw_ec(cd.voltage)
    # _LOG.debug("GOT VOLTAGE %f RAW EC: %f",cd.voltage, raw_ec)
    if 0.9 < raw_ec < 1.9:
        cd.buffer_solution = LOW_BUFFER_SOLUTION
        cd.kvalue_low = calc_kvalue(LOW_BUFFER_SOLUTION, cd.voltage, cd.temperature)
        _LOG.info(
            "Calibration Solution: %fus/cm kvalue_low: %f",
            cd.buffer_solution,
            cd.kvalue_low,
        )
    #elif 9 < raw_ec < 16.8: # original values from DFRobot
    elif 9 < raw_ec < 20:
        cd.buffer_solution = HIGH_BUFFER_SOLUTION
        cd.kvalue_high = calc_kvalue(HIGH_BUFFER_SOLUTION, cd.voltage, cd.temperature)
        _LOG.info(
            "Calibration Solution:%fms/cm kvalue_high:%f ",
            cd.buffer_solution,
            cd.kvalue_high,
        )
    else:
        cd.calibration_status = CalibrationStatus.ERROR
        cd.calibration_message = "Could not determine the calibration solution in use."

    cd.calibration_time = time.time()
    return

MODULE = None
def run_calibration(config_file, temperature=25.0) -> CalibrationData:
    """Run the calibration process"""
    module_config, sensor_config = parse_config(config_file)
    dfr0300_module = _init_module(module_config, "sensor", False)
    dfr0300_module.setup_sensor(sensor_config, None)
    global MODULE
    MODULE = dfr0300_module
    calibration_data = CalibrationData()
    if os.path.isfile(CALIBRATION_FILE):
        cd_tmp = read_calibration(CALIBRATION_FILE)
        _LOG.debug("Read Calibration Data: %s", cd_tmp)
        calibration_data.kvalue_low = cd_tmp.kvalue_low
        calibration_data.kvalue_high = cd_tmp.kvalue_high

    calc_calibration_voltage_and_temperature(
        dfr0300_module, temperature, calibration_data
    )
    if calibration_data.calibration_status == CalibrationStatus.ERROR:
        _LOG.warn("Error reading stable voltages when calibrating EC probe: %s", calibration_data)
        return calibration_data

    calibrate(calibration_data)
    if calibration_data.calibration_status == CalibrationStatus.ERROR:
        _LOG.warn("Buffer solution error when calibrating EC probe: %s", calibration_data)
        return calibration_data

    write_calibration(calibration_data, dfr0300_module.calibration_file)
    return calibration_data


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s rpi: %(message)s",
    )
    if not os.path.isfile(MQTTIO_CONFIG_FILE):
        _LOG.error("Config file not found: %s", MQTTIO_CONFIG_FILE)
        exit(1)

    run_calibration(MQTTIO_CONFIG_FILE, CALIBRATION_TEMPERATURE)
