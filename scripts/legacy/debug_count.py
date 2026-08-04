
import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo
print(f"Total Torneos: {Torneo.objects.count()}")
for t in Torneo.objects.all():
    print(f"Torneo: {t.nombre} (ID: {t.id})")
