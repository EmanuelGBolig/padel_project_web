from django.db.models import Count, Q
from django.core.cache import cache

def get_division_rankings(division):
    """
    Calcula el ranking de jugadores para una división específica.
    Retorna una lista de diccionarios ordenada por puntos.
    Usa caché para optimizar rendimiento.
    """
    if not division:
        return []

    cache_key = f'rankings_jugadores_div_{division.id}'
    cached_rankings = cache.get(cache_key)
    
    if cached_rankings is not None:
        return cached_rankings

    from .models import CustomUser

    # Obtener jugadores que:
    # 1. Pertenecen a esta división (aunque no hayan jugado)
    # 2. O Han jugado en un equipo de esta división (aunque sean de otra, si eso fuera posible)
    jugadores_con_stats = CustomUser.objects.filter(
        Q(division=division) |
        Q(equipos_como_jugador1__division=division) | 
        Q(equipos_como_jugador2__division=division)
    ).distinct().annotate(
        # Victorias como jugador1 en partidos de eliminación
        victorias_j1_elim=Count(
            'equipos_como_jugador1__partidos_bracket_ganados',
            filter=Q(equipos_como_jugador1__partidos_bracket_ganados__isnull=False),
            distinct=True
        ),
        # Victorias como jugador1 en partidos de grupo
        victorias_j1_grupo=Count(
            'equipos_como_jugador1__partidos_grupo_ganados',
            filter=Q(equipos_como_jugador1__partidos_grupo_ganados__isnull=False),
            distinct=True
        ),
        # Victorias como jugador2 en partidos de eliminación
        victorias_j2_elim=Count(
            'equipos_como_jugador2__partidos_bracket_ganados',
            filter=Q(equipos_como_jugador2__partidos_bracket_ganados__isnull=False),
            distinct=True
        ),
        # Victorias como jugador2 en partidos de grupo
        victorias_j2_grupo=Count(
            'equipos_como_jugador2__partidos_grupo_ganados',
            filter=Q(equipos_como_jugador2__partidos_grupo_ganados__isnull=False),
            distinct=True
        ),
        # Partidos jugados como jugador1 en eliminación
        partidos_j1_elim_1=Count(
            'equipos_como_jugador1__partidos_bracket_e1',
            filter=Q(equipos_como_jugador1__partidos_bracket_e1__ganador__isnull=False),
            distinct=True
        ),
        partidos_j1_elim_2=Count(
            'equipos_como_jugador1__partidos_bracket_e2',
            filter=Q(equipos_como_jugador1__partidos_bracket_e2__ganador__isnull=False),
            distinct=True
        ),
        # Partidos jugados como jugador1 en grupo
        partidos_j1_grupo_1=Count(
            'equipos_como_jugador1__partidos_grupo_e1',
            filter=Q(equipos_como_jugador1__partidos_grupo_e1__ganador__isnull=False),
            distinct=True
        ),
        partidos_j1_grupo_2=Count(
            'equipos_como_jugador1__partidos_grupo_e2',
            filter=Q(equipos_como_jugador1__partidos_grupo_e2__ganador__isnull=False),
            distinct=True
        ),
        # Partidos jugados como jugador2 en eliminación
        partidos_j2_elim_1=Count(
            'equipos_como_jugador2__partidos_bracket_e1',
            filter=Q(equipos_como_jugador2__partidos_bracket_e1__ganador__isnull=False),
            distinct=True
        ),
        partidos_j2_elim_2=Count(
            'equipos_como_jugador2__partidos_bracket_e2',
            filter=Q(equipos_como_jugador2__partidos_bracket_e2__ganador__isnull=False),
            distinct=True
        ),
        # Partidos jugados como jugador2 en grupo
        partidos_j2_grupo_1=Count(
            'equipos_como_jugador2__partidos_grupo_e1',
            filter=Q(equipos_como_jugador2__partidos_grupo_e1__ganador__isnull=False),
            distinct=True
        ),
        partidos_j2_grupo_2=Count(
            'equipos_como_jugador2__partidos_grupo_e2',
            filter=Q(equipos_como_jugador2__partidos_grupo_e2__ganador__isnull=False),
            distinct=True
        ),
        # Torneos ganados
        torneos_j1=Count('equipos_como_jugador1__torneos_ganados', distinct=True),
        torneos_j2=Count('equipos_como_jugador2__torneos_ganados', distinct=True),
    )
    
    # Procesar jugadores y calcular métricas
    jugadores_con_puntos = []
    for jugador in jugadores_con_stats:
        # Calcular totales
        victorias_total = (jugador.victorias_j1_elim + jugador.victorias_j1_grupo +
                          jugador.victorias_j2_elim + jugador.victorias_j2_grupo)
        
        partidos_total = (jugador.partidos_j1_elim_1 + jugador.partidos_j1_elim_2 +
                         jugador.partidos_j1_grupo_1 + jugador.partidos_j1_grupo_2 +
                         jugador.partidos_j2_elim_1 + jugador.partidos_j2_elim_2 +
                         jugador.partidos_j2_grupo_1 + jugador.partidos_j2_grupo_2)
        
        torneos_ganados = jugador.torneos_j1 + jugador.torneos_j2
        
        # Calcular win rate
        if partidos_total > 0:
            win_rate = round((victorias_total / partidos_total) * 100, 1)
        else:
            win_rate = 0
        
        # Calcular puntos de ranking
        puntos = victorias_total * 3  # 3 puntos por victoria
        puntos += torneos_ganados * 50  # 50 puntos por torneo ganado
        
        # Bonus por win rate alto (más estricto para jugadores)
        if win_rate >= 75 and partidos_total >= 10:
            puntos += 20
        
        # Include all users
        # Obtener equipo(s) actual(es) del jugador en esta división
        equipos_actuales = []
        if hasattr(jugador, 'equipo') and jugador.equipo and jugador.equipo.division == division:
            equipos_actuales.append(jugador.equipo)
        
        jugadores_con_puntos.append({
            'jugador': jugador,
            'puntos': puntos,
            'victorias': victorias_total,
            'win_rate': win_rate,
            'torneos_ganados': torneos_ganados,
            'equipos': equipos_actuales,
            'partidos_totales': partidos_total
        })
    
    # Ordenar por puntos
    jugadores_con_puntos.sort(key=lambda x: x['puntos'], reverse=True)
    
    # Agregar posición
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
