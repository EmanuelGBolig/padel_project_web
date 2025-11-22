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
division = Division.objects.first()
torneo = Torneo.objects.get(id=8)

print(f"Creando 16 equipos adicionales...")
created = 0

for i in range(33, 49):
    u1, _ = User.objects.get_or_create(
        email=f'jugador{i*2-1}@example.com',
        defaults={
            'nombre': f'Jugador{i*2-1}',
            'apellido': f'Apellido{i*2-1}',
            'tipo_usuario': 'PLAYER',
            'division': division
        }
    )
    
    u2, _ = User.objects.get_or_create(
        email=f'jugador{i*2}@example.com',
        defaults={
            'nombre': f'Jugador{i*2}',
            'apellido': f'Apellido{i*2}',
            'tipo_usuario': 'PLAYER',
            'division': division
        }
    )
    
    equipo, c = Equipo.objects.get_or_create(
        jugador1=u1,
        jugador2=u2,
        defaults={'division': division}
    )
    
    if c:
        Inscripcion.objects.create(torneo=torneo, equipo=equipo)
        created += 1
        print(f"  {equipo.nombre}")

print(f"\nEquipos creados e inscritos: {created}")
print(f"Total inscripciones: {torneo.inscripciones.count()}")
