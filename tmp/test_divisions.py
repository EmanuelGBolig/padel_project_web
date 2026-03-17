import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser, Division
from equipos.models import Equipo
from torneos.models import Torneo
from torneos.views import TorneoDetailView

def test_flexible_divisions():
    print("--- Testing Flexible Divisions ---")
    
    # 1. Setup divisions
    div4 = Division.objects.get_or_create(nombre="Cuarta", orden=4)[0]
    div5 = Division.objects.get_or_create(nombre="Quinta", orden=5)[0]
    div6 = Division.objects.get_or_create(nombre="Sexta", orden=6)[0]
    
    # 2. Setup players
    p4 = CustomUser.objects.filter(tipo_usuario='PLAYER', division=div4).first()
    p6 = CustomUser.objects.filter(tipo_usuario='PLAYER', division=div6).first()
    
    if not p4 or not p6:
        print("Error: Could not find required test players. Ensure you have players in Cuarta and Sexta.")
        return

    print(f"Player 1: {p4.email} (Division: {p4.division})")
    print(f"Player 2: {p6.email} (Division: {p6.division})")

    # 3. Create mixed team
    team_name = "Test Mix Team"
    # Delete if exists
    Equipo.objects.filter(jugador1=p4, jugador2=p6).delete()
    
    team = Equipo(jugador1=p4, jugador2=p6)
    team.save() # This triggers our new logic
    
    print(f"Team created: {team.nombre}")
    print(f"Team assigned division: {team.division} (Expected: {div4})")
    assert team.division == div4
    
    # 4. Test eligibility
    view = TorneoDetailView()
    
    t4 = Torneo.objects.get_or_create(nombre="Torneo 4ta", division=div4)[0]
    t5 = Torneo.objects.get_or_create(nombre="Torneo 5ta", division=div5)[0]
    t6 = Torneo.objects.get_or_create(nombre="Torneo 6ta", division=div6)[0]
    t3 = Torneo.objects.get_or_create(nombre="Torneo 3ra", division=Division.objects.get_or_create(nombre="Tercera", orden=3)[0])[0]
    t_libre = Torneo.objects.get_or_create(nombre="Torneo Libre", division=None)[0]

    print("\nVerifying eligibility for 4ta/6ta pair:")
    
    def check(torneo, expected):
        allowed = view._es_division_permitida(team, torneo)
        status = "PASS" if allowed == expected else "FAIL"
        print(f"  - {torneo.nombre}: {'Allowed' if allowed else 'Blocked'} (Expected: {'Allowed' if expected else 'Blocked'}) -> {status}")
        return allowed == expected

    results = [
        check(t4, True),
        check(t5, True),
        check(t6, True),
        check(t3, False),
        check(t_libre, True),
    ]

    if all(results):
        print("\nSUCCESS: All eligibility checks passed!")
    else:
        print("\nFAILURE: Some eligibility checks failed.")

if __name__ == "__main__":
    test_flexible_divisions()
