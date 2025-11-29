import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Division
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion, Partido, Grupo, EquipoGrupo, PartidoGrupo
from django.test import RequestFactory
from equipos.views import RankingListView

User = get_user_model()

def verify_cross_division():
    print("--- Verifying Cross-Division Features ---")

    # 1. Setup Data
    print("1. Setting up data...")
    # Clean up
    User.objects.filter(email__contains='@test.com').delete()
    Torneo.objects.filter(nombre__startswith="Test Cross Div").delete()
    Division.objects.filter(nombre__in=["Div A", "Div B"]).delete()

    div_a = Division.objects.create(nombre="Div A")
    div_b = Division.objects.create(nombre="Div B")

    # Create Team in Div A
    u1 = User.objects.create_user(email='u1@test.com', password='123', division=div_a, nombre='U1', apellido='Test')
    u2 = User.objects.create_user(email='u2@test.com', password='123', division=div_a, nombre='U2', apellido='Test')
    team_a = Equipo.objects.create(jugador1=u1, jugador2=u2, division=div_a)
    print(f"Created Team A in {div_a.nombre}: {team_a}")

    # Create Tournament in Div B
    torneo_b = Torneo.objects.create(
        nombre="Test Cross Div Tournament",
        division=div_b,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
        cupos_totales=8,
        estado=Torneo.Estado.ABIERTO
    )
    print(f"Created Tournament in {div_b.nombre}: {torneo_b}")

    # 2. Verify Registration
    print("\n2. Verifying Registration...")
    try:
        Inscripcion.objects.create(torneo=torneo_b, equipo=team_a)
        print("SUCCESS: Team A registered in Tournament B (Cross-Division).")
    except Exception as e:
        print(f"FAILURE: Registration failed: {e}")
        return

    # 3. Simulate Match Result in Div B Tournament
    print("\n3. Simulating Match Result...")
    # Create dummy group and match
    grupo = Grupo.objects.create(torneo=torneo_b, nombre="Grupo A")
    
    # Create dummy opponent
    u3 = User.objects.create_user(email='u3@test.com', password='123', division=div_b, nombre='U3', apellido='TestOpp')
    u4 = User.objects.create_user(email='u4@test.com', password='123', division=div_b, nombre='U4', apellido='TestOpp')
    team_b = Equipo.objects.create(jugador1=u3, jugador2=u4, division=div_b)
    
    partido = PartidoGrupo.objects.create(
        grupo=grupo,
        equipo1=team_a,
        equipo2=team_b,
        ganador=team_a, # Team A wins!
        e1_set1=6, e2_set1=0,
        e1_set2=6, e2_set2=0
    )
    print(f"Match created: {team_a} beat {team_b} in {torneo_b}")

    # 4. Verify Rankings
    print("\n4. Verifying Rankings...")
    
    # Clear cache to ensure fresh results
    from django.core.cache import cache
    cache.clear()

    view = RankingListView()
    view.request = RequestFactory().get('/rankings/')
    
    rankings = view.get_queryset()
    
    # Check Div B Ranking
    ranking_b = next((r for r in rankings if r['division'].id == div_b.id), None)
    if ranking_b:
        team_entry = next((e for e in ranking_b['equipos'] if e['equipo'].id == team_a.id), None)
        if team_entry:
            print(f"SUCCESS: Team A found in Div B Ranking with {team_entry['puntos']} points.")
            if team_entry['puntos'] >= 3:
                 print("Points calculation correct (>= 3 for win).")
            else:
                 print(f"FAILURE: Points incorrect. Expected >= 3, got {team_entry['puntos']}")
        else:
            print("FAILURE: Team A NOT found in Div B Ranking.")
    else:
        print("FAILURE: Div B Ranking not generated.")

    # Check Div A Ranking
    ranking_a = next((r for r in rankings if r['division'].id == div_a.id), None)
    if ranking_a:
        team_entry_a = next((e for e in ranking_a['equipos'] if e['equipo'].id == team_a.id), None)
        if team_entry_a:
             print(f"WARNING: Team A found in Div A Ranking with {team_entry_a['puntos']} points.")
             if team_entry_a['puntos'] == 0:
                 print("Correct: 0 points in Div A.")
             else:
                 print("FAILURE: Team A should have 0 points in Div A.")
        else:
            print("SUCCESS: Team A not found in Div A Ranking (or has 0 points and was filtered if logic does that).")
    else:
        print("Info: Div A Ranking not generated (expected if no activity).")

if __name__ == "__main__":
    verify_cross_division()
