from django.db.models import Count, Q, Sum, Value, IntegerField
from django.db.models.functions import Coalesce
from django.core.cache import cache

def get_division_rankings(division):
    """
    Calcula el ranking de jugadores para una división específica.
    Estrategia: Consultas simples por partido/torneo, agrupadas en Python.
    Usa caché para optimizar rendimiento.
    """
    if not division:
        return []

    cache_key = f'rankings_jugadores_div_{division.id}'
    cached_rankings = cache.get(cache_key)
    
    if cached_rankings is not None:
        return cached_rankings

    from .models import CustomUser
    from torneos.models import Partido, PartidoGrupo, Torneo

    # 1. Todos los torneos de esta división
    torneo_ids = list(Torneo.objects.filter(division=division).values_list('id', flat=True))

    if not torneo_ids:
        # No hay torneos, solo devolver jugadores de la división con 0 puntos
        jugadores = CustomUser.objects.filter(
            division=division, tipo_usuario='PLAYER'
        ).select_related('division')
        result = [{
            'jugador': j, 'puntos': 0, 'victorias': 0,
            'win_rate': 0, 'torneos_ganados': 0,
            'equipos': [], 'partidos_totales': 0
        } for j in jugadores]
        for i, item in enumerate(result, 1):
            item['posicion'] = i
        cache.set(cache_key, result, 300)
        return result

    # 2. Victorias en partidos de eliminación (bracket) — consulta simple
    victorias_bracket = (
        Partido.objects.filter(torneo_id__in=torneo_ids, ganador__isnull=False)
        .values('ganador__jugador1', 'ganador__jugador2')
        .annotate(wins=Count('id'))
    )

    # 3. Victorias en partidos de grupo — consulta simple
    victorias_grupo = (
        PartidoGrupo.objects.filter(
            grupo__torneo_id__in=torneo_ids, ganador__isnull=False
        )
        .values('ganador__jugador1', 'ganador__jugador2')
        .annotate(wins=Count('id'))
    )

    # 4. Partidos jugados en bracket — consulta simple
    partidos_bracket = (
        Partido.objects.filter(torneo_id__in=torneo_ids, ganador__isnull=False)
        .values('equipo1__jugador1', 'equipo1__jugador2', 'equipo2__jugador1', 'equipo2__jugador2')
    )

    # 5. Partidos jugados en grupo — consulta simple
    partidos_grupo = (
        PartidoGrupo.objects.filter(
            grupo__torneo_id__in=torneo_ids, ganador__isnull=False
        )
        .values('equipo1__jugador1', 'equipo1__jugador2', 'equipo2__jugador1', 'equipo2__jugador2')
    )

    # 6. Torneos ganados
    torneos_ganados_data = (
        Torneo.objects.filter(id__in=torneo_ids, campeon__isnull=False)
        .values('campeon__jugador1', 'campeon__jugador2')
    )

    # Agregar datos por jugador en Python (más rápido que múltiples JOINs en SQL)
    victorias_por_jugador = {}
    partidos_por_jugador = {}
    torneos_ganados_por_jugador = {}

    def add_wins(jugador_id, wins=1):
        if jugador_id:
            victorias_por_jugador[jugador_id] = victorias_por_jugador.get(jugador_id, 0) + wins

    def add_partidos(jugador_id, count=1):
        if jugador_id:
            partidos_por_jugador[jugador_id] = partidos_por_jugador.get(jugador_id, 0) + count

    def add_torneo(jugador_id):
        if jugador_id:
            torneos_ganados_por_jugador[jugador_id] = torneos_ganados_por_jugador.get(jugador_id, 0) + 1

    for v in victorias_bracket:
        add_wins(v['ganador__jugador1'], v['wins'])
        add_wins(v['ganador__jugador2'], v['wins'])

    for v in victorias_grupo:
        add_wins(v['ganador__jugador1'], v['wins'])
        add_wins(v['ganador__jugador2'], v['wins'])

    for p in partidos_bracket:
        add_partidos(p['equipo1__jugador1'])
        add_partidos(p['equipo1__jugador2'])
        add_partidos(p['equipo2__jugador1'])
        add_partidos(p['equipo2__jugador2'])

    for p in partidos_grupo:
        add_partidos(p['equipo1__jugador1'])
        add_partidos(p['equipo1__jugador2'])
        add_partidos(p['equipo2__jugador1'])
        add_partidos(p['equipo2__jugador2'])

    for t in torneos_ganados_data:
        add_torneo(t['campeon__jugador1'])
        add_torneo(t['campeon__jugador2'])

    # Obtener todos los jugadores relevantes: de la división O que hayan participado
    jugador_ids_con_datos = (
        set(victorias_por_jugador.keys()) |
        set(partidos_por_jugador.keys()) |
        set(torneos_ganados_por_jugador.keys())
    )

    jugadores = CustomUser.objects.filter(
        Q(division=division) | Q(id__in=jugador_ids_con_datos),
        tipo_usuario='PLAYER'
    ).distinct().select_related('division')

    # Construir lista de ranking en Python
    jugadores_con_puntos = []
    for jugador in jugadores:
        victorias = victorias_por_jugador.get(jugador.id, 0)
        partidos = partidos_por_jugador.get(jugador.id, 0)
        t_ganados = torneos_ganados_por_jugador.get(jugador.id, 0)

        win_rate = round((victorias / partidos) * 100, 1) if partidos > 0 else 0
        puntos = victorias * 3 + t_ganados * 50
        if win_rate >= 75 and partidos >= 10:
            puntos += 20

        equipos_actuales = []
        if hasattr(jugador, 'equipo') and jugador.equipo and jugador.equipo.division == division:
            equipos_actuales.append(jugador.equipo)

        jugadores_con_puntos.append({
            'jugador': jugador,
            'puntos': puntos,
            'victorias': victorias,
            'win_rate': win_rate,
            'torneos_ganados': t_ganados,
            'equipos': equipos_actuales,
            'partidos_totales': partidos,
        })

    # Ordenar y agregar posición
    jugadores_con_puntos.sort(key=lambda x: x['puntos'], reverse=True)
    for i, item in enumerate(jugadores_con_puntos, 1):
        item['posicion'] = i

    # Guardar en cache por 5 minutos
    cache.set(cache_key, jugadores_con_puntos, 300)

    return jugadores_con_puntos


def get_user_ranking(user):
    """
    Obtiene la información de ranking para un usuario específico.
    Retorna un diccionario con la info del ranking o None si no tiene división/ranking.
    """
    if not user.division:
        return None
        
    rankings = get_division_rankings(user.division)
    
    for item in rankings:
        if item['jugador'].id == user.id:
            return item
            
    return None

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


def send_email_async(subject, html_template, context, recipient_list, from_email=None):
    """
    Función utilitaria para enviar correos de forma asíncrona usando hilos.
    """
    from django.core.mail import send_mail
    from django.conf import settings
    from django.template.loader import render_to_string
    from django.utils.html import strip_tags
    import threading
    import sys

    # Renderizar el cuerpo del correo
    html_message = render_to_string(html_template, context)
    plain_message = strip_tags(html_message)
    
    # Usar remitente por defecto si no se especifica
    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    def _send():
        print(f"--- [Async Mail] Enviando a {recipient_list} desde {from_email} ---")
        try:
            send_mail(
                subject,
                plain_message,
                from_email,
                recipient_list,
                html_message=html_message,
                fail_silently=False, 
            )
            print("--- [Async Mail] Enviado correctamente ---")
        except Exception as e:
            print(f"!!! [Async Mail] Error: {e}")
            import traceback
            traceback.print_exc()

    email_thread = threading.Thread(target=_send)
    email_thread.start()
