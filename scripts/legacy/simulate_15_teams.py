
import os
import django
import random
from django.utils import timezone
from datetime import timedelta
import string

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Division
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion, Partido, Grupo, EquipoGrupo
from torneos.views import AdminTorneoManageView  # We might need logic from here, but better to reimplement core logic for script

User = get_user_model()

def simulate_15_teams():
    print("--- Simulating 15-Team Tournament ---")

    # 1. Cleanup old simulation data
    Torneo.objects.filter(nombre__startswith="Simulation 15").delete()
    User.objects.filter(email__contains='@sim15.com').delete()
    print("Cleaned up old data.")

    # 2. Setup Division & Tournament
    division, _ = Division.objects.get_or_create(nombre="Simulation Div", defaults={'orden': 999})
    
    torneo = Torneo.objects.create(
        nombre=f"Simulation 15 - {timezone.now().strftime('%H:%M:%S')}",
        division=division,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=7),
        cupos_totales=15,
        equipos_por_grupo=3,
        estado=Torneo.Estado.ABIERTO
    )
    print(f"Created Tournament: {torneo.nombre}")

    # 3. Create 15 Teams and Register them
    equipos_registrados = []
    for i in range(1, 16):
        email1 = f"p1_{i}@sim15.com"
        email2 = f"p2_{i}@sim15.com"
        
        # Use simpler unique emails if deletion failed partially
        import time
        ts = int(time.time())
        email1 = f"p1_{i}_{ts}@sim15.com"
        email2 = f"p2_{i}_{ts}@sim15.com"
        
        jugador1 = User.objects.create_user(email=email1, nombre=f'J1_Team{i}', password='123')
        jugador2 = User.objects.create_user(email=email2, nombre=f'J2_Team{i}', password='123')
        
        equipo = Equipo.objects.create(jugador1=jugador1, jugador2=jugador2, division=division)
        
        Inscripcion.objects.create(torneo=torneo, equipo=equipo)
        equipos_registrados.append(equipo)
    
    print(f"Registered {len(equipos_registrados)} teams.")

    # 4. Start Tournament (Group Generation)
    from torneos.formats import get_format
    from torneos.views import generar_partidos_grupos
    # Based on previous generic reads, let's assume we need to implement generating group matches manually if import fails
    # But usually utils has it. Let's try to simulate the logic inline to be safe.
    
    custom_format = get_format(15)
    if not custom_format:
        print("ERROR: Format for 15 teams not found!")
        return

    print(f"Format found: {custom_format.teams} teams, {custom_format.groups} groups.")

    # Create Groups
    letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    sizes = custom_format.teams_per_group # Should be 3 (int)
    if isinstance(sizes, int):
        sizes = [sizes] * custom_format.groups
    
    current_team_idx = 0
    # Shuffle for randomness
    random.shuffle(equipos_registrados)

    from torneos.models import PartidoGrupo

    for i in range(custom_format.groups):
        group_size = sizes[i]
        grupo_nombre = f"Zona {letras[i]}"
        grupo = Grupo.objects.create(torneo=torneo, nombre=grupo_nombre)
        
        equipos_grupo = []
        for _ in range(group_size):
            if current_team_idx < len(equipos_registrados):
                eq = equipos_registrados[current_team_idx]
                equipos_grupo.append(eq)
                current_team_idx += 1
        
        # Add to EquipoGrupo
        for idx, eq in enumerate(equipos_grupo, start=1):
            EquipoGrupo.objects.create(grupo=grupo, equipo=eq, numero=idx)
        
        print(f"  Created {grupo_nombre} with {len(equipos_grupo)} teams.")
        
        # Generate Group Matches (All vs All)
        import itertools
        matches = list(itertools.combinations(equipos_grupo, 2))
        for m in matches:
            PartidoGrupo.objects.create(grupo=grupo, equipo1=m[0], equipo2=m[1])

    torneo.estado = Torneo.Estado.EN_JUEGO
    torneo.save()
    print("Tournament Started! (Groups Created)")

    # 5. Simulate Group Phase Matches
    partidos_grupo = PartidoGrupo.objects.filter(grupo__torneo=torneo)
    print(f"Simulating {partidos_grupo.count()} group matches...")
    
    for p in partidos_grupo:
        # Determine winner randomly
        winner = random.choice([p.equipo1, p.equipo2])
        p.ganador = winner
        
        # Fake stats for simulation (2-0 sets)
        if winner == p.equipo1:
            p.e1_sets_ganados = 2
            p.e2_sets_ganados = 0
            p.e1_games_ganados = 12
            p.e2_games_ganados = 4
            # Also fill detail fields just in case
            p.e1_set1, p.e2_set1 = 6, 2
            p.e1_set2, p.e2_set2 = 6, 2
        else:
            p.e1_sets_ganados = 0
            p.e2_sets_ganados = 2
            p.e1_games_ganados = 4
            p.e2_games_ganados = 12
            p.e1_set1, p.e2_set1 = 2, 6
            p.e1_set2, p.e2_set2 = 2, 6
            
        p.save()
        
        # Signal handles table update, so we don't need manual EG update!
        # The signal `actualizar_tabla_de_posiciones` listens to post_save of PartidoGrupo.
        # So manual update lines below are redundant and potentially conflicting/overwritten.
        # Let's remove them.

    print("Group matches finished.")

    # 6. Generate Bracket (Play-offs)
    print("Generating Bracket...")
    
    grupos_map = {}
    for g in torneo.grupos.all():
        letra = g.nombre.split(' ')[-1]
        grupos_map[letra] = g

    created_matches = {}
    matches_def = sorted(custom_format.bracket_structure, key=lambda x: x['round'])

    for m_def in matches_def:
        ronda_num = m_def['round']
        match_id = m_def['id']
        
        # Resolve E1
        e1 = None
        t1_def = m_def.get('t1')
        if t1_def:
            if isinstance(t1_def, tuple):
                g_letra, g_pos = t1_def
                if g_letra in grupos_map:
                    # Sort table by PG
                    tabla = grupos_map[g_letra].tabla.all().order_by('-partidos_ganados')
                    if len(tabla) >= g_pos:
                        e1 = tabla[g_pos-1].equipo
        
        # Resolve E2
        e2 = None
        t2_def = m_def.get('t2')
        if t2_def:
            if isinstance(t2_def, tuple):
                g_letra, g_pos = t2_def
                if g_letra in grupos_map:
                    tabla = grupos_map[g_letra].tabla.all().order_by('-partidos_ganados')
                    if len(tabla) >= g_pos:
                        e2 = tabla[g_pos-1].equipo
        
        p = Partido.objects.create(
            torneo=torneo,
            ronda=ronda_num,
            orden_partido=match_id,
            equipo1=e1,
            equipo2=e2
        )
        created_matches[match_id] = p
        
        e1_name = e1 or "Waiting..."
        e2_name = e2 or "Waiting..."
        print(f"  Created Match {match_id} (R{ronda_num}): {e1_name} vs {e2_name}")

    # Link matches
    for m_def in matches_def:
        match_id = m_def['id']
        next_id = m_def.get('next')
        if next_id and next_id in created_matches:
            current_match = created_matches[match_id]
            next_match = created_matches[next_id]
            current_match.siguiente_partido = next_match
            current_match.save()
            print(f"    Linked Match {match_id} -> {next_id}")

    print("Bracket Generated Successfully.")

    # 7. Simulate Bracket (Round by Round)
    max_round = 4
    for r in range(1, max_round + 1):
        print(f"Simulating Round {r}...")
        matches_round = Partido.objects.filter(torneo=torneo, ronda=r)
        
        if not matches_round.exists():
            print(f"  No matches in Round {r}.")
            continue
            
        for p in matches_round:
            # Refresh from DB to see if teams propagated
            p.refresh_from_db()
            
            if not p.equipo1 or not p.equipo2:
                print(f"  Match {p.orden_partido} has missing teams ({p.equipo1} vs {p.equipo2}). Skipping (maybe waiting for previous round results).")
                continue
            
            winner = random.choice([p.equipo1, p.equipo2])
            p.ganador = winner
            p.resultado = "6-4,6-4"
            p.save()
            print(f"  Match {p.orden_partido}: {p.equipo1} vs {p.equipo2} -> Winner: {winner}")
            
            if p.siguiente_partido:
                next_p = p.siguiente_partido
                # We need to load next_p again to ensure we update the fresh object? 
                # Or just update fields.
                
                # Logic to determine slot:
                # If next_p.equipo1 is empty, fill it. Else fill equipo2.
                # In real views, this logic might be more complex (e.g. knowing which 'feeder' match allows into slot 1 vs slot 2).
                # Here we just fill first available slot.
                if not next_p.equipo1:
                    next_p.equipo1 = winner
                elif not next_p.equipo2:
                    next_p.equipo2 = winner
                next_p.save()
                print(f"    -> Advanced to Match {next_p.orden_partido}")
        
    print("Simulation Complete.")

if __name__ == '__main__':
    simulate_15_teams()
