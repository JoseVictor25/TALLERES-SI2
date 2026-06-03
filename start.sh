#!/usr/bin/env bash

# Render provee la base de datos con el formato postgres://
# SQLAlchemy asíncrono y síncrono requieren un prefijo ligeramente diferente.
# Reemplazamos "postgres://" por "postgresql://" y "postgresql+asyncpg://" en tiempo de ejecución.

export SYNC_DATABASE_URL=$(echo $RENDER_DB_URL | sed 's/^postgres:\/\//postgresql:\/\//')
export DATABASE_URL=$(echo $RENDER_DB_URL | sed 's/^postgres:\/\//postgresql+asyncpg:\/\//')

echo "Ejecutando migraciones de Alembic..."
alembic upgrade head

echo "Iniciando servidor Uvicorn..."
# Render provee el puerto automáticamente a través de la variable $PORT
uvicorn app.main:app --host 0.0.0.0 --port $PORT
