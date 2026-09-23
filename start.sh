#!/usr/bin/env sh
set -e

echo "==> Coletando arquivos estaticos..."
python manage.py collectstatic --noinput

echo "==> Verificando e gerando migracoes..."
python manage.py makemigrations --noinput

echo "==> Aplicando migracoes no banco de dados..."
python manage.py migrate --noinput

echo "==> Garantindo evento inicial (Helena & Victor)..."
python manage.py seed_wedding

echo "==> Verificando superusuario administrativo..."
python create_admin.py

echo "==> Iniciando servidor Gunicorn em producao..."
exec gunicorn config.wsgi
