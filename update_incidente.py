import psycopg2
conn = psycopg2.connect('postgresql://postgres:josevictor2001@localhost:5432/talleres_devv')
conn.autocommit = True
cur = conn.cursor()
cur.execute("UPDATE tipo_incidente SET concepto = 'Problema no identificado' WHERE concepto = 'informacion_insuficiente'")
print('Updated to Problema no identificado')
