from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q
from .models import PartidoGrupo, EquipoGrupo

@receiver(post_save, sender=PartidoGrupo)
def actualizar_tabla_de_posiciones(sender, instance, **kwargs):
    """
    Recalcula las estadísticas de un grupo CADA VEZ que un partido se guarda.
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