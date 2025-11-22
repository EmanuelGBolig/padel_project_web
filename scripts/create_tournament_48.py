"""
Script corregido para crear un torneo con 48 equipos y grupos de 3
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
from datetime import date, datetime, timedelta

User = get_user_model()

# Obtener la división
division = Division.objects.first()
print(f"División: {division.nombre}")

# Verificar equipos existentes
total_equipos = Equipo.objects.filter(division=division).count()
print(f"Equipos en división {division.nombre}: {total_equipos}")

# Crear el torneo
torneo = Torneo.objects.create(
    nombre="Torneo Grande 48 Equipos",
    division=division,
    fecha_inicio=date.today(),
    fecha_limite_inscripcion=datetime.now() + timedelta(days=7),
    cupos_totales=48,
    equipos_por_grupo=3,
    estado='AB',  # Abierto
    tipo_torneo='G'  # Grupos + Eliminatoria
)
print(f"\nTorneo creado: {torneo.nombre}")
print(f"ID: {torneo.id}")
print(f"Cupos totales: {torneo.cupos_totales}")
print(f"Equipos por grupo: {torneo.equipos_por_grupo}")

# Inscribir los primeros 48 equipos
equipos = Equipo.objects.filter(division=division).order_by('id')[:48]
print(f"\nInscribiendo {len(equipos)} equipos...")

count = 0
for equipo in equipos:
    Inscripcion.objects.create(
        torneo=torneo,
        equipo=equipo
    )
    count += 1
    if count % 10 == 0:
        print(f"  {count} equipos inscritos...")

print(f"\nTotal inscripciones: {torneo.inscripciones.count()}")
print(f"\nURL: http://localhost:8000/torneos/{torneo.id}/")
print("\n✓ Torneo creado exitosamente!")
print("  Ahora puedes iniciar el torneo desde el panel de administración.")
