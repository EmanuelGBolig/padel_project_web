"""
Crear 16 equipos adicionales e inscribirlos en el torneo
"""
import os
import sys
import django

# Add parent directory to sys.path to allow importing project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion
from accounts.models import Division

User = get_user_model()

# Obtener división y torneo
division = Division.objects.first()
torneo = Torneo.objects.get(id=8)

print(f"Torneo: {torneo.nombre}")
print(f"Inscripciones actuales: {torneo.inscripciones.count()}")

# Crear 16 equipos adicionales
print("\nCreando 16 equipos adicionales...")
equipos_nuevos = []

for i in range(33, 49):  # 33 a 48 = 16 equipos
    # Crear jugador 1
    email1 = f"jugador{i*2-1}@test.com"
    user1, _ = User.objects.get_or_create(
        email=email1,
        defaults={
            'nombre': f'Jugador{i*2-1}',
            'apellido': f'Apellido{i*2-1}',
            'tipo_usuario': 'PLAYER',
            'division': division
        }
    )
    if _:
        user1.set_password('password123')
        user1.save()
    
    # Crear jugador 2
    email2 = f"jugador{i*2}@test.com"
    user2, _ = User.objects.get_or_create(
        email=email2,
        defaults={
            'nombre': f'Jugador{i*2}',
            'apellido': f'Apellido{i*2}',
            'tipo_usuario': 'PLAYER',
            'division': division
        }
    )
    if _:
        user2.set_password('password123')
        user2.save()
    
    # Crear equipo
    equipo, created = Equipo.objects.get_or_create(
        jugador1=user1,
        jugador2=user2,
        defaults={'division': division}
    )
    if created:
        equipos_nuevos.append(equipo)
        print(f"  {equipo.nombre}")

print(f"\nEquipos nuevos creados: {len(equipos_nuevos)}")
print(f"Total equipos: {Equipo.objects.filter(division=division).count()}")

# Inscribir todos los equipos que no estén inscritos
print("\nInscribiendo equipos faltantes...")
equipos_inscritos = torneo.equipos_inscritos.all()
equipos_todos = Equipo.objects.filter(division=division)[:48]

count = 0
for equipo in equipos_todos:
    if equipo not in equipos_inscritos:
        Inscripcion.objects.create(torneo=torneo, equipo=equipo)
        count += 1
        print(f"  Inscrito: {equipo.nombre}")

print(f"\nEquipos inscritos en este script: {count}")
print(f"Total inscripciones: {torneo.inscripciones.count()}")
print(f"\n✓ Completado!")
