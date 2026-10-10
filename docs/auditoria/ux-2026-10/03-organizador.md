# Auditoría de producto — flujo del organizador de club

**Fecha:** 2026-10-09 · **Viewport:** 375x812 (DPR 2) · **Temas:** claro (`corporate`, el default) y oscuro (`business`)
**Cuenta:** `organizador.demo@todopadel.club` · **Datos:** torneo 1 "6TA CABALLEROS" (EN JUEGO), torneo 2 (ABIERTO), torneo 4 (FINALIZADO)
**Método:** Playwright contra `localhost:8010` + lectura de código + pruebas de formulario en memoria.
**No se escribió nada en la base de datos.** Los formularios se probaron con `is_valid()` sobre instancias no persistidas y el swap de htmx se simuló inyectando el HTML exacto que devuelve `refrescar_zona()`.

> **Nota sobre el medidor de contraste.** El primer barrido dio ~87 fallas en `/gestionar/`: era un falso positivo mío. Pintaba el lienzo de negro antes de medir, así que todo `background-color: transparent` se leía como negro opaco. Corregido (lienzo transparente + desmultiplicar alfa + apilar capas), los números bajaron a 53/56 y las fallas que quedan están verificadas leyendo los colores computados crudos (`fg`/`bg` en RGB, sin parsear oklch a mano). Los `ratio` de abajo son de la versión corregida.

---

## Resumen de la tarea real

**"Cargar el resultado de un partido que se acaba de jugar"**, desde que el organizador saca el celular:

| # | Acción | Costo medido |
|---|---|---|
| 1 | Abre la app → cae en `/` (la home **pública**, no en su panel) | — |
| 2 | Toca el menú hamburguesa | 1 toque |
| 3 | "Listar Torneos" (no hay entrada al Panel en el menú) | 1 toque |
| 4 | Scrollea y toca "Gestionar" del torneo | 1 toque + scroll |
| 5 | **Scrollea 894px** hasta la primera zona | scroll |
| 6 | Toca la cabecera de la zona (acordeón nivel 1) | 1 toque |
| 7 | Scrollea hasta el partido | scroll |
| 8 | Toca el partido (acordeón nivel 2) | 1 toque |
| 9 | Toca "Cargar Resultado" | 1 toque |
| 10 | Escribe 4–6 números | 4–6 toques |
| 11 | **Baja el teclado o scrollea dentro del popup** (Guardar no se ve) | 1–2 gestos |
| 12 | "Guardar resultado" | 1 toque |
| 13 | **La zona se cierra sola y el scroll salta 601px hacia arriba** → volver al paso 5 | — |

**≈ 11 toques y 3 scrolls para el primer resultado, y ≈ 8 toques + 2 scrolls para cada uno de los 21 siguientes**, porque el paso 13 descarta el trabajo de los pasos 5–8.

¿Se puede con una mano? El popup sí (es lo mejor diseñado del flujo). Llegar al popup y volver, no.
¿Hay confirmación clara? Sí, hay un toast "✓ Guardado en Zona A" y se ve aunque estés scrolleado abajo. Bien.
¿Se puede equivocar fácil? **Sí**: el popup acepta y guarda resultados sin ganador diciendo "Guardado" (A2), y los tres botones más grandes de la primera pantalla son los tres destructivos (A4).

---

# ALTO

## A1 · Después de guardar cada resultado, la zona se cierra sola y el organizador pierde el lugar

**Qué pasa.** `refrescar_zona()` devuelve el panel de la zona con `HX-Reswap: outerHTML`. El partial `_grupo_panel.html` renderiza el checkbox del colapso **sin `checked`**, y nada lo vuelve a abrir después del swap: la única restauración de estado (`restaurar()`) corre en `DOMContentLoaded`, y acá no hay recarga de página.

**Archivo:línea.**
- `torneos/views.py:1367-1406` (`refrescar_zona`, el `HX-Retarget` + `outerHTML`)
- `torneos/templates/torneos/partials/_grupo_panel.html:13` → `<input type="checkbox" class="group-checkbox" data-panel-id="grupo-{{ grupo.pk }}" />`
- `torneos/templates/torneos/admin_torneo_manage.html:826-871` (`guardar`/`restaurar`: guarda en `sessionStorage` en `htmx:beforeRequest`, pero **nadie lo lee** salvo en `DOMContentLoaded`)
- No hay ningún listener de `htmx:afterSwap` en la app salvo uno en `torneo_detail.html:854`.

**Evidencia medida** (swap simulado con el HTML idéntico al del server):

```
ANTES de guardar:  scrollY 1054  alto 2580  zonaAbierta True   partidosAbiertos 1  botonVisible True
DESPUES del swap:  scrollY  453  alto 1979  zonaAbierta False  partidosAbiertos 0  botonVisible False (y=960)
```

Y el render del partial confirma que viene cerrado:
```
group-checkbox con checked? False
total de checkboxes de colapso en el panel devuelto: 3   (todos sin checked)
```

**Por qué le importa al borde de la cancha.** Es el costo multiplicado por 22. El comentario del propio partial dice que el refresco parcial se hizo justamente para que *"el organizador no perdiera el lugar en cada uno"* — y se arregló la recarga pero no el colapso. Cargar una zona de 4 partidos obliga a reabrir la zona 4 veces, con un salto de scroll de 601px en el medio.

**Arreglo.** Dos líneas, cualquiera de las dos:
- En `refrescar_zona`, pasar al contexto si el panel estaba abierto y renderizar `{% if abierto %}checked{% endif %}` (htmx puede mandarlo en un `hx-vals`), **o**
- en `admin_torneo_manage.html`, exponer `restaurar()` y llamarla en `htmx:afterSwap` (el estado ya está guardado en `sessionStorage` por `guardar()` en `htmx:beforeRequest`; solo falta leerlo).

**Veredicto:** bug.

---

## A2 · El popup guarda "resultados" que no definen ganador y avisa "Guardado" igual

**Qué pasa.** `CargarResultadoGrupoForm.clean()` no valida que alguien haya ganado. Si los sets empatan (o están vacíos), `instance.ganador = None` y el form es válido. El navegador tampoco lo frena (los seis campos son `required=False`), el toast dice "✓ Guardado en Zona A", y el partido vuelve a aparecer **sin resultado** porque el panel solo lo muestra `{% if partido.ganador %}`.

**Archivo:línea.** `torneos/forms.py:385-408` (rama NORMAL de `clean()`; el `else: self.instance.ganador = None` no agrega ningún error) · `torneos/templates/torneos/partials/_grupo_panel.html:172`.

**Evidencia medida** (form probado en memoria, sin guardar, sobre un partido que **ya tenía** ganador):

```
OK  | todo vacio, "se jugo normal"                 | sets 0-0  games 0-0   | ganador: None
OK  | empate 1-1 en sets (6-4 / 4-6, sin tercero)  | sets 1-1  games 10-10 | ganador: None
OK  | empate 6-6 en el set 1                       | sets 0-0  games 6-6   | ganador: None
OK  | un lado vacio (6 vs nada)                    | sets 0-0  games 0-0   | ganador: None
```

Y en el navegador, con 6-4 / 4-6 cargado:
```
Empate 1-1 (6-4 / 4-6, sin tercero): navegador lo acepta=True, contador="1-1", hay aviso de error en pantalla=False
Form COMPLETAMENTE VACIO: valido para el navegador=True, contador "0-0", boton Guardar deshabilitado=False
```

**Por qué le importa.** Es el error típico de apuro: cargás los dos primeros sets, te llaman, tocás Guardar. La app te dice que guardó. El partido queda sin ganador, no se nota (no muestra "Resultado:"), **y la zona no se puede cerrar nunca**: `grupo_terminado` exige `p.ganador` en todos los partidos, así que "Avanzar Clasificados" queda deshabilitado con el tooltip genérico "Faltan resultados por cargar en el grupo" y el organizador no tiene forma de saber cuál. Peor: si el partido ya tenía resultado, un Guardar en vacío **lo borra** y dispara igual el recálculo de la tabla.

**Arreglo.**
1. En `clean()`, si `resolucion == NORMAL` y no hay ganador, `add_error(None, "Cargá el resultado completo: todavía no hay un ganador. Si el partido no se jugó, elegí Walkover o Abandono.")`.
2. En el JS del popup, deshabilitar "Guardar resultado" mientras el contador en vivo esté empatado o en 0-0 (el contador ya existe, solo hay que atarlo al botón).

**Veredicto:** bug.

---

## A3 · En modo claro —el tema por defecto— todos los botones primarios están a 2.54:1, incluido "Guardar resultado"

**Qué pasa.** `theme/templates/base.html` fuerza `color: white` en `.btn-primary`/`.btn-success` y después lo **corrige solo para el tema oscuro**. Resultado: el tema que casi nadie prueba (oscuro) está bien y el default está mal.

```css
/* theme/templates/base.html:112-120 */
.btn-primary, .btn-success {
    background-color: #10b981 !important;
    color: white !important;            /* ← 2.54:1 en modo claro */
}
[data-theme="business"] .btn-primary,
[data-theme="business"] .btn-success {
    color: #1a1a1a !important;          /* ← 6.86:1, el arreglo está solo en oscuro */
}
```
El token de DaisyUI tiene la misma inversión: `--pc: 98% 0.01 163` en corporate vs `15% 0.02 163` en business (`base.html:92-103`).

**Evidencia medida** (colores computados crudos, sin parsear oklch):

| Botón | Modo claro | Modo oscuro |
|---|---|---|
| `btn-primary` "Editar Resultado" | fg(255,255,255) bg(16,185,129) → **2.54:1** | fg(26,26,26) → 6.86:1 |
| `btn-success` "Avanzar Clasificados" | **2.54:1** | 6.86:1 |
| `btn-primary` "Guardar" (cobros, x6) | **2.54:1** | 6.86:1 |
| `btn-primary` "+ Nuevo torneo" | **2.54:1** | 6.86:1 |

Mínimo WCAG AA para 14px semibold: 4.5:1. También falla el umbral de texto grande (3.0:1).

**Por qué le importa.** "Guardar resultado" es el botón que el organizador toca 22 veces por torneo, al sol, apurado. Blanco sobre verde claro a plena luz es la peor combinación posible.

**Arreglo.** Invertir la regla: `color: #053a2c` (o `#1a1a1a`) como base y, si hace falta, white solo donde el fondo sea oscuro. Y alinear `--pc` de corporate con el de business.

**Veredicto:** bug (regresión de contraste en el tema por defecto).

---

## A4 · La primera pantalla de un torneo en juego son tres botones destructivos gigantes; cargar resultado está 994px más abajo

**Qué se ve** (captura `g1_tope_claro.png`, 375x812): título, badges, "Horarios · PDF", "Pantalla TV", "Configuración" y después, a todo lo ancho y apilados, **"Regenerar Llave" · "Reemplazar Pareja" · "Finalizar Torneo"**. No se ve ni una zona.

**Mapa vertical medido de `/torneos/admin/1/gestionar/`:**
```
y=217  h1 "6TA CABALLEROS"
y=345  Horarios · PDF
y=441  Configuración
y=529  Regenerar Llave      ← borra TODOS los resultados de la llave
y=641  Finalizar Torneo     ← cierra el torneo
y=734  buscador "Buscar equipo, grupo o ronda..."
y=814  sección "Zonas"
y=896  "➕ Agregar una zona con parejas nuevas"
y=994  Zona A               ← la primera acción útil, a 894px de scroll
```
Página: 178 KB de HTML en el DOM, 1979px (2.4 pantallas), 5 zonas, 22 partidos, 89 botones, **0 colapsos abiertos**.

Encima el texto de esos botones es ilegible en los **dos** temas:
- `btn-warning text-white` "Regenerar Llave": fg(255,255,255) bg(255,190,0) → **1.66:1**
- `btn-error text-white` "Finalizar Torneo": fg(255,255,255) bg(255,88,97) → **3.08:1**

`torneos/templates/torneos/admin_torneo_manage.html:152` y `:176` (`btn btn-warning text-white`), `:193` (`btn btn-error text-white`). En toda la app hay 11 `btn-success`, 6 `btn-error`, 4 `btn-primary`, 3 `btn-warning` y 3 `btn-info` con `text-white` pegado.

**Por qué le importa.** Jerarquía invertida en la pantalla más usada: lo que se hace una vez por torneo (y es irreversible) ocupa la primera pantalla, y lo que se hace 22 veces está escondido detrás de scroll + dos acordeones. Un pulgar que entra a la pantalla y arrastra para scrollear pasa justo por encima de "Regenerar Llave".

**Arreglo.**
1. Mandar las tres acciones de ciclo de vida a un menú "⋯ Más acciones" o al final de la página, y dejar arriba solo lo informativo + el buscador.
2. Subir las zonas: que la primera zona empiece dentro de la primera pantalla.
3. Sacar `text-white` de `btn-warning`/`btn-error` y dejar que DaisyUI use `warning-content`/`error-content`.

**Veredicto:** decisión mejorable (jerarquía) + bug (contraste 1.66:1).

---

## A5 · Con el teclado numérico abierto no se ve "Guardar resultado" ni "¿Cómo terminó?"

**Evidencia medida** (mismo popup, solo cambia el alto de viewport):
```
sin teclado (812px):  modal top 118 bottom 758 alto 640  scrollea=False  guardarVisible=True
teclado abierto (380px): modal top 72 bottom 372 alto 300  scrollea=True  guardarVisible=False (top 596)
                                                           "¿Cómo terminó?" visible=False
```
Captura `p_popup_380.png`: con el teclado arriba solo entran Set 1 y Set 2. El encabezado fijo ("Cargar resultado" + "Zona A" + la X) se come 145px de los 380 disponibles — el 38%.

**Archivo:línea.** `torneos/templates/torneos/partials/_form_resultado.html:28-47` (encabezado) y `:130-134` (botonera al final del `<form>`).

**Por qué le importa.** Es exactamente el escenario del brief: una mano, teclado numérico abierto, gente esperando. Después de tipear el último número hay que bajar el teclado o scrollear adentro del popup para encontrar Guardar. Son 1–2 gestos extra por resultado, ×22.

**Arreglo.** Botonera sticky dentro del `modal-box` (`position: sticky; bottom: 0` con fondo `bg-base-100`) y encabezado compacto (una línea, sin subtítulo) cuando `max-height: 500px`. Alternativa barata: al cargar el último set, hacer `scrollIntoView` del botón Guardar.

**Veredicto:** bug de layout.

---

## A6 · El Panel del organizador cuenta mal los partidos: dice 0/9 cuando van 13/22

**Qué pasa.** `OrganizadorDashboardView` cuenta solo `Partido` (la llave) y nunca `PartidoGrupo` (las zonas), que es donde está el grueso del torneo.

```python
# torneos/views.py:1828-1833
partidos = Partido.objects.filter(torneo__in=torneos)
partidos_agg = partidos.aggregate(
    total=Count('id'), jugados=Count('id', filter=Q(ganador__isnull=False)))
```

**Evidencia medida** (club Demo, lectura directa de la base):
```
Lo que CUENTA el dashboard (solo Partido / llave):   {'total': 9,  'jug': 0}
Lo que IGNORA   el dashboard (PartidoGrupo / zonas): {'total': 13, 'jug': 13}

Dashboard muestra: 0/9 jugados, 9 pendientes
Realidad:          13/22 jugados, 9 pendientes
```
Confirmado en pantalla: la tarjeta dice **"0/9 Partidos jugados · 9 pendientes"**.

**Por qué le importa.** Es la única métrica de avance del cliente que paga. Abre el panel después de una jornada en la que cargó 13 resultados y la app le dice que no jugó ninguno. Mata la confianza en el resto de los números.

**Arreglo.** Sumar las dos fuentes:
```python
zonas_agg = PartidoGrupo.objects.filter(grupo__torneo__in=torneos).aggregate(
    total=Count('id'), jugados=Count('id', filter=Q(ganador__isnull=False)))
partidos_total  = (partidos_agg['total']  or 0) + (zonas_agg['total']  or 0)
partidos_jugados = (partidos_agg['jugados'] or 0) + (zonas_agg['jugados'] or 0)
```
Y actualizar `torneos.tests.DashboardOrganizadorTests` con un caso de zona.

**Veredicto:** bug.

---

# MEDIO

## M1 · Ningún feedback de carga en los POST de htmx, y desde el 2º resultado el popup abre vacío

**Evidencia medida.**
```
grep -rn "hx-indicator|hx-disabled-elt|htmx-request" --include=*.html  →  0 resultados en toda la app
boton Guardar: hxIndicator=None  hxDisabledElt=None  disabled=False  onclick=None
```
Además, el handler de `zonaActualizada` hace `c.innerHTML = ''` (`admin_torneo_manage.html:887`), que **destruye el esqueleto de carga** del modal. Medido:
```
con esqueleto: alto de la caja = 292px
tras innerHTML='': alto de la caja = 0px, esqueleto=False
```
O sea: el primer resultado del día abre con esqueleto; del segundo en adelante, tocar "Cargar Resultado" oscurece la pantalla y **no muestra absolutamente nada** hasta que llega la respuesta.

**Por qué le importa.** Señal de club, 3G. El organizador toca Guardar, no pasa nada visible, toca de nuevo → doble POST → doble recálculo del ranking de toda la división (hallazgo previo #6) y sensación de app colgada.

**Arreglo.** En `_form_resultado.html`, agregar al `<form>`: `hx-disabled-elt="find button[type=submit]"` y un `hx-indicator` con un spinner dentro del botón. Y en lugar de `c.innerHTML = ''`, reponer el esqueleto (guardarlo en una constante y reinyectarlo).

**Veredicto:** bug.

## M2 · El buscador es el atajo bueno, pero está enterrado, no es sticky, no abre el partido y no avisa cuando no encuentra nada

El filtro de `#adminSearchInput` filtra zonas + rondas y **autoexpande la zona** que matchea: es, de lejos, el camino más rápido al partido. Pero:

```
Escribo "Galloo":  zonasVisibles 1  zonasAbiertas 1  partidosVisibles 4  partidosAbiertos 0
                   botonResultadoVisible False (y=1413)  scrollY 0
Escribo "zzz":     zonasVisibles 0  rondasVisibles 0  hayMensajeDeNadaEncontrado False  alto 1281
Es sticky?         sticky: None   aria-label: None   label visible: False
```
- Abre la zona pero **no el partido** → siguen faltando 2 toques.
- No hace scroll al resultado: el botón queda a y=1413 con `scrollY 0`.
- Está a y=734, debajo de los tres botones destructivos, y se va de pantalla apenas scrolleás.
- Con 0 coincidencias la pantalla queda **en blanco, sin ningún mensaje**: un organizador que escribe mal un apellido cree que se rompió.

**Archivo:línea.** `torneos/templates/torneos/admin_torneo_manage.html:204-224` (el input) y `:717-790` (el filtro).

**Arreglo.** Subir el buscador arriba de todo y hacerlo `sticky top-[65px]`; si hay exactamente 1 partido visible, abrirlo y hacerle `scrollIntoView`; agregar `<p>No encontramos ninguna pareja ni zona con "X".</p>` cuando el filtro deja todo oculto; ponerle `aria-label`.

**Veredicto:** decisión mejorable (el "sin resultados en blanco" es bug).

## M3 · Targets táctiles por debajo de 40px en las acciones principales de cada pantalla

Medido a 375x812 (solo elementos visibles, sin contar drawer ni modales cerrados):

| Pantalla | Control | Tamaño | Qué hace |
|---|---|---|---|
| `/admin/2/cobros/` | select de estado de pago (**x6**) | 113x32 | **la acción principal de la pantalla** |
| `/admin/2/gestionar/` | "Eliminar pareja del torneo" (**x6**) | 34x24 | destructivo (tiene `confirm`) |
| `/admin/listado/` | "Eliminar" torneo (**x4**) | 293x24 | destructivo (va a página de confirmación) |
| `/admin/embudo/` | filtros de período (x3) | 311x24 | y no parecen botones |
| `/admin/1/gestionar/` | "Intercambiar Equipos" (x5) | 36x36 | icono sin etiqueta |
| menú lateral | las 21 entradas | 36px de alto | navegación |

`torneos/templates/torneos/admin_torneo_manage.html:413-415` (`btn btn-xs btn-ghost text-error`, con `title` pero **sin `aria-label`**).

**Por qué le importa.** Un select de 32px con el dedo en la mano que sostiene el celular es una ruleta: el organizador cobra la inscripción parado en la puerta. Y "Eliminar" de 24px a ancho completo, justo debajo de "Gestionar", es un mis-tap esperando.

**Arreglo.** `select-md` en cobros (48px); subir los `btn-xs` destructivos a `btn-sm` con `min-h-[40px]`; darles `aria-label` a los de ícono.

**Veredicto:** decisión mejorable.

## M4 · W.O. y Abandono: selects de 32px, marcador en vivo que miente y ayuda que no cambia

**Evidencia medida** (con 6-4 / 4-6 ya tipeado, cambio a Walkover):
```
Al elegir Walkover: ladoGanadorVisible=True  h=32  setsSiguenVisibles=False  marcador="1-1"  altoModal=474
Al elegir Abandono: ladoAbandonaVisible=True h=32  setsVisibles=True  altoModal=706
                    ayuda: ['Zona A', 'Dejá el set 3 vacío si el partido terminó en dos.']
```
Tres problemas:
1. `lado_ganador` / `lado_abandona` usan `select-sm` → **32px**, cuando los campos de games miden 56px y "¿Cómo terminó?" mide 48px. Los campos del caso raro y estresante son los más chicos. (`torneos/forms.py:303-307` (zona) y `:465-469` (llave))
2. Al elegir W.O. los sets se esconden pero **el contador grande sigue mostrando "1-1"**, cuando lo que se va a guardar es 2-0. El organizador ve en pantalla un marcador que contradice lo que graba. (`_form_resultado.html:148-165`: `contar()` no se re-ejecuta dentro de `verCasoEspecial()`)
3. En Abandono, el texto de ayuda sigue diciendo *"Dejá el set 3 vacío si el partido terminó en dos"* y nunca explica que hay que cargar el parcial hasta donde se jugó.

**Arreglo.** `select-md` para los dos lados; llamar `contar()` dentro de `verCasoEspecial()` y poner el marcador en 2-0/0-2 cuando el caso es W.O.; cambiar el texto de ayuda por "Cargá los games como iban cuando se retiraron" en Abandono y ocultarlo en W.O.

**Veredicto:** bug menor (el marcador) + decisión mejorable.

## M5 · El menú del organizador no tiene su Panel, y sí tiene un CTA de venta

Las 21 entradas visibles del drawer para un ORGANIZER:
```
Inicio · En Juego · Inscripciones · Buscar
Mi Organización: Ajustes · Sponsors · Horarios·PDF · Perfil Público · Mi Perfil
Administración:  Listar Torneos · Crear Torneo · Crear Jugador · Crear Pareja · Organizadores · Historial
Rankings: Jugadores · Circuitos · Americanos
"Creá tu torneo"  →  https://wa.me/5492236886313?text=Hola! Quiero organizar un torneo en TodoPadel.
```
- **No está `/torneos/admin/dashboard/`.** El panel del cliente que paga no se puede abrir desde el menú.
- **"Creá tu torneo"** (botón primario, el único de 40px) le vende el producto por WhatsApp a alguien que ya es cliente. También aparece en el pie de `/admin/2/cobros/`.
- Cobros, Embudo, Formatos, Revisar torneos y Circuitos-admin **solo existen dentro de `/accounts/perfil/`** (`accounts/templates/accounts/perfil.html:126-145`), una lista larga de botones que nada indica que sea el centro de control.
- Después de loguearse, el organizador cae en `/` (la home pública), no en su panel.

**Arreglo.** Sección "Mi club" en el menú con Panel · Cobros · Embudo · Formatos · Circuitos; ocultar el CTA de WhatsApp si `user.tipo_usuario == 'ORGANIZER'`; redirigir el login de organizadores a `torneos:dashboard`.

**Veredicto:** decisión mejorable (el CTA de venta a un cliente es un error de producto).

## M6 · "Circuitos" del menú lleva a un callejón sin salida

El menú apunta a `torneos:circuito_list` (la lista **pública**) para todos los roles (`theme/templates/base.html:1161`). Para el organizador eso es:

> **Circuitos** — Ligas que acumulan puntos a lo largo de varios torneos.
> *Todavía no hay circuitos activos.*

Sin botón, sin explicación, sin salida. El "+ Nuevo circuito" vive en `/torneos/admin/circuitos/`, que solo se linkea desde `accounts/perfil.html:140`.

**Archivo:línea.** `torneos/templates/torneos/circuito_list.html:25-29`.

**Arreglo.** En el `{% else %}` del template, si el usuario es organizador/admin, mostrar "Todavía no creaste ningún circuito" + botón a `torneos:circuito_crear`. Y que el menú apunte a `circuito_admin_list` para ORGANIZER/ADMIN.

**Veredicto:** bug de navegación.

## M7 · El resultado en games, que es el dato que se chequea, es lo menos legible de la pantalla

En `_grupo_panel.html:172-175` el score va así:
```html
<div class="text-xs text-center mt-1 text-primary font-bold">
    Resultado: {{ partido.e1_sets_ganados }}-{{ partido.e2_sets_ganados }}
    <span class="opacity-70 font-normal">({{ partido.resultado }})</span>
</div>
```
Medido en modo claro: el `(6-1 4-6 6-4)` queda a **1.71:1 a 12px**, y aparece **12 veces** en la pantalla — es el patrón que más se repite entre las 53 fallas de contraste de `/gestionar/`.

**Por qué le importa.** Cuando el organizador vuelve a mirar un partido ya cargado es para verificar el score, no el 2-1 de sets. El dato que va a chequear está en el texto más chico y más lavado.

**Arreglo.** Sacar `opacity-70` del span y subirlo a `text-sm`; dejar `text-primary` solo en el marcador de sets y el detalle en `text-base-content/80`.

**Veredicto:** bug de contraste.

## M8 · "Cancelar" con el mismo peso visual que "Guardar resultado", a 52px, sin red

Medido: "Guardar resultado" 304x44 en y=642, "Cancelar" 304x44 en y=694. Mismo ancho, misma altura, separación de 8px. `Cancelar` llama `resultado_modal.close()` directo: **se pierde todo lo tipeado sin preguntar**.

**Archivo:línea.** `torneos/templates/torneos/partials/_form_resultado.html:131-134`.

**Arreglo.** Achicar "Cancelar" (`btn-sm`, ancho automático, centrado) y separarlo más; o reemplazarlo por la X del encabezado, que ya existe y hace lo mismo.

**Veredicto:** decisión mejorable.

## M9 · "Avanzar Clasificados" es un ícono de 42px sin etiqueta, dentro del área que se toca para abrir la zona

Medido en la cabecera de Zona A:
```
cabecera: 307x72 (el checkbox del colapso cubre los 307x72 enteros)
botones encima: "Avanzar Clasificados" 42x40 en x=199 (enabled)  +  "Intercambiar Equipos" 36x36 en x=249
```
La etiqueta es `hidden md:inline` (`_grupo_panel.html:49`), así que en mobile es un ícono mudo con `tooltip` (que en touch no existe). Ocupa 78 de los 307px de la fila que hay que tocar para abrir la zona.

Tiene `confirm()`, así que es recuperable. Pero es el único control de la zona que no se entiende sin pasar el mouse.

**Arreglo.** En mobile, sacar los dos botones de la cabecera y ponerlos dentro del `collapse-content`, al lado de la tabla de posiciones, con su texto completo.

**Veredicto:** decisión mejorable.

---

# BAJO

## B1 · Selects con el `---------` por defecto de Django

Confirmado en 3 pantallas del organizador:
```
/accounts/organizador/crear-jugador-dummy/   division: '---------'
/equipos/organizador/crear-pareja/           jugador1, jugador2, division: '---------'
/accounts/organizacion/ajustes/              receptor_notificaciones: '---------'
```
En la misma pantalla, "Género" sí tiene "Seleccioná el género". Para un usuario poco técnico, nueve guiones no dicen nada.
**Arreglo.** `empty_label="Elegí la división"` / `"Elegí al jugador"` / `"Elegí quién recibe los avisos"`.

## B2 · Los nombres de pareja se cortan a mitad de palabra en el popup

Captura `g4_popup_claro.png`: "Barrionuevo/Sos" + "a" en la línea siguiente. La columna del nombre mide ~120px con `break-words` (`_form_resultado.html:59-72`).
**Arreglo.** `hyphens: auto` + `text-balance`, o mostrar el código corto de pareja arriba y el nombre completo abajo en una línea a ancho completo.

## B3 · Textos por debajo de 11px

- "SET 1 / SET 2 / SET 3" en el popup: **10px** (son la única referencia de qué fila es cuál).
- "Organizado por" en el listado: 10px, x4.
- "Formatos recomendados: PNG, JPG..." en ajustes: 10px a 2.5:1.

## B4 · Aire muerto y ruido en la parte de arriba de todas las pantallas

La navbar fija termina en y=65 y el primer título real aparece en y=217–239: **~174px (21% de la primera pantalla)** ocupados solo por un "← Volver". Pasa en las 10 pantallas medidas.
En `/admin/listado/`, encima, el encabezado decorativo "Gestión de Torneos / Administra y supervisa todos tus torneos activos" se come ~400px, y después **cada tarjeta mide 395px (media pantalla)** y arranca con una banda que repite el logo y el nombre **del propio club del organizador** — un dato que ya sabe, cuatro veces seguidas.

## B5 · El toast de confirmación aparece arriba mientras el pulgar y los ojos están abajo

Medido: con `scrollY 1167` el toast sigue visible (está fijo) en `top: 16`, pero a ~1100px de donde el organizador está mirando. Funciona, pero el refuerzo llega lejos del lugar de la acción. Combinado con A1 (el panel colapsa justo debajo), el feedback aparece arriba y el contexto desaparece abajo.

## B6 · `badge-success` "Inscripción Abierta" a 2.18:1 en los dos temas

fg(243,251,246) sobre bg(0,195,135). Es el badge que marca qué torneos aceptan inscripciones en el dashboard y el listado.

---

# Lo que está bien (y conviene no tocar)

1. **El popup de resultado es lo mejor diseñado del flujo.** Campos de **120x56px con fuente de 24px**, `type="number"` + `inputmode="numeric"` (abre el teclado numérico), `min/max`, `aria-label` individual por campo ("Games de Galloo/Perez en el set 1") y un **contador de sets en vivo que pinta de verde al que va ganando**. Para una app de club amateur eso está muy por encima del promedio. Los problemas de A2/A5/M4/M8 son del borde, no del núcleo.
2. **El refresco parcial por htmx está bien pensado.** Guardar devuelve 12,4 KB (el panel de la zona) en lugar de recargar los 178 KB. Solo le falta A1.
3. **Hay confirmación de guardado.** El toast "✓ Guardado en Zona A" existe, dice en qué zona, y se ve esté donde esté el scroll. Muchas apps de este tipo no tienen nada.
4. **Cero scroll horizontal** en las 15 pantallas medidas, en los dos temas. El trabajo previo de mobile se nota.
5. **El estado vacío de Formatos es un buen ejemplo**: explica para qué sirve, tiene CTA y está escrito en rioplatense ("Guardá tu propia estructura de zonas... y reusala"). Sirve de molde para arreglar el de Circuitos (M6).
6. **El hallazgo previo #3 está arreglado**: "Crear jugador" y "Crear pareja" ya no tienen título ni labels invisibles en modo claro.
7. **El microcopy en general es bueno** ("Dónde se cae la gente en el camino a anotarse a un torneo", "Este torneo no tiene precio cargado, así que no se puede calcular cuánto falta"). El tono rioplatense es consistente.
8. **El embudo y los cobros** tienen la información correcta y bien jerarquizada; sus problemas son de contraste y de tamaño de control, no de contenido.

---

# Orden sugerido de ataque

| # | Hallazgo | Costo | Impacto diario |
|---|---|---|---|
| 1 | **A1** zona que se cierra al guardar | 2 líneas de JS | ×22 por torneo |
| 2 | **A3** `btn-primary` a 2.54:1 en modo claro | 1 línea de CSS | toda la app |
| 3 | **A2** resultados sin ganador que dicen "Guardado" | 1 validación + 1 `disabled` | datos corruptos silenciosos |
| 4 | **A6** 0/9 partidos en el panel | 4 líneas de vista + test | confianza del cliente |
| 5 | **A5** Guardar fuera de vista con el teclado | `sticky bottom-0` | ×22 por torneo |
| 6 | **A4** jerarquía invertida + 1.66:1 en los destructivos | mover bloque + sacar `text-white` | riesgo de pérdida de datos |
| 7 | **M1** sin spinner ni bloqueo de doble envío | 2 atributos htmx | señal de club |
| 8 | **M3** targets de 24–32px en cobros y borrados | cambio de clases | precisión al borde de la cancha |
