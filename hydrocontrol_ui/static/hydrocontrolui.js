// baseUrl is set in the template that calls this file
function updateState() {
  const url = new URL("status", baseUrl);
  fetch(url)
    .then((response) => response.json())
    .then(updateStatus);
}

function updateStatus(data) {
  const current_ec = document.getElementById("current-ec");
  current_ec.innerText = data.state.current_ec;
  const dose_time = document.getElementById("last-dosetime");
  dose_time.innerText = new Date(
    data.state.last_dose_time * 1000
  ).toGMTString();
  const dose_count = document.getElementById("dose-count");
  dose_count.innerText = data.state.dose_count;
  const total_dose_time = document.getElementById("total-dose-time");
  total_dose_time.innerText = data.state.total_dose_time;
  const calibration_temperature = document.getElementById(
    "calibrate-ecprobe-temperature"
  );
  calibration_temperature.innerText = data.state.calibration_temperature;
  const calibration_status = document.getElementById(
    "calibrate-ecprobe-status"
  );
  calibration_status.innerText = data.state.calibration_status_message;
}

function addParamsSubmit(ev) {
  ev.preventDefault();
  const formData = new FormData(this);
  const url = new URL("control", baseUrl);
  fetch(url, {
    method: "POST",
    body: formData,
  })
    .then((response) => response.json())
    .then((response) => paramsUpdate(response.parameters));
  ev.submitter.blur(); // Remove focus from the button
}

function paramsUpdate(parameters) {
  // We reset the parameters in case the server has changed them
  if ("dose_duration" in parameters) {
    const dose_duration = document.getElementById("dose-duration");
    dose_duration.value = parameters.dose_duration;
  }
  if ("equilibration_time" in parameters) {
    const equilibration_time = document.getElementById("equilibration-time");
    equilibration_time.value = parameters.equilibration_time;
  }
  if ("target_ec" in parameters) {
    const target_ec = document.getElementById("target-ec");
    target_ec.value = parameters.target_ec;
  }
}

var form = document.getElementById("set-parameters-form");
form.addEventListener("submit", addParamsSubmit);

function addDoseSubmit(ev) {
  ev.preventDefault();
  const formData = new FormData(this);
  const url = new URL("dose", baseUrl);
  fetch(url, {
    method: "POST",
    body: formData,
  });
  ev.submitter.blur(); // Remove focus from the button
}

var form = document.getElementById("manual-dose-form");
form.addEventListener("submit", addDoseSubmit);

function addCalibrateSubmit(ev) {
  ev.preventDefault();
  const formData = new FormData(this);
  const url = new URL("calibrate_ec", baseUrl);
  fetch(url, {
    method: "POST",
    body: formData,
  });
  ev.submitter.blur(); // Remove focus from the button
  updateState();
}

var form = document.getElementById("calibrate-ecprobe");
form.addEventListener("submit", addCalibrateSubmit);

setInterval(updateState, 5000);
