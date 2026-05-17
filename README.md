# 🎮 Kahoot Offline (Sistema de Trivia en Tiempo Real)

Un clon de Kahoot diseñado para funcionar en entornos **completamente offline** (sin acceso a internet). Utiliza la infraestructura de una red local (LAN) para conectar los dispositivos de los jugadores directamente a una computadora central que actúa como servidor.

## 🚀 Tecnologías Utilizadas

- **Backend:** Python 3.12 + FastAPI (Asíncrono y de alto rendimiento).
- **Tiempo Real:** WebSockets nativos (comunicación bidireccional con latencia cero).
- **Base de Datos:** SQLite3 (Base de datos relacional local en un archivo `.db`, sin instalaciones externas).
- **Frontend:** HTML5, CSS3 y JavaScript Vanilla (sin frameworks, ideal para máxima compatibilidad con celulares viejos).

---

## 💻 Configuración e Instalación

1. **Clonar o descargar** este repositorio en tu máquina local.
2. Instalar las dependencias necesarias ejecutando en la terminal:
   ```bash
   python -m pip install fastapi uvicorn websockets
⚙️ Cómo ponerlo en marcha
Crear la red local: Activa la "Zona con cobertura inalámbrica" (Hotspot) de tu notebook o asegúrate de que todos los dispositivos estén conectados a la misma red Wi-Fi.

Iniciar el servidor: Corre el siguiente comando en la raíz del proyecto para levantar Uvicorn escuchando en toda la red local:
   ```bash
   python -m uvicorn main:app --reload --host 0.0.0.0
   ```
Averiguar la IP local: Abre otra terminal y ejecuta **ipconfig** para conocer tu dirección IPv4 local (ejemplo: 192.168.1.4).

🎮 Acceso a las Pantallas
El sistema cuenta con dos interfaces diferenciadas según el rol:

1. 🖥️ Vista del Anfitrión (Host)
Es la pantalla principal que se proyecta en la TV, notebook o proyector. Muestra las preguntas, el tiempo y el ranking.

URL Local: http://localhost:8000/host -> ej:http://10.34.51.173:8000/host (anfitrion)

2. 📱 Vista del Jugador (Cliente)
Es la interfaz optimizada para celulares que actúa como control remoto para responder la trivia.

URL desde la Red LAN: http://<TU_IP_LOCAL>:8000 (Ejemplo: http://192.168.X.X:8000) -> ej:http://10.34.51.173:8000 (chicos)

📌 Estado Actual del Proyecto

[x] Fase 1: Infraestructura de red local (LAN) y comunicación HTTP.

[x] Fase 2: Arquitectura en tiempo real con WebSockets para envío de respuestas.

[x] Fase 3: Persistencia local de datos con SQLite3 y carga de preguntas semilla.

[x] Fase 4: Lógica de juego (Sincronización de turnos, contador de tiempo y puntajes).