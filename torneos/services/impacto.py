"""Cuánto alcanzan a los datos YA existentes los cambios de comportamiento.

Los arreglos de la auditoría cambiaron algunas reglas. Casi todos son mejoras
puras, pero tres tocan cosas que hoy funcionan y conviene mirar contra los datos
reales ANTES de desplegar. Como no hay shell en Render, esto se consume desde la
página de diagnóstico.

Es de SOLO LECTURA: cuenta y explica, no modifica nada.
"""
from django.contrib.auth import get_user_model

from ..models import Americano
from .alta_sin_cuenta import _cola_telefono, _solo_digitos


def americanos_sin_club():
    """Americanos con `organizacion` vacía.

    `AmericanoManageView` pasó a filtrar por club (antes cualquier organizador
    podía gestionar el de otro). Un americano sin club queda fuera del alcance
    de TODO organizador: sólo lo puede tocar un admin. Si hay alguno acá, hay
    que asignarle club.
    """
    huerfanos = list(
        Americano.objects.filter(organizacion__isnull=True)
        .order_by('-id')[:50]
    )
    return {
        'total': Americano.objects.count(),
        'huerfanos': huerfanos,
        'cantidad': Americano.objects.filter(organizacion__isnull=True).count(),
    }


def telefonos_afectados():
    """Teléfonos que dejan de engancharse solos en el alta sin cuenta.

    Antes se comparaban los últimos 8 dígitos y se tomaba el primero que
    matcheara; ahora se normaliza el número argentino completo, se comparan 10
    dígitos y si hay más de un candidato NO se engancha.

    Dos consecuencias sobre lo que ya existe:

    - Un número guardado con menos de 10 dígitos ya no matchea con nada: el alta
      va a crear una cuenta nueva en vez de reusar la existente.
    - Un número compartido por dos cuentas deja de enganchar (antes elegía una al
      azar, que es el bug). Son duplicados reales: se resuelven fusionando.

    En los dos casos el costo es un duplicado de más, que la herramienta de
    fusión arregla. El riesgo que se saca es peor: anotar a la persona
    equivocada y mostrarle sus datos a un desconocido.
    """
    User = get_user_model()
    con_telefono = User.objects.exclude(numero_telefono='').exclude(
        numero_telefono__isnull=True)

    cortos = []
    por_cola = {}
    for pk, nombre, numero in con_telefono.values_list(
            'id', 'nombre', 'numero_telefono'):
        cola = _cola_telefono(numero)
        if cola:
            por_cola.setdefault(cola, []).append((pk, nombre, numero))
        else:
            cortos.append({'pk': pk, 'nombre': nombre, 'numero': numero,
                           'digitos': len(_solo_digitos(numero))})

    compartidos = [
        {'cola': cola, 'cuentas': cuentas}
        for cola, cuentas in por_cola.items() if len(cuentas) > 1
    ]
    return {
        'total': con_telefono.count(),
        'normalizables': sum(len(v) for v in por_cola.values()),
        'cortos': cortos[:30],
        'cantidad_cortos': len(cortos),
        'compartidos': compartidos[:30],
        'cantidad_compartidos': len(compartidos),
    }


def cuentas_fusionadas():
    """Cuentas ya fusionadas, que el alta dejó de "resucitar".

    No es un riesgo: es el arreglo. Se muestra para que se vea el alcance.
    """
    User = get_user_model()
    return User.objects.filter(merged_into__isnull=False).count()


def revisar_impacto():
    """Todo junto, listo para el template."""
    americanos = americanos_sin_club()
    telefonos = telefonos_afectados()
    return {
        'americanos': americanos,
        'telefonos': telefonos,
        'fusionadas': cuentas_fusionadas(),
        # Lo único que exige acción antes de desplegar.
        'requiere_accion': americanos['cantidad'] > 0,
    }
