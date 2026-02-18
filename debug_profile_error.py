import os
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser
from accounts.utils import get_player_stats, get_user_ranking
from torneos.models import Torneo, Partido
from equipos.models import Equipo

def test_profile_stats():
    print("--- Starting Debug on Crash Reproduction ---")
    
    # 1. Get/Create User
    user = CustomUser.objects.first()
    if not user:
        user = CustomUser.objects.create(email="crash@test.com", nombre="Crash", apellido="User")
    
    # 2. Setup Malformed Tournament (Finalized but no winner)
    from torneos.models import Torneo, Inscripcion, Grupo
    from equipos.models import Equipo
    from django.utils import timezone
    
    # Check if we already have one
    torneo = Torneo.objects.filter(nombre="Crash Torneo").first()
    if not torneo:
        torneo = Torneo.objects.create(
            nombre="Crash Torneo",
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now(), # Add this
            estado=Torneo.Estado.FINALIZADO, # !!! FINALIZED
            ganador_del_torneo=None # !!! NO WINNER
        )
        # Create team for user
        from accounts.models import Division
        div, _ = Division.objects.get_or_create(nombre="Crash Div", orden=99)
        equipo = Equipo.objects.create(
            jugador1=user, 
            jugador2=None, 
            nombre="Crash Team",
            division=div,
            categoria='M'
        )
        Inscripcion.objects.create(torneo=torneo, equipo=equipo)
        print("Created problematic tournament.")
    else:
        print("Using existing problematic tournament.")
        
    # 3. Simulate Template Logic
    print(f"Simulating template render for user: {user.email}")
    stats = get_player_stats(user)
    torneos_finalizados = [i.torneo for i in stats['inscripciones'] if i.torneo.estado == 'FN']
    
    print(f"Found {len(torneos_finalizados)} finalized tournaments.")
    
    for t in torneos_finalizados:
        print(f"Checking tournament: {t.nombre}, Winner: {t.ganador_del_torneo}")
        try:
            # THIS IS THE FIXED LINE
            # {% if torneo.ganador_del_torneo and (torneo.ganador_del_torneo.jugador1 == perfil_usuario or torneo.ganador_del_torneo.jugador2 == perfil_usuario) %}
            if t.ganador_del_torneo and (t.ganador_del_torneo.jugador1 == user or t.ganador_del_torneo.jugador2 == user):
                print("User is winner")
            else:
                print("User is not winner (or no winner)")
        except AttributeError as e:
            print(f"!!! CAUGHT EXPECTED ERROR: {e}")
            print("CONFIRMED: Accessing .jugador1 on None (ganador_del_torneo) caused the crash.")
            return

    print("--- Finished Debugging (No crash found?) ---")

if __name__ == "__main__":
    test_profile_stats()
