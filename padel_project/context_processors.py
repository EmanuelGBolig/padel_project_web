from equipos.models import Invitation
from torneos.models import Partido, PartidoGrupo
from django.db.models import Q

def notifications(request):
    if not request.user.is_authenticated:
        return {}

    user = request.user
    notification_count = 0
    pending_invitations = 0
    upcoming_matches = 0

    # 1. Invitaciones Pendientes (Recibidas)
    pending_invitations = Invitation.objects.filter(
        invited=user,
        status=Invitation.Status.PENDING
    ).count()

    # 2. Próximos Partidos (Si tiene equipo)
    if hasattr(user, 'equipo') and user.equipo:
        equipo = user.equipo
        
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

    return {
        'notification_count': notification_count,
        'pending_invitations_count': pending_invitations,
        'upcoming_matches_count': upcoming_matches,
    }
