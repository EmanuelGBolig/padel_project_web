from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from django.core.cache import cache
from .models import PartidoGrupo, EquipoGrupo, Partido


import threading
from accounts.utils import actualizar_rankings_en_bd

def invalidar_cache_division(division):
    """Borra el caché de rankings cuando cambia algo en una división y regenera la BD."""
    if division:
        cache.delete(f'rankings_jugadores_div_{division.id}')
        
        # Corremos la actualización de BD asíncrona para no trabar el thread de Django Guardar
        threading.Thread(target=actualizar_rankings_en_bd, args=(division,)).start()
def invalidar_cache_jugadores_equipo(equipo):
    """Borra el caché de stats de los jugadores de un equipo."""
    if equipo:
        if equipo.jugador1_id:
            cache.delete(f'player_stats_{equipo.jugador1_id}')
        if equipo.jugador2_id:
            cache.delete(f'player_stats_{equipo.jugador2_id}')


@receiver(post_save, sender=PartidoGrupo)
def actualizar_tabla_de_posiciones(sender, instance, **kwargs):
    """
    Recalcula las estadísticas de un grupo CADA VEZ que un partido se guarda.
    También invalida el caché de rankings si hay ganador asignado.
    """
    grupo = instance.grupo

    # Recalculamos para todos los equipos de este grupo
    for equipo_grupo in EquipoGrupo.objects.filter(grupo=grupo):
        equipo = equipo_grupo.equipo

        # Obtenemos todos los partidos JUGADOS y FINALIZADOS de este equipo en este grupo
        partidos_jugados = PartidoGrupo.objects.filter(
            grupo=grupo, ganador__isnull=False
        ).filter(Q(equipo1=equipo) | Q(equipo2=equipo))

        # Reseteamos todo a 0
        equipo_grupo.partidos_jugados = partidos_jugados.count()
        equipo_grupo.partidos_ganados = 0
        equipo_grupo.partidos_perdidos = 0
        equipo_grupo.sets_a_favor = 0
        equipo_grupo.sets_en_contra = 0
        equipo_grupo.games_a_favor = 0
        equipo_grupo.games_en_contra = 0

        # Sumamos las estadísticas de cada partido
        for partido in partidos_jugados:
            if partido.ganador == equipo:
                equipo_grupo.partidos_ganados += 1
            else:
                equipo_grupo.partidos_perdidos += 1

            # Sumar sets y games
            if partido.equipo1 == equipo:
                equipo_grupo.sets_a_favor += partido.e1_sets_ganados
                equipo_grupo.sets_en_contra += partido.e2_sets_ganados
                equipo_grupo.games_a_favor += partido.e1_games_ganados
                equipo_grupo.games_en_contra += partido.e2_games_ganados
            else:  # (equipo es equipo2)
                equipo_grupo.sets_a_favor += partido.e2_sets_ganados
                equipo_grupo.sets_en_contra += partido.e1_sets_ganados
                equipo_grupo.games_a_favor += partido.e2_games_ganados
                equipo_grupo.games_en_contra += partido.e1_games_ganados

        # Calcular diferencias
        equipo_grupo.diferencia_sets = equipo_grupo.sets_a_favor - equipo_grupo.sets_en_contra
        equipo_grupo.diferencia_games = equipo_grupo.games_a_favor - equipo_grupo.games_en_contra

        # Guardamos la tabla de posiciones actualizada
        equipo_grupo.save()

    # Invalidar caché de rankings si hay ganador
    if instance.ganador:
        division = grupo.torneo.division if grupo and grupo.torneo else None
        invalidar_cache_division(division)
        invalidar_cache_jugadores_equipo(instance.equipo1)
        invalidar_cache_jugadores_equipo(instance.equipo2)


@receiver(post_save, sender=Partido)
def invalidar_cache_partido_bracket(sender, instance, **kwargs):
    """Invalida caché de rankings cuando se guarda un resultado de partido de bracket."""
    if instance.ganador:
        division = instance.torneo.division if instance.torneo else None
        invalidar_cache_division(division)
        invalidar_cache_jugadores_equipo(instance.equipo1)
        invalidar_cache_jugadores_equipo(instance.equipo2)


@receiver(post_save, sender=PartidoGrupo)
def check_llaves_internas_generacion(sender, instance, **kwargs):
    """
    Genera automáticamente la Ronda 2 (Partido de Ganadores y Partido de Perdedores)
    y asigna prioridades cuando se termina la Ronda 1 en formato Llaves.
    """
    grupo = instance.grupo
    torneo = grupo.torneo
    
    # Validar que aplique la regla
    from .models import Torneo
    if torneo.formato_grupos_4 != Torneo.FormatoZonas4.LLAVES:
        return
        
    if grupo.tabla.count() != 4:
        return
        
    if not instance.ganador:
        return
        
    partidos_del_grupo = list(PartidoGrupo.objects.filter(grupo=grupo).order_by('id'))
    
    # Si hay exactamente 2 partidos y ambos tienen ganador, es momento de crear la Ronda 2
    if len(partidos_del_grupo) == 2:
        p1 = partidos_del_grupo[0]
        p2 = partidos_del_grupo[1]
        
        if p1.ganador and p2.ganador:
            perdedor1 = p1.equipo1 if p1.ganador == p1.equipo2 else p1.equipo2
            perdedor2 = p2.equipo1 if p2.ganador == p2.equipo2 else p2.equipo2
            
            # Ganador vs Ganador (Ronda 2)
            PartidoGrupo.objects.create(
                grupo=grupo,
                equipo1=p1.ganador,
                equipo2=p2.ganador
            )
            
            # Perdedor vs Perdedor (Ronda 2)
            PartidoGrupo.objects.create(
                grupo=grupo,
                equipo1=perdedor1,
                equipo2=perdedor2
            )
    
    # NOTA: No asignamos prioridades manuales. 
    # El ranking se calcula por victorias/sets/games sobre los 4 partidos totales.
