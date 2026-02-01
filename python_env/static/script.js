document.addEventListener('DOMContentLoaded', () => {
    fetchStatus();
    setInterval(fetchStatus, 5000); // Rafraîchir toutes les 5 secondes
});

async function fetchStatus() {
    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        
        document.getElementById('cpu-usage').textContent = data.cpu_percent ? data.cpu_percent.toFixed(1) : '--';
        document.getElementById('ram-usage').textContent = data.ram_percent ? data.ram_percent.toFixed(1) : '--';
        document.getElementById('throttle-level').textContent = data.throttle_level !== undefined ? data.throttle_level : '--';
        document.getElementById('aws-ready').textContent = data.aws_ready ? 'Oui' : 'Non';
        document.getElementById('api-server-running').textContent = data.api_server_running ? 'Oui' : 'Non';
        document.getElementById('pipeline-ok').textContent = data.pipeline_ok ? 'Oui' : 'Non';

    } catch (error) {
        console.error('Erreur lors de la récupération du statut:', error);
        document.getElementById('cpu-usage').textContent = 'Erreur';
        document.getElementById('ram-usage').textContent = 'Erreur';
        document.getElementById('throttle-level').textContent = 'Erreur';
        document.getElementById('aws-ready').textContent = 'Erreur';
        document.getElementById('api-server-running').textContent = 'Erreur';
        document.getElementById('pipeline-ok').textContent = 'Erreur';
    }
}

async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        const data = await response.json();
        document.getElementById('config-display').textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        console.error('Erreur lors de la récupération de la configuration:', error);
        document.getElementById('config-display').textContent = 'Erreur lors du chargement de la configuration.';
    }
}

async function startService() {
    const serviceName = document.getElementById('service-select').value;
    try {
        const response = await fetch('/api/control/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ service: serviceName })
        });
        const result = await response.json();
        alert(result.message);
        fetchStatus(); // Rafraîchir le statut après l'action
    } catch (error) {
        console.error('Erreur lors du démarrage du service:', error);
        alert('Erreur lors du démarrage du service.');
    }
}

async function stopService() {
    const serviceName = document.getElementById('service-select').value;
    try {
        const response = await fetch('/api/control/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ service: serviceName })
        });
        const result = await response.json();
        alert(result.message);
        fetchStatus(); // Rafraîchir le statut après l'action
    } catch (error) {
        console.error('Erreur lors de l\'arrêt du service:', error);
        alert('Erreur lors de l\'arrêt du service.');
    }
}
