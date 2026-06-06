import psycopg2
conn = psycopg2.connect('postgresql://postgres:josevictor2001@localhost:5432/talleres_devv')
conn.autocommit = True
cur = conn.cursor()

try:
    cur.execute("SELECT id FROM especialidad WHERE nombre = 'Mecanica de Gas Natural (GNV/GLP)'")
    row = cur.fetchone()
    if row:
        id_especialidad = row[0]
    else:
        cur.execute("INSERT INTO especialidad (nombre, descripcion) VALUES ('Mecanica de Gas Natural (GNV/GLP)', 'Instalacion, mantenimiento y reparacion de sistemas a gas') RETURNING id")
        id_especialidad = cur.fetchone()[0]

    cur.execute("SELECT id FROM categoria_incidente WHERE nombre = 'Problemas a Gas'")
    row = cur.fetchone()
    if row:
        id_categoria = row[0]
    else:
        cur.execute("INSERT INTO categoria_incidente (nombre) VALUES ('Problemas a Gas') RETURNING id")
        id_categoria = cur.fetchone()[0]

    cur.execute("SELECT id FROM tipo_incidente WHERE concepto = 'Problemas con el sistema de gas'")
    row = cur.fetchone()
    if row:
        id_incidente = row[0]
    else:
        cur.execute("INSERT INTO tipo_incidente (concepto, prioridad, requiere_remolque, id_categoria_incidente) VALUES ('Problemas con el sistema de gas', 3, false, %s) RETURNING id", (id_categoria,))
        id_incidente = cur.fetchone()[0]

    cur.execute("SELECT * FROM requiere_especialidad WHERE id_categoria_incidente=%s AND id_especialidad=%s", (id_categoria, id_especialidad))
    if not cur.fetchone():
        cur.execute("INSERT INTO requiere_especialidad (id_categoria_incidente, id_especialidad) VALUES (%s, %s)", (id_categoria, id_especialidad))

    print(f'Exito. Especialidad: {id_especialidad}, Categoria: {id_categoria}, Incidente: {id_incidente}')
except Exception as e:
    print("Error:", e)
