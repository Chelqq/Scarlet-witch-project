// Este archivo debe ser incluido en todas las vistas HTML
// Se recomienda guardarlo como static/assets/js/arduino-websocket.js

// Inicializar Socket.IO
let socket;
let isConnected = false;
let connectionInfo = {
    connection_type: null,
    serial_port: null,
    host: null,
    port: null
};

// Función para inicializar Socket.IO
function initSocketIO() {

     // Verificar si ya existe una conexión
     if (socket && socket.connected) {
        console.log('Socket.IO ya está conectado');
        return;
    }
    
    // Inicializar la conexión Socket.IO
    socket = io.connect(window.location.origin);
    
    // Manejar eventos de conexión
    socket.on('connect', function() {
        console.log('Conectado a WebSocket');
        
        // Solicitar estado actual de conexión
        socket.emit('get_connection_status', {}, function(response) {
            // Actualizar UI basado en el estado de conexión
            updateConnectionUI(response);
            
            // Almacenar la información de conexión para uso futuro
            if (response.is_connected) {
                isConnected = true;
                connectionInfo = response;
                console.log("Usando conexión existente:", connectionInfo);
            }
        });
    });
    
    // Agregar manejador para desconexiones
    socket.on('disconnect', function() {
        console.log('Desconectado de WebSocket');
        isConnected = false;
    });
    
    // Manejador para actualizaciones de estado de conexión
    socket.on('connection_status', function(data) {
        updateConnectionUI(data);
        
        // Actualizar variables globales
        isConnected = data.is_connected;
        connectionInfo = data;
    });

    socket.on('arduino_connection_result', function(data) {
        handleConnectionResult(data);
    });
    
    socket.on('reset_servos_result', function(data) {
        handleResetResult(data);
    });
    
    socket.on('run_sequence_result', function(data) {
        handleSequenceResult(data);
    });
}

// Función para conectar con Arduino
function connectToArduino(useTcp, serialPort, host, tcpPort) {
    if (!socket || !socket.connected) {
        showNotification('warning', 'No hay conexión con el servidor WebSocket');
        return;
    }
    
    let connectData = {};
    
    if (useTcp) {
        connectData = {
            use_tcp: true,
            host: host,
            port: parseInt(tcpPort)
        };
    } else {
        connectData = {
            use_tcp: false,
            serial_port: serialPort
        };
    }
    
    // Mostrar notificación de "Conectando..."
    updateConnectionStatusUI('Conectando...', null);
    
    // Enviar solicitud de conexión
    socket.emit('connect_arduino', connectData, function(response) {
        console.log('Respuesta de conexión:', response);
        // La actualización de la UI se maneja en el evento 'arduino_connection_result'
    });
}

// Función para mover un servo
function moveServo(servoId, angle) {
    return new Promise((resolve, reject) => {
        if (!socket || !socket.connected) {
            reject(new Error('No hay conexión WebSocket'));
            return;
        }
        
        if (!isConnected) {
            console.warn('Arduino no está conectado, usando última configuración conocida');
        }
        
        socket.emit('set_servo', {
            servo_id: servoId,
            angle: angle
        }, function(response) {
            if (response.status === 'success') {
                resolve(response);
            } else {
                reject(new Error(response.message));
            }
        });
    });
}

// Función para resetear todos los servos
function resetAllServos() {
    if (!socket || !socket.connected) {
        showNotification('warning', 'No hay conexión con el servidor WebSocket');
        return;
    }
    
    if (!isConnected) {
        showNotification('warning', 'Arduino no está conectado');
        return;
    }
    
    socket.emit('reset_servos', {}, function(response) {
        if (response.status === 'success') {
            showNotification('success', response.message);
            
            // Si se está en la vista de control de servos, actualizar los sliders
            updateAllServosUI();
        } else {
            showNotification('danger', response.message);
        }
    });
}

// Función para ejecutar secuencia
function executeSequence(sequence) {
    if (!socket || !socket.connected) {
        showNotification('warning', 'No hay conexión con el servidor WebSocket');
        return;
    }
    
    if (!isConnected) {
        showNotification('warning', 'Arduino no está conectado');
        return;
    }
    
    showNotification('info', `Ejecutando secuencia: ${sequence.name}`);
    
    socket.emit('run_sequence', { sequence: sequence }, function(response) {
        // La respuesta final se maneja en el evento 'run_sequence_result'
        console.log('Enviada solicitud para ejecutar secuencia');
    });
}

// Función para actualizar la UI de conexión
function updateConnectionUI(data) {
    isConnected = data.is_connected;
    connectionInfo = data;
    
    // Actualizar estado de conexión en la UI
    updateConnectionStatusUI(
        isConnected ? 'Conectado' : 'Desconectado',
        isConnected
    );
    
    // Actualizar campos de la UI según el tipo de conexión
    if (isConnected) {
        if (data.connection_type === 'wifi') {
            // Si hay campos para conexión WiFi, actualizarlos
            if (document.getElementById('esp32-ip')) {
                document.getElementById('esp32-ip').value = data.host || '';
            }
            if (document.getElementById('esp32-port')) {
                document.getElementById('esp32-port').value = data.port || 8888;
            }
            
            // Seleccionar radio button de WiFi si existe
            if (document.getElementById('connection-wifi')) {
                document.getElementById('connection-wifi').checked = true;
                toggleConnectionForm();
            }
        } else {
            // Si hay campo para puerto serie, actualizarlo
            if (document.getElementById('arduino-port')) {
                document.getElementById('arduino-port').value = data.serial_port || 'COM12';
            }
            
            // Seleccionar radio button de conexión directa si existe
            if (document.getElementById('connection-direct')) {
                document.getElementById('connection-direct').checked = true;
                toggleConnectionForm();
            }
        }
    }
}

// Función para actualizar la UI del estado de conexión
function updateConnectionStatusUI(status, connected) {
    const statusElements = document.querySelectorAll('#connection-status');
    
    statusElements.forEach(element => {
        // Limpiar clases previas
        element.classList.remove('badge-secondary', 'badge-danger', 'badge-success', 'badge-warning');
        
        // Establecer texto y clase según estado
        element.textContent = status;
        
        if (connected === null) { // Conectando...
            element.classList.add('badge-warning');
        } else if (connected) {
            element.classList.add('badge-success');
        } else {
            element.classList.add('badge-danger');
        }
    });
}

// Función para manejar el resultado de conexión
function handleConnectionResult(data) {
    if (data.status === 'success') {
        updateConnectionUI(data.connection_info);
        showNotification('success', data.message);
    } else {
        updateConnectionStatusUI('Desconectado', false);
        showNotification('danger', data.message);
    }
}

// Función para manejar el resultado de reset
function handleResetResult(data) {
    if (data.status === 'success') {
        showNotification('success', data.message);
        updateAllServosUI();
    } else {
        showNotification('danger', data.message);
    }
}

// Función para manejar el resultado de ejecución de secuencia
function handleSequenceResult(data) {
    if (data.status === 'success') {
        showNotification('success', data.message);
    } else {
        showNotification('danger', data.message || 'Error al ejecutar secuencia');
        if (data.details && data.details.length) {
            console.error('Detalles del error:', data.details);
        }
    }
}

// Función para actualizar todos los sliders de servo a 90°
function updateAllServosUI() {
    // Esta función debe implementarse en cada vista específica
    // que tenga controles de servo
    if (typeof updateAllServosToDefaultPosition === 'function') {
        updateAllServosToDefaultPosition();
    }
}

// Función para mostrar notificaciones
function showNotification(type, message) {
    if (typeof $.notify === 'function') {
        $.notify({
            icon: type === 'success' ? 'tim-icons icon-check-2' : 'tim-icons icon-alert-circle-exc',
            message: message
        }, {
            type: type,
            timer: 4000,
            placement: {
                from: 'top',
                align: 'right'
            }
        });
    } else {
        // Fallback si $.notify no está disponible
        console.log(`Notificación [${type}]: ${message}`);
        alert(`${message}`);
    }
}

// Función para alternar entre formularios de conexión
function toggleConnectionForm() {
    const directForm = document.getElementById('direct-connection-form');
    const wifiForm = document.getElementById('wifi-connection-form');
    
    if (!directForm || !wifiForm) {
        return; // No están presentes ambos formularios
    }
    
    const useWifi = document.getElementById('connection-wifi').checked;
    
    if (useWifi) {
        directForm.style.display = 'none';
        wifiForm.style.display = 'block';
    } else {
        directForm.style.display = 'block';
        wifiForm.style.display = 'none';
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar Socket.IO
    initSocketIO();
    
    // Configurar event listeners para controles de conexión si existen
    if (document.getElementById('connection-direct')) {
        document.getElementById('connection-direct').addEventListener('change', toggleConnectionForm);
    }
    
    if (document.getElementById('connection-wifi')) {
        document.getElementById('connection-wifi').addEventListener('change', toggleConnectionForm);
    }
    
    if (document.getElementById('connect-direct-button')) {
        document.getElementById('connect-direct-button').addEventListener('click', function() {
            const port = document.getElementById('arduino-port').value;
            connectToArduino(false, port);
        });
    }
    
    if (document.getElementById('connect-wifi-button')) {
        document.getElementById('connect-wifi-button').addEventListener('click', function() {
            const host = document.getElementById('esp32-ip').value;
            const port = document.getElementById('esp32-port').value;
            connectToArduino(true, null, host, port);
        });
    }
    
    if (document.getElementById('reset-all')) {
        document.getElementById('reset-all').addEventListener('click', resetAllServos);
    }
});