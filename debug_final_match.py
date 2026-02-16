
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo, Partido
from django.db.models import Max

print("--- Inspecting Tournaments and Final Matches ---")
torneos = Torneo.objects.all()

for t in torneos:
    print(f"ID: {t.id} | Nombre: {t.nombre} | Estado: {t.estado} | Ganador: {t.ganador_del_torneo}")
    
    # Get max round to identify the final
    max_ronda = t.partidos.aggregate(Max('ronda'))['ronda__max']
    if max_ronda:
        finals = Partido.objects.filter(torneo=t, ronda=max_ronda)
        for f in finals:
            print(f"  Final Match ID: {f.id} | Ronda: {f.ronda} | Ganador: {f.ganador}")
            print(f"  Siguiente Partido: {f.siguiente_partido}")
            if f.siguiente_partido is None and f.ganador is not None:
                print("  => This SHOULD have set the tournament winner.")
                if t.ganador_del_torneo != f.ganador:
                     print("  => MISMATCH: Tournament winner is not set correctly!")
                     
                     # Fix it manually for now to verify if ranking works after fix
                     # Uncomment to apply fix
                     # t.ganador_del_torneo = f.ganador
                     # t.estado = 'FN'
                     # t.save()
                     # print("  => FIXED manually for testing.")

    print("-" * 30)

