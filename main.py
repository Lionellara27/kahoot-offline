from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import json
import time 

from database import inicializar_db, obtener_todas_las_preguntas

app = FastAPI()

inicializar_db()
app.mount("/static", StaticFiles(directory="static"), name="static")

with open("templates/jugador.html", "r", encoding="utf-8") as f:
    HTML_PLAYER = f.read()

with open("templates/host.html", "r", encoding="utf-8") as f:
    HTML_HOST = f.read()

class AdministradorJuego:
    def __init__(self):
        self.host_socket: WebSocket = None
        self.conexiones = {}       
        self.ranking = {}          
        self.preguntas = obtener_todas_las_preguntas()
        self.indice_pregunta_actual = -1
        self.tiempo_inicio_pregunta = 0.0
        
        # Contadores por ronda
        self.votos_correctos = 0
        self.votos_incorrectos = 0
        
        # Contadores globales para el gráfico final
        self.global_correctos = 0
        self.global_incorrectos = 0

    async def conectar_host(self, websocket: WebSocket):
        await websocket.accept()
        self.host_socket = websocket
        await self.enviar_ranking_actualizado()

    async def conectar_jugador(self, websocket: WebSocket, nombre: str):
        await websocket.accept()
        self.conexiones[websocket] = nombre
        if nombre not in self.ranking:
            self.ranking[nombre] = {"puntos": 0, "tiempo_total": 0.0}
        await self.enviar_ranking_actualizado()

    async def desconectar_jugador(self, websocket: WebSocket):
        if websocket in self.conexiones:
            del self.conexiones[websocket] 
            await self.enviar_ranking_actualizado()
    async def avanzar_pregunta(self):
        if not self.preguntas:
            return
        
        self.votos_correctos = 0
        self.votos_incorrectos = 0
        self.indice_pregunta_actual += 1
        
        # 🏁 --- CONTROL DE FIN DE JUEGO (SECCIÓN CORREGIDA) ---
        if self.indice_pregunta_actual >= len(self.preguntas):
            # 1. Le avisamos al Host (Mantiene las estadísticas de Aylin para el gráfico final)
            if self.host_socket:
                await self.host_socket.send_text(json.dumps({
                    "evento": "JUEGO_TERMINADO",
                    "total_ok": self.global_correctos,
                    "total_err": self.global_incorrectos
                }))
            
            # 2. 🎯 ¡EL FIX! Recorremos cada celu activo y le inyectamos su puntaje real de 'self.ranking'
            for cliente_ws, nombre in self.conexiones.items():
                try:
                    jugador_data = self.ranking.get(nombre, {"puntos": 0})
                    await cliente_ws.send_text(json.dumps({
                        "evento": "JUEGO_TERMINADO",
                        "puntos": jugador_data["puntos"]
                    }))
                except:
                    pass
            return
        # --------------------------------------------------------
            
        pregunta = self.preguntas[self.indice_pregunta_actual]
        self.tiempo_inicio_pregunta = time.time() 
        
        if self.host_socket:
            await self.host_socket.send_text(json.dumps({
                "evento": "MOSTRAR_PREGUNTA",
                "enunciado": pregunta["enunciado"],
                "opcion_a": pregunta["opcion_a"],
                "opcion_b": pregunta["opcion_b"],
                "numero_actual": self.indice_pregunta_actual + 1,
                "total": len(self.preguntas),
                "correcta": pregunta["correcta"],
                "justificacion": pregunta["justificacion"]
            }))

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
            self.votos_correctos += 1
            self.global_correctos += 1 # Suma al histórico
        else:
            jugador["tiempo_total"] += 20.0 
            self.votos_incorrectos += 1
            self.global_incorrectos += 1 # Suma al histórico

        if self.host_socket:
            await self.host_socket.send_text(json.dumps({
                "evento": "ESTADISTICAS_VOTOS",
                "correctos": self.votos_correctos,
                "incorrectos": self.votos_incorrectos
            }))

        await self.enviar_ranking_actualizado()

    async def revelar_resultados(self):
        if self.indice_pregunta_actual >= 0 and self.indice_pregunta_actual < len(self.preguntas):
            correcta = self.preguntas[self.indice_pregunta_actual]["correcta"]
            for cliente_ws in self.conexiones.keys():
                try:
                    await cliente_ws.send_text(json.dumps({
                        "evento": "REVELAR_CORRECTA",
                        "correcta": correcta
                    }))
                except:
                    pass

    async def enviar_ranking_actualizado(self):
        if not self.host_socket:
            return
        lista_ranking = []
        for nombre, datos in self.ranking.items():
            lista_ranking.append({"nombre": nombre, "puntos": datos["puntos"], "tiempo_total": datos["tiempo_total"]})
        lista_ranking.sort(key=lambda x: (x["puntos"], -x["tiempo_total"]), reverse=True)
        ranking_limpio = [{"nombre": j["nombre"], "puntos": j["puntos"], "tiempo": j["tiempo_total"]} for j in lista_ranking]
        await self.host_socket.send_text(json.dumps({"evento": "ACTUALIZAR_RANKING", "ranking": ranking_limpio}))

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
            if datos.get("accion") == "SIGUIENTE_PREGUNTA":
                await controlador.avanzar_pregunta()
            elif datos.get("accion") == "REVELAR_RESULTADOS":
                await controlador.revelar_resultados()
    except WebSocketDisconnect:
        controlador.host_socket = None

@app.websocket("/ws/jugador")
async def ws_jugador(websocket: WebSocket, nombre: str = Query(...)):
    await controlador.conectar_jugador(websocket, nombre)
    try:
        while True:
            opcion = await websocket.receive_text()
            await controlador.procesar_voto(opcion, websocket)
    except WebSocketDisconnect:
        await controlador.desconectar_jugador(websocket)