#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py tailwind install
python manage.py tailwind build

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py createcachetable


# Scripts de automatización
python scripts/seed_divisions.py
python scripts/create_initial_superuser.py
# Reparación y recalculo de rankings (Añadido para corregir anomalías en producción)
python manage.py reparar_rankings

# migrar_rankings_historicos es un script puntual, NO debe correr en cada deploy
