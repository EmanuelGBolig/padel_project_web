"""Armado de los datos de las placas 9:16 para redes.

El pipeline de export (html2canvas a 1080×1920 + share sheet nativo) ya estaba
resuelto para las placas de torneo; acá se agregan las de jugador y de resultado
de partido, que son las que convierten cada partido en un posteo.
"""


def _iniciales_de(nombre, apellido=''):
    a = (nombre or '').strip()
    b = (apellido or '').strip()
    return ((a[:1] + b[:1]) or '?').upper()


def datos_placa_jugador(jugador):
    """Ficha del jugador: división, ranking, win rate, racha y logros."""
    from accounts.utils import get_player_achievements, get_player_stats, get_user_ranking

    stats = get_player_stats(jugador)
    ranking = get_user_ranking(jugador) or {}
    logros = get_player_achievements(jugador, stats) or []

    # Sólo los logros conseguidos: una placa con casilleros vacíos no se comparte.
    desbloqueados = [l for l in logros if l.get('unlocked')]

    return {
        'nombre': jugador.full_name,
        'iniciales': _iniciales_de(jugador.nombre, jugador.apellido),
        'foto': jugador.imagen.url if getattr(jugador, 'imagen', None) else '',
        'division': jugador.division.nombre if jugador.division else 'Sin división',
        'ciudad': getattr(jugador, 'ciudad', '') or '',
        'posicion_ranking': ranking.get('posicion'),
        'puntos': ranking.get('puntos'),
        'partidos_jugados': stats.get('partidos_jugados', 0),
        'victorias': stats.get('victorias', 0),
        'derrotas': stats.get('derrotas', 0),
        'win_rate': stats.get('win_rate', 0),
        'racha_actual': stats.get('racha_actual', 0),
        'racha_maxima': stats.get('racha_maxima', 0),
        'torneos_jugados': stats.get('torneos_jugados', 0),
        'torneos_ganados': stats.get('torneos_ganados', 0),
        'logros': desbloqueados[:3],
        'url_label': 'todopadel.club',
    }


def datos_placa_resultado(partido):
    """Resultado de un partido, de zona o de llave."""
    e1, e2 = partido.equipo1, partido.equipo2
    torneo = getattr(partido, 'torneo', None) or partido.grupo.torneo

    # El contexto es la ronda (llave) o el nombre de la zona.
    if hasattr(partido, 'nombre_ronda'):
        contexto = partido.nombre_ronda
    else:
        contexto = partido.grupo.nombre

    ganador = partido.ganador
    return {
        'org_nombre': torneo.organizacion.nombre if torneo.organizacion else 'TodoPadel',
        'org_iniciales': _iniciales_de(torneo.organizacion.nombre) if torneo.organizacion else 'TP',
        'torneo': torneo.nombre,
        'division': torneo.division.nombre if torneo.division else 'Libre',
        'contexto': contexto,
        'e1': e1.nombre if e1 else 'A definir',
        'e2': e2.nombre if e2 else 'A definir',
        'e1_gano': bool(ganador and e1 and ganador.pk == e1.pk),
        'e2_gano': bool(ganador and e2 and ganador.pk == e2.pk),
        'resultado': partido.resultado or '',
        'resolucion': partido.etiqueta_resolucion if hasattr(partido, 'etiqueta_resolucion') else '',
        'fecha': partido.fecha_hora,
        'jugado': bool(ganador),
        'url_label': 'todopadel.club',
    }
