#!/usr/bin/env bash


echo "Ejecutando migraciones de Alembic..."
alembic upgrade head

echo "Ejecutando scripts para inicializar datos base..."
python seed_roles.py
python seed_especialidades.py
python seed_tipos_incidente.py
python seed_diagnostico.py

echo "Iniciando servidor Uvicorn..."
# Render provee el puerto automáticamente a través de la variable $PORT
uvicorn app.main:app --host 0.0.0.0 --port $PORT
