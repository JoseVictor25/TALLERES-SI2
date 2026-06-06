import psycopg2
conn = psycopg2.connect('postgresql://postgres:josevictor2001@localhost:5432/talleres_devv')
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute("SELECT id FROM categoria_incidente WHERE nombre = 'Desconocido'")
    row = cur.fetchone()
    if row:
        id_categoria = row[0]
    else:
        cur.execute("INSERT INTO categoria_incidente (nombre) VALUES ('Desconocido') RETURNING id")
        id_categoria = cur.fetchone()[0]

    cur.execute("SELECT id FROM tipo_incidente WHERE concepto = 'informacion_insuficiente'")
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO tipo_incidente (concepto, prioridad, requiere_remolque, id_categoria_incidente) VALUES ('informacion_insuficiente', 5, false, %s) RETURNING id", (id_categoria,))
        print("Exito insertando informacion_insuficiente")
    else:
        print("Ya existe informacion_insuficiente")
except Exception as e:
    print("Error:", e)
