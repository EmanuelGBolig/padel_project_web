
import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo, Partido
from equipos.models import Equipo
from django.db.models import Count, Q

print("--- Inspecting Tournaments ---")
torneos = Torneo.objects.all()

for t in torneos:
    print(f"ID: {t.id} | Nombre: {t.nombre} | Estado: {t.estado} | Ganador: {t.ganador_del_torneo}")
    
    # Check Final Match
    final_matches = Partido.objects.filter(torneo=t, siguiente_partido__isnull=True)
    for fm in final_matches:
        print(f"  -> Final Match ID: {fm.id} | Ronda: {fm.ronda} | Ganador: {fm.ganador} | Resultado: {fm.resultado}")
        
    print("-" * 30)

print("\n--- Testing Ranking Calculation for a Team ---")
# Pick a team that should have points
if torneos.exists() and torneos.first().ganador_del_torneo:
    team = torneos.first().ganador_del_torneo
    print(f"Testing team: {team.nombre}")
    
    # Manual Calc from View Logic
    victorias = team.partidos_bracket_ganados.count() + team.partidos_grupo_ganados.count()
    torneos_ganados = team.torneos_ganados.count()
    
    print(f"  Victorias: {victorias}")
    print(f"  Torneos Ganados: {torneos_ganados}")
    print(f"  Puntos (calc): {victorias * 3 + torneos_ganados * 50}")
else:
    print("No tournament winner found to test.")
