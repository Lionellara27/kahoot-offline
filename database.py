import sqlite3

def inicializar_db():
    # Se conecta al archivo (si no existe, lo crea automáticamente)
    conexion = sqlite3.connect("kahoot.db")
    cursor = conexion.cursor()
    
    # 1. Crear tabla de Preguntas
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS preguntas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enunciado TEXT NOT NULL,
        opcion_a TEXT NOT NULL,
        opcion_b TEXT NOT NULL,
        correcta TEXT NOT NULL
    )
    """)
    
    # 2. Insertar unas preguntas de prueba si la tabla está vacía
    cursor.execute("SELECT COUNT(*) FROM preguntas")
    if cursor.fetchone()[0] == 0:
        preguntas_semilla = [
            ("¿Qué lenguaje estamos usando para el Backend de este juego?", "Java", "Python", "B"),
            ("¿Qué protocolo mantiene el canal abierto en tiempo real?", "HTTP", "WebSockets", "B"),
            ("¿En qué tipo de red funciona este Kahoot sin internet?", "LAN (Local)", "WAN (Internet)", "A")
        ]
        cursor.executemany("""
        INSERT INTO preguntas (enunciado, opcion_a, opcion_b, correcta)
        VALUES (?, ?, ?, ?)
        """, preguntas_semilla)
        conexion.commit()
        print("🗃️ Base de datos inicializada con preguntas de prueba.")
        
    conexion.close()

def obtener_todas_las_preguntas():
    conexion = sqlite3.connect("kahoot.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT id, enunciado, opcion_a, opcion_b, correcta FROM preguntas")
    filas = cursor.fetchall()
    conexion.close()
    
    # Mapeamos a un formato diccionario que FastAPI maneja mejor
    preguntas = []
    for fila in filas:
        preguntas.append({
            "id": fila[0],
            "enunciado": fila[1],
            "opcion_a": fila[2],
            "opcion_b": fila[3],
            "correcta": fila[4]
        })
    return preguntas