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
        cache.delete(f'rankings_equipos_div_{division.id}')
        
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
