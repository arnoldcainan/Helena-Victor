#!/usr/bin/env sh
set -e

echo "==> Coletando arquivos estaticos..."
python manage.py collectstatic --noinput

echo "==> Aplicando migracoes no banco PostgreSQL..."
python manage.py migrate --noinput

echo "==> Verificando superusuario..."
python create_admin.py

echo "==> Iniciando servidor Gunicorn..."
exec gunicorn config.wsgi
