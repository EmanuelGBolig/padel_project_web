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


def guardar_en_panel(user_ids, *, title, body, url='/'):
    """Deja la notificación guardada para la campanita del navbar.

    Va aparte del envío push a propósito: el push puede no llegar nunca (celular
    en silencio, permiso no otorgado, VAPID sin configurar) y aun así el usuario
    tiene que poder entrar y ver qué pasó.
    """
    from .models import Notificacion

    if not user_ids:
        return
    Notificacion.objects.bulk_create([
        Notificacion(usuario_id=uid, titulo=title[:120], cuerpo=body or '', url=url or '/')
        for uid in user_ids
    ])
    _invalidar_contador(user_ids)


def _invalidar_contador(user_ids):
    """El navbar cachea el contador 60s: al crear o leer una, hay que tirarlo."""
    from django.core.cache import cache

    cache.delete_many([f'notifications_count_{uid}' for uid in user_ids])


def send_push_to_users(users, *, title, body, url='/', tag=None, guardar=True):
    """Envía una notificación a todos los dispositivos de `users` (en un hilo).

    `users` puede ser un queryset, lista de usuarios o de IDs.
    No bloquea el request.

    Además la **guarda** en el panel de notificaciones (salvo `guardar=False`).
    Eso se hace antes de mirar si el push está activo, justamente para que el
    historial exista incluso cuando VAPID no está configurado.
    """
    from .models import PushSubscription

    user_ids = [getattr(u, 'id', u) for u in users]

    if guardar:
        try:
            guardar_en_panel(user_ids, title=title, body=body, url=url)
        except Exception:
            # Un aviso no se puede llevar puesta la acción que lo disparó
            # (aceptar una invitación, cargar un resultado…).
            logger.exception("[push] No se pudo guardar la notificación en el panel")

    if not push_activo():
        return

    subs = list(PushSubscription.objects.filter(user_id__in=user_ids))
    if not subs:
        return

    payload_json = json.dumps({'title': title, 'body': body, 'url': url, 'tag': tag})

    def _worker():
        # Django abre una conexión por thread: hay que cerrarla o queda colgada.
        from django.db import connection
        try:
            vencidas = []
            for sub in subs:
                if _enviar_a_suscripcion(sub, payload_json):
                    vencidas.append(sub.pk)
            if vencidas:
                PushSubscription.objects.filter(pk__in=vencidas).delete()
                logger.info(f"[push] {len(vencidas)} suscripciones vencidas eliminadas.")
            logger.info(f"[push] '{title}' enviada a {len(subs) - len(vencidas)} dispositivos.")
        except Exception:
            logger.exception("[push] Fallo enviando notificaciones")
        finally:
            connection.close()

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
