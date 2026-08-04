"""Siembra las 8 divisiones base. Idempotente: corre en cada deploy (build.sh).

`Division.orden` es NOT NULL y unique, así que hay que pasarlo sí o sí al crear:
un `get_or_create(nombre=...)` pelado explota con IntegrityError en una base
vacía y, como build.sh usa `set -o errexit`, se cae el deploy entero. En una base
que ya tiene las divisiones no se nota, porque nunca entra a crear.
"""
import os
import sys

import django

# Add parent directory to sys.path to allow importing project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division  # noqa: E402

# El orden define la jerarquía: 1 es la división más alta.
DIVISIONES_INICIALES = [
    ("Primera", 1),
    ("Segunda", 2),
    ("Tercera", 3),
    ("Cuarta", 4),
    ("Quinta", 5),
    ("Sexta", 6),
    ("Séptima", 7),
    ("Octava", 8),
]


def seed_divisions():
    print("--- Verificando Divisiones ---")

    creadas = 0
    for nombre, orden in DIVISIONES_INICIALES:
        division, created = Division.objects.get_or_create(
            nombre=nombre, defaults={'orden': orden}
        )
        if created:
            print(f"  [+] Creada división: {nombre} (orden {orden})")
            creadas += 1
        else:
            # Reparar filas viejas que hayan quedado sin orden.
            if division.orden is None:
                division.orden = orden
                division.save(update_fields=['orden'])
                print(f"  [~] {nombre}: se completó el orden faltante ({orden})")
            else:
                print(f"  [ ] Ya existe: {nombre}")

    print(f"\nProceso completado. Se crearon {creadas} nuevas divisiones.")
    print(f"Total de divisiones en base de datos: {Division.objects.count()}")


if __name__ == "__main__":
    seed_divisions()
