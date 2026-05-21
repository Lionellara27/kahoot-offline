from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, Form, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
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
        print("🖥️ ¡Pantalla Principal (Host) conectada con éxito!") 
        await self.enviar_ranking_actualizado()

    async def conectar_jugador(self, websocket: WebSocket, nombre: str):
        await websocket.accept()
        self.conexiones[websocket] = nombre

        if nombre not in self.ranking:
            self.ranking[nombre] = {"puntos": 0, "tiempo_total": 0.0}
            print(f"📱📱 El alumno '{nombre}' se ha unido por primera vez.") 
        else:
            print(f"🔄🔄 ¡Reconexión detectada! El alumno '{nombre}' recuperó su sesión.")
        
        # 🎮 ELEGANT REPLAY FIX: Al conectarse, le avisamos al celu en qué estado está el Lobby
        # Si la trivia aún no arrancó, le gatillamos que el lobby está listo para usar
        if self.indice_pregunta_actual == -1:
            try:
                await websocket.send_text(json.dumps({"evento": "LOBBY_ABIERTO"}))
            except:
                pass

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
        
        # CONTROL DE FIN DE JUEGO (Si llegamos al final por las buenas)
        if self.indice_pregunta_actual >= len(self.preguntas):
            await self.finalizar_juego()
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
            self.global_correctos += 1 
        else:
            jugador["tiempo_total"] += 20.0 
            self.votos_incorrectos += 1
            self.global_incorrectos += 1 

        if self.host_socket:
            await self.host_socket.send_text(json.dumps({
                "evento": "ESTADISTICAS_VOTOS",
                "correctos": self.votos_correctos,
                "incorrectos": self.votos_incorrectos
            }))
            
        await self.enviar_ranking_actualizado()

    async def revelar_resultados(self):
        if self.indice_pregunta_actual >= 0 and self.indice_pregunta_actual < len(self.preguntas):
            pregunta = self.preguntas[self.indice_pregunta_actual]
            correcta = pregunta["correcta"]
            justificacion = pregunta["justificacion"]
            
            # 🎯 FIX CRÍTICO JUGADOR: Mandamos la correcta Y LA JUSTIFICACIÓN para que la renderice en los celus
            for cliente_ws in self.conexiones.keys():
                try:
                    await cliente_ws.send_text(json.dumps({
                        "evento": "REVELAR_CORRECTA",
                        "correcta": correcta,
                        "justificacion": justificacion
                    }))
                except:
                    pass

    # 🛑 BUG 2 Y 3: MÉTODO ÚNICO PARA MANEJAR EL FIN DEL JUEGO (NORMAL O FORZADO)
    async def finalizar_juego(self):
        # Calculamos cuántas interacciones totales se quedaron colgadas (Sin Responder)
        # Total interacciones esperadas = cantidad de alumnos jugando x cantidad de preguntas que pasaron
        total_alumnos = len(self.ranking)
        preguntas_jugadas = max(1, self.indice_pregunta_actual if self.indice_pregunta_actual < len(self.preguntas) else len(self.preguntas))
        esperados = total_alumnos * preguntas_jugadas
        votos_totales = self.global_correctos + self.global_incorrectos
        global_sin_responder = max(0, esperados - votos_totales)

        # 1. Avisamos al Host con la data del Gráfico Triple
        if self.host_socket:
            await self.host_socket.send_text(json.dumps({
                "evento": "JUEGO_TERMINADO",
                "total_ok": self.global_correctos,
                "total_err": self.global_incorrectos,
                "total_sr": global_sin_responder
            }))
        
        # 2. Mandamos el cierre a cada dispositivo celular/notebook
        for cliente_ws, nombre in self.conexiones.items():
            try:
                jugador_data = self.ranking.get(nombre, {"puntos": 0})
                await cliente_ws.send_text(json.dumps({
                    "evento": "JUEGO_TERMINADO",
                    "puntos": jugador_data["puntos"]
                }))
            except:
                pass

        # 🎮 LOBBY REPLAY TRIGGER: Desparramamos el evento masivo para activar el botón verde de "Jugar de nuevo"
        for cliente_ws in self.conexiones.keys():
            try:
                await cliente_ws.send_text(json.dumps({"evento": "LOBBY_ABIERTO"}))
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

def limpiar_sala(self):
        """ 🧹 Método escoba: Resetea puntos a 0 pero mantiene a los pibes en el aula """
        # A todos los que jugaron, los volvemos a poner en 0
        for nombre in self.ranking:
            self.ranking[nombre] = {"puntos": 0, "tiempo_total": 0.0}
            
        self.indice_pregunta_actual = -1
        self.votos_correctos = 0
        self.votos_incorrectos = 0
        self.global_correctos = 0
        self.global_incorrectos = 0
        print("🧹 ¡SALA LIMPIA! Puntos reseteados a 0 para el siguiente nivel.")

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
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Login Docente</title>
        <style>
            body { font-family: Arial, sans-serif; background: #1a1a1a; color: white; text-align: center; padding-top: 100px; margin: 0; }
            .caja { max-width: 350px; margin: 0 auto; background: #2a2a2a; padding: 30px; border-radius: 12px; border: 1px solid #444; box-shadow: 0px 4px 15px rgba(0,0,0,0.5); position: relative; }
            h2 { margin-top: 0; color: #ffeb3b; }
            input { width: 90%; padding: 12px; margin: 15px 0; border-radius: 6px; border: 1px solid #555; background: #333; color: white; text-align: center; font-size: 16px; box-sizing: border-box; }
            input:focus { border-color: #008CBA; outline: none; }
            button { background: #008CBA; color: white; padding: 12px; border: none; border-radius: 6px; width: 90%; font-weight: bold; cursor: pointer; font-size: 16px; transition: background 0.2s; }
            button:hover { background: #007096; }
            
            /* 🚨 Estilo del nuevo cartel flotante estético */
            .alerta-error {
                display: none;
                background-color: #e21b3c;
                color: white;
                padding: 12px;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 15px;
                font-size: 14px;
                box-shadow: 0px 2px 8px rgba(0,0,0,0.3);
                animation: sacudida 0.3s ease-in-out;
            }
            @keyframes sacudida {
                0%, 100% { transform: translateX(0); }
                20%, 60% { transform: translateX(-6px); }
                40%, 80% { transform: translateX(6px); }
            }
        </style>
    </head>
    <body>
        <div class="caja">
            <h2>🔐 Panel Docente</h2>
            <form id="form-login" onsubmit="enviarLogin(event)">
                <input type="password" id="clave" placeholder="Contraseña..." required autocomplete="off">
                <button type="submit">Ingresar</button>
            </form>
            
            <div id="cartel-error" class="alerta-error">❌ Contraseña incorrecta</div>
        </div>

        <script>
            async function enviarLogin(event) {
                event.preventDefault(); // Evita que la página se recargue de forma fea
                const claveInput = document.getElementById("clave").value;
                const cartel = document.getElementById("cartel-error");
                
                // Ocultamos el cartel por si estaba visible de un intento anterior
                cartel.style.display = "none";

                // Enviamos los datos por atrás (Fetch API) simulando el formulario
                const formData = new FormData();
                formData.append("clave", claveInput);

                try {
                    const response = await fetch("/login", {
                        method: "POST",
                        body: formData
                    });

                    // Si el servidor redirige con éxito (303), seguimos la ruta al panel
                    if (response.redirected) {
                        window.location.href = response.url;
                    } else {
                        // Si no redirige, significa que devolvió el error
                        mostrarError();
                    }
                } catch (error) {
                    mostrarError();
                }
            }

            function mostrarError() {
                const cartel = document.getElementById("cartel-error");
                cartel.style.display = "block";
                document.getElementById("clave").value = ""; // Limpia el input
                document.getElementById("clave").focus();
            }
        </script>
    </body>
    </html>
    """)

@app.post("/login")
def procesar_login(clave: str = Form(...)):
    if clave == CLAVE_DOCENTE:
        respuesta = RedirectResponse(url="/panel", status_code=303)
        respuesta.set_cookie(key="autorizado", value="si", httponly=True)
        return respuesta
    # 🎯 Ajuste clave: si falla, devolvemos un código HTTP 401 (No autorizado) para que el JavaScript lo atrape
    return JSONResponse(status_code=401, content={"error": "Clave incorrecta"})

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
async def ws_host(websocket: WebSocket, nivel: int = 1): # 🎯 Recibe el nivel dinámico de la TV
    
    # 💥 Pisamos las preguntas del juego con las del nivel elegido antes de conectar
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

            # 🧹 ACÁ ESTÁ LA MAGIA PARA EL "EFECTO PEPE":
            elif datos.get("accion") == "CERRAR_SALA":
                controlador.limpiar_sala()
                
            # 🎯 BUG 2: ATRACHAMOS EL BOTÓN ROJO DE EMERGENCIA DEL PROFE
            elif datos.get("accion") == "FORZAR_FIN_TRIVIA":
                # Verificamos si tu controlador ya tiene un método de cierre.
                # Si se llama distinto (ej: finalizar_juego), cambiale el nombre acá:
                if hasattr(controlador, "finalizar_juego"):
                    await controlador.finalizar_juego()
                elif hasattr(controlador, "terminar_trivia"):
                    await controlador.terminar_trivia()
                else:
                    # Si no existía un método genérico, lo disparamos directo emitiendo el evento
                    await controlador.enviar_final_juego()

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