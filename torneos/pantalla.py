"""Pantalla del club para TV: `/tv/<alias>/`.

Junta los torneos EN JUEGO de una organización (las canchas son del club y las
comparten varias categorías) y arma las placas de un carrusel:

    canchas · próximos · últimos resultados · zonas · llave · inscripciones · sponsors

Qué partido está "en juego" se deduce solo, sin que el organizador toque nada
extra: en cada cancha, el primer partido pendiente cuya hora ya llegó. Al
cargar el resultado, la cancha pasa al siguiente. Ver "Pantalla del club (TV)"
en ARQUITECTURA.md.
"""
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from datetime import timezone as dt_timezone
from typing import Optional

from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView

from accounts.models import Organizacion
from .models import EquipoGrupo, Grupo, Partido, PartidoGrupo, ResolucionPartido, Torneo
from .templatetags.torneo_extras import get_team_display, nombre_ronda_dinamico

# Un partido pendiente cuya hora ya pasó cuenta como "en juego" hasta que se carga
# el resultado. Pasado este margen se lo da por olvidado (nadie cargó el resultado)
# para que no tape la cancha para siempre.
VENTANA_EN_JUEGO = timedelta(hours=6)
# Un resultado cargado hace menos que esto se muestra en su cancha como "Terminó".
RECIEN_TERMINADO = timedelta(minutes=15)
# Al cargarse la final, Partido.save() pasa el torneo a FINALIZADO. Sin esta
# ventana la TV lo sacaría justo en el momento del campeón.
VENTANA_CAMPEON = timedelta(hours=4)

CANCHAS_POR_PLACA = 8
PARTIDOS_POR_PLACA = 8      # próximos y resultados: 2 columnas x 4 renglones
PLACAS_POR_LISTA = 2        # como mucho 2 placas de próximos y 2 de resultados
ZONAS_POR_PLACA = 6
INSCRIPCIONES_MAX = 4

# Segundos que se queda cada placa en pantalla.
DURACION = {
    'campeones': 15, 'canchas': 20, 'proximos': 14, 'resultados': 14, 'zonas': 15,
    'llave': 20, 'inscripcion': 12, 'sponsors': 10, 'vacia': 30,
}

_EPOCA = datetime(1970, 1, 1, tzinfo=dt_timezone.utc)
_PLACEHOLDER_ZONA = re.compile(r'^(\d+)([A-Za-z])$')


# --- Datos normalizados ----------------------------------------------------------

@dataclass
class PartidoTV:
    """Un partido de zona o de llave, con lo que la TV necesita y nada más."""
    tipo: str                    # 'zona' | 'llave'
    pk: int
    torneo: Torneo
    fase: str                    # 'Zona A', 'Semifinal'...
    pareja1: str
    pareja2: str
    definido: bool               # ya se conocen las dos parejas
    ganador: int                 # 0 = pendiente, 1 o 2
    sets: list                   # [(6, 4), (3, 6), (10, 8)]
    marcador: str                # texto cuando no hay sets: 'W.O.', 'Bye'...
    fecha_hora: Optional[datetime]
    cancha: str
    finalizado_en: Optional[datetime]
    ronda: int = 0
    siguiente_pk: Optional[int] = None
    jugandose: bool = False      # lo marca armar_pantalla: es el "en juego" de su cancha

    @property
    def es_bye(self):
        return self.marcador == 'Bye'

    # Cada set como (games, lo ganó): se pinta de verde el set ganado, no la fila
    # entera, porque el ganador del partido puede haber perdido un set.
    @property
    def sets_pareja1(self):
        return [(a, a > b) for a, b in self.sets]

    @property
    def sets_pareja2(self):
        return [(b, b > a) for a, b in self.sets]


@dataclass
class CanchaTV:
    nombre: str
    en_juego: Optional[PartidoTV] = None
    proximo: Optional[PartidoTV] = None
    recien_terminado: Optional[PartidoTV] = None


@dataclass
class Placa:
    """Una pantalla del carrusel. `clave` es estable entre refrescos: el JS la usa
    para seguir en la misma placa cuando llegan datos nuevos."""
    tipo: str
    clave: str
    titulo: str
    subtitulo: str = ''
    datos: dict = field(default_factory=dict)

    @property
    def duracion(self):
        return DURACION.get(self.tipo, 12)


# --- Helpers ---------------------------------------------------------------------

def orden_natural_cancha(nombre):
    """'1' < '2' < '10' < 'Central'."""
    return (0, int(nombre), '') if nombre.isdigit() else (1, 0, nombre.lower())


def canchas_usadas(organizacion):
    """Canchas que la organización ya cargó alguna vez, para sugerirlas al programar."""
    if organizacion is None:
        return []
    nombres = set(
        PartidoGrupo.objects.filter(grupo__torneo__organizacion=organizacion)
        .exclude(cancha='').values_list('cancha', flat=True).distinct()
    ) | set(
        Partido.objects.filter(torneo__organizacion=organizacion)
        .exclude(cancha='').values_list('cancha', flat=True).distinct()
    )
    return sorted(nombres, key=orden_natural_cancha)


def _nombre_pareja(equipo, placeholder=None):
    if equipo is not None:
        return get_team_display(equipo, None)
    if placeholder:
        m = _PLACEHOLDER_ZONA.match(placeholder.strip())
        return f"{m.group(1)}° Zona {m.group(2).upper()}" if m else placeholder
    return 'A definir'


def _cuando(p):
    """Para ordenar resultados: cuándo se cargó, o si no se sabe, cuándo se jugó."""
    return p.finalizado_en or p.fecha_hora or _EPOCA


def _desde_zona(pg, torneo):
    sets = [
        (a, b) for a, b in (
            (pg.e1_set1, pg.e2_set1), (pg.e1_set2, pg.e2_set2), (pg.e1_set3, pg.e2_set3))
        if a is not None and b is not None
    ]
    ganador = 0
    if pg.ganador_id:
        ganador = 1 if pg.ganador_id == pg.equipo1_id else 2
    return PartidoTV(
        tipo='zona', pk=pg.pk, torneo=torneo, fase=pg.grupo.nombre,
        pareja1=_nombre_pareja(pg.equipo1), pareja2=_nombre_pareja(pg.equipo2),
        definido=True, ganador=ganador,
        sets=[] if pg.resolucion == ResolucionPartido.WALKOVER else sets,
        marcador=pg.etiqueta_resolucion,
        fecha_hora=pg.fecha_hora, cancha=pg.cancha, finalizado_en=pg.finalizado_en,
    )


def _desde_llave(p, torneo, total_rondas):
    ganador = 0
    if p.ganador_id:
        ganador = 1 if p.ganador_id == p.equipo1_id else 2
    sets = []
    if p.resolucion != ResolucionPartido.WALKOVER and p.sets_local and p.sets_visitante:
        sets = [
            (a, b) for a, b in zip(p.sets_local, p.sets_visitante)
            if a is not None and b is not None
        ]
    if p.resultado == 'Bye':
        marcador = 'Bye'
    elif sets:
        marcador = p.etiqueta_resolucion
    else:
        marcador = p.etiqueta_resolucion or (p.resultado or '')
    return PartidoTV(
        tipo='llave', pk=p.pk, torneo=torneo,
        fase=nombre_ronda_dinamico(p.ronda, total_rondas),
        pareja1=_nombre_pareja(p.equipo1, p.placeholder_e1),
        pareja2=_nombre_pareja(p.equipo2, p.placeholder_e2),
        definido=p.equipo1_id is not None and p.equipo2_id is not None,
        ganador=ganador, sets=sets, marcador=marcador,
        fecha_hora=p.fecha_hora, cancha=p.cancha, finalizado_en=p.finalizado_en,
        ronda=p.ronda, siguiente_pk=p.siguiente_partido_id,
    )


def _paginar(lista, tamano, maximo=None):
    paginas = [lista[i:i + tamano] for i in range(0, len(lista), tamano)]
    return paginas[:maximo] if maximo else paginas


# --- Armado de la pantalla -------------------------------------------------------

def armar_canchas(partidos, ahora):
    """Estado de cada cancha a partir de los partidos (de todos los torneos del club)."""
    pendientes = defaultdict(list)
    terminados = defaultdict(list)
    for p in partidos:
        if not p.cancha:
            continue
        if p.ganador:
            if p.finalizado_en and p.finalizado_en >= ahora - RECIEN_TERMINADO and not p.es_bye:
                terminados[p.cancha].append(p)
        elif p.fecha_hora and p.fecha_hora >= ahora - VENTANA_EN_JUEGO:
            pendientes[p.cancha].append(p)

    canchas = []
    for nombre in sorted(set(pendientes) | set(terminados), key=orden_natural_cancha):
        lista = sorted(pendientes[nombre], key=lambda p: (p.fecha_hora, p.pk))
        en_juego = next((p for p in lista if p.fecha_hora <= ahora and p.definido), None)
        resto = [p for p in lista if p is not en_juego]
        cancha = CanchaTV(nombre=nombre, en_juego=en_juego, proximo=resto[0] if resto else None)
        if en_juego is None and terminados[nombre]:
            cancha.recien_terminado = max(terminados[nombre], key=_cuando)
        canchas.append(cancha)
    return canchas


def armar_pantalla(organizacion, torneo_ids=None, ahora=None):
    """Arma todo lo que muestra la TV. Devuelve el contexto del template."""
    ahora = ahora or timezone.now()

    recien_finalizados = Torneo.objects.filter(
        organizacion=organizacion, estado=Torneo.Estado.FINALIZADO,
        partidos__siguiente_partido__isnull=True,
        partidos__finalizado_en__gte=ahora - VENTANA_CAMPEON,
    ).values('pk')
    torneos = Torneo.objects.filter(organizacion=organizacion).filter(
        Q(estado=Torneo.Estado.EN_JUEGO) | Q(pk__in=recien_finalizados)
    ).select_related(
        'division', 'formato_personalizado', 'ganador_del_torneo',
    ).order_by('fecha_inicio', 'nombre')
    if torneo_ids:
        torneos = torneos.filter(pk__in=torneo_ids)
    torneos = list(torneos)
    por_pk = {t.pk: t for t in torneos}

    # Partidos de llave, por torneo (para la placa de la llave y para el total de rondas).
    llaves = defaultdict(list)
    for p in Partido.objects.filter(torneo__in=torneos).select_related('equipo1', 'equipo2') \
            .order_by('ronda', 'orden_partido'):
        llaves[p.torneo_id].append(p)
    total_rondas = {tid: max(p.ronda for p in lista) for tid, lista in llaves.items()}

    partidos = [
        _desde_zona(pg, por_pk[pg.grupo.torneo_id])
        for pg in PartidoGrupo.objects.filter(grupo__torneo__in=torneos)
        .select_related('grupo', 'equipo1', 'equipo2')
    ]
    partidos_llave = {
        tid: [_desde_llave(p, por_pk[tid], total_rondas[tid]) for p in lista]
        for tid, lista in llaves.items()
    }
    for lista in partidos_llave.values():
        # Las rondas futuras sin nada todavía ("A definir" vs "A definir") son
        # estructura de la llave, no partidos para listar.
        partidos.extend(p for p in lista if p.definido or p.pareja1 != 'A definir' or p.pareja2 != 'A definir')

    canchas = armar_canchas(partidos, ahora)
    en_juego_pks = set()
    for c in canchas:
        if c.en_juego:
            c.en_juego.jugandose = True   # es el mismo objeto que aparece en la llave
            en_juego_pks.add((c.en_juego.tipo, c.en_juego.pk))

    proximos = sorted(
        (p for p in partidos
         if not p.ganador and p.fecha_hora and p.fecha_hora >= ahora - VENTANA_EN_JUEGO
         and (p.tipo, p.pk) not in en_juego_pks),
        key=lambda p: (p.fecha_hora, orden_natural_cancha(p.cancha or '~'), p.pk),
    )
    resultados = sorted(
        (p for p in partidos if p.ganador and not p.es_bye),
        key=lambda p: (_cuando(p), p.pk), reverse=True,
    )

    placas = []
    campeones = [t for t in torneos if t.estado == Torneo.Estado.FINALIZADO and t.ganador_del_torneo]
    if campeones:
        placas.append(Placa(
            'campeones', 'campeones', '¡Tenemos campeones!' if len(campeones) > 1 else '¡Tenemos campeón!',
            '', {'torneos': [(t, _nombre_pareja(t.ganador_del_torneo)) for t in campeones]},
        ))

    paginas = _paginar(canchas, CANCHAS_POR_PLACA)
    for i, pagina in enumerate(paginas, 1):
        placas.append(Placa(
            'canchas', f'canchas-{i}', 'En cancha ahora',
            f'{i} de {len(paginas)}' if len(paginas) > 1 else '',
            {'canchas': pagina},
        ))

    paginas = _paginar(proximos, PARTIDOS_POR_PLACA, PLACAS_POR_LISTA)
    for i, pagina in enumerate(paginas, 1):
        placas.append(Placa('proximos', f'proximos-{i}', 'Próximos partidos', '', {'partidos': pagina}))

    paginas = _paginar(resultados, PARTIDOS_POR_PLACA, PLACAS_POR_LISTA)
    for i, pagina in enumerate(paginas, 1):
        placas.append(Placa('resultados', f'resultados-{i}', 'Últimos resultados', '', {'partidos': pagina}))

    placas.extend(_placas_zonas(torneos, partidos, llaves))
    placas.extend(_placas_llave(torneos, partidos_llave))
    placas.extend(_placas_inscripcion(organizacion))

    sponsors = list(organizacion.sponsors.all())
    if sponsors:
        placas.append(Placa('sponsors', 'sponsors', 'Nos acompañan', '', {'sponsors': sponsors}))

    if not placas:
        placas.append(Placa('vacia', 'vacia', organizacion.nombre))

    return {
        'torneos': torneos,
        'varios_torneos': len(torneos) > 1,
        'placas': placas,
        'canchas': canchas,
        'hay_en_vivo': any(t.estado == Torneo.Estado.EN_JUEGO for t in torneos),
    }


def _placas_zonas(torneos, partidos, llaves):
    """Tablas de posiciones. Una vez que las zonas terminaron y ya hay llave, se
    dejan de mostrar: la llave pasa a ser lo importante y el carrusel no se alarga."""
    zonas_pendientes = {p.torneo.pk for p in partidos if p.tipo == 'zona' and not p.ganador}
    con_zonas = [t for t in torneos if t.pk in zonas_pendientes or not llaves.get(t.pk)]
    if not con_zonas:
        return []

    grupos = defaultdict(list)
    for g in Grupo.objects.filter(torneo__in=con_zonas).order_by('nombre').prefetch_related(
            Prefetch('tabla', queryset=EquipoGrupo.objects.select_related('equipo'))):
        grupos[g.torneo_id].append(g)

    placas = []
    for torneo in con_zonas:
        if not grupos[torneo.pk]:
            continue
        fp = torneo.formato_personalizado
        clasifican = fp.clasifican_por_grupo if fp else 2
        zonas = [{
            'nombre': g.nombre,
            'filas': [{
                'posicion': i,
                'pareja': _nombre_pareja(eg.equipo),
                'pj': eg.partidos_jugados, 'pg': eg.partidos_ganados,
                'ds': eg.diferencia_sets, 'dg': eg.diferencia_games,
                'clasifica': i <= clasifican and eg.partidos_jugados > 0,
            } for i, eg in enumerate(g.tabla.all(), 1)],
        } for g in grupos[torneo.pk]]
        paginas = _paginar(zonas, ZONAS_POR_PLACA)
        for i, pagina in enumerate(paginas, 1):
            placas.append(Placa(
                'zonas', f'zonas-{torneo.pk}-{i}', f'Zonas · {torneo.nombre}',
                f'{i} de {len(paginas)}' if len(paginas) > 1 else '',
                {'zonas': pagina, 'torneo': torneo},
            ))
    return placas


def _placas_llave(torneos, partidos_llave):
    placas = []
    for torneo in torneos:
        lista = partidos_llave.get(torneo.pk)
        if not lista:
            continue
        rondas = defaultdict(list)
        for p in lista:
            rondas[p.ronda].append(p)
        columnas = [{'nombre': ps[0].fase, 'partidos': ps} for _, ps in sorted(rondas.items())]
        placas.append(Placa(
            'llave', f'llave-{torneo.pk}', f'Llave · {torneo.nombre}', '',
            {'rondas': columnas, 'torneo': torneo},
        ))
    return placas


def _placas_inscripcion(organizacion):
    abiertos = list(
        Torneo.objects.filter(organizacion=organizacion, estado=Torneo.Estado.ABIERTO)
        .select_related('division').order_by('fecha_inicio')[:INSCRIPCIONES_MAX]
    )
    if not abiertos:
        return []
    return [Placa('inscripcion', 'inscripcion', 'Inscripciones abiertas', '', {'torneos': abiertos})]


def _ids_torneos(valor):
    """`?t=12,15` -> [12, 15]. Sirve para dedicar una TV a ciertas categorías."""
    return [int(x) for x in (valor or '').split(',') if x.strip().isdigit()]


# --- Vista -----------------------------------------------------------------------

@method_decorator(never_cache, name='dispatch')
class PantallaClubView(TemplateView):
    """Pantalla pública para la TV del club. Sin login: en la TV no hay cómo
    loguearse cómodo, y todo lo que muestra ya es público en la ficha del torneo.

    `?parcial=1` devuelve solo las placas: el JS las pide cada 30 s y las cambia
    sin recargar, para que el carrusel no vuelva a empezar.
    """
    template_name = 'torneos/pantalla/pantalla.html'

    def get_template_names(self):
        if self.request.GET.get('parcial'):
            return ['torneos/pantalla/_placas.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        organizacion = get_object_or_404(Organizacion, alias=self.kwargs['alias'])
        ahora = timezone.now()
        torneo_ids = _ids_torneos(self.request.GET.get('t'))
        context.update(armar_pantalla(organizacion, torneo_ids=torneo_ids, ahora=ahora))
        # `?solo=canchas` (o `canchas,proximos`): una TV fija en ciertas placas, por
        # ejemplo la de la entrada solo con las canchas y otra rotando todo.
        solo = [s.strip() for s in self.request.GET.get('solo', '').split(',') if s.strip()]
        if solo:
            context['placas'] = (
                [p for p in context['placas'] if p.tipo in solo]
                or [Placa('vacia', 'vacia', organizacion.nombre)]
            )

        torneos = context['torneos']
        if len(torneos) == 1:
            destino = reverse('torneos:detail', kwargs={'pk': torneos[0].pk})
        else:
            destino = reverse('accounts:organizador_detalle', kwargs={'pk': organizacion.pk})
        context.update({
            'organizacion': organizacion,
            'ahora': ahora,
            'hoy': timezone.localtime(ahora).strftime('%Y%m%d'),
            # El reloj de la TV sale de la hora del servidor: muchas TVs tienen la
            # hora o el huso mal configurados.
            'ahora_ms': int(ahora.timestamp() * 1000),
            'offset_min': int(timezone.localtime(ahora).utcoffset().total_seconds() // 60),
            'url_celular': self.request.build_absolute_uri(destino),
            'base_url': self.request.build_absolute_uri('/').rstrip('/'),
            'url_parcial': self.request.get_full_path() + ('&' if self.request.GET else '?') + 'parcial=1',
        })
        return context
