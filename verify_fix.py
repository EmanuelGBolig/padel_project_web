
import os
import django
import sys
from django.db.models import Count, Q

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo

print("--- Verifying Tournament Winners ---")
torneos = Torneo.objects.all()
for t in torneos:
    print(f"ID: {t.id} | Nombre: {t.nombre} | Estado: {t.estado} | Ganador: {t.ganador_del_torneo}")

    if t.ganador_del_torneo:
        equipo = t.ganador_del_torneo
        print(f"  Team: {equipo.nombre}")
        
        # Simulate Ranking Points
        # 1. Victorias en partidos del torneo
        # We need to filter by tournament to be precise, as per ranking view logic
        victorias_elim = equipo.partidos_bracket_ganados.filter(torneo=t).count()
        victorias_grupo = equipo.partidos_grupo_ganados.filter(grupo__torneo=t).count()
        victorias_total = victorias_elim + victorias_grupo
        
        # 2. Torneos Ganados (in this division/globally depending on view)
        torneos_ganados = equipo.torneos_ganados.count()
        
        puntos = victorias_total * 3 + torneos_ganados * 50
        
        print(f"  Victorias (This Tournament): {victorias_total}")
        print(f"  Torneos Ganados Total: {torneos_ganados}")
        print(f"  Estimated Ranking Points: {puntos}")
        
        if torneos_ganados > 0:
            print("  SUCCESS: Tournament win is now counted.")
        else:
            print("  FAIL: Tournament win is NOT counted (should be impossible if we just saw it above).")

