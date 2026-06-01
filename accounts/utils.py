from django.db.models import Count, Q, Sum, Value, IntegerField
from django.db.models.functions import Coalesce
from django.core.cache import cache
from .models import CustomUser

def get_division_rankings(division, genero=None, force_recalc=False):
    if not division:
        return []

    genero_key = genero if genero in ('MASCULINO', 'FEMENINO') else 'ALL'
    cache_key = f'rankings_jugadores_div_{division.id}_gen_{genero_key}'
    
    if not force_recalc:
        cached_rankings = cache.get(cache_key)
        if cached_rankings is not None:
            return cached_rankings

        from equipos.models import RankingJugador
        from django.db.models import Prefetch
        from equipos.models import Equipo

        # Prefetch de equipos para el jugador para evitar N+1 en el loop de abajo
        equipos_prefetch = Prefetch(
            'jugador__equipos_como_jugador1',
            queryset=Equipo.objects.all().select_related('jugador1', 'jugador2', 'division')
        )
        equipos_prefetch2 = Prefetch(
            'jugador__equipos_como_jugador2',
            queryset=Equipo.objects.all().select_related('jugador1', 'jugador2', 'division')
        )

        rankings_db = RankingJugador.objects.filter(
            division=division, jugador__merged_into__isnull=True
        ).select_related('jugador').prefetch_related(
            equipos_prefetch, equipos_prefetch2
        ).order_by('-puntos', '-torneos_ganados', '-victorias')

        # Filtrar por género si se especifica
        if genero_key != 'ALL':
            rankings_db = rankings_db.filter(jugador__genero=genero_key)

        result = []
        jugadores_en_ranking = set()

        for i, r in enumerate(rankings_db, 1):
            win_rate = round((r.victorias / r.partidos_jugados) * 100, 1) if r.partidos_jugados > 0 else 0
            equipos_j1 = list(r.jugador.equipos_como_jugador1.all())
            equipos_j2 = list(r.jugador.equipos_como_jugador2.all())
            primer_equipo = equipos_j1[0] if equipos_j1 else (equipos_j2[0] if equipos_j2 else None)

            result.append({
                'jugador': r.jugador,
                'puntos': r.puntos,
                'victorias': r.victorias,
                'win_rate': win_rate,
                'torneos_ganados': r.torneos_ganados,
                'equipos': [primer_equipo] if primer_equipo else [],
                'partidos_totales': r.partidos_jugados,
                'posicion': i
            })
            jugadores_en_ranking.add(r.jugador.id)
        
        # --- NUEVA LÓGICA: Añadir jugadores que están en la división pero no en la tabla RankingJugador ---
        jugadores_faltantes_qs = CustomUser.objects.filter(
            division=division,
            tipo_usuario='PLAYER',
            merged_into__isnull=True,
        ).exclude(id__in=jugadores_en_ranking).select_related('division').prefetch_related('equipos_como_jugador1', 'equipos_como_jugador2')

        if genero_key != 'ALL':
            jugadores_faltantes_qs = jugadores_faltantes_qs.filter(genero=genero_key)

        next_pos = len(result) + 1
        for j in jugadores_faltantes_qs:
            # Intentar obtener un equipo para el jugador
            equipos_j1 = list(j.equipos_como_jugador1.all())
            equipos_j2 = list(j.equipos_como_jugador2.all())
            primer_equipo = equipos_j1[0] if equipos_j1 else (equipos_j2[0] if equipos_j2 else None)

            result.append({
                'jugador': j,
                'puntos': 0,
                'victorias': 0,
                'win_rate': 0,
                'torneos_ganados': 0,
                'equipos': [primer_equipo] if primer_equipo else [],
                'partidos_totales': 0,
                'posicion': next_pos
            })
            next_pos += 1
        
        cache.set(cache_key, result, 300)
        return result

    from torneos.models import Partido, PartidoGrupo, Torneo

    torneo_ids = list(Torneo.objects.filter(division=division).values_list('id', flat=True))

    if not torneo_ids:
        jugadores_qs = CustomUser.objects.filter(
            division=division, tipo_usuario='PLAYER', merged_into__isnull=True
        ).select_related('division')
        if genero_key != 'ALL':
            jugadores_qs = jugadores_qs.filter(genero=genero_key)
        result = [{
            'jugador': j, 'puntos': 0, 'victorias': 0,
            'win_rate': 0, 'torneos_ganados': 0,
            'equipos': [], 'partidos_totales': 0
        } for j in jugadores_qs]
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
        players_in_match = {p['equipo1__jugador1'], p['equipo1__jugador2'], p['equipo2__jugador1'], p['equipo2__jugador2']}
        for jid in players_in_match:
            if jid: add_partidos(jid, 1)
            
        add_victorias(p['ganador__jugador1'], 1)
        add_victorias(p['ganador__jugador2'], 1)

    for p in partidos_grupo:
        players_in_match = {p['equipo1__jugador1'], p['equipo1__jugador2'], p['equipo2__jugador1'], p['equipo2__jugador2']}
        for jid in players_in_match:
            if jid: add_partidos(jid, 1)

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

    jugadores_qs = CustomUser.objects.filter(
        Q(division=division) | Q(id__in=jugador_ids_con_datos),
        tipo_usuario='PLAYER',
        merged_into__isnull=True,
    ).distinct().select_related('division').prefetch_related('equipos_como_jugador1', 'equipos_como_jugador2')
    if genero_key != 'ALL':
        jugadores_qs = jugadores_qs.filter(genero=genero_key)
    jugadores = jugadores_qs

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

def calcular_puntos_por_jugador(torneo_ids):
    """Puntos acumulados por jugador para un conjunto de torneos (TP-12, circuitos).

    Usa el MISMO esquema que el ranking general: 15 pts por victoria de zona,
    45/90/180/360 por ronda máxima alcanzada en la llave (octavos/cuartos/semi/final)
    y 600 al campeón. Devuelve {jugador_id: {'puntos','victorias','partidos','torneos_ganados'}}.

    Función independiente de get_division_rankings para no alterar el ranking existente.
    """
    from torneos.models import Partido, PartidoGrupo, Torneo

    torneo_ids = list(torneo_ids)
    data = {}

    def ensure(jid):
        if jid not in data:
            data[jid] = {'puntos': 0, 'victorias': 0, 'partidos': 0, 'torneos_ganados': 0}
        return data[jid]

    if not torneo_ids:
        return data

    # Victorias en zona (15 pts c/u)
    for v in (PartidoGrupo.objects
              .filter(grupo__torneo_id__in=torneo_ids, ganador__isnull=False)
              .values('ganador__jugador1', 'ganador__jugador2')
              .annotate(wins=Count('id'))):
        for key in ('ganador__jugador1', 'ganador__jugador2'):
            jid = v[key]
            if jid:
                d = ensure(jid)
                d['puntos'] += v['wins'] * 15
                d['victorias'] += v['wins']

    # Partidos jugados (zona + llave)
    for qs in (
        PartidoGrupo.objects.filter(grupo__torneo_id__in=torneo_ids, ganador__isnull=False),
        Partido.objects.filter(torneo_id__in=torneo_ids, ganador__isnull=False),
    ):
        for p in qs.values('equipo1__jugador1', 'equipo1__jugador2',
                           'equipo2__jugador1', 'equipo2__jugador2'):
            for key in ('equipo1__jugador1', 'equipo1__jugador2',
                        'equipo2__jugador1', 'equipo2__jugador2'):
                if p[key]:
                    ensure(p[key])['partidos'] += 1

    # Victorias en la llave
    for p in (Partido.objects.filter(torneo_id__in=torneo_ids, ganador__isnull=False)
              .values('ganador__jugador1', 'ganador__jugador2')):
        for key in ('ganador__jugador1', 'ganador__jugador2'):
            if p[key]:
                ensure(p[key])['victorias'] += 1

    # Campeones (600 pts)
    camps = {}
    for t in (Torneo.objects.filter(id__in=torneo_ids, ganador_del_torneo__isnull=False)
              .values('id', 'ganador_del_torneo__jugador1', 'ganador_del_torneo__jugador2')):
        s = set()
        for key in ('ganador_del_torneo__jugador1', 'ganador_del_torneo__jugador2'):
            if t[key]:
                s.add(t[key])
                ensure(t[key])['torneos_ganados'] += 1
        camps[t['id']] = s

    # Ronda máxima por jugador por torneo
    max_ronda = {}  # (torneo_id, jugador_id) -> ronda
    for bm in (Partido.objects
               .filter(torneo_id__in=torneo_ids, equipo1__isnull=False,
                       equipo2__isnull=False, ganador__isnull=False)
               .values('torneo_id', 'ronda', 'equipo1__jugador1', 'equipo1__jugador2',
                       'equipo2__jugador1', 'equipo2__jugador2')):
        for key in ('equipo1__jugador1', 'equipo1__jugador2',
                    'equipo2__jugador1', 'equipo2__jugador2'):
            jid = bm[key]
            if jid:
                k = (bm['torneo_id'], jid)
                if bm['ronda'] > max_ronda.get(k, 0):
                    max_ronda[k] = bm['ronda']

    puntos_ronda = {4: 360, 3: 180, 2: 90, 1: 45}
    for (tid, jid), mx in max_ronda.items():
        if jid in camps.get(tid, set()):
            ensure(jid)['puntos'] += 600
        else:
            ensure(jid)['puntos'] += puntos_ronda.get(mx, 0)

    return data


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

    # 5. Resultados recientes (TP-19.2): últimos partidos jugados con ganador.
    #    Se computan acá para compartir la caché/invalidación de las stats.
    _etiqueta_reso = {'W': 'W.O.', 'A': 'Abandono'}
    raw = []
    pg_qs = PartidoGrupo.objects.filter(
        Q(equipo1_id__in=todos_equipo_ids) | Q(equipo2_id__in=todos_equipo_ids),
        ganador__isnull=False,
    ).select_related('grupo__torneo', 'equipo1', 'equipo2')
    for p in pg_qs:
        ts = p.fecha_hora.timestamp() if p.fecha_hora else 0
        raw.append((ts, 'g', p))
    pe_qs = Partido.objects.filter(
        Q(equipo1_id__in=todos_equipo_ids) | Q(equipo2_id__in=todos_equipo_ids),
        ganador__isnull=False,
    ).select_related('torneo', 'equipo1', 'equipo2')
    for p in pe_qs:
        ts = p.fecha_hora.timestamp() if p.fecha_hora else 0
        raw.append((ts, 'e', p))
    raw.sort(key=lambda x: x[0], reverse=True)

    resultados_recientes = []
    for ts, kind, p in raw[:8]:
        mine1 = p.equipo1_id in todos_equipo_ids
        rival = p.equipo2 if mine1 else p.equipo1
        if kind == 'g':
            torneo_nombre = p.grupo.torneo.nombre
            contexto = p.grupo.nombre
        else:
            torneo_nombre = p.torneo.nombre
            contexto = p.nombre_ronda
        reso = getattr(p, 'resolucion', 'N')
        resultados_recientes.append({
            'torneo': torneo_nombre,
            'contexto': contexto,
            'fecha': p.fecha_hora,
            'rival': rival.nombre if rival else '—',
            'resultado': p.resultado,
            'gano': p.ganador_id in todos_equipo_ids,
            'etiqueta': _etiqueta_reso.get(reso, ''),
        })

    # 6. Racha (TP-19.4): sobre el historial completo, en orden cronológico.
    historial_asc = sorted(raw, key=lambda x: x[0])
    wins_seq = [p.ganador_id in todos_equipo_ids for _ts, _k, p in historial_asc]
    racha_maxima = 0
    cur = 0
    for w in wins_seq:
        cur = cur + 1 if w else 0
        racha_maxima = max(racha_maxima, cur)
    racha_actual = 0
    for w in reversed(wins_seq):
        if w:
            racha_actual += 1
        else:
            break

    result = {
        'partidos_jugados': total_partidos,
        'victorias': total_victorias,
        'derrotas': total_derrotas,
        'win_rate': win_rate,
        'torneos_jugados': torneos_jugados,
        'torneos_ganados': torneos_ganados,
        'inscripciones': list(inscripciones),
        'resultados_recientes': resultados_recientes,
        'racha_actual': racha_actual,
        'racha_maxima': racha_maxima,
    }
    cache.set(cache_key, result, 300)
    return result


def get_player_achievements(jugador, stats):
    """Logros del jugador (TP-19.4), derivados de stats ya cacheadas.

    Devuelve lista de dicts {emoji, titulo, desc, unlocked}. Los que requieren
    histórico de posición de ranking (no existe hoy) quedan bloqueados.
    """
    pj = stats.get('partidos_jugados', 0)
    tg = stats.get('torneos_ganados', 0)
    wr = stats.get('win_rate', 0)
    rmax = stats.get('racha_maxima', 0)
    plural = 's' if tg != 1 else ''
    return [
        {'emoji': '🏆', 'titulo': 'Campeón',
         'desc': f'{tg} título{plural} ganado{plural}', 'unlocked': tg > 0},
        {'emoji': '🔥', 'titulo': f'Racha máx: {rmax}' if rmax else 'Racha',
         'desc': 'victorias seguidas', 'unlocked': rmax >= 3},
        {'emoji': '🎾', 'titulo': '+10 partidos',
         'desc': 'jugador activo', 'unlocked': pj >= 10},
        {'emoji': '🎯', 'titulo': 'Efectivo',
         'desc': '60%+ de win rate', 'unlocked': wr >= 60 and pj >= 5},
        {'emoji': '💯', 'titulo': '100% en zona',
         'desc': 'ganá todos los partidos de una zona', 'unlocked': False},
        {'emoji': '⭐', 'titulo': 'Top 10',
         'desc': 'entrá al top 10 del ranking', 'unlocked': False},
    ]


def get_profile_completeness(user):
    """% de perfil completo + checklist con CTAs (TP-19.4)."""
    from django.urls import reverse
    ficha_ok = bool(
        user.posicion_cancha or user.mano_habil or user.club
        or user.ciudad or user.juega_desde or user.bio
    )
    items = [
        {'label': 'Foto de perfil', 'done': bool(user.imagen),
         'cta_url': '#upload-foto', 'cta_text': 'Subir'},
        {'label': 'Tu división', 'done': bool(user.division_id),
         'cta_url': '', 'cta_text': ''},
        {'label': 'Formá tu pareja', 'done': bool(getattr(user, 'equipo', None)),
         'cta_url': reverse('equipos:crear'), 'cta_text': 'Crear'},
        {'label': 'Ficha de juego', 'done': ficha_ok,
         'cta_url': '', 'cta_text': 'Editar'},
        {'label': 'Tu Instagram', 'done': bool(user.instagram),
         'cta_url': '', 'cta_text': 'Agregar'},
    ]
    done = sum(1 for i in items if i['done'])
    total = len(items)
    return {'pct': round(done / total * 100), 'items': items, 'done': done, 'total': total}

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

def actualizar_rankings_en_bd(division):
    """
    Recalcula los rankings de Jugadores y Equipos para una división específica
    y guarda esos valores defintivamente en las tablas RankingJugador y RankingEquipo.
    Se manda a llamar desde los signals (post_save de partidos).
    """
    if not division:
        return

    from equipos.models import RankingJugador
    
    # IMPORTANTE: Borramos los registros actuales de la división para evitar puntos obsoletos
    # de jugadores que ya no participan o torneos eliminados.
    RankingJugador.objects.filter(division=division).delete()

    # 1. Traer data cruda de jugadores (está en este mismo archivo, usamos recalc forzado)
    jugadores_data = get_division_rankings(division, force_recalc=True)
    for item in jugadores_data:
        RankingJugador.objects.update_or_create(
            jugador=item['jugador'],
            division=division,
            defaults={
                'puntos': item['puntos'],
                'torneos_ganados': item['torneos_ganados'],
                'victorias': item['victorias'],
                'partidos_jugados': item['partidos_totales']
            }
        )


def _normalizar_nombre(s):
    """minúsculas + sin tildes + espacios colapsados (para comparar nombres)."""
    import unicodedata
    s = (s or '').strip().lower()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ' '.join(s.split())


def find_duplicate_candidates(limit_pairs=20000):
    """Detecta posibles cuentas duplicadas de jugadores (TP-20).

    Agrupa por nombre normalizado (sin tildes/mayúsculas):
      - clave exacta igual  -> confianza 'alta'
      - similitud >= 0.88    -> confianza 'media'
    NUNCA fusiona sola: devuelve grupos para que un humano confirme. El canónico
    sugerido es la cuenta real (no dummy) más antigua del grupo.
    """
    from difflib import SequenceMatcher

    users = list(CustomUser.objects.filter(
        tipo_usuario='PLAYER', merged_into__isnull=True
    ).select_related('division').order_by('date_joined'))

    info = [{'user': u, 'key': _normalizar_nombre(f"{u.nombre} {u.apellido}")} for u in users]

    # Union-Find sobre los índices
    parent = list(range(len(info)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    by_key = {}
    for idx, it in enumerate(info):
        if it['key']:
            by_key.setdefault(it['key'], []).append(idx)

    # 1) Claves exactas iguales -> mismo grupo
    for idxs in by_key.values():
        for j in idxs[1:]:
            union(idxs[0], j)

    # 2) Claves distintas pero muy similares -> mismo grupo
    keys = list(by_key.keys())
    pairs = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            pairs += 1
            if pairs > limit_pairs:
                break
            ka, kb = keys[i], keys[j]
            if abs(len(ka) - len(kb)) > 4:
                continue
            if SequenceMatcher(None, ka, kb).ratio() >= 0.88:
                union(by_key[ka][0], by_key[kb][0])

    grupos = {}
    for idx, it in enumerate(info):
        if it['key']:
            grupos.setdefault(find(idx), []).append(it)

    resultado = []
    for items in grupos.values():
        if len(items) < 2:
            continue
        usuarios = [x['user'] for x in items]
        confianza = 'alta' if len({x['key'] for x in items}) == 1 else 'media'
        reales = [u for u in usuarios if not u.is_dummy]
        canonico = reales[0] if reales else usuarios[0]
        resultado.append({
            'confianza': confianza,
            'usuarios': usuarios,
            'sugerido_id': canonico.id,
        })
    resultado.sort(key=lambda g: (0 if g['confianza'] == 'alta' else 1, -len(g['usuarios'])))
    return resultado


def _mover_historial_equipo(src_id, dst_id):
    """Mueve todo el historial del equipo `src_id` al equipo `dst_id` (TP-20).

    Inscripciones y EquipoGrupo se reasignan evitando duplicados (mismo torneo/grupo);
    partidos y ganadores se reapuntan al equipo destino.
    """
    from torneos.models import Inscripcion, EquipoGrupo, PartidoGrupo, Partido, Torneo

    for ins in Inscripcion.objects.filter(equipo_id=src_id):
        if Inscripcion.objects.filter(equipo_id=dst_id, torneo_id=ins.torneo_id).exists():
            ins.delete()
        else:
            ins.equipo_id = dst_id
            ins.save()

    for eg in EquipoGrupo.objects.filter(equipo_id=src_id):
        if EquipoGrupo.objects.filter(equipo_id=dst_id, grupo_id=eg.grupo_id).exists():
            eg.delete()
        else:
            eg.equipo_id = dst_id
            eg.save()

    PartidoGrupo.objects.filter(equipo1_id=src_id).update(equipo1_id=dst_id)
    PartidoGrupo.objects.filter(equipo2_id=src_id).update(equipo2_id=dst_id)
    PartidoGrupo.objects.filter(ganador_id=src_id).update(ganador_id=dst_id)
    Partido.objects.filter(equipo1_id=src_id).update(equipo1_id=dst_id)
    Partido.objects.filter(equipo2_id=src_id).update(equipo2_id=dst_id)
    Partido.objects.filter(ganador_id=src_id).update(ganador_id=dst_id)
    Torneo.objects.filter(ganador_del_torneo_id=src_id).update(ganador_del_torneo_id=dst_id)


def merge_users(dummy_user, real_user):
    """
    Fusiona la cuenta `dummy_user` (origen) dentro de `real_user` (destino),
    traspasando todo el historial. (TP-20)

    - Si el origen es DUMMY: se elimina al terminar (no tiene login real).
    - Si el origen es una cuenta REAL: se DESACTIVA y se marca `merged_into` al
      destino (no se borra), para preservar su email y poder enrutar el login
      a la cuenta canónica en la etapa 2.

    El destino debe ser una cuenta real (no se fusiona dentro de un dummy).
    """
    from django.db import transaction
    from equipos.models import Equipo

    if real_user.is_dummy:
        raise ValueError("El usuario destino debe ser una cuenta Real.")
    if dummy_user.pk == real_user.pk:
        raise ValueError("No se puede fusionar una cuenta consigo misma.")

    with transaction.atomic():
        # 1+2. Traspasar equipos del origen al destino, equipo por equipo, de forma
        # SEGURA ante la constraint unique_active_team (par activo único). Si ya
        # existe el equipo (destino, compañero), se absorbe el historial ahí; si no,
        # se reasigna el equipo al destino. (Antes un .update() masivo rompía la
        # constraint a mitad de camino — TP-20 fix.)
        source_team_ids = list(Equipo.objects.filter(
            Q(jugador1=dummy_user) | Q(jugador2=dummy_user)
        ).values_list('id', flat=True))

        for tid in source_team_ids:
            t = Equipo.objects.filter(pk=tid).first()
            if not t:
                continue
            partner_id = t.jugador2_id if t.jugador1_id == dummy_user.id else t.jugador1_id

            # Equipo sin compañero, o "auto-pareja" (origen + destino): no tiene
            # sentido como pareja tras la fusión -> se desactiva y se reasigna el
            # slot del origen al destino (el historial queda atado al equipo inactivo).
            if partner_id is None or partner_id == real_user.id:
                nj1, nj2 = real_user.id, partner_id
                if nj2 is not None and nj1 > nj2:
                    nj1, nj2 = nj2, nj1
                Equipo.objects.filter(pk=tid).update(
                    jugador1_id=nj1, jugador2_id=nj2, esta_activo=False
                )
                continue

            # ¿Ya existe un equipo (destino, compañero) en cualquier orden?
            # Preferimos el activo como canónico para no dejar la pareja sin equipo activo.
            canonical = Equipo.objects.filter(
                Q(jugador1_id=real_user.id, jugador2_id=partner_id)
                | Q(jugador1_id=partner_id, jugador2_id=real_user.id)
            ).exclude(pk=tid).order_by('-esta_activo', 'id').first()

            if canonical:
                _mover_historial_equipo(tid, canonical.id)
                Equipo.objects.filter(pk=tid).delete()
            else:
                nj1, nj2 = real_user.id, partner_id
                if nj1 > nj2:
                    nj1, nj2 = nj2, nj1
                Equipo.objects.filter(pk=tid).update(jugador1_id=nj1, jugador2_id=nj2)
                eq = Equipo.objects.filter(pk=tid).first()
                if eq:
                    eq.save()  # re-normaliza nombre/división

        # 3. Cerrar la cuenta origen
        if dummy_user.is_dummy:
            # Los dummies no tienen login ni valor propio: se eliminan.
            dummy_user.delete()
        else:
            # Cuenta real: se desactiva y se enlaza a la canónica (no se borra).
            dummy_user.is_active = False
            dummy_user.merged_into = real_user
            dummy_user.save(update_fields=['is_active', 'merged_into'])

        # 4. Forzar recalculo de rankings para las divisiones del usuario real
        from accounts.models import Division
        for div in Division.objects.all():
            actualizar_rankings_en_bd(div)

