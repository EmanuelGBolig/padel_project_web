import logging
import threading

from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.utils import actualizar_rankings_en_bd

from .models import PartidoGrupo, EquipoGrupo, Partido

logger = logging.getLogger(__name__)

def _recalcular_rankings(division):
    """Worker del thread: recalcula y SIEMPRE cierra la conexión a la base.

    Sin el finally, cada thread deja abierta su propia conexión a Postgres
    (Django abre una por thread) y se agotan las conexiones del plan.
    """
    from django.db import connection
    try:
        actualizar_rankings_en_bd(division)
    except Exception:
        logger.exception("Fallo al actualizar rankings de la división %s", division)
    finally:
        connection.close()


def invalidar_cache_division(division):
    """Borra el caché de rankings cuando cambia algo en una división y regenera la BD."""
    if division:
        # get_division_rankings cachea por división Y género (sufijo _gen_XXX).
        # Borrar sólo `rankings_jugadores_div_<id>` no invalidaba nada: los
        # rankings quedaban servidos del caché hasta que vencía el TTL.
        for genero_key in ('ALL', 'MASCULINO', 'FEMENINO'):
            cache.delete(f'rankings_jugadores_div_{division.id}_gen_{genero_key}')

        # Corremos la actualización de BD asíncrona para no trabar el thread de Django Guardar
        threading.Thread(target=_recalcular_rankings, args=(division,), daemon=True).start()
def invalidar_cache_jugadores_equipo(equipo):
    """Borra el caché de stats de los jugadores de un equipo."""
    if equipo:
        if equipo.jugador1_id:
            cache.delete(f'player_stats_{equipo.jugador1_id}')
        if equipo.jugador2_id:
            cache.delete(f'player_stats_{equipo.jugador2_id}')


CAMPOS_TABLA = [
    'partidos_jugados', 'partidos_ganados', 'partidos_perdidos',
    'sets_a_favor', 'sets_en_contra', 'games_a_favor', 'games_en_contra',
    'diferencia_sets', 'diferencia_games',
]


@receiver(post_save, sender=PartidoGrupo)
def actualizar_tabla_de_posiciones(sender, instance, **kwargs):
    """
    Recalcula las estadísticas de un grupo CADA VEZ que un partido se guarda.
    También invalida el caché de rankings si hay ganador asignado.

    Se resuelve con 3 queries fijas (filas de la tabla + partidos jugados +
    bulk_update). La versión anterior lanzaba 2 queries POR EQUIPO del grupo,
    justo en la acción que el organizador más repite.
    """
    grupo_id = instance.grupo_id

    filas = list(EquipoGrupo.objects.filter(grupo_id=grupo_id))
    if not filas:
        return

    # Acumulador por equipo, en memoria.
    acc = {
        f.equipo_id: dict(
            partidos_jugados=0, partidos_ganados=0, partidos_perdidos=0,
            sets_a_favor=0, sets_en_contra=0, games_a_favor=0, games_en_contra=0,
        )
        for f in filas
    }

    partidos = PartidoGrupo.objects.filter(
        grupo_id=grupo_id, ganador__isnull=False
    ).values(
        'equipo1_id', 'equipo2_id', 'ganador_id',
        'e1_sets_ganados', 'e2_sets_ganados',
        'e1_games_ganados', 'e2_games_ganados',
    )

    for p in partidos:
        for equipo_id, es_e1 in ((p['equipo1_id'], True), (p['equipo2_id'], False)):
            datos = acc.get(equipo_id)
            if datos is None:
                continue  # equipo que ya no está en la tabla del grupo
            datos['partidos_jugados'] += 1
            if p['ganador_id'] == equipo_id:
                datos['partidos_ganados'] += 1
            else:
                datos['partidos_perdidos'] += 1
            if es_e1:
                datos['sets_a_favor'] += p['e1_sets_ganados']
                datos['sets_en_contra'] += p['e2_sets_ganados']
                datos['games_a_favor'] += p['e1_games_ganados']
                datos['games_en_contra'] += p['e2_games_ganados']
            else:
                datos['sets_a_favor'] += p['e2_sets_ganados']
                datos['sets_en_contra'] += p['e1_sets_ganados']
                datos['games_a_favor'] += p['e2_games_ganados']
                datos['games_en_contra'] += p['e1_games_ganados']

    for fila in filas:
        datos = acc[fila.equipo_id]
        for campo, valor in datos.items():
            setattr(fila, campo, valor)
        fila.diferencia_sets = datos['sets_a_favor'] - datos['sets_en_contra']
        fila.diferencia_games = datos['games_a_favor'] - datos['games_en_contra']

    EquipoGrupo.objects.bulk_update(filas, CAMPOS_TABLA)

    grupo = instance.grupo
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
