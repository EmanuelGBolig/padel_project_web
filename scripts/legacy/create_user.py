import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser

u, created = CustomUser.objects.get_or_create(email='test@example.com')
u.nombre = 'Jugador'
u.apellido = 'Prueba'
u.set_password('password123')
u.tipo_usuario = 'PLAYER'
u.save()

print("User created/updated successfully.")
