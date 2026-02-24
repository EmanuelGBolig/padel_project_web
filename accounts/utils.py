from django.db.models import Count, Q, Sum, Value, IntegerField
from django.db.models.functions import Coalesce
from django.core.cache import cache

def get_division_rankings(division):
    if not division:
        return []

    cache_key = f'rankings_jugadores_div_{division.id}'
    cached_rankings = cache.get(cache_key)
    
    if cached_rankings is not None:
        return cached_rankings

    from .models import CustomUser
    from torneos.models import Partido, PartidoGrupo, Torneo

    torneo_ids = list(Torneo.objects.filter(division=division).values_list('id', flat=True))

    if not torneo_ids:
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

    # 1. Victorias en partidos de grupo (15 puntos por victoria)
    victorias_grupo = (
        PartidoGrupo.objects.filter(
            grupo__torneo_id__in=torneo_ids, ganador__isnull=False
        )
        .values('ganador__jugador1', 'ganador__jugador2')
        .annotate(wins=Count('id'))
    )

    # 2. Partidos totales para estadisticas (jugados)
    partidos_bracket = Partido.objects.filter(torneo_id__in=torneo_ids, ganador__isnull=False).values(
        'equipo1__jugador1', 'equipo1__jugador2', 'equipo2__jugador1', 'equipo2__jugador2', 'ganador__jugador1', 'ganador__jugador2'
    )
    partidos_grupo = PartidoGrupo.objects.filter(grupo__torneo_id__in=torneo_ids, ganador__isnull=False).values(
        'equipo1__jugador1', 'equipo1__jugador2', 'equipo2__jugador1', 'equipo2__jugador2', 'ganador__jugador1', 'ganador__jugador2'
    )

    # 3. Puntos por Bracket (Ronda máxima)
    # Rondas: 4=Final, 3=Semi, 2=Cuartos, 1=Octavos
    bracket_matches = Partido.objects.filter(
        torneo_id__in=torneo_ids, equipo1__isnull=False, equipo2__isnull=False, ganador__isnull=False
    ).values(
        'torneo_id', 'ronda', 'ganador__jugador1', 'ganador__jugador2',
        'equipo1__jugador1', 'equipo1__jugador2', 'equipo2__jugador1', 'equipo2__jugador2'
    )
    
    torneos_ganadores = Torneo.objects.filter(id__in=torneo_ids, ganador_del_torneo__isnull=False).values(
        'id', 'ganador_del_torneo__jugador1', 'ganador_del_torneo__jugador2'
    )

    victorias_por_jugador = {}
    partidos_por_jugador = {}
    puntos_por_jugador = {}
    torneos_ganados_por_jugador = {}

    def add_victorias(jid, count):
        if jid: victorias_por_jugador[jid] = victorias_por_jugador.get(jid, 0) + count

    def add_partidos(jid, count):
        if jid: partidos_por_jugador[jid] = partidos_por_jugador.get(jid, 0) + count

    def add_puntos(jid, pts):
        if jid: puntos_por_jugador[jid] = puntos_por_jugador.get(jid, 0) + pts

    def add_torneo(jid):
        if jid: torneos_ganados_por_jugador[jid] = torneos_ganados_por_jugador.get(jid, 0) + 1

    for v in victorias_grupo:
        add_victorias(v['ganador__jugador1'], v['wins'])
        add_victorias(v['ganador__jugador2'], v['wins'])
        add_puntos(v['ganador__jugador1'], v['wins'] * 15)
        add_puntos(v['ganador__jugador2'], v['wins'] * 15)

    for p in partidos_bracket:
        add_partidos(p['equipo1__jugador1'], 1)
        add_partidos(p['equipo1__jugador2'], 1)
        add_partidos(p['equipo2__jugador1'], 1)
        add_partidos(p['equipo2__jugador2'], 1)
        add_victorias(p['ganador__jugador1'], 1)
        add_victorias(p['ganador__jugador2'], 1)

    for p in partidos_grupo:
        add_partidos(p['equipo1__jugador1'], 1)
        add_partidos(p['equipo1__jugador2'], 1)
        add_partidos(p['equipo2__jugador1'], 1)
        add_partidos(p['equipo2__jugador2'], 1)

    # Determinar Campeones por Torneo
    camps = {}
    for t in torneos_ganadores:
        tid = t['id']
        j1 = t['ganador_del_torneo__jugador1']
        j2 = t['ganador_del_torneo__jugador2']
        camps[tid] = {j1, j2}
        add_torneo(j1)
        add_torneo(j2)

    # Max ronda logic
    max_ronda_jugador_torneo = {} # {torneo_id: {jugador_id: max_ronda}}
    for bm in bracket_matches:
        tid = bm['torneo_id']
        ronda = bm['ronda']
        if tid not in max_ronda_jugador_torneo:
            max_ronda_jugador_torneo[tid] = {}
        for d in ['equipo1__jugador1', 'equipo1__jugador2', 'equipo2__jugador1', 'equipo2__jugador2']:
            jid = bm[d]
            if jid:
                curr = max_ronda_jugador_torneo[tid].get(jid, 0)
                if ronda > curr:
                    max_ronda_jugador_torneo[tid][jid] = ronda

    # Points assign
    for tid, jugadores_rondas in max_ronda_jugador_torneo.items():
        torneo_campeones = camps.get(tid, set())
        for jid, mx_rnda in jugadores_rondas.items():
            if jid in torneo_campeones:
                add_puntos(jid, 600)
            else:
                if mx_rnda == 4:
                    add_puntos(jid, 360) # Finalista
                elif mx_rnda == 3:
                    add_puntos(jid, 180) # Semifinal
                elif mx_rnda == 2:
                    add_puntos(jid, 90)  # Cuartos
                elif mx_rnda == 1:
                    add_puntos(jid, 45)  # Octavos

    jugador_ids_con_datos = (
        set(victorias_por_jugador.keys()) |
        set(partidos_por_jugador.keys()) |
        set(torneos_ganados_por_jugador.keys()) |
        set(puntos_por_jugador.keys())
    )

    jugadores = CustomUser.objects.filter(
        Q(division=division) | Q(id__in=jugador_ids_con_datos),
        tipo_usuario='PLAYER'
    ).distinct().select_related('division').prefetch_related('equipos_como_jugador1', 'equipos_como_jugador2')

    jugadores_con_puntos = []
    for jugador in jugadores:
        victorias = victorias_por_jugador.get(jugador.id, 0)
        partidos = partidos_por_jugador.get(jugador.id, 0)
        t_ganados = torneos_ganados_por_jugador.get(jugador.id, 0)
        puntos = puntos_por_jugador.get(jugador.id, 0)

        win_rate = round((victorias / partidos) * 100, 1) if partidos > 0 else 0

        equipos_j1 = list(jugador.equipos_como_jugador1.all())
        equipos_j2 = list(jugador.equipos_como_jugador2.all())
        
        primer_equipo = None
        if equipos_j1:
            primer_equipo = equipos_j1[0]
        elif equipos_j2:
            primer_equipo = equipos_j2[0]

        jugadores_con_puntos.append({
            'jugador': jugador,
            'puntos': puntos,
            'victorias': victorias,
            'win_rate': win_rate,
            'torneos_ganados': t_ganados,
            'equipos': [primer_equipo] if primer_equipo else [],
            'partidos_totales': partidos,
        })

    jugadores_con_puntos.sort(
        key=lambda x: (
            x['puntos'],
            x['torneos_ganados'],
            x['win_rate'],
            x['victorias']
        ),
        reverse=True
    )

    for i, item in enumerate(jugadores_con_puntos, 1):
        item['posicion'] = i

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
    Usa consultas directas (sin N+1) y caché.
    """
    cache_key = f'player_stats_{jugador.id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from torneos.models import Partido, PartidoGrupo, Inscripcion

    # IDs de equipos del jugador (consulta mínima)
    equipo_ids_j1 = list(jugador.equipos_como_jugador1.values_list('id', flat=True))
    equipo_ids_j2 = list(jugador.equipos_como_jugador2.values_list('id', flat=True))
    todos_equipo_ids = equipo_ids_j1 + equipo_ids_j2

    if not todos_equipo_ids:
        result = {
            'partidos_jugados': 0, 'victorias': 0, 'derrotas': 0,
            'win_rate': 0, 'torneos_jugados': 0, 'torneos_ganados': 0,
            'inscripciones': []
        }
        cache.set(cache_key, result, 300)
        return result

    # 1. Victorias (consultas directas, sin loops)
    victorias_elim = Partido.objects.filter(
        ganador_id__in=todos_equipo_ids, ganador__isnull=False
    ).count()
    victorias_grupo = PartidoGrupo.objects.filter(
        ganador_id__in=todos_equipo_ids, ganador__isnull=False
    ).count()
    total_victorias = victorias_elim + victorias_grupo

    # 2. Partidos jugados (consultas directas)
    partidos_elim = Partido.objects.filter(
        Q(equipo1_id__in=todos_equipo_ids) | Q(equipo2_id__in=todos_equipo_ids),
        ganador__isnull=False
    ).count()
    partidos_grupo = PartidoGrupo.objects.filter(
        Q(equipo1_id__in=todos_equipo_ids) | Q(equipo2_id__in=todos_equipo_ids),
        ganador__isnull=False
    ).count()
    total_partidos = partidos_elim + partidos_grupo

    total_derrotas = total_partidos - total_victorias
    win_rate = round((total_victorias / total_partidos) * 100, 1) if total_partidos > 0 else 0

    # 3. Torneos ganados
    torneos_ganados = Partido.objects.filter(
        ganador_id__in=todos_equipo_ids,
        es_final=True
    ).count() if hasattr(Partido, 'es_final') else \
        jugador.equipos_como_jugador1.filter(torneos_ganados__isnull=False).count() + \
        jugador.equipos_como_jugador2.filter(torneos_ganados__isnull=False).count()

    # 4. Inscripciones (consulta única con select_related)
    inscripciones = Inscripcion.objects.filter(
        Q(equipo__jugador1=jugador) | Q(equipo__jugador2=jugador)
    ).select_related(
        'torneo', 
        'torneo__division',
        'torneo__ganador_del_torneo',
        'torneo__ganador_del_torneo__jugador1',
        'torneo__ganador_del_torneo__jugador2',
        'equipo', 
        'equipo__division'
    ).order_by('-fecha_inscripcion')


    torneos_jugados = inscripciones.count()

    result = {
        'partidos_jugados': total_partidos,
        'victorias': total_victorias,
        'derrotas': total_derrotas,
        'win_rate': win_rate,
        'torneos_jugados': torneos_jugados,
        'torneos_ganados': torneos_ganados,
        'inscripciones': list(inscripciones)
    }
    cache.set(cache_key, result, 300)
    return result

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
