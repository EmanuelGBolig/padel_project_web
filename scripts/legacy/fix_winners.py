
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo, Partido
from django.db.models import Max

print("--- Fixing Tournament Winners ---")
# Find tournaments that are 'FN' or should be, but have no winner set
torneos = Torneo.objects.annotate(max_ronda=Max('partidos__ronda'))

for t in torneos:
    if not t.max_ronda:
        continue
        
    final_matches = Partido.objects.filter(torneo=t, ronda=t.max_ronda)
    for f in final_matches:
        if f.ganador and not t.ganador_del_torneo:
            print(f"Fixing Tournament {t.id} ({t.nombre})")
            print(f"  Final Match Winner: {f.ganador}")
            t.ganador_del_torneo = f.ganador
            t.estado = 'FN'
            t.save()
            print("  -> Saved!")
        elif f.ganador and t.ganador_del_torneo != f.ganador:
             print(f"Mismatch in Tournament {t.id}")
             print(f"  Torneo Winner: {t.ganador_del_torneo}")
             print(f"  Match Winner: {f.ganador}")
             t.ganador_del_torneo = f.ganador
             t.save()
             print("  -> Fixed!")

