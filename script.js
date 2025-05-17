document.addEventListener('DOMContentLoaded', function() {
    // Check bot status periodically
    function checkBotStatus() {
        fetch('/api/bot_status')
            .then(response => response.json())
            .then(data => {
                const statusDot = document.getElementById('statusDot');
                const statusText = document.getElementById('statusText');
                const startButton = document.querySelector('button[type="submit"]');
                
                if (data.running) {
                    statusDot.className = 'status-dot active';
                    statusText.textContent = 'Работает';
                    if (startButton) {
                        startButton.disabled = true;
                    }
                } else {
                    statusDot.className = 'status-dot inactive';
                    statusText.textContent = 'Остановлен';
                    if (startButton) {
                        startButton.disabled = false;
                    }
                }
            })
            .catch(error => {
                console.error('Error checking bot status:', error);
            });
    }
    
    // Check status initially and then every 10 seconds
    if (document.getElementById('botStatusIndicator')) {
        checkBotStatus();
        setInterval(checkBotStatus, 10000);
    }
    
    // Initialize tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))
    
    // Auto-dismiss alerts after 5 seconds
    const alertList = document.querySelectorAll('.alert')
    alertList.forEach(function (alert) {
        setTimeout(function() {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });
});
