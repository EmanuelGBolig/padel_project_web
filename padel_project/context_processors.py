from equipos.models import Invitation
from torneos.models import Partido, PartidoGrupo
from django.db.models import Q

def notifications(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    
    # Intentar obtener del caché para no saturar con 3-5 queries por cada click
    from django.core.cache import cache
    cache_key = f'notifications_count_{user.id}'
    cached_data = cache.get(cache_key)
    if cached_data:
        return cached_data

    notification_count = 0
    pending_invitations = 0
    upcoming_matches = 0

    # 1. Invitaciones Pendientes (Recibidas)
    pending_invitations = Invitation.objects.filter(
        invited=user,
        status=Invitation.Status.PENDING
    ).count()

    # 2. Próximos Partidos (Si tiene equipo)
    # Evitar llamar a la propiedad .equipo múltiples veces
    equipo = user.equipo
    if equipo:
        # Partidos de Eliminatoria Pendientes
        matches_elim = Partido.objects.filter(
            Q(equipo1=equipo) | Q(equipo2=equipo),
            ganador__isnull=True,
            torneo__estado__in=['AB', 'EJ']
        ).count()

        # Partidos de Fase de Grupos Pendientes
        matches_group = PartidoGrupo.objects.filter(
            Q(equipo1=equipo) | Q(equipo2=equipo),
            ganador__isnull=True,
            grupo__torneo__estado__in=['AB', 'EJ']
        ).count()
        
        upcoming_matches = matches_elim + matches_group

    notification_count = pending_invitations + upcoming_matches

    res = {
        'notification_count': notification_count,
        'pending_invitations_count': pending_invitations,
        'upcoming_matches_count': upcoming_matches,
    }
    # Cache por 60 segundos (suficiente para fluidez sin perder mucha frescura)
    cache.set(cache_key, res, 60)
    return res

