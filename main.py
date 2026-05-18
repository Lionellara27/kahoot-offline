from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import json
import time # Reloj -> esto para medir el tiempo que tardan en responder los chicos

from database import inicializar_db, obtener_preguntas_por_nivel, obtener_lista_niveles

app = FastAPI()
#aca se inicializa la BD (SQLite)
inicializar_db()

#colocamos los recursos estaticos! (logo del CET CET N°11 y unrn)
app.mount("/static", StaticFiles(directory="static"), name="static")

#Cargamos los frontend limpios desde sus archivos HTML independientes
with open("templates/jugador.html", "r", encoding="utf-8") as f:
    HTML_PLAYER = f.read()

with open("templates/host.html", "r", encoding="utf-8") as f:
    HTML_HOST = f.read()

with open("templates/admin_crear.html", "r", encoding="utf-8") as f:
    HTML_CREAR = f.read()

with open("templates/admin_modificar.html", "r", encoding="utf-8") as f:
    HTML_MODIFICAR = f.read()

with open("templates/admin_eliminar.html", "r", encoding="utf-8") as f:
    HTML_ELIMINAR = f.read()

# GESTOR DE CONEXIONES Y LÓGICA CENTRAL DEL JUEGO (PERSISTENTE)
class AdministradorJuego:
    def __init__(self):
        self.host_socket: WebSocket = None
        # -> Diccionario volátil: mapea solo conexiones web activas { websocket: "Nombre" }
        self.conexiones = {}
        # -> Diccionario persistente: retiene puntajes { "Nombre": {"puntos": int, "tiempo_total": float} }
        self.ranking = {}    
        
        self.preguntas = []
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
        print("🖥️ ¡Pantalla Principal (Host) conectada con éxito!") #para ver en consola si todo va bien
        await self.enviar_ranking_actualizado()

    async def conectar_jugador(self, websocket: WebSocket, nombre: str):
        await websocket.accept()
        # Registramos la nueva conexión física del celular/notebook
        self.conexiones[websocket] = nombre

        # -->CONTROL DE PERSISTENCIA:
        # Si el alumno es nuevo, le creamos el perfil desde cero.
        if nombre not in self.ranking:
            self.ranking[nombre] = {"puntos": 0, "tiempo_total": 0.0}
            print(f"📱📱 El alumno '{nombre}' se ha unido por primera vez.") #uso el emoji y el print para saber de donde se conecta y que hace
        else:
            # Si ya existía en el ranking, conserva sus puntos intactos!
            print(f"🔄🔄 ¡Reconexión detectada! El alumno '{nombre}' recuperó su sesión y sus puntos.")
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
        
        # CONTROL DE FIN DE JUEGO (SECCIÓN CORREGIDA by:Lio) si llegamos a la ultilima pregunta termina
        if self.indice_pregunta_actual >= len(self.preguntas):
            #PRIMERO 1. Avisamos al Host para que muestre el podio definitivo en la TV(osea mostrar pantalla host)
            if self.host_socket:
                await self.host_socket.send_text(json.dumps({
                    "evento": "JUEGO_TERMINADO",
                    "total_ok": self.global_correctos,
                    "total_err": self.global_incorrectos
                }))
            
            #SEGUNDO 2. Recorremos cada celular/notebook conectado y le mandamos su puntaje final personalizado
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
            
        pregunta = self.preguntas[self.indice_pregunta_actual]
        self.tiempo_inicio_pregunta = time.time() 

        # Enviamos al Host con el contador de progreso y LA RESPUESTA CORRECTA oculta
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
            
        # "DIFUNDIMOS" A TODOS los celulares pasándole el texto completo
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
            
        # ACÁ YA NO HAY NADA MÁS. No se envía ningún mensaje de revelar al Host.
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

# =====================================================================
# 🛡️ CAPA DE SEGURIDAD Y PANEL DOCENTE CENTRAL
# =====================================================================
CLAVE_DOCENTE = "Esfa2026Esfa"  # Clave maestra para el taller

@app.get("/login")
def vista_login():
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><title>Login Docente</title>
        <style>
            body { font-family: Arial; background: #1a1a1a; color: white; text-align: center; padding-top: 100px; }
            .caja { max-width: 350px; margin: 0 auto; background: #2a2a2a; padding: 30px; border-radius: 12px; border: 1px solid #444; }
            input { width: 90%; padding: 10px; margin: 15px 0; border-radius: 6px; border: 1px solid #555; background: #333; color: white; text-align: center; }
            button { background: #008CBA; color: white; padding: 10px; border: none; border-radius: 6px; width: 95%; font-weight: bold; cursor: pointer; }
        </style>
    </head>
    <body>
        <div class="caja">
            <h2>🔐 Panel Docente</h2>
            <form action="/login" method="post">
                <input type="password" name="clave" placeholder="Contraseña..." required autocomplete="off">
                <button type="submit">Ingresar</button>
            </form>
        </div>
    </body>
    </html>
    """)

@app.post("/login")
def procesar_login(clave: str = Form(...)):
    if clave == CLAVE_DOCENTE:
        respuesta = RedirectResponse(url="/panel", status_code=303)
        respuesta.set_cookie(key="autorizado", value="si", httponly=True)
        return respuesta
    return HTMLResponse(content="<script>alert('❌ Clave incorrecta'); window.location='/login';</script>")

@app.get("/panel")
def vista_panel(autorizado: str = Cookie(None)):
    if autorizado != "si":
        return RedirectResponse(url="/login", status_code=303)
        
    # 📊 Leemos la realidad de la Base de Datos
    niveles_existentes = obtener_lista_niveles() 
    cantidad_actual = len(niveles_existentes)
    
    # 🚫 Control del límite: Si hay 5, bloqueamos el botón con CSS/disabled
    boton_crear_deshabilitado = "disabled style='background:#555; cursor:not-allowed;'" if cantidad_actual >= 5 else ""

    # 🎮 Generamos los botones de juego dinámicamente según los niveles reales
    botones_juego_html = ""
    for n in niveles_existentes:
        botones_juego_html += f'<a href="/host?nivel={n}" class="btn">🎮 Jugar Nivel {n}</a>'
    
    if not botones_juego_html:
        botones_juego_html = "<p style='color:#aaa;'>No hay niveles creados. ¡Crea el primero arriba!</p>"

    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"><title>Panel de Control</title>
        <style>
            body {{ font-family: Arial; background: #1a1a1a; color: white; text-align: center; padding-top: 40px; }}
            .row-ops {{ display: flex; justify-content: center; gap: 15px; margin-bottom: 30px; }}
            .btn-op {{ background: #E74C3C; color: white; padding: 15px 25px; border-radius: 8px; text-decoration: none; font-weight: bold; font-size: 16px; border: none; cursor: pointer; }}
            .btn {{ display: inline-block; background: #4CAF50; color: white; padding: 20px; margin: 10px; border-radius: 10px; text-decoration: none; font-weight: bold; font-size: 18px; min-width: 180px; }}
            .contador {{ font-size: 18px; color: #ffeb3b; font-weight: bold; margin-bottom: 20px; }}
        </style>
    </head>
    <body>
        <h1>🎛️ Panel de Control - Selección de Trivia</h1>
        
        <div class="row-ops">
            <button onclick="window.location='/admin/crear'" class="btn-op" {boton_crear_deshabilitado}>📄 Crear NIVEL</button>
            <button onclick="window.location='/admin/modificar'" class="btn-op" style="background:#d35400;">📝 Modificar Nivel</button>
            <button onclick="window.location='/admin/eliminar'" class="btn-op" style="background:#c0392b;">🗑️ Eliminar Nivel</button>
        </div>

        <div class="contador">Niveles creados: {cantidad_actual}/5</div>
        
        <hr style="border-color: #333; max-width: 800px; margin: 30px auto;">
        
        <p>Elegí qué nivel vas a lanzar en el proyector:</p>
        <div>
            {botones_juego_html}
        </div>
    </body>
    </html>
    """)


# =====================================================================
# 🖥️ VISTAS HTTP DE INTERFAZ DE JUEGO (PÚBLICA Y PROTEGIDA)
# =====================================================================

@app.get("/")
def vista_jugador():
    """ 📱 Celulares de los chicos: entran directo sin clave """
    return HTMLResponse(content=HTML_PLAYER)

@app.get("/host")
def vista_host(autorizado: str = Cookie(None)):
    """ 🖥️ Pantalla del Proyector: Protegida estrictamente por el escudo """
    if autorizado != "si":
        return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content=HTML_HOST)


# =====================================================================
# 🗂️ VISTAS ADMINISTRATIVAS (GET HTML)
# =====================================================================

@app.get("/admin/crear")
def vista_admin_crear(autorizado: str = Cookie(None)):
    if autorizado != "si": return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content=HTML_CREAR)

@app.get("/admin/modificar")
def vista_admin_modificar(autorizado: str = Cookie(None)):
    if autorizado != "si": return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content=HTML_MODIFICAR)

@app.get("/admin/eliminar")
def vista_admin_eliminar(autorizado: str = Cookie(None)):
    if autorizado != "si": return RedirectResponse(url="/login", status_code=303)
    return HTMLResponse(content=HTML_ELIMINAR)


# =====================================================================
# 🔌 ENDPOINTS API (Para las peticiones Fetch de JavaScript)
# =====================================================================

@app.get("/admin/api/niveles")
def api_lista_niveles(autorizado: str = Cookie(None)):
    if autorizado != "si": return {"error": "No autorizado"}
    return obtener_lista_niveles()

@app.get("/admin/api/preguntas")
def api_traer_preguntas(nivel: int, autorizado: str = Cookie(None)):
    if autorizado != "si": return {"error": "No autorizado"}
    return obtener_preguntas_por_nivel(nivel)


# =====================================================================
# 💾 PROCESAMIENTO DE DATOS (POST)
# =====================================================================
from database import insertar_preguntas_lote, eliminar_nivel_completo
from fastapi import Request

@app.post("/admin/guardar-lote")
async def procesar_guardar_lote(request: Request, autorizado: str = Cookie(None)):
    if autorizado != "si": return RedirectResponse(url="/login", status_code=303)
    
    form_data = await request.form()
    nivel = int(form_data.get("nivel"))
    
    enunciados = form_data.getlist("enunciado")
    opciones_a = form_data.getlist("opcion_a")
    opciones_b = form_data.getlist("opcion_b")
    correctas = form_data.getlist("correcta")
    justificaciones = form_data.getlist("justificacion")
    
    lote_preguntas = []
    for i in range(len(enunciados)):
        lote_preguntas.append((
            nivel,
            f"PREG-{i+1:02d}",
            enunciados[i],
            opciones_a[i],
            opciones_b[i],
            correctas[i],
            justificaciones[i]
        ))
    
    insertar_preguntas_lote(lote_preguntas)
    return RedirectResponse(url="/panel", status_code=303)


@app.post("/admin/actualizar-lote")
async def procesar_actualizar_lote(request: Request, autorizado: str = Cookie(None)):
    if autorizado != "si": return RedirectResponse(url="/login", status_code=303)
    
    form_data = await request.form()
    nivel = int(form_data.get("nivel"))
    
    enunciados = form_data.getlist("enunciado")
    opciones_a = form_data.getlist("opcion_a")
    opciones_b = form_data.getlist("opcion_b")
    correctas = form_data.getlist("correcta")
    justificaciones = form_data.getlist("justificacion")
    
    lote_actualizado = []
    for i in range(len(enunciados)):
        lote_actualizado.append((
            nivel, f"PREG-{i+1:02d}", enunciados[i], opciones_a[i], opciones_b[i], correctas[i], justificaciones[i]
        ))
    
    # Aplicamos Delete & Replace para actualizar limpiamente
    eliminar_nivel_completo(nivel)
    insertar_preguntas_lote(lote_actualizado)
    
    return RedirectResponse(url="/panel", status_code=303)


@app.post("/admin/eliminar-lote")
async def procesar_eliminar_lote(nivel: int = Form(...), autorizado: str = Cookie(None)):
    if autorizado != "si": return RedirectResponse(url="/login", status_code=303)
    
    eliminar_nivel_completo(nivel)
    return RedirectResponse(url="/panel", status_code=303)

    # =====================================================================
# 🔌 ENDPOINTS WEBSOCKETS (Capa de Comunicación Asíncrona)
# =====================================================================

@app.websocket("/ws/host")
async def ws_host(websocket: WebSocket, nivel: int = 1): # 🎯 Ahora recibe el nivel dinámico de la TV
    
    # 💥 Pisanos las preguntas del juego con las del nivel elegido antes de conectar
    controlador.preguntas = obtener_preguntas_por_nivel(nivel)
    controlador.indice_pregunta_actual = -1 # Reseteamos por seguridad
    
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
    # 📱 Los celus se conectan acá y esperan lo que mande el controlador
    await controlador.conectar_jugador(websocket, nombre)
    try:
        while True:
            opcion = await websocket.receive_text()
            await controlador.procesar_voto(opcion, websocket)
    except WebSocketDisconnect:
        await controlador.desconectar_jugador(websocket)