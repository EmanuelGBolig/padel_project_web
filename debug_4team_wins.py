
import os
import django
import sys
from django.db.models import Count, Q

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo, Partido
from equipos.models import Equipo
from accounts.models import CustomUser

print("--- Debugging 4-Team Tournament Ranking ---")

# 1. Find a 4-team tournament (or create one in memory/test db if possible, but here we query existing)
# We look for a completed tournament with roughly 3 matches (2 semis + 1 final)
torneos = Torneo.objects.annotate(num_partidos=Count('partidos')).filter(num_partidos__gte=3, estado='FN')

target_torneo = None
for t in torneos:
    # Check if it has exactly 4 teams? Or close to it.
    # A 4 team bracket has 3 matches.
    if t.partidos.count() == 3:
        target_torneo = t
        break

if not target_torneo:
    print("No exact 4-team tournament (3 matches) found. Using the last finished tournament.")
    target_torneo = Torneo.objects.filter(estado='FN').last()

if target_torneo:
    print(f"Analyzing Tournament: {target_torneo.nombre} (ID: {target_torneo.id})")
    
    ganador = target_torneo.ganador_del_torneo
    if ganador:
        print(f"Winner: {ganador.nombre}")
        
        # Check matches won by this team in this tournament
        matches_won = Partido.objects.filter(torneo=target_torneo, ganador=ganador)
        print(f"Matches Won Query Count: {matches_won.count()}")
        for m in matches_won:
            print(f" - Ronda {m.ronda} vs {m.equipo1 if m.equipo2==ganador else m.equipo2}")
            
        # Retrieve Stats using the logic from accounts/views.py (Checking Player Ranking logic)
        # We simulate what the view does for one of the players of the winning team
        player = ganador.jugador1
        print(f"Checking Player: {player.email}")
        
        # Logic from accounts/views.py
        # ...
        # victorias_j1_elim = Count('equipos_como_jugador1__partidos_bracket_ganados', filter=Q(...))
        
        # Simplified manual count for this player in this tournament
        # He is player 1 of 'ganador' team
        
        # Count victories as Player 1 of ANY team in this tournament's bracket
        # Note: The view counts GLOBAL victories, but let's check if it sees these specific ones.
        
        p1_wins = Partido.objects.filter(
            ganador__jugador1=player,
            torneo=target_torneo
        ).count()
        
        p2_wins = Partido.objects.filter(
            ganador__jugador2=player,
            torneo=target_torneo
        ).count()
        
        print(f"Player Total Wins in Torneo (Manual check): {p1_wins + p2_wins}")

    else:
        print("Tournament has no winner set!")
else:
    print("No finished tournaments found.")
