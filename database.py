import sqlite3

DB_NAME = "kahoot.db"

def inicializar_db():
    # Se conecta al archivo (si no existe, lo crea automáticamente)
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    
    # 1. Crear tabla de Preguntas si no existe
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS preguntas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enunciado TEXT NOT NULL,
        opcion_a TEXT NOT NULL,
        opcion_b TEXT NOT NULL,
        correcta TEXT NOT NULL
    )
    """)
    
    # 2. 🔥 LIMPIEZA: Vaciamos las preguntas viejas de prueba para meter las del taller
    cursor.execute("DELETE FROM preguntas")
    
    # 3. 📝 Lista con tus 10 preguntas oficiales para el taller de la ESFA
    preguntas_taller = [
        ('Si ves el número "24" suelto en un pizarrón de la escuela, sin saber de qué se trata... ¿Qué es?', 
         'Un Dato (un hecho crudo sin procesar)', 'Información (ya tiene contexto y significado)', 'A'),
         
        ('Si la profesora les dice: "Sol de Mayo hizo 24 goles a favor en el torneo de la comarca", esto es...', 
         'Un Dato suelto', 'Información (el dato ya está organizado y tiene un contexto claro)', 'B'),
         
        ('Si el equipo de la Peña ganó sus últimos 2 partidos y metió 6 goles, ¿se puede asegurar que va a seguir ganando siempre?', 
         'Sí, los datos del pasado garantizan el futuro con 100% de certeza', 'No, los datos ayudan a predecir y entender la realidad, pero no son una verdad absoluta', 'B'),
         
        ('Explicarle a un compañero de qué se trata tu encuesta y pedirle permiso explícito antes de que responda se conoce como...', 
         'Consentimiento Informado', 'Selección aleatoria de la Muestra', 'A'),
         
        ('¿Qué es LibreOffice Calc y cuál es su función principal en un taller de datos?', 
         'Es una cuadrícula digital diseñada para organizar datos, hacer cálculos automáticos y generar gráficos', 'Es un programa de diseño gráfico para editar fotos del campo y retocar el logo', 'A'),
         
        ('¿Cuál es la verdadera ventaja de clasificar y estructurar los datos que recolectamos en el territorio?', 
         'Solamente lograr que la computadora se vea más prolija y ordenada', 'Poder analizar la información claramente para tomar mejores decisiones basadas en la realidad', 'B'),
         
        ('Si en la clase de Organización y Gestión hablan de un "Gráfico de Torta", se están refiriendo a...', 
         'Un lemon pie o un bizcochuelo para compartir en el recreo de la ESFA', 'Una herramienta visual redonda dividida en porciones que facilita entender los porcentajes', 'B'),
         
        ('Si medimos los niveles de glucemia de un paciente y el resultado arroja exactamente "115 mg/dL", ¿qué tipo de dato es?', 
         'Un dato Numérico', 'Un dato Categórico (una etiqueta de texto)', 'A'),
         
        ('Si queremos saber cuál fue el día del mes con la temperatura más extrema registrada en la parcela, ¿qué función usamos?', 
         'La función PROMEDIO', 'La función MÁXIMO (MAX)', 'B'),
         
        ('Cuando usamos una Inteligencia Artificial para analizar datos, ¿a qué nos referimos con la palabra "Prompt"?', 
         'A la instrucción o pregunta clara y específica que le escribimos a la IA para obtener una buena respuesta', 'A un cable especial que se conecta a los celulares para transmitir datos sin internet', 'A')
    ]
    
    # 4. Inyectamos todas las preguntas oficiales juntas
    cursor.executemany("""
    INSERT INTO preguntas (enunciado, opcion_a, opcion_b, correcta) 
    VALUES (?, ?, ?, ?)
    """, preguntas_taller)
    
    conexion.commit()
    conexion.close()
    print("🗃️ Base de datos inicializada con las 10 preguntas oficiales del taller de la ESFA.")


def obtener_todas_las_preguntas():
    conexion = sqlite3.connect(DB_NAME)
    # Usamos sqlite3.Row para mapear automáticamente los nombres de las columnas
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    
    cursor.execute("SELECT enunciado, opcion_a, opcion_b, correcta FROM preguntas")
    filas = cursor.fetchall()
    conexion.close()
    
    # Devolvemos una lista limpia de diccionarios que el main.py entiende de una
    return [dict(fila) for fila in filas]