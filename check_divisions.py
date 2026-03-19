import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division, CustomUser

sextas = Division.objects.filter(nombre__icontains='Sexta')
print(f"Found {sextas.count()} divisions matching 'Sexta':")
for s in sextas:
    player_count = CustomUser.objects.filter(division=s, tipo_usuario='PLAYER').count()
    print(f"- ID: {s.id}, Nombre: {s.nombre}, Jugadores: {player_count}")

# Check users with division=None
none_count = CustomUser.objects.filter(division=None, tipo_usuario='PLAYER').count()
print(f"Players with no division: {none_count}")
