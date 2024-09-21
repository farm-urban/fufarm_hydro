"""Calibrate the EC sensor"""

import dataclasses
import datetime
from enum import IntEnum
import json
import logging
import os
import statistics
import time


import yaml

from mqtt_io.modules.sensor import dfr0300
from mqtt_io.server import _init_module

MQTTIO_CONFIG_FILE = "./mqtt-io.yml"
INITIAL_KVALUE = 1.0
CALIBRATION_FILE_ENCODING = "ascii"
CALIBRATION_TEMPERATURE = 25.0
CALIBRATION_VALID = 60 * 60 * 24 * 28  # 28 days
LOW_BUFFER_SOLUTION = 1.413
HIGH_BUFFER_SOLUTION = 12.88
RES2 = 820.0
ECREF = 200.0


class CalibrationException(Exception):
    """Exception for calibration errors."""

    pass


class CalibrationStatus(IntEnum):
    """Enum for calibration status."""

    NOT_CALIBRATED = 0
    CALIBRATING = 1
    CALIBRATED = 2
    ERROR = 3


_LOG = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class CalibrationPoint:
    """Class to handle calibration of a single point"""

    buffer_solution: float = -1.0
    voltage: float = -1.0
    temperature: float = -1.0
    time: int = 0
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    message: str = "Unknown Status"


@dataclasses.dataclass(slots=True)
class CalibrationData:
    """Class to handle calibration data"""

    kvalue_low: float = INITIAL_KVALUE
    kvalue_high: float = INITIAL_KVALUE
    temperature: float = CALIBRATION_TEMPERATURE
    status: CalibrationStatus = CalibrationStatus.NOT_CALIBRATED
    message: str = "Unknown Status"
    point_low: CalibrationPoint = dataclasses.field(default_factory=CalibrationPoint)
    point_high: CalibrationPoint = dataclasses.field(default_factory=CalibrationPoint)

    def __post_init__(self):
        """https://stackoverflow.com/questions/53376099/python-dataclass-from-a-nested-dict"""
        if isinstance(self.point_low, dict):
            self.point_low = CalibrationPoint(**self.point_low)
        if isinstance(self.point_high, dict):
            self.point_high = CalibrationPoint(**self.point_high)
        if self.calibration_time < 0:
            self.status = CalibrationStatus.NOT_CALIBRATED
            self.message = "Not Calibrated"
        elif time.time() - self.calibration_time <= CALIBRATION_VALID:
            self.status = CalibrationStatus.CALIBRATED
            timestamp = datetime.datetime.fromtimestamp(self.calibration_time)
            self.message = f"Calibration OK. Last calibrated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        elif time.time() - self.calibration_time > CALIBRATION_VALID:
            self.status = CalibrationStatus.NOT_CALIBRATED
            timestamp = datetime.datetime.fromtimestamp(self.calibration_time)
            self.message = f"Calibration expired. Last calibrated: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

    @property
    def calibration_time(self) -> int:
        """Return the calibration time from the last point calibrated."""
        time_low = self._calibration_time(self.point_low)
        time_high = self._calibration_time(self.point_high)
        if time_low > 0 and time_high > 0:
            if time_low > time_high:
                return time_low
            return time_high
        return -1

    @staticmethod
    def _calibration_time(point: CalibrationPoint) -> int:
        if point and point.status == CalibrationStatus.CALIBRATED:
            return point.time
        return -1


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


def calc_calibration_voltage_and_temperature(dfr0300_module, temperature):
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
        raise CalibrationException(
            f"Cannot calibrate - stdev of voltages is > {max_stdev}"
        )
    voltage = statistics.fmean(voltages)
    temperature = statistics.fmean(temperatures)
    _LOG.debug(
        "Calibration voltage: %s, temperature: %s",
        voltage,
        temperature,
    )
    return voltage, temperature


@staticmethod
def calc_raw_ec(voltage: float) -> float:
    """Convert voltage to raw EC"""
    return 1000 * voltage / RES2 / ECREF


def calibrate(
    calibration_data: CalibrationData, voltage: float, temperature: float
) -> None:
    """Calculate the calibration parameters"""

    def calc_kvalue(ec_solution: float, voltage: float, temperature: float) -> float:
        comp_ec_solution = ec_solution * (1.0 + 0.0185 * (temperature - 25.0))
        return round(RES2 * ECREF * comp_ec_solution / 1000.0 / voltage, 2)

    cd = calibration_data
    cd.status = CalibrationStatus.ERROR
    cd.message = "Could not determine the calibration solution in use."
    raw_ec = calc_raw_ec(voltage)
    # _LOG.debug("GOT VOLTAGE %f RAW EC: %f",voltage, raw_ec)
    if 0.9 < raw_ec < 1.9:
        msg = "Calibration Low Successful"
        cd.kvalue_low = calc_kvalue(LOW_BUFFER_SOLUTION, voltage, temperature)
        cd.status = CalibrationStatus.CALIBRATED
        cd.message = msg
        cd.point_low.buffer_solution = LOW_BUFFER_SOLUTION
        cd.point_low.status = CalibrationStatus.CALIBRATED
        cd.point_low.message = msg
        cd.point_low.time = time.time()
        _LOG.info(
            "Calibration Solution: %fus/cm kvalue_low: %f",
            cd.point_low.buffer_solution,
            cd.kvalue_low,
        )
    # elif 9 < raw_ec < 16.8: # original values from DFRobot
    elif 9 < raw_ec < 20:
        msg = "Calibration High Successful"
        cd.kvalue_high = calc_kvalue(HIGH_BUFFER_SOLUTION, voltage, temperature)
        cd.status = CalibrationStatus.CALIBRATED
        cd.message = msg
        cd.point_high.buffer_solution = HIGH_BUFFER_SOLUTION
        cd.point_high.status = CalibrationStatus.CALIBRATED
        cd.point_high.message = msg
        cd.point_high.time = time.time()
        _LOG.info(
            "Calibration Solution:%fms/cm kvalue_high:%f ",
            cd.point_high.buffer_solution,
            cd.kvalue_high,
        )
    return


def run_calibration(calibration_data: CalibrationData, mqttio_config_file: str) -> None:
    """Run the calibration process"""
    module_config, sensor_config = parse_config(mqttio_config_file)
    dfr0300_module = _init_module(module_config, "sensor", False)
    dfr0300_module.setup_sensor(sensor_config, None)
    try:
        voltage, temperature = calc_calibration_voltage_and_temperature(
            dfr0300_module, calibration_data.temperature
        )
    except CalibrationException as e:
        _LOG.warning(
            "Error reading stable voltages when calibrating EC probe: %s",
            e,
        )
        calibration_data.status = CalibrationStatus.ERROR
        calibration_data.message = e
        return

    calibrate(calibration_data, voltage, temperature)
    if calibration_data.status == CalibrationStatus.ERROR:
        _LOG.warning(
            "Buffer solution error when calibrating EC probe: %s", calibration_data
        )
        return calibration_data
    write_calibration(calibration_data, dfr0300_module.calibration_file)
    return


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s rpi: %(message)s",
    )
    if not os.path.isfile(MQTTIO_CONFIG_FILE):
        _LOG.error("Config file not found: %s", MQTTIO_CONFIG_FILE)
        exit(1)

    run_calibration(MQTTIO_CONFIG_FILE, CALIBRATION_TEMPERATURE)
