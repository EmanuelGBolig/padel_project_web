"""Estado de cobro de las inscripciones de un torneo.

El circuito real es por transferencia y comprobante por WhatsApp: acá sólo se
lleva el registro para que el organizador sepa quién pagó y quién no, sin
cruzar una planilla aparte.
"""
from django.db.models import Count, Q, Sum
from django.utils import timezone

from ..models import EstadoPago, Inscripcion


def resumen_de_cobros(torneo):
    """Totales de cobro del torneo, en una sola query.

    Devuelve un dict con los conteos por estado, lo recaudado y lo que falta.
    """
    agg = torneo.inscripciones.aggregate(
        total=Count('id'),
        pendientes=Count('id', filter=Q(estado_pago=EstadoPago.PENDIENTE)),
        senados=Count('id', filter=Q(estado_pago=EstadoPago.SENADO)),
        pagados=Count('id', filter=Q(estado_pago=EstadoPago.PAGADO)),
        exentos=Count('id', filter=Q(estado_pago=EstadoPago.EXENTO)),
        recaudado=Sum('monto_pagado'),
    )
    total = agg['total'] or 0
    recaudado = agg['recaudado'] or 0

    precio = torneo.precio_inscripcion or 0
    # Los exentos no se esperan cobrar.
    esperado = precio * max(0, total - (agg['exentos'] or 0))

    return {
        'total': total,
        'pendientes': agg['pendientes'] or 0,
        'senados': agg['senados'] or 0,
        'pagados': agg['pagados'] or 0,
        'exentos': agg['exentos'] or 0,
        'recaudado': recaudado,
        'esperado': esperado,
        'falta': max(0, esperado - recaudado),
        'pct': round(100 * recaudado / esperado) if esperado else 0,
    }


def marcar_pago(inscripcion, estado, monto=None, nota=None):
    """Cambia el estado de pago de una inscripción.

    Devuelve la inscripción actualizada. `fecha_pago` se sella la primera vez
    que queda saldada, y se limpia si vuelve a pendiente.
    """
    if estado not in dict(EstadoPago.choices):
        raise ValueError(f"Estado de pago inválido: {estado}")

    inscripcion.estado_pago = estado

    if monto is not None:
        inscripcion.monto_pagado = monto or None
    if nota is not None:
        inscripcion.nota_pago = nota[:200]

    if estado in (EstadoPago.PAGADO, EstadoPago.SENADO):
        if not inscripcion.fecha_pago:
            inscripcion.fecha_pago = timezone.now()
    elif estado == EstadoPago.PENDIENTE:
        inscripcion.fecha_pago = None

    inscripcion.save(update_fields=[
        'estado_pago', 'monto_pagado', 'nota_pago', 'fecha_pago',
    ])
    return inscripcion


def inscripciones_con_pago(torneo):
    """Inscripciones del torneo listas para mostrar en el panel de cobros."""
    return (
        Inscripcion.objects
        .filter(torneo=torneo)
        .select_related('equipo', 'equipo__jugador1', 'equipo__jugador2')
        .order_by('estado_pago', 'fecha_inscripcion')
    )
