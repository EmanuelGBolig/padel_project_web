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
python manage.py migrar_rankings_historicos
