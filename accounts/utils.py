from django.db.models import Count, Q

def get_player_stats(jugador):
    """
    Calcula las estadísticas completas de un jugador.
    Retorna un diccionario con:
    - partidos_jugados
    - partidos_ganados
    - partidos_perdidos
    - win_rate
    - torneos_jugados (incluye finalizados y en juego)
    - torneos_ganados
    - racha_actual (si se implementa)
    """
    
    # 1. Calcular Victorias
    victorias_j1_elim = jugador.equipos_como_jugador1.filter(
        partidos_bracket_ganados__isnull=False
    ).count()
    
    victorias_j1_grupo = jugador.equipos_como_jugador1.filter(
        partidos_grupo_ganados__isnull=False
    ).count()
    
    victorias_j2_elim = jugador.equipos_como_jugador2.filter(
        partidos_bracket_ganados__isnull=False
    ).count()
    
    victorias_j2_grupo = jugador.equipos_como_jugador2.filter(
        partidos_grupo_ganados__isnull=False
    ).count()
    
    total_victorias = victorias_j1_elim + victorias_j1_grupo + victorias_j2_elim + victorias_j2_grupo

    # 2. Calcular Partidos Jugados (Ganados + Perdidos)
    # Nota: Esto es una aproximación, lo ideal es contar todos los partidos donde participó el equipo
    # y el partido tiene resultado.
    
    # Helper para contar partidos jugados por queryset de equipos
    def contar_partidos_equipos(equipos_qs):
        count = 0
        for equipo in equipos_qs:
            # Partidos de Grupo
            count += equipo.partidos_grupo_e1.filter(ganador__isnull=False).count()
            count += equipo.partidos_grupo_e2.filter(ganador__isnull=False).count()
            # Partidos de Bracket
            count += equipo.partidos_bracket_e1.filter(ganador__isnull=False).count()
            count += equipo.partidos_bracket_e2.filter(ganador__isnull=False).count()
        return count

    # Esta lógica es pesada si se itera, pero para un solo perfil está bien.
    # Para el ranking masivo usamos annotate. Este helper es para el perfil detallado.
    
    partidos_jugados = 0
    
    # Equipos donde es J1
    equipos_j1 = jugador.equipos_como_jugador1.all()
    for equipo in equipos_j1:
         partidos_jugados += equipo.partidos_grupo_e1.filter(ganador__isnull=False).count()
         partidos_jugados += equipo.partidos_grupo_e2.filter(ganador__isnull=False).count()
         partidos_jugados += equipo.partidos_bracket_e1.filter(ganador__isnull=False).count()
         partidos_jugados += equipo.partidos_bracket_e2.filter(ganador__isnull=False).count()

    # Equipos donde es J2
    equipos_j2 = jugador.equipos_como_jugador2.all()
    for equipo in equipos_j2:
         partidos_jugados += equipo.partidos_grupo_e1.filter(ganador__isnull=False).count()
         partidos_jugados += equipo.partidos_grupo_e2.filter(ganador__isnull=False).count()
         partidos_jugados += equipo.partidos_bracket_e1.filter(ganador__isnull=False).count()
         partidos_jugados += equipo.partidos_bracket_e2.filter(ganador__isnull=False).count()

    total_derrotas = partidos_jugados - total_victorias
    
    win_rate = 0
    if partidos_jugados > 0:
        win_rate = round((total_victorias / partidos_jugados) * 100, 1)

    # 3. Torneos
    # Torneos ganados
    torneos_ganados = jugador.equipos_como_jugador1.filter(torneos_ganados__isnull=False).count() + \
                      jugador.equipos_como_jugador2.filter(torneos_ganados__isnull=False).count()

    # Torneos jugados (a través de inscripciones sería lo más correcto, pero equipos vinculados a torneos también sirve si hay relación directa o inferida)
    # Asumiendo que Equipo se crea por torneo o Inscripción vincula Equipo-Torneo
    
    from torneos.models import Inscripcion
    
    # Torneos donde ha participado (estado FINALIZADO o EN_JUEGO)
    inscripciones = Inscripcion.objects.filter(
        Q(equipo__jugador1=jugador) | Q(equipo__jugador2=jugador)
    ).select_related('torneo')
    
    torneos_jugados = inscripciones.count()
    
    return {
        'partidos_jugados': partidos_jugados,
        'victorias': total_victorias,
        'derrotas': total_derrotas,
        'win_rate': win_rate,
        'torneos_jugados': torneos_jugados,
        'torneos_ganados': torneos_ganados,
        'inscripciones': inscripciones # Para listar los torneos
    }
