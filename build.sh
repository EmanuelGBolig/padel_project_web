#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py tailwind install
python manage.py tailwind build

python manage.py collectstatic --no-input
python manage.py migrate
python manage.py createcachetable

# Siembra idempotente de las 8 divisiones (get_or_create, no pisa nada).
python scripts/seed_divisions.py

# --- NO agregar scripts de reparación puntual acá ---
# Un script de arreglo se corre UNA vez, a mano, desde el shell de Render:
#     python manage.py <comando>
# Si se deja en el build, se re-ejecuta en cada deploy.
#
# Sacados a propósito:
#   - scripts/create_initial_superuser.py  -> el superusuario ya existe; recrearlo en cada
#     deploy no aporta nada y el script arrastra credenciales por defecto.
#   - python manage.py reparar_rankings    -> fusiona parejas duplicadas y BORRA Equipos,
#     Inscripciones y EquipoGrupo. Era un arreglo puntual de una anomalía vieja.
#   - python manage.py migrar_rankings_historicos -> también puntual.
