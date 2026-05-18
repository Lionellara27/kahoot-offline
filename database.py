import sqlite3

DB_NAME = "kahoot.db"

def inicializar_db():
    conexion = sqlite3.connect(DB_NAME)
    cursor = conexion.cursor()
    cursor.execute("DROP TABLE IF EXISTS preguntas")
    
    # 1. Creamos la tabla nueva con la Clave Primaria Natural y la columna de justificación
    cursor.execute("""
    CREATE TABLE preguntas (
        codigo_pregunta TEXT PRIMARY KEY,
        enunciado TEXT NOT NULL,
        opcion_a TEXT NOT NULL,
        opcion_b TEXT NOT NULL,
        correcta TEXT NOT NULL,
        justificacion TEXT NOT NULL
    )
    """)
    
    # 3. Lista con las 10 preguntas y sus justificaciones
    preguntas_taller = [
        ('PREG-01', 'Si ves el número "24" suelto en un pizarrón de la escuela, sin saber de qué se trata... ¿Qué es?', 
         'Un Dato (un hecho crudo sin procesar)', 'Información (ya tiene contexto y significado)', 'A',
         'Un dato por sí solo carece de sentido. Necesitamos saber "24 de qué" para que se convierta en información útil.'),
         
        ('PREG-02', 'Si la profesora les dice: "Sol de Mayo hizo 24 goles a favor en el torneo de la comarca", esto es...', 
         'Un Dato suelto', 'Información (el dato ya está organizado y tiene un contexto claro)', 'B',
         'Al darle un contexto claro (el equipo y el torneo), el número 24 se transforma en información valiosa.'),
         
        ('PREG-03', 'Si el equipo de la Peña ganó sus últimos 2 partidos y metió 6 goles, ¿se puede asegurar que va a seguir ganando siempre?', 
         'Sí, los datos del pasado garantizan el futuro con 100% de certeza', 'No, los datos ayudan a predecir y entender la realidad, pero no son una verdad absoluta', 'B',
         'Los datos muestran tendencias históricas, pero en la realidad física siempre hay variables impredecibles.'),
         
        ('PREG-04', 'Explicarle a un compañero de qué se trata tu encuesta y pedirle permiso explícito antes de que responda se conoce como...', 
         'Consentimiento Informado', 'Selección aleatoria de la Muestra', 'A',
         'En toda recolección de datos es fundamental la ética: la persona debe aceptar cómo se usará su información.'),
         
        ('PREG-05', '¿Qué es LibreOffice Calc y cuál es su función principal en un taller de datos?', 
         'Es una cuadrícula digital diseñada para organizar datos, hacer cálculos automáticos y generar gráficos', 'Es un programa de diseño gráfico para editar fotos del campo y retocar el logo', 'A',
         'Es la herramienta libre ideal para cargar, organizar y analizar grandes volúmenes de datos numéricos y de texto.'),
         
        ('PREG-06', '¿Cuál es la verdadera ventaja de clasificar y estructurar los datos que recolectamos en el territorio?', 
         'Solamente lograr que la computadora se vea más prolija y ordenada', 'Poder analizar la información claramente para tomar mejores decisiones basadas en la realidad', 'B',
         'El objetivo de estructurar los datos no es estético, sino facilitar el análisis para resolver problemas reales en el campo.'),
         
        ('PREG-07', '¿Cuál es la función principal de un "Gráfico de Torta" al representar datos de un proyecto?', 
         'Mostrar la tendencia o evolución de una variable a lo largo del tiempo cronológico', 
         'Representar la proporción o porcentaje de diferentes categorías respecto a un total', 'B',
         'El gráfico circular o de torta es la herramienta ideal para visualizar cómo se distribuye un total en porciones o porcentajes.'),
         
        ('PREG-08', 'Si medimos los niveles de glucemia de un paciente y el resultado arroja exactamente "115 mg/dL", ¿qué tipo de dato es?', 
         'Un dato Numérico', 'Un dato Categórico (una etiqueta de texto)', 'A',
         'Es un dato cuantitativo (numérico) porque representa una cantidad exacta que podemos operar matemáticamente.'),
         
        ('PREG-09', 'Si queremos saber cuál fue el día del mes con la temperatura más extrema registrada en la parcela, ¿qué función usamos?', 
         'La función PROMEDIO', 'La función MÁXIMO (MAX)', 'B',
         'La función =MAX() escanea instantáneamente un rango de celdas para devolver el valor más alto registrado.'),
         
        ('PREG-10', 'Además de responder preguntas como un chat, ¿para qué otra cosa podemos utilizar la Inteligencia Artificial?',
         'Como herramienta aliada para generar tablas de datos sintéticos (de prueba) para que nosotros practiquemos.', 'Para que nos hackee las netbooks de la escuela y podamos jugar sin internet', 'A',
         'Crear "Datos Sintéticos" realistas con IA es una práctica muy utilizada para testear sistemas o armar clases.')
    ]
    
    cursor.executemany("""
    INSERT INTO preguntas (codigo_pregunta, enunciado, opcion_a, opcion_b, correcta, justificacion) 
    VALUES (?, ?, ?, ?, ?, ?)
    """, preguntas_taller)
    
    conexion.commit()
    conexion.close()
    print("🗃️ Base de datos inicializada con preguntas y justificaciones.")

def obtener_todas_las_preguntas():
    conexion = sqlite3.connect(DB_NAME)
    conexion.row_factory = sqlite3.Row
    cursor = conexion.cursor()
    cursor.execute("SELECT enunciado, opcion_a, opcion_b, correcta, justificacion FROM preguntas")
    filas = cursor.fetchall()
    conexion.close()
    return [dict(fila) for fila in filas]