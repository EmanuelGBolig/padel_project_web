import logging
from django.core.mail import send_mass_mail
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def notificar_nuevo_torneo(torneo):
    """
    Envía un email a todos los jugadores elegibles cuando se crea un nuevo torneo.
    Elegibilidad:
    - tipo_usuario == PLAYER, is_active=True, is_dummy=False
    - División dentro del rango ±1 del torneo (o cualquier división si el torneo es libre)
    - Género compatible con la categoría del torneo
    """
    from accounts.models import CustomUser

    jugadores = CustomUser.objects.filter(
        tipo_usuario=CustomUser.TipoUsuario.PLAYER,
        is_active=True,
        is_dummy=False,
    ).exclude(email='')

    # --- Filtro por género / categoría ---
    if torneo.categoria == 'M':   # Masculino
        jugadores = jugadores.filter(genero='MASCULINO')
    elif torneo.categoria == 'F':  # Femenino
        jugadores = jugadores.filter(genero='FEMENINO')
    # Mixto ('X') → no filtramos por género

    # --- Filtro por división ---
    if torneo.division is not None:
        # Incluir misma división y adyacentes (±1 en orden)
        orden_torneo = torneo.division.orden
        jugadores = jugadores.filter(
            division__orden__gte=orden_torneo - 1,
            division__orden__lte=orden_torneo + 1,
        )

    if not jugadores.exists():
        logger.info(f"[emails] Torneo '{torneo.nombre}': no hay jugadores elegibles para notificar.")
        return

    # --- Armar los mensajes ---
    site_url = getattr(settings, 'SITE_URL', 'https://todopadel.club')
    torneo_url = f"{site_url}/torneos/{torneo.pk}/"
    from_email = settings.DEFAULT_FROM_EMAIL if not settings.DEBUG else 'noreply@todopadel.club'

    asunto = f"🎾 Nuevo torneo disponible: {torneo.nombre}"

    mensajes = []
    for jugador in jugadores:
        contexto = {
            'jugador': jugador,
            'torneo': torneo,
            'torneo_url': torneo_url,
        }
        cuerpo_html = render_to_string('torneos/emails/nuevo_torneo.html', contexto)
        # send_mass_mail requiere (asunto, cuerpo_texto, from, [destinatarios])
        # Usamos el HTML como cuerpo de texto plano de respaldo simplificado
        cuerpo_texto = (
            f"Hola {jugador.full_name},\n\n"
            f"Se abrió la inscripción para el torneo: {torneo.nombre}\n"
            f"División: {torneo.division or 'Libre'}\n"
            f"Categoría: {torneo.get_categoria_display()}\n"
            f"Fecha: {torneo.fecha_inicio.strftime('%d/%m/%Y')}\n\n"
            f"Inscribite acá: {torneo_url}\n\n"
            f"— El equipo de TodoPadel"
        )
        mensajes.append((asunto, cuerpo_texto, from_email, [jugador.email]))

    try:
        enviados = send_mass_mail(tuple(mensajes), fail_silently=False)
        logger.info(f"[emails] Torneo '{torneo.nombre}': {enviados} emails enviados a jugadores elegibles.")
    except Exception as e:
        logger.error(f"[emails] Error al enviar notificaciones para torneo '{torneo.nombre}': {e}")
