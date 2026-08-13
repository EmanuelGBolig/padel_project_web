"""Chequeos de consistencia de un torneo.

Buscan datos que "no cierran" entre sí: partidos que quedaron en una zona
distinta a la de sus parejas, parejas sin partidos, etc. Son de SOLO LECTURA.

Los consume el comando `manage.py revisar_torneo` y la vista web (para quien no
tiene shell en Render).
"""
from collections import defaultdict

from ..models import EquipoGrupo, PartidoGrupo, Torneo


def revisar_torneo(torneo):
    """Devuelve la lista de inconsistencias encontradas en un torneo."""
    problemas = []

    grupos = list(torneo.grupos.prefetch_related('tabla__equipo', 'partidos_grupo'))

    # Zona de cada equipo segun la TABLA de posiciones
    zona_de = {}
    equipos_repetidos = defaultdict(list)
    for g in grupos:
        for fila in g.tabla.all():
            if fila.equipo_id in zona_de:
                equipos_repetidos[fila.equipo_id].append(g.nombre)
            else:
                zona_de[fila.equipo_id] = g
                equipos_repetidos[fila.equipo_id].append(g.nombre)

    # 1) Una pareja cargada en dos zonas a la vez
    for equipo_id, nombres in equipos_repetidos.items():
        if len(nombres) > 1:
            eq = EquipoGrupo.objects.filter(equipo_id=equipo_id).first()
            problemas.append({
                'tipo': 'pareja_en_dos_zonas',
                'gravedad': 'alta',
                'detalle': f"«{eq.equipo if eq else equipo_id}» figura en {', '.join(nombres)}.",
                'sugerencia': 'Sacala de una de las dos zonas desde Gestionar.',
            })

    # 2) El partido esta en una zona distinta a la de sus parejas.
    #    Es el que hace que el cronograma impreso muestre una zona y la pantalla
    #    de Zonas otra: el cronograma lee la zona DEL PARTIDO.
    for g in grupos:
        for p in g.partidos_grupo.all():
            for lado, equipo_id in (('equipo1', p.equipo1_id), ('equipo2', p.equipo2_id)):
                if not equipo_id:
                    continue
                zona_equipo = zona_de.get(equipo_id)
                if zona_equipo is None:
                    problemas.append({
                        'tipo': 'pareja_sin_zona',
                        'gravedad': 'alta',
                        'detalle': (f"El partido de {g.nombre} incluye una pareja "
                                    f"que no está en la tabla de ninguna zona."),
                        'sugerencia': 'Reasignala a una zona desde Gestionar.',
                    })
                elif zona_equipo.pk != g.pk:
                    equipo = getattr(p, lado)
                    problemas.append({
                        'tipo': 'partido_en_zona_ajena',
                        'gravedad': 'alta',
                        'detalle': (f"«{equipo}» juega un partido listado en {g.nombre}, "
                                    f"pero en la tabla figura en {zona_equipo.nombre}."),
                        'sugerencia': ('Por eso el cronograma impreso muestra una zona y '
                                       'la pantalla de Zonas otra. Rearmá ese partido.'),
                    })

    # 3) Parejas en la tabla que no tienen ningun partido
    for g in grupos:
        con_partido = set()
        for p in g.partidos_grupo.all():
            con_partido.add(p.equipo1_id)
            con_partido.add(p.equipo2_id)
        for fila in g.tabla.all():
            if fila.equipo_id not in con_partido:
                problemas.append({
                    'tipo': 'pareja_sin_partidos',
                    'gravedad': 'media',
                    'detalle': f"«{fila.equipo}» está en {g.nombre} pero no tiene partidos.",
                    'sugerencia': 'Regenerá los partidos de esa zona.',
                })

    # 4) Nombres de zona mezclados ("Zona A" con "Grupo B")
    prefijos = {n.nombre.split(' ')[0] for n in grupos if ' ' in n.nombre}
    if len(prefijos) > 1:
        problemas.append({
            'tipo': 'nombres_mezclados',
            'gravedad': 'baja',
            'detalle': f"Las zonas usan nombres distintos entre sí: {', '.join(sorted(prefijos))}.",
            'sugerencia': 'Es sólo cosmético, pero confunde en el cronograma impreso.',
        })

    return problemas


def revisar_todos(organizacion=None):
    """Revisa los torneos en juego (y abiertos con zonas ya armadas)."""
    qs = Torneo.objects.filter(estado__in=[Torneo.Estado.EN_JUEGO, Torneo.Estado.ABIERTO])
    if organizacion is not None:
        qs = qs.filter(organizacion=organizacion)

    salida = []
    for t in qs.prefetch_related('grupos'):
        if not t.grupos.exists():
            continue
        problemas = revisar_torneo(t)
        salida.append({'torneo': t, 'problemas': problemas})
    return salida
