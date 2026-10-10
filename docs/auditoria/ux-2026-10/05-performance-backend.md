# Auditoría 05 — Performance y optimización del backend

**Proyecto:** TodoPadel (Django 5, SQLite en dev / PostgreSQL en Render)
**Fecha:** 2026-10-10
**Alcance:** consultas SQL, N+1, caché, índices y trabajo por request. No se miran imágenes ni CSS.

## Cómo se midió

Cliente de test de Django (`django.test.Client`) + `CaptureQueriesContext`, SQL normalizado por regex
para detectar la MISMA consulta repetida. Se mide el **mejor de 2-3 corridas** después de un warmup
(el warmup llena el cached loader de templates y los cachés de perfil, así que los números de abajo
son el caso **caliente**: el frío es peor).

Dos bases:

| Base | Datos | Para qué |
|---|---|---|
| `db.sqlite3` del repo (solo lectura, GETs) | 4 torneos, 28 usuarios, 12 parejas, 1 división | Confirmar/corregir las mediciones previas |
| **Copia** en el scratchpad (`perf/db_escala.sqlite3`) | **10 torneos, 50 parejas, 100 jugadores, 8 divisiones, 12 zonas y 31 partidos de llave por torneo, 506 inscripciones** | Extrapolar a un club real y medir el camino de escritura |

> La base del repo **no se tocó**: solo GETs. Lo verifiqué al final (`torneos 4, users 28, div 1,
> insc 6, grupos 5, eg 16, pg 13, p 9`, idéntico al arranque) y `git status` quedó igual que al
> empezar. Todo lo que escribe (cargar resultados, programar horarios) corrió contra la copia.
> Scripts en `scratchpad/perf/`: `base.py`, `sweep.py`, `sweep_escala.py`, `poblar_escala.py`,
> `fix_programacion.py`, `fix_equipo.py`, `fix_mi_equipo.py`, `fix_pack_escala.py`, `fix_pack2.py`,
> `camino_escritura.py`, `fix_escritura.py`, `cache_cost.py`, `escala.py`.

---

## 1. Tabla de mediciones

### 1.1 Datos del repo (chicos) — confirmación de lo que ya habías medido

| Rol | Pantalla | Queries | ms | HTML crudo | Repetidas |
|---|---|---|---|---|---|
| anon | `/` | 5 | 21 | 95 KB | x2 `torneos_torneo` |
| anon | `/para-organizadores/` | 0 | 3 | 78 KB | — |
| anon | `/torneos/abiertos/` | 5 | 15 | 58 KB | — |
| anon | `/torneos/en-juego/` | 4 | 13 | 60 KB | — |
| anon | `/torneos/finalizados/` | 5 | 17 | 57 KB | — |
| anon | `/torneos/1/` | **20** | 59 | 142 KB | 3 pares de `customuser` |
| anon | `/torneos/2/` | 8 | 30 | 68 KB | **x2 COUNT inscripcion** |
| anon | **`/torneos/1/programacion/`** | **23** | 34 | 78 KB | **x10 `torneos_torneo` + x9 `MAX(ronda)`** |
| anon | `/torneos/1/vivo/` | 13 | 21 | 82 KB | — |
| anon | `/accounts/rankings/` | 5 | 7 | 60 KB | x4 `accounts_division` |
| anon | `/accounts/organizador/1/` | 9 | 14 | 68 KB | x3 `accounts_division` |
| anon | `/tv/club-demo/` | 8 | 22 | 46 KB | — |
| anon | `/sitemap.xml` | 3 | 5 | 1,5 KB | — |
| jug (sin pareja) | `/` | 12 | 24 | 106 KB | x2+x2 `equipos_equipo` |
| jug | `/torneos/abiertos/` | 16 | 15 | 69 KB | **x4+x4 `equipos_equipo`** |
| jug | `/torneos/1/` | 29 | 49 | 155 KB | x6 `equipos_equipo` |
| jug | `/torneos/1/programacion/` | 26 | 38 | 89 KB | x10 + x9 |
| **jug (con pareja)** | **`/equipos/mi-equipo/`** | **28** | 32 | 68 KB | **x3 y x3 de 4 COUNT distintos** |
| jug (con pareja) | `/accounts/perfil/` (cache frío) | 15 | 21 | 96 KB | **x3 `MAX(ronda)`** + x4 equipo |
| jug (con pareja) | `/torneos/2/` | 21 | 60 | 85 KB | **x3 COUNT inscripcion** + x4 equipo |
| org | `/torneos/admin/dashboard/` | 15 | 20 | 71 KB | x3 `accounts_division` |
| org | `/torneos/admin/listado/` | 10 | 20 | 86 KB | **x4 COUNT inscripcion** |
| org | `/torneos/admin/embudo/` | 13 | 9 | 67 KB | — |
| org | **`/torneos/admin/revisar/`** | **41** | 23 | 68 KB | **x19 `customuser`, x10 `equipo`, x5 `equipogrupo`** |
| org | `/torneos/admin/1/gestionar/` | **25** | 35 | **201 KB** | **x3 exists(grupo), x2 exists(partido), x2 organizacion** |
| org | `/torneos/admin/1/cobros/` | 7 | 10 | 65 KB | — |
| org | `/accounts/organizador/1/programacion/` | **19** | 34 | 104 KB | **x8 `MAX(ronda)`** |
| org | `…/programacion/imprimir/` | 17 | 25 | 17 KB | x8 `MAX(ronda)` |
| org | `/equipos/admin/listado/` | 7 | 11 | 87 KB | — |
| org | `/accounts/usuarios/duplicados/` | 5 | 15 | 63 KB | — (es CPU, no SQL) |
| org | `/torneos/1/placa/` | 7 | 7 | 9 KB | — |
| org | `/torneos/admin/1/inscriptos.csv` | 4 | 9 | 0,1 KB | — |

**Correcciones a tus números:**

- `/torneos/1/programacion/`: **23 queries confirmadas**, y las 10 iguales de `torneos_torneo` son
  solo la mitad del problema: hay **otras 9** consultas `SELECT MAX(ronda)`. En total **18 de 23
  consultas son desperdicio**, no 10.
- `/torneos/admin/1/gestionar/`: me da **25** (no 21) y **201 KB** (no 191). La diferencia son las 2
  queries de sesión+usuario y 2 de organización; si lo medís como `admin` da 24.
- `/torneos/1/`: me da **20** anónimo y **142 KB** (no 16/123 KB). Logueado con pareja: **31**.
- `/torneos/admin/dashboard/`: 14 como admin, **15 como organizador**. Confirmado.
- home: **5 queries / 95 KB**. Confirmado exacto.

### 1.2 Club realista (10 torneos / 50 parejas / 8 divisiones)

`wire` = lo que viaja de verdad (GZipMiddleware está activo y funciona).

| Rol | Pantalla | Queries | ms | HTML crudo | wire | Repetidas |
|---|---|---|---|---|---|---|
| anon | `/` | 5 | 13 | 119 KB | 19 KB | — |
| anon | `/torneos/abiertos/` | 7 | 7 | 63 KB | 14 KB | x3 COUNT insc |
| anon | `/torneos/finalizados/` | 10 | 15 | 67 KB | 13 KB | **x6 `torneos_partido`** |
| anon | `/torneos/<en juego>/` | 20 | 68 | **404 KB** | 26 KB | x4 customuser |
| anon | `/torneos/<abierto>/` | 9 | 18 | 105 KB | 17 KB | x3 COUNT insc |
| anon | **`/torneos/<x>/programacion/`** | **67** | 71 | 139 KB | 17 KB | **x32 `torneos_torneo` + x31 `MAX(ronda)`** |
| anon | `/torneos/<x>/vivo/` | 13 | 27 | 136 KB | 15 KB | — |
| anon | `/tv/club-demo/` | 10 | 47 | 138 KB | 11 KB | x3 COUNT insc |
| anon | `/tv/club-demo/?parcial=1` | **10** | 46 | 111 KB | **3,8 KB** | igual que la completa |
| jug | `/` | 12 | 20 | 129 KB | 21 KB | x3 equipo |
| jug | `/torneos/mis-torneos/` | **16** | 18 | 83 KB | 15 KB | **x10 `accounts_organizacion`** |
| jug | `/torneos/abiertos/` | **19** | 20 | 73 KB | 15 KB | **x7 equipo** + x3 COUNT |
| jug | **`/equipos/mi-equipo/`** | **31** | 57 | 68 KB | 14 KB | **x7 equipo + x3,x3,x3,x3 COUNT** |
| jug | `/torneos/<abierto>/` | 24 | 47 | 122 KB | 19 KB | x4 equipo, **x4 COUNT insc**, x3 division |
| org | `/torneos/admin/dashboard/` | **18** | 20 | 77 KB | 15 KB | **x6 `accounts_division`** |
| org | `/torneos/admin/listado/` | **20** | 20 | 135 KB | 17 KB | **x14 COUNT inscripcion** |
| org | `/torneos/admin/embudo/` | 13 | 9 | 67 KB | 14 KB | — |
| org | `/torneos/admin/revisar/` | **53** | 64 | 69 KB | 14 KB | x18 customuser, x9 equipo |
| org | `/torneos/admin/<en juego>/gestionar/` | 26 | **88** | **531 KB** | 29 KB | x3 exists |
| org | `/torneos/admin/<abierto>/cobros/` | 7 | 42 | 304 KB | 20 KB | — |
| org | `/accounts/organizador/1/programacion/` | 11 | 54 | 359 KB | 22 KB | — (ese día tenía pocos de llave) |
| org | `/accounts/usuarios/duplicados/` | **5** | **115** | 105 KB | 15 KB | **es CPU puro** |

### 1.3 Camino de escritura (lo que hace el organizador al borde de la cancha)

Medido sobre la copia, contando **todas** las sentencias SQL que dispara un `save()`:

| Acción | Sentencias | De las cuales a `django_cache` |
|---|---|---|
| Cargar resultado de **zona** | **36** | 24 |
| **Programar día/hora** de un partido | **21** | 17 |
| Cron marcando un recordatorio enviado | **21** | 17 |
| Cargar resultado de **llave** | **56** | 42 |

Proyección para un torneo de 50 parejas (72 partidos de zona + 31 de llave):

| | Hoy | Con el arreglo A1 |
|---|---|---|
| Programar los 72 horarios | **1.512** sentencias | **72** |
| Cargar los 72 resultados de zona | **2.592** | 1.296 |
| Cargar los 31 de llave | **1.736** | 651 |
| Cron con 50 recordatorios (cada 30 min) | **1.050** | 50 |

---

## 2. Hallazgos

### Estado de los hallazgos de performance previos (`docs/auditoria/hallazgos.json`)

| # | Título (abreviado) | Hoy |
|---|---|---|
| 3 | `merge_users` recalcula todas las divisiones sincrónico | **ARREGLADO** (va por `_programar_recalculo`, fuera del atomic) |
| 5 | Cada resultado dispara recálculo completo del ranking | **ARREGLADO** (debounce por división, `RANKINGS_DEBOUNCE_SEGUNDOS`) |
| 6 | Gestionar carga todos los equipos de la plataforma | **ARREGLADO** (banda ±2 de división en SQL) |
| 8 | `CustomUser.equipo` no cacheada | **SIGUE ABIERTO** → A3 |
| 9 | Caché con blobs pesados de modelos picklados | **SIGUE ABIERTO** → M6 |
| 10 | Duplicados: difflib O(K²) sin caché | **SIGUE ABIERTO** → M5 |
| 13 | `MiEquipoDetailView` recomputa stats | **SIGUE ABIERTO (peor de lo descrito)** → A4 |
| 16 | `nombre_ronda` hace un aggregate por partido | **SIGUE ABIERTO (en 3 lugares)** → A2 |
| 18 | Cron de recordatorios sin índice ni cota | **SIGUE ABIERTO** → M8 |
| 19 | `post_save` recalcula tabla aunque no cambie el resultado | **ARREGLADO A MEDIAS**: `actualizar_tabla_de_posiciones` ya tiene el guard `CAMPOS_SIN_IMPACTO`, pero `check_llaves_internas_generacion` no, y `equipos/signals.py` tampoco → A1 |
| 20 | N+1 de COUNT por tarjeta en los listados | **SIGUE ABIERTO** → A5 |
| 26 | Cachés de perfil que nunca se invalidan | **SIGUE ABIERTO** → M7 |
| 32 | Ranking del circuito sin caché | **SIGUE ABIERTO** (verificado por código, no hay circuitos en la base) → B6 |
| 34 | `cupos_disponibles` 4 COUNT por ficha | **ABIERTO, pero son 3, no 4** → B1 |

---

## ALTO

### A1 — La invalidación de caché de `equipos/signals.py` borra claves que NADIE escribe: 17 de 21 sentencias al programar un horario (NUEVO)

`equipos/signals.py:12-32` está enganchado a `post_save` **y** `post_delete` de `Partido`,
`PartidoGrupo` y `Torneo`. En cada guardado recorre `Division.objects.all()` y borra tres familias
de claves:

```python
cache.delete('rankings_jugadores_all')                    # nadie la setea
for division in Division.objects.all():
    cache.delete(f'rankings_div_{division.id}')           # nadie la setea
    cache.delete(f'rankings_jugadores_div_{division.id}') # nadie la setea (la real lleva _gen_XXX)
```

La clave real que escribe `get_division_rankings` (`accounts/utils.py:11`) es
`rankings_jugadores_div_{id}_gen_{ALL|MASCULINO|FEMENINO}`, y ya la invalida bien
`torneos/signals.py:81`. O sea: **este receiver es código muerto que cuesta una query por división
y por guardado.** Verificado:

```
cache.get('rankings_jugadores_all')      = None
cache.get('rankings_div_1')              = None
cache.get('rankings_jugadores_div_1')    = None
cache.get('rankings_jugadores_div_1_gen_ALL') = list   <- la clave REAL
```

Evidencia, `pg.save(update_fields=['fecha_hora'])` con 8 divisiones — **21 sentencias para cambiar
una hora**:

```
UPDATE  torneos_partidogrupo SET fecha_hora = ...
DELETE  rankings_jugadores_all
SELECT  accounts_division (las 8)
DELETE  rankings_div_2 / rankings_jugadores_div_2
DELETE  rankings_div_3 / rankings_jugadores_div_3
... (x8 divisiones = 16 DELETE)
SELECT  torneos_grupo        <- check_llaves_internas_generacion
SELECT  torneos_torneo       <- idem
-> 17 de 21 son DELETE de claves que nadie setea
```

Con **DatabaseCache cada `cache.delete` es un `DELETE` real contra Postgres.** La fórmula es
`2 + 2×N_divisiones` sentencias por guardado; en producción hay 8 divisiones sembradas por
`scripts/seed_divisions.py`, así que son 18.

**Arreglo:** borrar el receiver `invalidar_cache_rankings` de `equipos/signals.py` (la invalidación
correcta ya existe en `torneos/signals.py:invalidar_cache_division`) y agregar el guard de
`update_fields` a `check_llaves_internas_generacion`, que hoy no lo tiene:

```python
uf = kwargs.get('update_fields')
if uf and set(uf) <= CAMPOS_SIN_IMPACTO:
    return
```

**Ganancia medida** (`fix_escritura.py`, copia a escala):

| Camino | Antes | Después | Ahorro |
|---|---|---|---|
| Resultado de zona | 36 | **18** | −50 % |
| **Programar horario** | 21 | **1** | **−95 %** |
| Cron marcando recordatorio | 21 | **1** | **−95 %** |
| Resultado de llave | 56 | **21** | −62 % |

Esto es el hallazgo de mayor impacto de toda la auditoría: el flujo que el organizador más repite
(programar los horarios del finde, cargar resultados entre partidos) baja de **1.512 → 72**
sentencias para 72 partidos.

---

### A2 — `/programacion/`: N+1 **doble** (deref del FK + aggregate por partido). 67 queries con 31 partidos de llave

Confirmo tu diagnóstico y lo amplío: `TorneoProgramacionView` (`torneos/views.py:3429`) llama
`pb.nombre_ronda` dentro del loop, y la property (`torneos/models.py:591-606`) hace **dos** cosas
caras por partido:

```python
torneo = self.torneo                                   # (1) deref del FK -> 1 SELECT por fila
max_ronda = getattr(torneo, '_max_ronda_cache', None)
if max_ronda is None:
    max_ronda = torneo.partidos.aggregate(Max('ronda'))['ronda__max']   # (2) 1 aggregate por fila
    torneo._max_ronda_cache = max_ronda                # el cache muere con esa instancia
```

**Tenías razón: `select_related('torneo')` NO alcanza, y lo verifiqué empíricamente.**
`OrganizacionProgramacionView` (`accounts/views.py:645`) **sí** tiene `select_related('torneo')` y
aun así paga **8 aggregates con 8 partidos de llave** (31 con los datos de escala). El deref
desaparece, el aggregate no, porque `select_related` instancia un `Torneo` distinto por fila y
`_max_ronda_cache` no se comparte.

Evidencia a escala (31 partidos de llave):

```
/torneos/<x>/programacion/   67 queries
   x32  SELECT "torneos_torneo"... WHERE id = ?          <- deref del FK (31 + 1 de la vista)
   x31  SELECT MAX("torneos_partido"."ronda") ... WHERE torneo_id = ?
```

**63 de 67 queries son desperdicio.** Escala lineal: `queries ≈ 2 × nº de partidos de llave + 5`.
Un torneo de 64 parejas (63 partidos) daría ~131 queries; en Postgres remoto, con 2-5 ms de RTT,
son 0,3-0,7 s de puro ida y vuelta.

**Arreglo (el correcto, medido):** no usar la property en loops. El máximo sale **de los partidos
que ya trajiste**, sin ninguna query extra:

```python
partidos_bracket = list(Partido.objects.filter(torneo=torneo).select_related(...))
total_rondas = max((p.ronda for p in partidos_bracket), default=0)
...
'fase': nombre_ronda_dinamico(pb.ronda, total_rondas),   # el template tag ya existe
```

Para `OrganizacionProgramacionView`, que filtra por fecha y abarca varios torneos, el máximo no se
puede derivar del subconjunto: **una** query agrupada alcanza.

```python
maximos = {r['torneo']: r['m'] for r in
           Partido.objects.filter(torneo__in=torneos_base).values('torneo').annotate(m=Max('ronda'))}
```

**Ganancia medida** (HTML byte a byte idéntico en los tres casos):

| Pantalla | Antes | Después | ms |
|---|---|---|---|
| `/torneos/1/programacion/` (datos del repo) | 23 | **5** | 19,9 → 11,8 |
| `/torneos/<x>/programacion/` (escala, 31 de llave) | **67** | **5** | 70,0 → 35,3 |
| `/accounts/organizador/1/programacion/` | 19 | **12** | 19,5 → 16,7 |

El mismo N+1 está en `get_player_stats` (`accounts/utils.py:485`, `contexto = p.nombre_ronda`):
**x3 `MAX(ronda)` medidas en `/accounts/perfil/` con caché frío**, hasta 8 por miss. Ahí
`select_related('torneo')` tampoco salva.

---

### A3 — `CustomUser.equipo` sigue siendo un `@property` sin cachear (hallazgo 8, ABIERTO)

`accounts/models.py:219-231`. Cada acceso hace 1-2 queries (la segunda si no es jugador1), y **no
guarda nada**. Se evalúa 3-4 veces por request en las páginas más calientes. Para un jugador **sin
pareja activa** son 2 queries por acceso porque siempre falla el primer `first()`.

Evidencia, `/torneos/2/` logueado:

```
 4 SELECT equipos_equipo WHERE jugador1_id = 1 AND esta_activo ... LIMIT 1
 5 SELECT equipos_equipo WHERE jugador1_id = 1 AND esta_activo ... LIMIT 1
 6 SELECT equipos_equipo WHERE jugador1_id = 1 AND esta_activo ... LIMIT 1
13 SELECT equipos_equipo WHERE jugador1_id = 1 AND esta_activo ... LIMIT 1
```

Los tres primeros son `hasattr(user,'equipo')`, `user.equipo is not None` y `equipo = user.equipo`
de `TorneoDetailView` (`torneos/views.py:2043-2049`); el cuarto es el context processor
`notifications`. En `/torneos/abiertos/` a escala son **7**.

**Arreglo:** `cached_property` (una línea).

**Ganancia medida** (`fix_equipo.py`, jugador sin pareja, datos del repo):

| Pantalla | Antes | Después |
|---|---|---|
| `/torneos/abiertos/` | 16 | **10** |
| `/torneos/2/` | 17 | **13** |
| `/torneos/1/` | 29 | **25** |
| `/` | 12 | **10** |
| **Total 7 pantallas** | **93** | **77** (−17 %) |

A escala, con pareja: `/torneos/abiertos/` 19 → **13**, `/equipos/mi-equipo/` 31 → 21 (junto con A4).

---

### A4 — `MiEquipoDetailView`: 31 queries, ~16 redundantes (hallazgo 13, ABIERTO y peor de lo descrito)

Los métodos del modelo se llaman entre sí sin memoizar (`equipos/models.py:107-145`):
`get_derrotas()` vuelve a llamar a `get_partidos_jugados()` + `get_victorias()`, y `get_win_rate()`
los llama **otra vez**. Encima `get_object()` corre 2 veces (una en `get()`, otra en
`get_context_data`), y cada una resuelve `user.equipo` (A3) + un `select_related().get()`.

Evidencia (datos del repo, usuario con pareja), 28 queries:

```
x3  SELECT COUNT(*) FROM torneos_partido      WHERE (equipo1_id=? OR equipo2_id=?) AND ganador IS NOT NULL
x3  SELECT COUNT(*) FROM torneos_partidogrupo WHERE (equipo1_id=? OR equipo2_id=?) AND ganador IS NOT NULL
x3  SELECT COUNT(*) FROM torneos_partido      WHERE ganador_id = ?
x3  SELECT COUNT(*) FROM torneos_partidogrupo WHERE ganador_id = ?
x4  SELECT equipos_equipo ... (get_object x2 + user.equipo x2)
```

Además `get_racha_actual()` y `get_ultimos_resultados()` repiten **las mismas dos consultas de
historial** (queries 19-26: cada método trae los partidos de nuevo y además deref de `ganador`).

**Arreglo:** guardar `self.object` y reusarlo; calcular `pj` y `vic` una vez y derivar
`derrotas`/`win_rate` de esos valores.

**Ganancia medida** (`fix_mi_equipo.py` / `fix_pack_escala.py`, HTML idéntico):

| Base | Antes | Después |
|---|---|---|
| Datos del repo | 28 | **18** (−36 %) |
| Escala | 31 | **21** (−32 %) |

Queda margen: reusar `get_player_stats()` (que **ya está cacheada**) en vez de los métodos del
modelo bajaría a ~10.

---

### A5 — N+1 de COUNT por tarjeta en los listados (hallazgo 20, ABIERTO)

`{{ torneo.inscripciones.count }}` sigue en 4 templates, sin `annotate`:

- `torneos/templates/torneos/admin_torneo_list.html:80` (`paginate_by = 20`)
- `torneos/templates/torneos/partials/torneo_card.html:40` (lo incluye `mis_torneos.html`)
- `torneos/templates/torneos/torneo_abierto_list.html:68` y `:114`

El home ya lo resuelve con `annotate` (`core/views.py:16`); la corrección nunca llegó a los otros.

Evidencia a escala: `/torneos/admin/listado/` → **20 queries, x14 `SELECT COUNT(*) FROM
torneos_inscripcion WHERE torneo_id = ?`**. Con la página llena (20 torneos) son 20 COUNT.

**Arreglo y comparación medida de las tres opciones** (20 torneos × 50 inscriptos):

| Opción | Queries | ms |
|---|---|---|
| Hoy: `.count()` por tarjeta | **15** | 9,71 |
| `prefetch_related('inscripciones')` (no toca templates) | 2 | 6,74 |
| **`annotate(n=Count('inscripciones'))`** + usar `{{ torneo.n }}` | **1** | **2,80** |

Recomiendo `annotate`: 1 query y 3,5× más rápido. `prefetch_related` sirve como parche sin tocar
templates, pero trae las 1.000 filas de inscripción a memoria. Medido en la vista completa:
`/torneos/admin/listado/` 20 → **7** queries con prefetch.

---

## MEDIO

### M1 — `Torneo.fecha_fin` es una property con query: N+1 en `/torneos/finalizados/` (NUEVO)

`torneos/models.py:272-281`:

```python
@property
def fecha_fin(self):
    if self.estado == self.Estado.FINALIZADO:
        ultimo_partido = self.partidos.filter(ganador__isnull=False).order_by('-fecha_hora').first()
```

`torneo_finalizado_list.html:90` la usa por tarjeta (`paginate_by = 12`) → **1 query + 1 sort por
torneo**, y `fecha_hora` **no tiene índice**, así que el `ORDER BY` se resuelve ordenando.

Evidencia a escala: `x6 SELECT torneos_partido ... ORDER BY fecha_hora DESC LIMIT 1`.

**Arreglo:** `annotate(_fecha_fin=Max('partidos__fecha_hora', filter=Q(partidos__ganador__isnull=False)))`
y que la property lea el valor anotado si está. **Medido: 10 → 4 queries (−60 %), HTML idéntico,
10,1 → 9,2 ms.** Con la página llena serían 12 → 1.

### M2 — `MisTorneosView` le falta `torneo__organizacion` en el `select_related` (NUEVO)

`torneos/views.py:3356` trae `'torneo', 'torneo__division', 'equipo'`, pero `torneo_card.html`
accede 4 veces a `torneo.organizacion` (logo, nombre, iniciales) → **1 query por tarjeta**.

Evidencia a escala: `x10 SELECT accounts_organizacion ... WHERE id = ?` sobre 16 queries totales.

**Arreglo:** agregar `'torneo__organizacion'` y `annotate(Count('torneo__inscripciones'))`.
**Medido: 16 → 6 queries (−62 %), HTML idéntico.**

### M3 — Dashboard del organizador: N+1 de `torneo.division` (NUEVO)

`OrganizadorDashboardView` (`torneos/views.py:1836-1847`) arma `proximos` (hasta 6) y `recientes`
(hasta 5) sin `select_related('division')`; `recientes` sí tiene el del campeón.
Evidencia a escala: **x6 `SELECT accounts_division WHERE id = ?`** de 18 queries.
**Arreglo:** `.select_related('division')` en las dos querysets. Ahorro: hasta 11 queries.

### M4 — `/torneos/admin/revisar/`: 1 `Equipo` + 2 `CustomUser` por problema detectado (NUEVO)

`torneos/services/diagnostico.py` hace `prefetch_related('tabla__equipo', 'partidos_grupo')`, pero:

- `str(equipo)` entra a `jugador1` y `jugador2` (`equipos/models.py:98-103`) y **no están
  precargados** → 2 queries de `CustomUser` por cada nombre de pareja que se imprime.
- `p.equipo1` / `p.equipo2` de `g.partidos_grupo.all()` no tienen `select_related` → 1 `Equipo` más.
- `EquipoGrupo.objects.filter(equipo_id=...).first()` (línea 33) es 1 query **dentro del loop**.

Evidencia: **41 queries con los datos del repo** (1 solo torneo con zonas) y **53 a escala**:
`x18 customuser, x9 equipo, x5 equipogrupo`. Escala con la cantidad de inconsistencias, no con el
tamaño del torneo, así que un club con datos sucios la paga caro.

**Arreglo:** `prefetch_related('tabla__equipo__jugador1', 'tabla__equipo__jugador2',
'partidos_grupo__equipo1__jugador1', …)` y resolver el `EquipoGrupo.objects.filter(...)` con un dict
precalculado.

### M5 — `find_duplicate_candidates`: sin caché, O(K²) y **a partir de ~500 jugadores deja de detectar** (hallazgo 10)

`accounts/utils.py:665-718`. Sigue sin caché: `PosiblesDuplicadosView.get_context_data` lo llama en
**cada GET**, y el POST de fusión redirige a la misma vista, así que se re-paga después de cada
fusión.

Benchmark del bucle real (claves sintéticas, mismo algoritmo línea por línea):

| Jugadores | Claves únicas | ms de CPU | Pares | ¿Toca el tope de 20.000? |
|---|---|---|---|---|
| 28 | 27 | 6 | 351 | no |
| 100 | 97 | **104** | 4.656 | no |
| 200 | 188 | **425** | 17.578 | no |
| 500 | 434 | 457 | 20.385 | **SÍ** |
| 1.000 | 750 | 361 | 20.722 | **SÍ** |
| 2.000 | 1.184 | 396 | 21.166 | **SÍ** |

Dos cosas, y la segunda no estaba en el hallazgo previo:

1. El tiempo **se estanca en ~450 ms** por el tope `limit_pairs=20000`, no explota. Pero son 450 ms
   de CPU bloqueando un worker de Gunicorn en cada carga de página, sin caché.
2. **El tope se alcanza a las ~434 claves y a partir de ahí la detección queda incompleta**: con
   1.000 jugadores el bucle corta en el par 20.722 de los ~280.000 posibles, o sea revisa el 7 %.
   La función **deja de encontrar duplicados silenciosamente** justo cuando más hacen falta.
   Esto es un bug de correctitud escondido detrás de una cota de performance.

Verificado también en la vista real: `/accounts/usuarios/duplicados/` = **5 queries pero 115 ms** con
128 usuarios (la pantalla con peor relación CPU/queries de todo el sistema).

**Arreglo:** bucketear por inicial o por longitud antes de comparar, y cachear el resultado unos
minutos invalidando tras cada fusión. Ojo: el bucketing **saca el tope**, así que sin caché el costo
vuelve a crecer (medido: 200 → 50 ms, 1.000 → 738 ms, 2.000 → 1.389 ms). El bucketing **y** el caché,
o directamente un management command periódico.

### M6 — DatabaseCache: cada `cache.set` son **5 sentencias** y una de ellas es `COUNT(*)` de toda la tabla (hallazgo 9, ampliado)

Medido (`cache_cost.py`):

| Operación | Sentencias |
|---|---|
| `cache.get()` (hit o miss) | 1 |
| **`cache.set()`** | **5**: `SELECT COUNT(*) FROM django_cache` + `BEGIN` + `SELECT cache_key,expires` + `INSERT/UPDATE` + `COMMIT` |
| `cache.delete()` | 1 |

El `SELECT COUNT(*) FROM django_cache` es el chequeo de `MAX_ENTRIES` (1.000) y corre en **cada
escritura**. En Postgres un `COUNT(*)` es un seq scan: no hay index-only count. O sea, el caché
cobra un scan de la tabla de caché por cada cosa que guarda.

Y lo que guarda es pesado. Tamaños reales en `django_cache` de la base de desarrollo:

```
:1:perfil_gestion_25        10.740 bytes
:1:perfil_stats_ctx_1        7.456 bytes
:1:public_profile_ctx_3      3.004 bytes
:1:player_stats_3            2.392 bytes
```

Con instancias de modelo picklado adentro: **1 `CustomUser` = 812 bytes, 1 `Equipo` con jugador1 y
jugador2 = 1.358 bytes**. Una fila del ranking (`{'jugador': CustomUser, 'equipos': [Equipo], …}`)
pesa ~2,1 KB → **una división de 200 jugadores es un blob de ~420 KB en UNA fila**, que se escribe
y se des-pickla en cada vista del ranking y en **cada** `get_user_ranking` (que además recorre la
lista entera en Python para encontrar una sola fila, y se llama desde el perfil propio y el público).

**Arreglo:** cachear datos planos (ids + los campos que usa el template), y para `get_user_ranking`
consultar `RankingJugador` directo por `(jugador, division)` en vez de deserializar la división
entera. Si Render lo permite, un Redis chico cambia el costo de `set` de 5 sentencias SQL a 1
comando de red.

### M7 — Dos cachés de perfil que nunca se invalidan (hallazgo 26, ABIERTO)

Inventario de claves (`SET` vs `DELETE`):

| Clave | Se escribe en | Se invalida en | TTL |
|---|---|---|---|
| `rankings_jugadores_div_{id}_gen_{X}` | `accounts/utils.py:92,112,278` | `torneos/signals.py:81` ✔ | 300 s |
| `player_stats_{id}` | `accounts/utils.py:392` | `torneos/signals.py:88,90` ✔ | 300 s |
| `perfil_gestion_{id}` | `accounts/views.py:242` | `torneos/views.py:2614` (solo un flujo) | 300 s |
| **`perfil_stats_ctx_{id}`** | `accounts/views.py:167` | **nunca** | 300 s |
| **`public_profile_ctx_{id}`** | `accounts/views.py:381` | **nunca** | 300 s |
| **`home_stats`** | `core/views.py:41` | **nunca** | **3600 s** |
| `notifications_count_{id}` | `context_processors.py:81` | `accounts/push.py:69` ✔ | 60 s |

Consecuencia: después de cargar un resultado, el jugador ve sus stats viejas en su perfil y en el
perfil público hasta 5 minutos. **Arreglo:** sumar `perfil_stats_ctx_{id}` y
`public_profile_ctx_{id}` a `invalidar_cache_jugadores_equipo` (`torneos/signals.py:85-91`), donde ya
se borra `player_stats_{id}`. Es una línea y aprovecha una invalidación que ya existe y ya funciona.

### M8 — `fecha_hora` sin índice en ninguno de los dos modelos, y el `__date` es inindexable (hallazgo 18, ABIERTO)

Índices declarados hoy:

| Modelo | `Meta.indexes` |
|---|---|
| `CustomUser` | `(tipo_usuario, is_dummy)`, `(division, tipo_usuario)`, `(organizacion)` |
| `Notificacion` | `(usuario, leida)` |
| `Torneo` | `(estado, fecha_inicio)`, `(ciudad)`, `(organizacion, estado)` |
| `Inscripcion` | `(torneo, estado_pago)` |
| `PartidoGrupo` | `(grupo, ganador)` |
| `Partido` | `(torneo, ronda, orden_partido)` |

**Falta `fecha_hora`** en `Partido` y `PartidoGrupo`, y se filtra por ahí en tres lugares:

```sql
-- cron de recordatorios (cada 30 min), torneos/services/recordatorios.py:56
WHERE fecha_hora >= '2026-10-10 02:47:57' AND fecha_hora IS NOT NULL AND ganador_id IS NULL
```

Seq scan de las dos tablas, que crecen con cada torneo jugado (103 partidos por torneo × 10 torneos
× temporadas). Y **sin cota superior**: trae a Python todos los partidos futuros aunque falten
semanas, y descarta por ventana en el loop.

```sql
-- OrganizacionProgramacionView (accounts/views.py:572,581) y la planilla imprimible
WHERE django_datetime_cast_date("fecha_hora", 'America/Argentina/Buenos_Aires', 'UTC') = '2026-01-01'
```

**Matiz importante que no estaba en el hallazgo previo:** acá hay una **función sobre la columna**,
así que `db_index=True` en `fecha_hora` **no se va a usar** para este filtro. Para que el índice
sirva hay que convertir el `__date=X` en un `__range=(inicio_local, fin_local)`.

**Arreglo:**
1. `models.Index(fields=['fecha_hora'])` en `Partido` y `PartidoGrupo` (migración).
2. Cota superior en el cron: `fecha_hora__lte=ahora + timedelta(hours=25)` (la ventana más lejana
   es 24 h + 45 min de holgura).
3. En `OrganizacionProgramacionView`, reemplazar `fecha_hora__date=f` por
   `fecha_hora__range=(inicio, fin)` calculando el rango con `timezone.localtime`.

### M9 — `/torneos/<pk>/vivo/` recarga la página COMPLETA cada 20 segundos, es pública y no tiene ningún caché (NUEVO)

`torneos/templates/torneos/torneo_vivo.html:106`:

```js
setTimeout(function () { window.location.reload(); }, 20000);
```

Cada espectador con la pestaña abierta genera **3 requests/minuto de la página entera**
(13 queries, 136 KB crudos / 15 KB comprimidos, 27 ms). Es el único endpoint con carga **sostenida**
y no tiene `cache_page`, ni ETag, ni GET condicional. Medido a escala:

| Espectadores | req/s | queries/s | ms de CPU por segundo |
|---|---|---|---|
| 1 | 0,05 | 0,7 | 1 |
| 20 | 1,00 | 13,0 | 29 |
| 50 | 2,50 | **32,5** | **73** |

Con 50 espectadores en un torneo es tolerable (7 % de un core). El problema es el pico de domingo
con 10 clubes jugando: ~500 espectadores → 25 req/s, **325 queries/s, 730 ms de CPU por segundo**,
que satura un Render de 1-2 workers.

La pantalla de TV (`/tv/<alias>/`) ya está mejor pensada: pide solo el parcial cada 30 s. **Pero
medí que `?parcial=1` cuesta las MISMAS 10 queries** (111 KB crudos vs 138 KB; 3,8 KB vs 11,2 KB
comprimidos): ahorra ancho de banda, no base de datos.

**Arreglo:** que `/vivo/` haga lo mismo que `/tv/` (fetch de un parcial en vez de `location.reload`)
y, en los dos, un `cache_page(10)` o un `Last-Modified` derivado de
`max(finalizado_en)` para que el poll devuelva 304 cuando no pasó nada. Con 10 s de caché la carga
sostenida baja ~70 %.

### M10 — `AdminTorneoManageView` repite `.exists()` y la organización

La pantalla que el organizador abre después de **cada** acción (todos los POST redirigen acá):

```
 6 SELECT 1 FROM torneos_grupo   WHERE torneo_id = 1 LIMIT 1     <- views.py:225
 8 SELECT 1 FROM torneos_grupo   WHERE torneo_id = 1 LIMIT 1     <- views.py:236
11 SELECT 1 FROM torneos_grupo   WHERE torneo_id = 1 LIMIT 1     <- views.py:308
12 SELECT 1 FROM torneos_partido WHERE torneo_id = 1 LIMIT 1     <- views.py:313
13 SELECT 1 FROM torneos_partido WHERE torneo_id = 1 LIMIT 1     <- views.py:321
 2 SELECT accounts_organizacion WHERE id = 1                     (x2)
```

**Arreglo:** `tiene_grupos = grupos.exists()` una vez y reusarlo; idem con los partidos. −3 queries
por GET, en una pantalla que se recarga en cada click.

### M11 — `calcular_embudo` barre tablas enteras y le pasa a SQL una lista `IN (...)` gigante

`torneos/services/embudo.py`: trae a memoria **todos** los ids de jugador, **toda** la tabla
`Equipo` dos veces (líneas 31 y 40) y **toda** la tabla `Inscripcion`; después hace

```python
equipos.exclude(id__in=equipos_inscriptos).count()   # equipos_inscriptos es un set de Python
```

que genera un `WHERE NOT (id IN (<todos los equipo_id inscriptos>))`. Con 10 clubes × 10 torneos ×
50 parejas son 5.000 literales en el SQL. Hoy son 13 queries y 9 ms, pero el **tamaño** de la query
crece linealmente con la plataforma. **Arreglo:** resolver los 3 escalones con agregaciones
(`Count(distinct)` / `Exists()` / `filter(inscripciones__isnull=True)`) en vez de sets de Python, y
cachear el embudo unos minutos (es una métrica, no un dato operativo).

### M12 — `conn_max_age=600` sin `conn_health_checks`

`padel_project/settings.py:154`:

```python
DATABASES = {'default': dj_database_url.config(conn_max_age=600, ssl_require=True)}
```

Conexiones persistentes 10 minutos **sin chequeo de salud**. Si Postgres o el proxy de Render corta
una conexión idle, el worker la reusa y el request muere con `OperationalError` en vez de reconectar.
**Arreglo:** `dj_database_url.config(conn_max_age=600, conn_health_checks=True, ssl_require=True)`.
Cuesta un `SELECT 1` por request reusado y elimina esa clase de error 500.

### M13 — `get_player_stats` trae el historial COMPLETO del jugador para mostrar 8 partidos

`accounts/utils.py:464-478`: `pg_qs` y `pe_qs` traen **todos** los partidos jugados del jugador
(sin `[:8]`, sin filtro de fecha), se juntan en una lista de Python, se ordenan y se cortan en 8.
Con un jugador de 10 torneos son ~100 filas con `select_related` de 3 tablas. Crece
linealmente por temporada. **Arreglo:** `.order_by('-fecha_hora')[:8]` en cada queryset y unir los
16 candidatos en Python. Encima evita los hasta 8 aggregates de `nombre_ronda` (A2).

---

## BAJO

### B1 — `cupos_disponibles` ejecuta el mismo COUNT 3 veces (hallazgo 34: son 3, no 4)

`Torneo.cupos_disponibles` (`torneos/models.py:285-287`) hace `inscripciones.count()` sin memoizar.
`torneo_detail.html:177-178` la evalúa 2 veces en el mismo `{% if %}`, y la vista cuenta lo mismo
para `hay_cupos` (`torneos/views.py:2070`). Medido en `/torneos/2/` con un usuario con pareja:
**x3 `SELECT COUNT(*) FROM torneos_inscripcion WHERE torneo_id = 2`** (anónimo: 2, porque no entra al
branch de `hay_cupos`). A escala en `/torneos/<abierto>/`: **x4** (la ficha + el card).
**Arreglo:** `{% with libres=torneo.cupos_disponibles %}` en el template y pasar `hay_cupos` derivado
de un único COUNT en la vista. `/tv/` tiene lo mismo en `pantalla/_placas.html:155` (x3 medidas).

### B2 — HTML crudo grande: 531 KB en gestionar, 404 KB en la ficha (es DOM, no ancho de banda)

`GZipMiddleware` está activo y primero en la cadena, y funciona bien:

| Pantalla (escala) | Crudo | Comprimido |
|---|---|---|
| `/torneos/admin/<x>/gestionar/` | **531 KB** | 29 KB |
| `/torneos/<x>/` | **404 KB** | 26 KB |
| `/accounts/organizador/1/programacion/` | 359 KB | 22 KB |
| `/torneos/admin/<x>/cobros/` | 304 KB | 20 KB |

O sea: el problema **no es el ancho de banda** (los 191-201 KB que medías son crudos; por el cable
viajan ~23 KB). Lo que sí paga el celular es parsear y mantener 400-530 KB de DOM: en un Android de
gama media son cientos de ms de layout y bastante memoria. Es la pantalla que el organizador tiene
abierta todo el día al borde de la cancha. **Arreglo:** paginar o colapsar server-side la lista de
inscriptos y las 12 zonas en `gestionar` (hoy se renderizan todas, abiertas o no).

### B3 — `/accounts/rankings/` consulta `accounts_division` 4 veces

Son 4 queries de una tabla de 8 filas: ruido, pero gratis de arreglar cacheando las divisiones en el
contexto.

### B4 — El parcial de la TV ahorra bytes, no queries

`/tv/club-demo/?parcial=1` corre el mismo `get_context_data` → **10 queries, 46 ms**, igual que la
página completa. Si alguna vez molesta, ahí va un `cache_page` corto.

### B5 — `GlobalSearchView` usa `unaccent__icontains`: seq scan, y es público sin throttle

`core/utils.py:71-77` arma `Q(campo__unaccent__icontains=valor)`, que en Postgres se traduce a
`UPPER(UNACCENT(col)) LIKE '%...%'`. **Función sobre la columna y comodín a la izquierda: ningún
índice sirve.** Se hace sobre `nombre`, `apellido` y `email` de `CustomUser`, sobre `Torneo.nombre` +
`division__nombre` y sobre `Equipo.nombre`, una vez por palabra de la búsqueda. Hoy son 3 queries y
11 ms; con 2.000 jugadores y 1.000 parejas son varios seq scans por request en un endpoint
**anónimo y sin límite de tasa**. **Arreglo:** extensión `pg_trgm` + índice GIN funcional sobre
`UPPER(unaccent(nombre))`, o como mínimo exigir 3 caracteres y throttlear.

### B6 — `Circuito.tabla_posiciones()` recalcula todo en cada visita (hallazgo 32, ABIERTO)

`torneos/models.py:785-811` llama a `calcular_puntos_por_jugador(torneo_ids)` en cada acceso, sin
caché, y es un **método** (no `cached_property`), así que si el template lo usa más de una vez se
recalcula entero otra vez. No hay circuitos en la base, así que esto queda verificado por código
y no medido. **Arreglo:** `cached_property` + caché 5 min con la misma invalidación por división que
ya existe.

### B7 — `check_llaves_internas_generacion` sin guard de `update_fields`

Cubierto por el arreglo de A1, pero vale aparte: `torneos/signals.py:195` entra a `instance.grupo` y
`grupo.torneo` (2 SELECT) en **todo** guardado de `PartidoGrupo`, incluso cuando solo se tocó
`fecha_hora` o `recordatorios_enviados`, para después salir por `if torneo.formato_grupos_4 != LLAVES:
return`. Son las 2 últimas sentencias de las 21 del ejemplo de A1.

---

## 3. Qué explota con un club real de 50 parejas y 10 torneos

Ordenado por cuánto empeora:

| Cosa | Hoy (datos demo) | Club real (medido en la copia) | Cómo escala |
|---|---|---|---|
| **Programar los horarios de un torneo** | — | **1.512 sentencias SQL** | 21 por partido, lineal (A1) |
| **`/programacion/`** | 23 queries | **67 queries** | `2 × partidos de llave + 5`; con 64 parejas, ~131 (A2) |
| Cargar los resultados de un torneo | — | **4.328 sentencias** (zona + llave) | 36 y 56 por partido (A1) |
| Cron de recordatorios | — | **1.050 sentencias cada 30 min** + 2 seq scans | 21 por partido marcado (A1 + M8) |
| `/torneos/admin/listado/` | 10 queries | **20** | 1 COUNT por tarjeta, hasta 20 por página (A5) |
| `/equipos/mi-equipo/` | 28 queries | **31** | fijo pero caro; crece con el historial (A4) |
| `/torneos/finalizados/` | 5 queries | **10** | 1 query + 1 sort por tarjeta, hasta 12 (M1) |
| `/torneos/mis-torneos/` | 4 queries | **16** | 1 query por torneo del jugador (M2) |
| `/accounts/usuarios/duplicados/` | 15 ms | **115 ms** (128 jug.) → **425 ms** (200) | O(K²) hasta el tope, y después **detecta mal** (M5) |
| Blob del ranking en `django_cache` | ~0 | **~420 KB en una fila** con 200 jugadores | 2,1 KB por jugador (M6) |
| `/torneos/<pk>/vivo/` | 13 q | **32,5 queries/s con 50 espectadores** | lineal en espectadores (M9) |
| HTML de `gestionar` | 201 KB | **531 KB** crudos / 29 KB comprimidos | lineal en parejas y zonas (B2) |

Lo que **no** explota, por si sirve para priorizar:

- El home ya está bien (5 queries, `annotate` + `select_related`), y a escala sigue en 5.
- `/tv/club-demo/`: 10 queries y 47 ms con 10 torneos. Bien resuelto.
- El dashboard usa agregaciones y no N+1 para los contadores; solo le falta el `select_related`
  de división (M3).
- El debounce de rankings (hallazgo 5) y la fusión asincrónica (hallazgo 3) funcionan: confirmado.
- `createcachetable` está en `build.sh`. Bien.
- La compresión gzip está activa y hace su trabajo.

---

## 4. Orden de ataque sugerido

| # | Hallazgo | Esfuerzo | Ganancia medida |
|---|---|---|---|
| 1 | **A1** borrar el receiver muerto de `equipos/signals.py` + guard de `update_fields` | borrar 20 líneas y agregar 3 | programar horario **21 → 1** (−95 %); resultado de zona −50 %; de llave −62 % |
| 2 | **A2** `total_rondas` una vez, `nombre_ronda_dinamico` en los loops | 3 vistas | `/programacion/` **67 → 5** (−93 %), 70 → 35 ms |
| 3 | **A3** `cached_property` en `CustomUser.equipo` | 1 línea | −16 queries en 7 pantallas; `/torneos/abiertos/` −37 % |
| 4 | **A5** `annotate` en los 4 listados | 4 vistas + 4 templates | `admin/listado/` **20 → 7**; el COUNT: 15 q/9,7 ms → 1 q/2,8 ms |
| 5 | **A4** memoizar `get_object` y las stats de `MiEquipoDetailView` | 1 vista | **31 → 21** (−32 %) |
| 6 | **M1 + M2 + M3** `annotate`/`select_related` que faltan | 3 vistas | finalizados **10 → 4**; mis-torneos **16 → 6**; dashboard −6 |
| 7 | **M7** invalidar `perfil_stats_ctx_` y `public_profile_ctx_` | 2 líneas | corrige stats viejas por 5 min |
| 8 | **M8** índice en `fecha_hora` + cota en el cron + `__range` | 1 migración + 2 vistas | saca 2 seq scans por corrida del cron |
| 9 | **M5** bucketing + caché en duplicados | 1 función | 425 → ~50 ms, y **vuelve a detectar** arriba de 500 jugadores |
| 10 | **M9** GET condicional / parcial en `/vivo/` | 1 template + 1 vista | −70 % de la carga sostenida |
| 11 | **M6** cachear datos planos en vez de instancias | refactor de `accounts/utils.py` | saca cientos de KB por fila de `django_cache` |
| 12 | **M12** `conn_health_checks=True` | 1 línea | elimina los 500 por conexión muerta |

Los primeros cinco son todos cambios chicos y localizados, con ganancia verificada y HTML idéntico
byte a byte antes y después.
