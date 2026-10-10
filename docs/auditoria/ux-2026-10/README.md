# Auditoría UX/UI y performance — octubre 2026

Siete informes, hechos en paralelo por área, todos **medidos** sobre la app corriendo
con datos reales: 35 pantallas × 2 temas a 375/390px, más una copia de la base poblada
con un club realista (10 torneos, 50 parejas, 100 jugadores) para medir qué escala mal.

No repite los 36 hallazgos de `docs/auditoria/hallazgos.json`; sí dice cuáles de ésos
siguen abiertos.

| # | Informe | Área |
|---|---|---|
| 00 | [frontend-assets](00-frontend-assets.md) | Peso de página, imágenes, terceros |
| 01 | [landing-home](01-landing-home.md) | Home y landing comercial |
| 02 | [jugador](02-jugador.md) | Flujo del jugador |
| 03 | [organizador](03-organizador.md) | Flujo del organizador al borde de la cancha |
| 04 | [features-nuevas](04-features-nuevas.md) | Pantalla TV, alta en 2 pasos, popup, errores |
| 05 | [performance-backend](05-performance-backend.md) | Consultas, caché, índices |
| 06 | [sistema-de-diseno](06-sistema-de-diseno.md) | Consistencia y accesibilidad |

---

## El titular

**La app no tiene un problema de diseño: tiene cuatro causas raíz que se multiplican por
pantalla.** Áreas que no se hablaron entre sí llegaron al mismo puñado de líneas de CSS.
Por eso la buena noticia: **~40 líneas en `styles.css` y `base.html` apagan la mayoría de
los hallazgos de impacto alto en toda la app a la vez.**

### 1. El verde de marca no se puede leer en el tema claro — que es el que viene por defecto

`#10b981` tiene luminancia 0.364: justo en el medio. No puede ser fondo de texto blanco
*y* texto sobre blanco. Hoy se usa para las dos cosas.

| Dónde | Contraste | Mínimo |
|---|---:|---:|
| `.btn-primary` (blanco sobre esmeralda) | **2.54:1** | 4.5 |
| `.text-primary` sobre tarjeta | 2.53:1 | 4.5 |
| Aviso `warning` (`text-white` forzado) | **1.66:1** | 4.5 |
| Botón "Regenerar llave" | 1.66:1 | 4.5 |
| Filas que clasifican en la tabla de posiciones | 2.07–2.54:1 | 4.5 |

**516 de 1193 nodos de texto (43%) quedan por debajo de AA en modo claro.**

Lo irónico: `base.html:117-119` **ya tiene el arreglo**, pero scopeado a
`[data-theme="business"]`. El tema oscuro —el que casi nadie prueba— está bien (6.86:1)
y el default está roto. Sacar ese scope es una línea.

Tres agentes distintos llegaron a esto por caminos independientes.

### 2. Una regla global de CSS rompe todos los `.alert`

`styles.css:22` apila en columna cualquier `.flex` con dos `.btn` adentro. Los banners son
`class="alert ... flex"` con un botón de acción y un `✕`, así que matchean. Resultado
medido: el banner de instalar pasa de 46px a **178px de alto**; los dos banners juntos se
comen **390px de 812 — el 56% de la primera pantalla**, en todas las páginas.

Agregar `:not(.alert)` al selector recupera ~208px en toda la app.

### 3. `text-white` pegado a mano en botones de color

11 `btn-success`, 6 `btn-error`, 4 `btn-primary`, 3 `btn-warning`, 3 `btn-info`, más el
bloque de `messages` en `base.html:725`. Es la causa concreta de la mitad de la tabla de
arriba. Sacándolo, DaisyUI usa su propio `*-content` y el `warning` pasa de 1.66 a 12.62:1.

### 4. No existe un token de "texto secundario"

496 declaraciones con 20 valores distintos de `opacity-NN` y `text-base-content/NN`, en 83
de 108 templates; **305 son ilegibles**. El piso seguro medido para los dos temas es 78%.

---

## Lo más grave por fuera del diseño

**Se puede borrar un resultado sin querer, y la app dice "✓ Guardado".**
`torneos/forms.py` no valida que alguien gane: con el popup vacío o con sets empatados,
`clean()` deja `ganador = None` y, como es un `ModelForm`, **pisa el ganador anterior**. El
partido deja de mostrar resultado y la zona **no se puede cerrar nunca**, porque "Avanzar
Clasificados" exige ganador en todos y el tooltip sólo dice "Faltan resultados".

**La TV marca mal quién clasifica.** `torneos/pantalla.py:352` hardcodea `clasifican = 2`,
pero **28 de los 43 tamaños de llave FAP** llevan un tercero al cuadro. En el 65% de los
torneos posibles, una pareja que clasifica aparece "afuera" en la tele del club — mientras
la placa siguiente del mismo carrusel muestra "3° Zona A" como cruce.

**El panel del organizador cuenta mal.** Muestra "0/9 jugados" con 13 de 22 partidos
cargados: `views.py:1829` cuenta sólo `Partido` (la llave) e ignora `PartidoGrupo` (las
zonas). Es la única métrica de avance que ve el cliente que paga.

**Contraseñas de 9.000 combinaciones sin límite de intentos.** `generar_password` es
nombre + 4 dígitos, y el nombre viaja en el mismo WhatsApp. `CustomLoginView` no tiene
throttle, aunque el repo ya lo usa en el código por mail y en el buscador público.

**La integridad del script de HTMX está desactivada por un typo.** `base.html:70` dice
`xintegrity=` en vez de `integrity=`: HTMX se baja de unpkg sin verificar. Bajé el archivo
y calculé el sha384: **el hash escrito es el correcto**, así que renombrar el atributo es
un arreglo de una letra que no rompe nada.

---

## Performance

**Backend.** El hallazgo más grande es código muerto: `equipos/signals.py:12-32` borra tres
claves de caché que **nadie escribe nunca** (la real lleva sufijo `_gen_`, y ya la invalida
bien `torneos/signals.py:81`). Con `DatabaseCache` cada borrado es un DELETE real: son
**17 de las 21 sentencias** que cuesta programar el horario de un partido. Borrar el
receiver lo baja de 21 a 1. En un torneo de 50 parejas, programar los 72 horarios pasa de
**1.512 a 72 sentencias**.

| Pantalla | Hoy | Arreglado | Cómo |
|---|---:|---:|---|
| Programar un horario | 21 q | **1** | borrar receiver muerto |
| `/programacion/` (a escala) | 67 q | **5** | no usar `nombre_ronda` en loops |
| `/mi-equipo/` | 31 q | 21 | memoizar |
| Listados de torneos | 15 q | **1** | `annotate` en vez de `.count` por tarjeta |

El N+1 de `/programacion/` es **doble**: 10 `SELECT torneo` + 9 `MAX(ronda)`, o sea 18 de
23 consultas son desperdicio. Y `select_related('torneo')` **no** lo arregla (está probado:
otra vista lo tiene y paga los aggregates igual); hay que sacar la property del loop.

**Frontend.** La home pesa 795 KB en celular y **556 KB son dos imágenes**: un fondo de
1920×1440 para una caja de 343px, y un logo de 519×480 que se muestra a 32×32 (8× más
grande de lo necesario, en todas las páginas). Convertidas a WebP del tamaño correcto:
**700 KB → 98 KB (−86%)**. Hay además 1,1 MB de fondos que no referencia ningún template.

El CSS **no** es el problema: en producción viaja en 20 KB con brotli y está bien
resuelto. No tocarlo.

---

## Las herramientas de auditoría estaban mintiendo

Esto explica por qué varios de estos problemas llevaban tiempo sin verse:

- **`verificar_mobile.py`** marcaba 15/15 pantallas por contar botones ocultos
  (`width: 0`) como desalineados. Pero además **el login no entra**: 5 rutas de admin
  redirigían a `/` con status 200, así que **medía la home seis veces** y decía que había
  auditado 15 pantallas. Corregido: 0/15, y las 15 medidas de verdad.
- **`auditoria_modo_claro.py`** daba "0 de 27 pantallas con texto ilegible". Es un **falso
  negativo**: resta luminancias en vez de calcular contraste, e ignora el alpha del texto.
  Por eso el problema de color del tema claro nunca apareció.
- **`auditoria_ui.py`** heredaba el mismo login roto, así que sus totales estaban inflados
  por repetición (266 botones reportados → 190 reales; 73 textos chicos → 15).

Las versiones corregidas quedaron en [`scripts/`](scripts/).

---

## Lo que está bien y conviene no romper

- **El popup de cargar resultado es lo mejor diseñado del producto**: casilleros de
  120×56px, `inputmode=numeric`, `aria-label` por campo, contador de sets en vivo.
- **La landing comercial es genuinamente buena**: pasa el test de los 5 segundos y el
  microcopy rioplatense está muy logrado. El problema de marca no es la landing: es que
  **la home no está a su altura**, y el prospecto hace ese salto de un toque.
- **La pantalla de TV está bien construida** (6 consultas, 9 ms) y la rotación funciona.
- **El tema oscuro pasa AA** en los colores de marca.
- **Cero desborde horizontal** en todas las pantallas, cero imágenes sin `alt`, cero
  botones de ícono sin nombre accesible, una sola familia tipográfica.
- El build de Tailwind, whitenoise con brotli y hash, y el refresco parcial por htmx
  (12 KB en vez de 178) están bien pensados.

---

## Orden de ataque sugerido

**Tanda 1 — una tarde, riesgo bajo, impacto en toda la app**
1. Sacar el scope `[data-theme="business"]` del arreglo de contraste (1 línea).
2. Sacar `text-white` del bloque de `messages` y de los botones de color.
3. `:not(.alert)` en la regla de `styles.css:22`.
4. Renombrar `xintegrity` → `integrity`.
5. Borrar el receiver muerto de `equipos/signals.py`.
6. Mover `color-scheme: light` al `@media print` global de `styles.css` (hoy sólo lo tiene
   la planilla, así que las demás páginas se imprimen con marco negro desde modo oscuro).

**Tanda 2 — correctitud**
7. Validar en `forms.py` que un resultado defina ganador.
8. Arreglar `clasifican` en la pantalla de TV.
9. Contar `PartidoGrupo` en el panel del organizador.
10. Throttle en el login.

**Tanda 3 — performance y peso**
11. Sacar `nombre_ronda` de los loops; `annotate` en los listados; `cached_property` en
    `CustomUser.equipo`.
12. Convertir las dos imágenes a WebP con `srcset`; borrar los fondos sin usar.

**Tanda 4 — lo premium de verdad**
13. El token de texto secundario y la escala tipográfica.
14. Unificar iconografía (62 emoji distintos conviviendo con 223 SVG).
15. Repensar la primera pantalla: hoy el 56% se lo comen dos banners de autopromoción.
