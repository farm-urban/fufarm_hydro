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

INITIAL_KVALUE = 1.0
CALIBRATION_FILE_ENCODING = "ascii"
CALIBRATION_FILENAME = "ec_calibration.json"


class CalibrationStatus(IntEnum):
    """Enum for calibration status."""

    NOT_CALIBRATED = 0
    CALIBRATING = 1
    CALIBRATED = 2
    ERROR = 3
    BUFFER_ERROR = 4


_LOG = logging.getLogger(__name__)


@dataclasses.dataclass
class CalibrationData:
    """Class to handle calibration data"""

    kvalue_low: float = INITIAL_KVALUE
    kvalue_mid: float = INITIAL_KVALUE
    kvalue_high: float = INITIAL_KVALUE
    buffer_solution: float = -1.0
    voltage: float = -1.0
    temperature: float = -1.0
    calibration_time: int = 0
    calibration_status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    calibration_message: str = "Uknown Status"


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
        calibration_data.calibration_status = CalibrationStatus.BUFFER_ERROR
        calibration_data.calibration_message = (
            f"Cannot calibrate - stdev of voltages is > {max_stdev}"
        )
        return calibration_data

    voltage = statistics.fmean(voltages)
    temperature = statistics.fmean(temperatures)
    _LOG.debug("Calibration voltage: %s, temperature: %s", voltage, temperature)
    return calibration_data


@staticmethod
def calc_raw_ec(voltage: float) -> float:
    """Convert voltage to raw EC"""
    return 1000 * voltage / 820.0 / 200.0


def calibrate(calibration_data: CalibrationData) -> None:
    """Calculate the calibration parameters"""

    def calc_kvalue(ec_solution: float, voltage: float, temperature: float) -> float:
        comp_ec_solution = ec_solution * (1.0 + 0.0185 * (temperature - 25.0))
        return round(820.0 * 200.0 * comp_ec_solution / 1000.0 / voltage, 2)

    cd = calibration_data
    cd.calibration_status = CalibrationStatus.CALIBRATED
    cd.calibration_message = "Calibration Successful"

    raw_ec = calc_raw_ec(cd.voltage)
    if 0.9 < raw_ec < 1.9:
        cd.buffer_solution = 1.413
        cd.kvalue_low = calc_kvalue(1.413, cd.voltage, cd.temperature)
        _LOG.info(
            "Buffer Solution: %fus/cm kvalue_low: %f",
            cd.buffer_solution,
            cd.kvalue_low,
        )
    elif 1.9 <= raw_ec < 4:
        cd.buffer_solution = 2.76
        cd.kvalue_mid = calc_kvalue(2.8, cd.voltage, cd.temperature)
        _LOG.info(
            "Buffer Solution: %fms/cm kvalue_mid: %f", cd.buffer_solution, cd.kvalue_mid
        )
    elif 9 < raw_ec < 16.8:
        cd.buffer_solution = 12.88
        cd.kvalue_high = calc_kvalue(12.88, cd.voltage, cd.temperature)
        _LOG.info(
            "Buffer Solution:%fms/cm kvalue_high:%f ",
            cd.buffer_solution,
            cd.kvalue_high,
        )
    else:
        # raise ValueError(">>>Buffer Solution Error Try Again<<<")
        cd.calibration_status = CalibrationStatus.ERROR
        cd.calibration_message = "Buffer Solution Error Try Again"
    cd.calibration_time = time.time()
    return


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
    module.kvalue_low = INITIAL_KVALUE
    module.kvalue_mid = INITIAL_KVALUE
    module.kvalue_high = INITIAL_KVALUE
    calibration_file = module.calibration_file
    if os.path.isfile(calibration_file):
        _LOG.info("Resetting EC calibration file: %s", calibration_file)
        calibration_file_bak = calibration_file + ".bak"
        os.rename(calibration_file, calibration_file_bak)
    return


def run_calibration(config_file, temperature=25.0) -> CalibrationData:
    """Run the calibration process"""
    module_config, sensor_config = parse_config(config_file)
    dfr0300_module = _init_module(module_config, "sensor", False)
    reset_calibration(dfr0300_module)
    dfr0300_module.setup_sensor(sensor_config, None)
    calibration_data = CalibrationData()
    calc_calibration_voltage_and_temperature(
        dfr0300_module, temperature, calibration_data
    )
    if calibration_data.calibration_status != CalibrationStatus.BUFFER_ERROR:
        calibrate(calibration_data)
        _LOG.info("Calibrating sensor with values: %s", calibration_data)
    write_calibration(calibration_data, dfr0300_module.calibration_file)
    return calibration_data


if __name__ == "__main__":
    MQTTIO_CONFIG_FILE = "mqtt-io.yml"
    CALIBRATION_TEMPERATURE = 25.0
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s rpi: %(message)s",
    )
    if not os.path.isfile(MQTTIO_CONFIG_FILE):
        _LOG.error("Config file not found: %s", MQTTIO_CONFIG_FILE)
        exit(1)

    run_calibration(MQTTIO_CONFIG_FILE, CALIBRATION_TEMPERATURE)
