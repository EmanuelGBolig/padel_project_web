import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser, Division
from equipos.models import RankingJugador, Equipo
from torneos.models import Torneo

div_sexta = Division.objects.filter(nombre__icontains='Sexta').first()
if not div_sexta:
    print("No division 'Sexta' found.")
else:
    print(f"Division: {div_sexta.nombre} (ID: {div_sexta.id})")
    
    players_in_db = CustomUser.objects.filter(division=div_sexta, tipo_usuario='PLAYER').count()
    print(f"Total players in DB for this division: {players_in_db}")
    
    ranking_records = RankingJugador.objects.filter(division=div_sexta).count()
    print(f"Total RankingJugador records for this division: {ranking_records}")
    
    torneos = Torneo.objects.filter(division=div_sexta).count()
    print(f"Total torneos for this division: {torneos}")

    # Check some rankings
    print("\nRankingJugador entries:")
    for r in RankingJugador.objects.filter(division=div_sexta):
        print(f"- {r.jugador.full_name}: {r.puntos} pts")
