  // function addSubmit(ev) {
  //   ev.preventDefault();
  //   fetch({{ url_for('add')|tojson }}, {
  //     method: 'POST',
  //     body: new FormData(this)
  //   })
  //     .then(response => response.json())
  //     .then(addShow);
  // }


  // function addShow(data) {
  //   var span = document.getElementById('result');
  //   span.innerText = data.result;
  // }

  function getCurrentEC() {
    let url = {{ url_for('status')|tojson }} + '?' + new URLSearchParams({ q: 'current_ec'}).toString();
    fetch(url)
    .then(response => response.json())
    .then(updateEC);
  }

  function updateEC(data) {
    let span = document.getElementById('current-ec');
    span.innerText = data.ec;
  }


  function getLastDosetime() {
    let url = {{ url_for('status')|tojson }} + '?' + new URLSearchParams({ q: 'last_dose_time'}).toString();
    fetch(url)
    .then(response => response.json())
      .then(updateLastDosetime);
  }

  function updateLastDosetime(data) {
    let span = document.getElementById('last-dosetime');
    span.innerText = data.last_dose_time;
  }


  // var form = document.getElementById('set-parameters');
  // form.addEventListener('submit', addSubmit);

  setInterval(getCurrentEC, 2000);
  setInterval(getLastDosetime, 2000);