import os
import django
from django.utils import timezone
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Division
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion, Partido
from torneos.views import AdminTorneoManageView
from django.test import RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage

User = get_user_model()

def get_mock_request(user):
    factory = RequestFactory()
    request = factory.post('/fake-url')
    request.user = user
    setattr(request, 'session', {})
    setattr(request, '_messages', FallbackStorage(request))
    return request

def verify_8_teams():
    print("--- Verifying 8-Team Format ---")

    # 1. Setup Data
    print("1. Setting up data...")
    # Clean up
    User.objects.filter(email__contains='@test8.com').delete()
    Torneo.objects.filter(nombre__startswith="Test 8 Teams").delete()
    
    division, _ = Division.objects.get_or_create(nombre="Octava")
    
    # Create Admin User for the view
    admin_user, _ = User.objects.get_or_create(email='admin@test8.com', defaults={'tipo_usuario': 'ADMIN', 'password': '123'})

    # Create Tournament
    torneo = Torneo.objects.create(
        nombre="Test 8 Teams Tournament",
        division=division,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
        cupos_totales=8,
        estado=Torneo.Estado.ABIERTO
    )
    print(f"Created Tournament: {torneo}")

    # Create 8 Teams
    import time
    suffix = int(time.time())
    teams = []
    for i in range(1, 9):
        # Use suffix in apellido to ensure unique team name (e.g. "Test8_12345 / Test8_12345")
        u1 = User.objects.create_user(email=f'u{i}a_{suffix}@test8.com', password='123', division=division, nombre=f'U{i}A', apellido=f'Test8_{suffix}_{i}')
        u2 = User.objects.create_user(email=f'u{i}b_{suffix}@test8.com', password='123', division=division, nombre=f'U{i}B', apellido=f'Test8_{suffix}_{i}')
        team = Equipo.objects.create(jugador1=u1, jugador2=u2, division=division)
        Inscripcion.objects.create(torneo=torneo, equipo=team)
        teams.append(team)
        print(f"Registered Team {i}: {team}")

    # Setup View
    view = AdminTorneoManageView()
    request = get_mock_request(admin_user)

    # 2. Start Tournament (Group Creation)
    print("\n2. Starting Tournament (Group Creation)...")
    view.iniciar_torneo_logica(request, torneo)
    
    groups = torneo.grupos.all()
    print(f"Groups created: {groups.count()}")
    for g in groups:
        team_count = g.equipos.count()
        print(f"Group {g.nombre}: {team_count} teams")
        if team_count != 4:
             print(f"FAILURE: Group {g.nombre} should have 4 teams, has {team_count}")
             return

    if groups.count() != 2:
        print(f"FAILURE: Expected 2 groups, got {groups.count()}")
        return
    
    print("SUCCESS: Groups created correctly (2 groups of 4).")

    # 3. Simulating Group Results... (Keep existing logic)
    print("\n3. Simulating Group Results...")
    from torneos.models import PartidoGrupo
    
    # Let's just assign winners to all matches to ensure positions are calculated
    for group in groups:
        matches = PartidoGrupo.objects.filter(grupo=group)
        # We want a clear 1st, 2nd, 3rd.
        # Team 1 wins all (3 wins)
        # Team 2 wins 2
        # Team 3 wins 1
        # Team 4 wins 0
        
        # Get teams in group
        g_teams = list(group.equipos.all())
        t1, t2, t3, t4 = g_teams[0], g_teams[1], g_teams[2], g_teams[3]
        
        # T1 beats everyone
        for m in matches.filter(equipo1=t1):
            m.ganador = t1
            m.e1_set1, m.e2_set1 = 6, 0
            m.e1_set2, m.e2_set2 = 6, 0
            m.e1_sets_ganados, m.e2_sets_ganados = 2, 0
            m.e1_games_ganados, m.e2_games_ganados = 12, 0
            m.save()
        for m in matches.filter(equipo2=t1):
            m.ganador = t1
            m.e1_set1, m.e2_set1 = 0, 6
            m.e1_set2, m.e2_set2 = 0, 6
            m.e1_sets_ganados, m.e2_sets_ganados = 0, 2
            m.e1_games_ganados, m.e2_games_ganados = 0, 12
            m.save()
        
        # T2 beats T3 and T4
        for m in matches.filter(equipo1=t2, equipo2__in=[t3, t4]):
            m.ganador = t2
            m.e1_set1, m.e2_set1 = 6, 0
            m.e1_set2, m.e2_set2 = 6, 0
            m.e1_sets_ganados, m.e2_sets_ganados = 2, 0
            m.e1_games_ganados, m.e2_games_ganados = 12, 0
            m.save()
        for m in matches.filter(equipo2=t2, equipo1__in=[t3, t4]):
            m.ganador = t2
            m.e1_set1, m.e2_set1 = 0, 6
            m.e1_set2, m.e2_set2 = 0, 6
            m.e1_sets_ganados, m.e2_sets_ganados = 0, 2
            m.e1_games_ganados, m.e2_games_ganados = 0, 12
            m.save()

        # T3 beats T4
        for m in matches.filter(equipo1=t3, equipo2=t4):
            m.ganador = t3
            m.e1_set1, m.e2_set1 = 6, 0
            m.e1_set2, m.e2_set2 = 6, 0
            m.e1_sets_ganados, m.e2_sets_ganados = 2, 0
            m.e1_games_ganados, m.e2_games_ganados = 12, 0
            m.save()
        for m in matches.filter(equipo2=t3, equipo1=t4):
            m.ganador = t3
            m.e1_set1, m.e2_set1 = 0, 6
            m.e1_set2, m.e2_set2 = 0, 6
            m.e1_sets_ganados, m.e2_sets_ganados = 0, 2
            m.e1_games_ganados, m.e2_games_ganados = 0, 12
            m.save()

    # 4. Generate Bracket
    print("\n4. Generating Bracket...")
    view.generar_octavos_logica(request, torneo)
    
    matches = Partido.objects.filter(torneo=torneo).order_by('ronda', 'orden_partido')
    print(f"Bracket Matches Created: {matches.count()}")
    
    expected_matches = 5 # 2 in Round 1, 2 in Round 2, 1 in Round 3
    if matches.count() != expected_matches:
        print(f"FAILURE: Expected {expected_matches} matches, got {matches.count()}")
        for m in matches:
            print(f" - R{m.ronda} | {m.equipo1} vs {m.equipo2}")
        return

    # Verify specific structure
    r1 = matches.filter(ronda=1)
    r2 = matches.filter(ronda=2)
    r3 = matches.filter(ronda=3)
    
    print(f"Round 1 matches: {r1.count()}")
    print(f"Round 2 matches: {r2.count()}")
    print(f"Round 3 matches: {r3.count()}")
    
    if r1.count() == 2 and r2.count() == 2 and r3.count() == 1:
        print("SUCCESS: Bracket structure correct (2 -> 2 -> 1).")
    else:
        print("FAILURE: Incorrect round distribution.")

if __name__ == "__main__":
    verify_8_teams()
