import sqlite3

DB_NAME = "kahoot.db"

def inicializar_db():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # 🎯 ESTRUCTURA GENÉRICA COMPLETA
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS preguntas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nivel INTEGER NOT NULL,
        codigo_pregunta TEXT,
        enunciado TEXT NOT NULL,
        opcion_a TEXT NOT NULL,
        opcion_b TEXT NOT NULL,
        correcta TEXT NOT NULL,
        justificacion TEXT NOT NULL
    )
    """)
    
    conexion.commit()
    conexion.close()
    print("🗃️ Base de datos inicializada de forma genérica y persistente.")


#MÉTODOS DE LECTURA Y FILTRADO (Para el Juego y la TV) =====================================================================

def obtener_preguntas_por_nivel(nivel: int):
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    cursor.execute("""
        SELECT enunciado, opcion_a, opcion_b, correcta, justificacion 
        FROM preguntas 
        WHERE nivel = ?
    """, (nivel,))
    
    filas = cursor.fetchall()
    conexion.close()
    return [dict(fila) for fila in filas]


def obtener_lista_niveles():
    """ 📊 Devuelve una lista ordenada con los números de niveles existentes.
        Ideal para calcular el contador X/5 y renderizar los botones de juego. """
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    cursor.execute("SELECT DISTINCT nivel FROM preguntas ORDER BY nivel")
    niveles = [fila[0] for fila in cursor.fetchall()]
    
    conexion.close()
    return niveles


# MÉTODOS C.R.U.D. (Para las acciones del Panel Docente) ==========================================================

def insertar_preguntas_lote(preguntas_nuevas: list):
    """ 📄 Graba un lote completo de preguntas en la BD.
        Recibe una lista de tuplas: [(nivel, codigo, enunciado, op_a, op_b, correcta, justi), ...] """
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    cursor.executemany("""
    INSERT INTO preguntas (nivel, codigo_pregunta, enunciado, opcion_a, opcion_b, correcta, justificacion) 
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """, preguntas_nuevas)
    
    conexion.commit()
    conexion.close()


def eliminar_nivel_completo(nivel: int):
    """ 🗑️ Borra absolutamente todas las preguntas vinculadas a un nivel específico. """
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    cursor.execute("DELETE FROM preguntas WHERE nivel = ?", (nivel,))
    
    conexion.commit()
    conexion.close()