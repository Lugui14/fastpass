// FastPass Global JavaScript helper scripts

document.addEventListener("DOMContentLoaded", function () {
    // Auto-dismiss alert messages after 5 seconds
    const alerts = document.querySelectorAll(".alert");
    alerts.forEach(function (alert) {
        setTimeout(function () {
            alert.style.transition = "opacity 0.5s ease";
            alert.style.opacity = "0";
            setTimeout(function () {
                alert.style.display = "none";
            }, 500);
        }, 5000);
    });
});
