import os
import django
import random
import math
from django.utils import timezone
from datetime import timedelta

# Configurar Django
import sys
# Add parent directory to sys.path to allow importing project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo, Inscripcion, Grupo, EquipoGrupo, PartidoGrupo, Partido
from equipos.models import Equipo
from accounts.models import Division
from django.contrib.auth import get_user_model

User = get_user_model()

def crear_datos_prueba():
    print("--- Iniciando Simulación de Torneo de 24 Equipos ---")

    # 1. Crear División y Torneo
    division, _ = Division.objects.get_or_create(nombre="Simulacion 24")
    
    torneo_nombre = f"Torneo 24 Equipos - {timezone.now().strftime('%H:%M:%S')}"
    torneo = Torneo.objects.create(
        nombre=torneo_nombre,
        division=division,
        fecha_inicio=timezone.now(),
        fecha_fin=timezone.now() + timedelta(days=7),
        cupos_totales=24,
        equipos_por_grupo=3,  # CLAVE: Grupos de 3
        estado=Torneo.Estado.ABIERTO
    )
    print(f"Torneo creado: {torneo.nombre} (ID: {torneo.id})")

    # 2. Crear/Obtener Equipos e Inscribirlos
    equipos_necesarios = 24
    equipos_inscritos = []

    # Asegurar que existen suficientes jugadores dummy
    for i in range(equipos_necesarios * 2):
        email = f"sim_player_{i}@test.com"
        if not User.objects.filter(email=email).exists():
            User.objects.create_user(email=email, password="password123", nombre=f"Sim{i}", apellido=f"Player{i}")

    jugadores = list(User.objects.filter(email__startswith="sim_player_"))
    
    for i in range(equipos_necesarios):
        j1 = jugadores.pop()
        j2 = jugadores.pop()
        nombre_equipo = f"EqSim_{i+1}"
        
        # Buscar equipo existente o crear
        equipo = Equipo.objects.filter(jugador1=j1, jugador2=j2).first()
        if not equipo:
            equipo = Equipo.objects.create(jugador1=j1, jugador2=j2, division=division)
        
        Inscripcion.objects.get_or_create(torneo=torneo, equipo=equipo)
        equipos_inscritos.append(equipo)

    print(f"Inscritos {len(equipos_inscritos)} equipos.")

    # 3. Iniciar Torneo (Generar Grupos)
    # Replicando lógica de iniciar_torneo_logica
    print("Generando fase de grupos...")
    equipos = list(equipos_inscritos)
    random.shuffle(equipos)
    
    equipos_por_grupo = torneo.equipos_por_grupo
    num_grupos = (len(equipos) + equipos_por_grupo - 1) // equipos_por_grupo
    letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

    from itertools import combinations

    for i in range(num_grupos):
        grupo = Grupo.objects.create(torneo=torneo, nombre=f"Grupo {letras[i]}")
        equipos_del_grupo = []
        for _ in range(equipos_por_grupo):
            if equipos:
                equipos_del_grupo.append(equipos.pop())

        for idx, eq in enumerate(equipos_del_grupo, start=1):
            EquipoGrupo.objects.create(grupo=grupo, equipo=eq, numero=idx)

        # Crear partidos de grupo
        partidos_a_crear = []
        for e1, e2 in combinations(equipos_del_grupo, 2):
            partidos_a_crear.append(PartidoGrupo(grupo=grupo, equipo1=e1, equipo2=e2))
        PartidoGrupo.objects.bulk_create(partidos_a_crear)

    torneo.estado = Torneo.Estado.EN_JUEGO
    torneo.save()
    print(f"Fase de grupos generada: {num_grupos} grupos.")

    # 4. Simular Resultados de Grupos
    print("Simulando partidos de grupo...")
    partidos_grupo = PartidoGrupo.objects.filter(grupo__torneo=torneo)
    for p in partidos_grupo:
        # Generar resultado aleatorio
        set1_e1 = random.randint(0, 6)
        set1_e2 = 6 if set1_e1 < 6 else random.randint(0, 5)
        
        set2_e1 = random.randint(0, 6)
        set2_e2 = 6 if set2_e1 < 6 else random.randint(0, 5)
        
        p.e1_set1 = set1_e1
        p.e2_set1 = set1_e2
        p.e1_set2 = set2_e1
        p.e2_set2 = set2_e2
        
        # Determinar ganador simple (quien ganó más sets)
        sets_e1 = (1 if set1_e1 > set1_e2 else 0) + (1 if set2_e1 > set2_e2 else 0)
        sets_e2 = (1 if set1_e2 > set1_e1 else 0) + (1 if set2_e2 > set2_e1 else 0)
        
        if sets_e1 > sets_e2:
            p.ganador = p.equipo1
        elif sets_e2 > sets_e1:
            p.ganador = p.equipo2
        else:
            # Empate (raro en padel pero posible en lógica simple), forzamos ganador
            p.ganador = p.equipo1
            
        p.save()

    print("Partidos de grupo finalizados.")

    # 5. Generar Octavos (Bracket)
    print("Generando bracket...")
    
    # Obtener clasificados
    clasificados = []
    grupos = torneo.grupos.all().order_by('nombre')
    for grupo in grupos:
        tabla = grupo.tabla.all() # Propiedad del modelo Grupo que devuelve tabla ordenada
        # Clasifican 2 por grupo
        for i in range(min(len(tabla), 2)):
            clasificados.append(tabla[i].equipo)
            
    num_equipos_bracket = len(clasificados)
    print(f"Clasificados: {num_equipos_bracket}")
    
    # Calcular tamaño bracket
    bracket_size = 2 ** math.ceil(math.log2(num_equipos_bracket))
    total_rondas = int(math.log2(bracket_size))
    ronda_inicio = 1 # Siempre 1 con nuestra nueva lógica
    
    print(f"Bracket Size: {bracket_size}, Total Rondas: {total_rondas}")

    partidos_ronda_superior = []
    
    # Crear estructura (Final hacia abajo)
    for r in range(total_rondas, 1, -1):
        cant_partidos = 2 ** (total_rondas - r)
        ronda_actual_objs = []
        for i in range(cant_partidos):
            p = Partido.objects.create(torneo=torneo, ronda=r, orden_partido=i+1)
            ronda_actual_objs.append(p)
            if partidos_ronda_superior:
                p.siguiente_partido = partidos_ronda_superior[i // 2]
                p.save()
        partidos_ronda_superior = ronda_actual_objs

    # Crear Ronda 1 (donde entran los equipos)
    random.shuffle(clasificados)
    num_byes = bracket_size - num_equipos_bracket
    slots = clasificados + [None] * num_byes
    
    cant_partidos_r1 = bracket_size // 2
    
    for i in range(cant_partidos_r1):
        e1 = slots.pop(0)
        e2 = slots.pop(0)
        
        p = Partido.objects.create(
            torneo=torneo,
            ronda=ronda_inicio,
            orden_partido=i+1,
            equipo1=e1,
            equipo2=e2,
            siguiente_partido=(partidos_ronda_superior[i // 2] if partidos_ronda_superior else None)
        )
        
        if not e2 and e1:
            p.ganador = e1
            p.resultado = "Bye"
            p.save()
            # Avanzar al siguiente
            if p.siguiente_partido:
                sig = p.siguiente_partido
                if p.orden_partido % 2 != 0:
                    sig.equipo1 = e1
                else:
                    sig.equipo2 = e1
                sig.save()

    print("Bracket generado.")
    
    # 6. Simular algunos partidos de bracket (opcional, para ver avance)
    # Simulamos la primera ronda completa
    print("Simulando primera ronda de bracket...")
    partidos_r1 = Partido.objects.filter(torneo=torneo, ronda=ronda_inicio, ganador__isnull=True)
    for p in partidos_r1:
        if p.equipo1 and p.equipo2:
            # Ganador aleatorio
            ganador = random.choice([p.equipo1, p.equipo2])
            p.ganador = ganador
            p.resultado = "6-4 6-4"
            p.save()
            
            # Avanzar
            if p.siguiente_partido:
                sig = p.siguiente_partido
                if p.orden_partido % 2 != 0:
                    sig.equipo1 = ganador
                else:
                    sig.equipo2 = ganador
                sig.save()

    print(f"Simulación completada. ID del Torneo: {torneo.id}")

if __name__ == "__main__":
    crear_datos_prueba()
