import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division, CustomUser

print("All Divisions in DB:")
for d in Division.objects.all().order_by('id'):
    p_count = CustomUser.objects.filter(division=d, tipo_usuario='PLAYER').count()
    print(f"- ID: {d.id}, Nombre: '{d.nombre}', Jugadores: {p_count}, Orden: {d.orden}")
