from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import json

# Importamos las funciones de nuestro nuevo archivo de base de datos
from database import inicializar_db, obtener_todas_las_preguntas

app = FastAPI()

# Inicializamos la base de datos local al arrancar el servidor
inicializar_db()

# --- GESTOR DE CONEXIONES (El Corazón de la Red) ---
class AdministradorJuego:
    def __init__(self):
        self.host_socket: WebSocket = None  # Guardamos la conexión de la notebook
        self.jugadores_activos = {}         # Diccionario de {websocket: nombre_jugador}

    async def conectar_host(self, websocket: WebSocket):
        await websocket.accept()
        self.host_socket = websocket
        print("🖥️ ¡Pantalla Principal (Host) conectada con éxito!")

    async def conectar_jugador(self, websocket: WebSocket):
        await websocket.accept()
        # Le asignamos un nombre provisorio por ahora basado en su puerto
        nombre = f"Jugador_{websocket.client.port}"
        self.jugadores_activos[websocket] = nombre
        print(f"📱 {nombre} se ha unido al juego.")
        
        # Le avisamos al Host que entró alguien nuevo si el Host está conectado
        if self.host_socket:
            await self.host_socket.send_text(json.dumps({
                "evento": "NUEVO_JUGADOR",
                "jugador": nombre
            }))

    def desconectar_jugador(self, websocket: WebSocket):
        if websocket in self.jugadores_activos:
            nombre = self.jugadores_activos[websocket]
            del self.jugadores_activos[websocket]
            print(f"❌ {nombre} abandonó la partida.")

    async def enviar_voto_al_host(self, opcion_elegida: str, websocket: WebSocket):
        nombre = self.jugadores_activos.get(websocket, "Anónimo")
        if self.host_socket:
            # Le mandamos el voto masticado en JSON a la pantalla principal
            await self.host_socket.send_text(json.dumps({
                "evento": "VOTO",
                "jugador": nombre,
                "opcion": opcion_elegida
            }))

controlador = AdministradorJuego()

# --- VISTAS HTML (Interfaces de prueba) ---

HTML_HOST = """
<!DOCTYPE html>
<html>
<head>
    <title>Kahoot Offline - PANTALLA PRINCIPAL</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #111; color: white; padding: 30px; text-align: center; }
        #lista-jugadores { display: flex; justify-content: center; gap: 15px; font-size: 20px; color: #00fa9a; }
        #consola-votos { margin-top: 30px; padding: 20px; background: #222; border-radius: 10px; height: 200px; overflow-y: auto; text-align: left; }
    </style>
</head>
<body>
    <h1>🖥️ PANTALLA PRINCIPAL (Notebook / TV)</h1>
    <h2>Jugadores en la sala:</h2>
    <div id="lista-jugadores">Esperando jugadores...</div>
    
    <h3>📥 Registro de Respuestas en Tiempo Real:</h3>
    <div id="consola-votos"></div>

    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws/host`);
        const lista = document.getElementById("lista-jugadores");
        const consola = document.getElementById("consola-votos");
        let jugadores = [];

        ws.onmessage = (event) => {
            const datos = JSON.parse(event.data);
            
            if (datos.evento === "NUEVO_JUGADOR") {
                jugadores.push(datos.jugador);
                lista.innerHTML = jugadores.map(j => `<span>👤 ${j}</span>`).join(" | ");
            }
            
            if (datos.evento === "VOTO") {
                consola.innerHTML += `<p style="color: #ffeb3b">📩 <b>${datos.jugador}</b> respondió la opción: <b>${datos.opcion}</b></p>`;
            }
        };
    </script>
</body>
</html>
"""

HTML_PLAYER = """
<!DOCTYPE html>
<html>
<head>
    <title>Kahoot Offline - CONTROL</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background-color: #222; color: white; padding: 20px; }
        .grid-botones { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 40px; }
        .btn { padding: 40px 20px; font-size: 24px; font-weight: bold; border: none; border-radius: 12px; color: white; cursor: pointer; }
        .red { background-color: #e21b3c; }
        .blue { background-color: #1368ce; }
    </style>
</head>
<body>
    <h2>🎮 Tu Control</h2>
    <p>Elegí la opción correcta rápido:</p>
    
    <div class="grid-botones">
        <button class="btn red" onclick="enviarVoto('A')">▲ A</button>
        <button class="btn blue" onclick="enviarVoto('B')">■ B</button>
    </div>

    <script>
        const ws = new WebSocket(`ws://${window.location.host}/ws/jugador`);
        
        function enviarVoto(opcion) {
            ws.send(opcion);
        }
    </script>
</body>
</html>
"""

# --- ENDPOINTS HTTP ---
@app.get("/host")
def vista_host():
    return HTMLResponse(content=HTML_HOST)

@app.get("/")
def vista_jugador():
    return HTMLResponse(content=HTML_PLAYER)

# --- ENDPOINTS WEBSOCKETS ---
@app.websocket("/ws/host")
async def ws_host(websocket: WebSocket):
    await controlador.conectar_host(websocket)
    try:
        while True:
            await websocket.receive_text()  # Mantenemos el canal abierto
    except WebSocketDisconnect:
        controlador.host_socket = None
        print("🖥️ El Host se desconectó.")

@app.websocket("/ws/jugador")
async def ws_jugador(websocket: WebSocket):
    await controlador.conectar_jugador(websocket)
    try:
        while True:
            opcion = await websocket.receive_text()
            await controlador.enviar_voto_al_host(opcion, websocket)
    except WebSocketDisconnect:
        controlador.desconectar_jugador(websocket)