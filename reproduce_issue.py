
import os
import django
import sys
import traceback
import uuid
import random
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Q

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
try:
    django.setup()
except Exception:
    pass

from torneos.models import Torneo, Partido, Inscripcion
from equipos.models import Equipo
from accounts.models import CustomUser, Division

print("--- Reproducing 4-Team Tournament Issue ---")

try:
    # 1. Setup Data
    suffix = uuid.uuid4().hex[:6]
    division, _ = Division.objects.get_or_create(nombre=f"Divisin Test {suffix}", defaults={'orden': random.randint(100, 99999)})

    # Create 4 Users/Teams
    users = []
    equipos = []
    for i in range(4):
        u_suffix = uuid.uuid4().hex[:6]
        
        email1 = f"u{i}a_{u_suffix}@test.com"
        username1 = f"u{i}a_{u_suffix}"
        
        email2 = f"u{i}b_{u_suffix}@test.com"
        username2 = f"u{i}b_{u_suffix}"
        
        print(f"Creating Pair {i}: {email1} & {email2}")

        defaults1 = {'nombre': f"User{i}A", 'apellido': f"Fam{i}A_{u_suffix}"}
        if hasattr(CustomUser, 'username'): defaults1['username'] = username1
        u1, _ = CustomUser.objects.get_or_create(email=email1, defaults=defaults1)
        
        defaults2 = {'nombre': f"User{i}B", 'apellido': f"Fam{i}B_{u_suffix}"}
        if hasattr(CustomUser, 'username'): defaults2['username'] = username2
        u2, _ = CustomUser.objects.get_or_create(email=email2, defaults=defaults2)
        
        # Create Equipo manually
        eq = Equipo.objects.filter(jugador1=u1, jugador2=u2, division=division).first()
        if not eq:
            print("  Creating Equipo...")
            # Provide a temporary unique name to satisfy NOT NULL constraint if save() fails to set it
            eq = Equipo(jugador1=u1, jugador2=u2, division=division, nombre=f"TempTeam_{i}_{u_suffix}")
            eq.save()
            print(f"  Equipo created: {eq.nombre} (ID: {eq.id})")
        else:
            print(f"  Equipo retrieved: {eq.nombre}")
            
        users.extend([u1, u2])
        equipos.append(eq)

    # 2. Create Tournament
    torneo = Torneo.objects.create(
        nombre=f"Torneo Test 4 Equipos {suffix}",
        division=division,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=1),
        cupos_totales=4,
        tipo_torneo=Torneo.TipoTorneo.ELIMINATORIA,
        estado=Torneo.Estado.ABIERTO
    )

    # 3. Inscribe Teams
    for eq in equipos:
        Inscripcion.objects.create(torneo=torneo, equipo=eq)

    print(f"Torneo '{torneo.nombre}' created with {torneo.inscripciones.count()} teams.")

    # 4. Start Tournament (Manual Matches)
    torneo.estado = Torneo.Estado.EN_JUEGO
    torneo.save()

    print("Generating matches manually...")
    # Round 1 (Semis)
    m1 = Partido.objects.create(torneo=torneo, equipo1=equipos[0], equipo2=equipos[1], ronda=1, orden_partido=1)
    m2 = Partido.objects.create(torneo=torneo, equipo1=equipos[2], equipo2=equipos[3], ronda=1, orden_partido=2)
    # Round 2 (Final)
    m3 = Partido.objects.create(torneo=torneo, ronda=2, orden_partido=1)
    
    # Link progression
    m1.siguiente_partido = m3
    m1.save()
    m2.siguiente_partido = m3
    m2.save()

    # 5. Play Semis
    print("\n--- Playing Semis ---")
    
    # Eq0 wins M1
    m1.set_jugado = True
    m1.ganador = m1.equipo1
    m1.save() # This should advance Eq0 to M3

    # Eq2 wins M2
    m2.set_jugado = True
    m2.ganador = m2.equipo1
    m2.save() # This should advance Eq2 to M3

    print(f"Semis Winners: {m1.ganador} & {m2.ganador}")

    # 6. Verify Final Linkage
    m3.refresh_from_db()
    print(f"Final Match: {m3.equipo1} vs {m3.equipo2}")
    if m3.equipo1 != m1.ganador or m3.equipo2 != m2.ganador:
        print("❌ Match progression failed! Finalists are not correct.")

    # 7. Play Final
    print("\n--- Playing Final ---")
    m3.ganador = m3.equipo1  # Eq0 Wins Tournament
    m3.save()

    # 8. Check Tournament Status
    torneo.refresh_from_db()
    print(f"Tournament Winner: {torneo.ganador_del_torneo}")
    print(f"Tournament State: {torneo.estado}")

    if torneo.ganador_del_torneo != m3.ganador:
        print("❌ Torneo.ganador_del_torneo NOT set correctly!")
    else:
        print("✅ Torneo.ganador_del_torneo set correctly.")

    # 9. Verify Ranking Logic (Simulated)
    # We calculate points for the Winner (Eq0)
    winner = m3.ganador
    # Count Matches Won
    wins = Partido.objects.filter(torneo=torneo, ganador=winner).count()
    print(f"\nWinner ({winner}) Total Matches Won in DB: {wins}")
    if wins != 2:
        print(f"❌ ERROR: Winner should have 2 wins, found {wins}.")
    else:
        print("✅ DB has 2 wins recorded.")

    # Check Views Logic 
    print("\n--- Checking View Logic ---")
    qs = Equipo.objects.filter(id=winner.id).annotate(
        victorias_eliminacion=Count(
            'partidos_bracket_ganados',
            filter=Q(
                partidos_bracket_ganados__isnull=False,
                partidos_bracket_ganados__torneo=torneo
            ),
            distinct=True
        ),
        torneos_ganados_count=Count(
            'torneos_ganados',
            filter=Q(torneos_ganados__id=torneo.id),
            distinct=True
        )
    )
    stats = qs.first()
    print(f"View Calculated Wins: {stats.victorias_eliminacion}")
    print(f"View Calculated Tournaments Won: {stats.torneos_ganados_count}")

    if stats.victorias_eliminacion != 2:
        print("❌ View Logic fails to count 2 wins!")
    else:
        print("✅ View Logic counts 2 wins correctly.")

    if stats.torneos_ganados_count != 1:
         print("❌ View Logic fails to count Tournament Win!")
    else:
         print("✅ View Logic counts Tournament Win correctly.")

except Exception:
    traceback.print_exc()
