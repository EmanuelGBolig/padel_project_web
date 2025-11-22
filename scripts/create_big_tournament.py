"""
Script para crear 48 equipos y un torneo con grupos de 3 equipos
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
from torneos.models import Torneo, Grupo, EquipoGrupo, Inscripcion
from accounts.models import Division
from datetime import date

User = get_user_model()

# Obtener la división (asumiendo que existe al menos una)
division = Division.objects.first()
if not division:
    print("Error: No hay divisiones en la base de datos")
    exit()

print(f"Usando división: {division.nombre}")

# Contar equipos existentes
equipos_existentes = Equipo.objects.count()
print(f"Equipos existentes: {equipos_existentes}")

# Crear equipos adicionales si es necesario
equipos_necesarios = 48 - equipos_existentes
if equipos_necesarios > 0:
    print(f"Creando {equipos_necesarios} equipos adicionales...")
    
    # Obtener o crear usuarios para los equipos
    usuarios_creados = 0
    for i in range(equipos_existentes + 1, 49):
        # Crear jugador 1
        email1 = f"jugador{i*2-1}@test.com"
        user1, created = User.objects.get_or_create(
            email=email1,
            defaults={
                'nombre': f'Jugador{i*2-1}',
                'apellido': f'Apellido{i*2-1}',
                'tipo_usuario': 'PLAYER',
                'division': division
            }
        )
        if created:
            user1.set_password('password123')
            user1.save()
            usuarios_creados += 1
        
        # Crear jugador 2
        email2 = f"jugador{i*2}@test.com"
        user2, created = User.objects.get_or_create(
            email=email2,
            defaults={
                'nombre': f'Jugador{i*2}',
                'apellido': f'Apellido{i*2}',
                'tipo_usuario': 'PLAYER',
                'division': division
            }
        )
        if created:
            user2.set_password('password123')
            user2.save()
            usuarios_creados += 1
        
        # Crear equipo
        equipo, created = Equipo.objects.get_or_create(
            jugador1=user1,
            jugador2=user2,
            defaults={'division': division}
        )
        if created:
            print(f"  Equipo creado: {equipo.nombre}")
    
    print(f"Usuarios creados: {usuarios_creados}")
    print(f"Total de equipos ahora: {Equipo.objects.count()}")

# Crear el torneo
print("\nCreando torneo con 48 equipos y grupos de 3...")
torneo = Torneo.objects.create(
    nombre="Torneo Grande 48 Equipos",
    division=division,
    fecha_inicio=date.today(),
    cupos=48,
    equipos_por_grupo=3,
    estado='AB'  # Abierto
)
print(f"Torneo creado: {torneo.nombre} (ID: {torneo.id})")

# Inscribir los 48 equipos
print("\nInscribiendo equipos...")
equipos = Equipo.objects.filter(division=division)[:48]
for equipo in equipos:
    Inscripcion.objects.create(
        torneo=torneo,
        equipo=equipo
    )
    print(f"  Inscrito: {equipo.nombre}")

print(f"\nTotal de inscripciones: {torneo.inscripciones.count()}")
print(f"URL del torneo: http://localhost:8000/torneos/{torneo.id}/")
print("\n¡Listo! Ahora puedes iniciar el torneo desde el panel de administración.")
