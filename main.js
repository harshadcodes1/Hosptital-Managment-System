// Confirm before destructive actions: <form data-confirm="Are you sure?">
document.addEventListener("submit", function (e) {
  var msg = e.target.getAttribute("data-confirm");
  if (msg && !window.confirm(msg)) e.preventDefault();
});

// Bill form: fill the consultation fee from the chosen doctor
var feeSelect = document.getElementById("fee-doctor");
if (feeSelect) {
  feeSelect.addEventListener("change", function () {
    var opt = feeSelect.options[feeSelect.selectedIndex];
    var fee = opt.getAttribute("data-fee");
    var amount = document.getElementById("amount");
    var desc = document.getElementById("description");
    if (fee) {
      amount.value = fee;
      if (!desc.value) desc.value = "Consultation - " + opt.getAttribute("data-name");
    }
  });
}

// Appointment form: show the selected doctor's working hours
var docSelect = document.getElementById("doctor-select");
var hint = document.getElementById("doctor-hint");
if (docSelect && hint) {
  var update = function () {
    var opt = docSelect.options[docSelect.selectedIndex];
    var s = opt && opt.getAttribute("data-schedule");
    hint.textContent = s ? "Available: " + s : "";
  };
  docSelect.addEventListener("change", update);
  update();
}
