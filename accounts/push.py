"""Envío de notificaciones Web Push (TP-11).

Usa pywebpush + claves VAPID (env vars VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY).
Si las claves no están configuradas, todo es no-op silencioso (no rompe nada).
Las suscripciones vencidas (404/410 del endpoint) se borran solas.
"""
import json
import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)


def push_activo():
    return bool(settings.VAPID_PRIVATE_KEY and settings.VAPID_PUBLIC_KEY)


def _enviar_a_suscripcion(sub, payload_json):
    """Envía a UNA suscripción. Devuelve True si hay que borrarla (vencida)."""
    from pywebpush import webpush, WebPushException

    try:
        webpush(
            subscription_info={
                'endpoint': sub.endpoint,
                'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
            },
            data=payload_json,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={'sub': settings.VAPID_ADMIN_EMAIL},
            ttl=86400,
        )
        return False
    except WebPushException as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status in (404, 410):
            return True  # suscripción vencida
        logger.warning(f"[push] Error enviando a {sub.endpoint[:50]}: {e}")
        return False
    except Exception as e:
        logger.warning(f"[push] Error inesperado: {e}")
        return False


def send_push_to_users(users, *, title, body, url='/', tag=None):
    """Envía una notificación a todos los dispositivos de `users` (en un hilo).

    `users` puede ser un queryset, lista de usuarios o de IDs.
    No bloquea el request; si VAPID no está configurado, no hace nada.
    """
    if not push_activo():
        return

    from .models import PushSubscription

    user_ids = [getattr(u, 'id', u) for u in users]
    subs = list(PushSubscription.objects.filter(user_id__in=user_ids))
    if not subs:
        return

    payload_json = json.dumps({'title': title, 'body': body, 'url': url, 'tag': tag})

    def _worker():
        vencidas = []
        for sub in subs:
            if _enviar_a_suscripcion(sub, payload_json):
                vencidas.append(sub.pk)
        if vencidas:
            PushSubscription.objects.filter(pk__in=vencidas).delete()
            logger.info(f"[push] {len(vencidas)} suscripciones vencidas eliminadas.")
        logger.info(f"[push] '{title}' enviada a {len(subs) - len(vencidas)} dispositivos.")

    threading.Thread(target=_worker, daemon=True).start()


def send_push_to_user(user, **kwargs):
    send_push_to_users([user], **kwargs)


def jugadores_de_equipos(*equipos):
    """Jugadores reales (no dummy) de uno o más equipos, para notificarlos."""
    out = []
    for eq in equipos:
        if not eq:
            continue
        for j in (eq.jugador1, eq.jugador2):
            if j and not getattr(j, 'is_dummy', False):
                out.append(j)
    return out
