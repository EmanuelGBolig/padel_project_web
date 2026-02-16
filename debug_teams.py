
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from equipos.models import Equipo
from django.db.models import F

print("--- Inspecting Teams with Email-like Names ---")
teams = Equipo.objects.filter(nombre__contains='@')

for t in teams:
    print(f"ID: {t.id}")
    print(f"Current Name: {t.nombre}")
    print(f"J1: {t.jugador1.email} | Apellido: '{t.jugador1.apellido}'")
    print(f"J2: {t.jugador2.email} | Apellido: '{t.jugador2.apellido}'")
    
    # Simulate what the name SHOULD be
    j1_nombre = t.jugador1.apellido or t.jugador1.email.split('@')[0]
    j2_nombre = t.jugador2.apellido or t.jugador2.email.split('@')[0]
    nombres_ordenados = sorted([j1_nombre, j2_nombre])
    expected_name = f"{nombres_ordenados[0]}/{nombres_ordenados[1]}"
    print(f"Expected Name: {expected_name}")
    print("-" * 30)

print(f"Total teams with '@' in name: {teams.count()}")
