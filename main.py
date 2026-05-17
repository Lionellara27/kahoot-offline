from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import time  # Reloj de alta precisión para medir los tiempos de respuesta de los chicos

from database import inicializar_db, obtener_todas_las_preguntas

app = FastAPI()

# 1. Inicializamos la base de datos relacional (SQLite)
inicializar_db()

# 2. Montamos la carpeta de recursos estáticos (para servir el logo del CET N°11)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 3. Cargamos los frontend limpios desde sus archivos HTML independientes
with open("templates/jugador.html", "r", encoding="utf-8") as f:
    HTML_PLAYER = f.read()

with open("templates/host.html", "r", encoding="utf-8") as f:
    HTML_HOST = f.read()


# --- GESTOR DE CONEXIONES Y LÓGICA CENTRAL DEL JUEGO (PERSISTENTE) ---
class AdministradorJuego:
    def __init__(self):
        self.host_socket: WebSocket = None
        # 🔌 Diccionario volátil: mapea solo conexiones web activas { websocket: "Nombre" }
        self.conexiones = {}       
        # 🏆 Diccionario persistente: retiene puntajes { "Nombre": {"puntos": int, "tiempo_total": float} }
        self.ranking = {}          
        
        self.preguntas = obtener_todas_las_preguntas()
        self.indice_pregunta_actual = -1
        self.tiempo_inicio_pregunta = 0.0

    async def conectar_host(self, websocket: WebSocket):
        await websocket.accept()
        self.host_socket = websocket
        print("🖥️ ¡Pantalla Principal (Host) conectada con éxito!")
        await self.enviar_ranking_actualizado()

    async def conectar_jugador(self, websocket: WebSocket, nombre: str):
        await websocket.accept()
        # Registramos la nueva conexión física del celular
        self.conexiones[websocket] = nombre
        
        # 🔥 CONTROL DE PERSISTENCIA:
        # Si el alumno es nuevo, le creamos el perfil desde cero.
        if nombre not in self.ranking:
            self.ranking[nombre] = {
                "puntos": 0,
                "tiempo_total": 0.0
            }
            print(f"📱 El alumno '{nombre}' se ha unido por primera vez.")
        else:
            # Si ya existía en el ranking, conserva sus puntos intactos!
            print(f"🔄 ¡Reconexión detectada! El alumno '{nombre}' recuperó su sesión y sus puntos.")
            
        await self.enviar_ranking_actualizado()

    async def desconectar_jugador(self, websocket: WebSocket):
        if websocket in self.conexiones:
            nombre = self.conexiones[websocket]
            # Borramos únicamente el WebSocket físico del listado de antenas activas
            del self.conexiones[websocket] 
            print(f"⚠️ '{nombre}' cerró el celu o perdió señal temporalmente. Sus puntos quedan guardados.")
            
            # ⛔ CRÍTICO: NO borramos nada de self.ranking. 
            # El alumno se mantiene visible en la TV con sus puntos intactos.
            await self.enviar_ranking_actualizado()
    async def avanzar_pregunta(self):
        if not self.preguntas:
            print("⚠️ No hay preguntas cargadas en la base de datos.")
            return
        
        self.indice_pregunta_actual += 1
        
        # 🔥 CONTROL DE FIN DE JUEGO: Si pasamos la última pregunta (índice 10), el juego termina
        if self.indice_pregunta_actual >= len(self.preguntas):
            if self.host_socket:
                await self.host_socket.send_text(json.dumps({
                    "evento": "JUEGO_TERMINADO"
                }))
            return
            
        pregunta = self.preguntas[self.indice_pregunta_actual]
        self.tiempo_inicio_pregunta = time.time() 
        
        # 🖥️ Enviamos al Host con el contador de progreso y LA RESPUESTA CORRECTA oculta
        if self.host_socket:
            await self.host_socket.send_text(json.dumps({
                "evento": "MOSTRAR_PREGUNTA",
                "enunciado": pregunta["enunciado"],
                "opcion_a": pregunta["opcion_a"],
                "opcion_b": pregunta["opcion_b"],
                "numero_actual": self.indice_pregunta_actual + 1,
                "total": len(self.preguntas),
                "correcta": pregunta["correcta"] # 🔥 Clave: el navegador del host la guarda pero no la muestra todavía
            }))

        # 📱 Broadcast masivo a los celulares pasándole el texto completo
        for cliente_ws in self.conexiones.keys():
            try:
                await cliente_ws.send_text(json.dumps({
                    "evento": "NUEVA_PREGUNTA",
                    "enunciado": pregunta["enunciado"],
                    "opcion_a": pregunta["opcion_a"],
                    "opcion_b": pregunta["opcion_b"]
                }))
            except:
                pass

    async def procesar_voto(self, opcion_elegida: str, websocket: WebSocket):
        if websocket not in self.conexiones or self.indice_pregunta_actual == -1:
            return
            
        tiempo_respuesta = time.time() - self.tiempo_inicio_pregunta
        pregunta = self.preguntas[self.indice_pregunta_actual]
        
        nombre = self.conexiones[websocket]
        jugador = self.ranking[nombre]

        if opcion_elegida == pregunta["correcta"]:
            jugador["puntos"] += 10  
            jugador["tiempo_total"] += tiempo_respuesta  
        else:
            jugador["tiempo_total"] += 10.0 

        # ✅ ACÁ YA NO HAY NADA MÁS. No se envía ningún mensaje de revelar al Host.
        await self.enviar_ranking_actualizado()

    async def enviar_ranking_actualizado(self):
        if not self.host_socket:
            return
            
        lista_ranking = []
        for nombre, datos in self.ranking.items():
            lista_ranking.append({
                "nombre": nombre,
                "puntos": datos["puntos"],
                "tiempo_total": datos["tiempo_total"]
            })
        
        lista_ranking.sort(key=lambda x: (x["puntos"], -x["tiempo_total"]), reverse=True)
        
        ranking_limpio = [
            {"nombre": j["nombre"], "puntos": j["puntos"], "tiempo": j["tiempo_total"]}
            for j in lista_ranking
        ]
        
        await self.host_socket.send_text(json.dumps({
            "evento": "ACTUALIZAR_RANKING",
            "ranking": ranking_limpio
        }))

controlador = AdministradorJuego()
# --- ENDPOINTS HTTP (Capa de Presentación) ---
@app.get("/host")
def vista_host():
    return HTMLResponse(content=HTML_HOST)

@app.get("/")
def vista_jugador():
    return HTMLResponse(content=HTML_PLAYER)


# --- ENDPOINTS WEBSOCKETS (Capa de Comunicación Asíncrona) ---
@app.websocket("/ws/host")
async def ws_host(websocket: WebSocket):
    await controlador.conectar_host(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            datos = json.loads(msg)
            # Escuchamos si el anfitrión hace clic en el botón de pasar de pregunta
            if datos.get("accion") == "SIGUIENTE_PREGUNTA":
                await controlador.avanzar_pregunta()
    except WebSocketDisconnect:
        controlador.host_socket = None
        print("🖥️ La Pantalla Principal (Host) se ha desconectado.")

@app.websocket("/ws/jugador")
async def ws_jugador(websocket: WebSocket, nombre: str = Query(...)):
    # Capturamos el parámetro 'nombre' enviado por el alumno desde el formulario de bienvenida
    await controlador.conectar_jugador(websocket, nombre)
    try:
        while True:
            opcion = await websocket.receive_text()
            await controlador.procesar_voto(opcion, websocket)
    except WebSocketDisconnect:
        await controlador.desconectar_jugador(websocket)