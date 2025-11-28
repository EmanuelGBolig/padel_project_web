from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache


@receiver(post_save, sender='torneos.Partido')
@receiver(post_delete, sender='torneos.Partido')
@receiver(post_save, sender='torneos.PartidoGrupo')
@receiver(post_delete, sender='torneos.PartidoGrupo')
@receiver(post_save, sender='torneos.Torneo')
@receiver(post_delete, sender='torneos.Torneo')
def invalidar_cache_rankings(sender, instance, **kwargs):
    """
    Invalida el cache de rankings cuando se actualiza un partido o torneo.
    Esto asegura que los rankings siempre muestren datos actualizados.
    """
    # Obtener todas las claves de cache que empiezan con 'rankings_'
    # En producción, considera usar cache.delete_pattern() si usas Redis
    
    # Para LocMemCache, debemos eliminar claves específicas
    # Eliminar cache de todas las divisiones y cache general
    cache.delete('rankings_all')
    
    # También eliminar cache de divisiones específicas
    # Esto requeriría conocer todos los IDs de división, así que
    # por simplicidad limpiamos todo durante 5 minutos después de un cambio
    from equipos.models import Division
    for division in Division.objects.all():
        cache.delete(f'rankings_div_{division.id}')
