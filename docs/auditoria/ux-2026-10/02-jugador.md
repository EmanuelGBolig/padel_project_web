# Auditoría de producto — flujo del jugador

**Fecha:** 2026-10-09 · **Dispositivo medido:** 375×812, `is_mobile`, DPR 2 · **Temas:** `corporate` (claro, por defecto) y `business` (oscuro) · **Cuenta:** `jugador1a@ejemplo.com` (PLAYER, sin foto, sin pareja — el estado de cualquier recién llegado).

**Método:** Playwright contra `http://localhost:8010`, sin escribir en la base. Contraste medido pintando el color en un `<canvas>` de 1px y leyendo el RGB resuelto (oklch no se puede parsear con regex), componiendo la pila de fondos semitransparentes hasta `<html>`. Scripts y capturas en el scratchpad (`medir_jugador.py`, `contraste2.py`, `recorrido.py`, `probe*.py`, `shots/`).

**No repito** los 36 hallazgos de `docs/auditoria/hallazgos.json` ni lo que ya encontraste vos (banner de instalar, 3 botones de la cabecera, "Ver en vivo" en rojo, 25% del cuadro visible, 123 KB / 16 queries de la ficha). Donde profundizo sobre algo tuyo lo aclaro.

---

## El recorrido real, cronometrado

Jugador logueado, celular, quiere saber **cuándo juega y cómo va su zona**. Estado por defecto (banners de onboarding visibles, que es lo que ve todo el mundo la primera vez y después de cada sesión nueva):

| Paso | Dónde queda | Costo |
|---|---|---|
| Home `/` | tarjeta del torneo en juego a y≈1.091 | 3,7 pantallas de alto; ~1.030 px de scroll |
| Ficha `/torneos/1/` | el nombre del torneo (`h1`) a **y=701 de 812** | **86 % de la primera pantalla antes del título** |
| Ver la zona | acordeón "Zonas" cerrado a y=1.084 | scroll 272 px + **1 toque** |
| Leer la tabla | primera fila a y=1.268 (con el acordeón abierto) | ~1.100 px de scroll acumulado |
| Ver mis horarios | `Más opciones` → `🗓️ Horarios · descargar PDF` | **2 toques dentro de un menú genérico** |
| Encontrar *mi* partido en la programación | 20 filas, nombres de 4 renglones, sin filtro ni búsqueda | página de **3.428 px** (4,2 pantallas) a escanear a ojo |
| Ver el cuadro | scroll horizontal, 24,5 % visible (1.328 px en 325) | ya reportado por vos |

Con los banners descartados mejora bastante (h1 a y=393, Zonas a y=776), pero el descarte dura **una sesión**: se guarda en `sessionStorage`.

---

# ALTO

## A1 · Los dos banners de onboarding se apilan en columna por una regla global y se comen 308 px de TODAS las páginas

**Archivo:** `theme/static_src/src/styles.css:22-33` (causa) · `theme/templates/base.html:766-797` (síntoma)

**Medido:** cada banner **150 px de alto**, el par con separación **308 px** = **37,9 % de la primera pantalla**, en abiertos, en-juego, finalizados, la ficha, vivo, programación, perfil, rankings, mis-torneos, buscar-compañero y la home. `getComputedStyle` del banner: `display:flex`, `flex-direction:**column**`, hijos apilados en `x=33` cada uno (emoji 309×28, texto 309×20, botón 309×**24**, ✕ 24×24).

**Causa raíz, verificada por experimento:** la regla global que apila las barras de acciones en mobile

```css
@media (max-width: 639px) {
    .flex:not(.join):not(.dropdown-content):has(> .btn + .btn) {
        flex-direction: column; align-items: stretch;
    }
}
```

matchea cualquier `.flex` con dos `.btn` hermanos. El banner es `class="alert ... flex items-center gap-3"` y sus dos últimos hijos son `<a class="btn btn-primary btn-xs">` + `<button class="btn btn-ghost btn-xs btn-circle">`: hermanos adyacentes → matchea. **Prueba causal:** removiendo el segundo `.btn` por JS, el mismo nodo pasa de `column` / **150 px** a `row` / **46 px**. El autor del banner escribió `flex items-center` esperando una fila; el CSS global se la dio vuelta en silencio.

**Por qué importa:** el jugador entra a ver su torneo y lo primero que recibe son dos avisos que no pidió, ocupando más de un tercio de la pantalla, en cada página. Y el `btn-xs` queda como una píldora de **309×24 px** (ancho completo pero 24 px de alto), una forma rarísima y difícil de pegarle.

**Arreglo (una línea):** excluir los alerts del selector —

```css
.flex:not(.join):not(.dropdown-content):not(.alert):has(> .btn + .btn) { … }
```

y revisar si hay otros `.alert`/`.card` que la regla esté torciendo. Ahorro medido: **208 px** de primera pantalla en todas las páginas de la app.

**Dos agravantes del mismo bloque:**
- El descarte usa `sessionStorage` (`base.html:809`), mientras que el banner de instalar usa `localStorage` (`base.html:761`). El aviso más molesto es el que se olvida: vuelve en cada sesión nueva de la PWA.
- La explicación ("Tu foto aparece en los rankings y torneos.", "Necesitás una pareja para inscribirte en torneos.") es `hidden sm:inline` (`base.html:775` y `789`): está escondida **exactamente en mobile**, que es donde se usa la app. El jugador lee "¡Formá tu pareja!" sin que nada le diga para qué.

---

## A2 · Blanco sobre el verde primario da 2,54:1 — falla AA en TODOS los botones del modo claro, que es el tema por defecto

**Archivos:** `theme/templates/base.html:112-120` y `:128-130` · `:92-104` (variables del tema)

**Medido (canvas, no regex):** `#10B981` tiene luminancia relativa 0,364 → contra blanco puro da **2,54:1**. WCAG AA pide 4,5:1. Inyecté un botón de cada variante en cada tema y medí el color resuelto:

| Variante | claro (`corporate`, **por defecto**) | oscuro (`business`) |
|---|---|---|
| `btn-primary` | blanco s/ #10B981 → **2,54** ✗ | #1a1a1a s/ #10B981 → **6,86** ✓ |
| `btn-success` | **2,54** ✗ | **6,86** ✓ |
| `btn-secondary` | **2,54** ✗ | **2,54** ✗ |
| `btn-info` | **2,54** ✗ | **2,54** ✗ |
| `btn-accent` | **2,54** ✗ | **2,54** ✗ |
| `btn-error` | 6,82 ✓ | 6,82 ✓ |
| `btn-warning` | 12,62 ✓ | 12,62 ✓ |

**Lo interesante: el modo oscuro ya está bien resuelto y el claro no.** `base.html:117-119` fuerza `color:#1a1a1a` para `.btn-primary`/`.btn-success` **sólo** bajo `[data-theme="business"]`; el claro se queda con el `color: white !important` de la línea 115. Es justo el agujero que describe `CLAUDE.md`: *"el modo claro es el tema por defecto, y casi nunca se prueba"*. Y `base.html:128-130` pisa `color:#fff !important` para secondary/accent/info **fuera de todo selector de tema**, así que esos tres fallan en los dos.

Botones concretos que lo sufren en el recorrido del jugador, todos a 2,54: `Filtrar` (abiertos, en-juego), `Ver e Inscribirse`, `Anotarme con mi pareja`, `Ver llaves y resultados`, `Descargar PDF`, `Publicar mi búsqueda`, `Compartir`, `📲 Instalar la app`, `Ver Resultados`. Más la inicial `J` del avatar del navbar (2,41) y el badge de horario del cuadro `09/08 09:00` (2,18).

**Y lo mismo sobre los datos**, que es lo grave: en la tabla de posiciones los **puestos que clasifican** se pintan con ese verde sobre fondo claro —

- `/torneos/1/vivo/` (`torneo_vivo.html:48`): `font-bold text-primary` en las filas 1 y 2 → **2,07:1** sobre la fila cebrada y **2,54:1** sobre la blanca.
- `/torneos/1/` (`torneo_detail.html:657`): `text-success font-bold bg-success/5` para las mismas filas.

O sea: las dos filas que al jugador más le importan son las menos legibles de la tabla, y se usa un código de color distinto para lo mismo en dos pantallas de la misma app.

**Por qué importa:** este público mira la app **al borde de la cancha, al sol, con el brillo peleando**. 2,5:1 en un botón verde con texto blanco es justo lo que se borra con reflejo. Y contradice la convención del propio `CLAUDE.md` ("el blanco fijo va únicamente sobre fondos de color sólido (`btn-primary`)"): el fondo es sólido, pero igual no alcanza.

**Arreglo, dos opciones concretas:**
1. **El más barato, y es copiar lo que el oscuro ya hace:** sacar el `[data-theme="business"]` de `base.html:117` para que `color:#1a1a1a` aplique en los dos temas, y hacer lo mismo con secondary/accent/info de la línea 129 (`color:#1a1a1a` en vez de `#fff`). Medido: 6,86:1 ✓. Un verde esmeralda con texto casi negro es además lo que hacen Spotify, Robinhood y el propio DaisyUI por defecto; no se pierde identidad de marca.
2. Si se quiere conservar el texto blanco: oscurecer el fondo a **`#047857`** (emerald-700) → **5,48:1** ✓. Ojo que `#059669`, que ya se usa en el `:hover` de la línea 122, sólo llega a **3,77** — no alcanza.

Para las filas que clasifican, no codificar con color solo: un fondo `bg-success/15` + un ícono o la palabra "Clasifica" en texto `base-content`.

---

## A3 · La pantalla que más busca el jugador (los horarios) está a dos toques dentro de un menú llamado "Más opciones", y una vez adentro no puede encontrar su partido

**Archivos:** `torneos/templates/torneos/torneo_detail.html:122` · `torneos/templates/torneos/torneo_programacion.html:56-92`

**Medido:** el único acceso a `/torneos/<id>/programacion/` desde la ficha es
`<li><a …>🗓️ Horarios · descargar PDF</a></li>`, el 1.º o 3.º ítem de un dropdown rotulado **"Más opciones"**. No hay ningún otro enlace a la programación en toda la app para un jugador (`grep` sobre todos los templates: 2 apariciones, una es la vista de administración).

Dentro de la programación: tabla de **20 partidos** en una página de **3.428 px**, columnas `Hora | Zona/Fase | Pareja | Pareja`, nombres completos que ocupan 3-4 renglones cada uno ("Andres Aquindo / Ricky Las Heras"). **Sin búsqueda, sin filtro por zona, sin resaltado del partido propio, y sin "vs"**: dos columnas rotuladas igual, "Pareja" y "Pareja", y el lector tiene que inferir que son rivales.

**Por qué importa:** "¿cuándo y contra quién juego?" es el trabajo número uno de este producto y es la ruta peor señalizada que tiene. El rótulo además promete un PDF, no una pantalla: "Horarios · descargar PDF" se lee como una acción de descarga, así que el que quiere mirar el horario ni lo abre.

**Arreglo:**
1. Subir "🗓️ Horarios" a acción primaria de la ficha cuando el torneo está `EJ` (junto a "Ver en vivo"), y renombrarlo a **"Horarios"**; el PDF que quede como botón dentro de esa pantalla (ya está).
2. En la programación, si el usuario está inscripto, un bloque fijo arriba: **"Tu próximo partido: Sáb 8, 13:00 · Zona A · vs Barrionuevo/Sosa"** — el view ya calcula `mis_partidos_pendientes` en `torneos/views.py:2085-2131`, solo hay que pasarlo acá.
3. Un campo de búsqueda que filtre filas por nombre (puro JS sobre la tabla, sin backend), y resaltar las filas del equipo propio.
4. Cambiar los dos `<th>Pareja</th>` por `Pareja` / `Rival` o meter una columna `vs`.

---

## A4 · "Zonas" arranca colapsado y "Cuadro Final" arranca abierto, siempre, sin mirar el estado del torneo

**Archivo:** `torneos/templates/torneos/torneo_detail.html:623` (Zonas, `<details>` sin `open`) vs `:724-725` (Cuadro Final, `<details … open>`)

**Medido** en `/torneos/1/`, con banners: el resumen "Zonas" cae en y=**1.084** (272 px por debajo del pliegue), cerrado. Abrirlo cuesta 1 toque y deja la primera fila de la tabla en y=**1.268**; la página pasa de 1.817 a 3.769 px. El Cuadro Final, en cambio, está abierto por defecto en y=1.206 y muestra 2 partidos sin resultado.

**Por qué importa:** la tabla de posiciones y los partidos de zona (con día, hora y cancha) son lo que el jugador va a buscar durante toda la fase de grupos, que es la mayor parte del torneo. Están cerrados y fuera de pantalla. El cuadro, que durante la fase de grupos está lleno de placeholders, está abierto. Peor: si el torneo está en zonas y todavía no hay llave, el bloque abierto no existe y la ficha no muestra **nada** de contenido útil sin un toque.

**Arreglo:** decidir el `open` por estado, no por template fijo —

```django
<details class="collapse collapse-arrow …" {% if not fase_eliminatoria_existente %}open{% endif %}>  {# Zonas #}
<details … {% if fase_eliminatoria_existente %}open{% endif %}>                                      {# Cuadro #}
```

y, si el usuario está inscripto, abrir siempre la zona en la que juega y hacerle scroll con `#zona-X`.

---

## A5 · Todo mensaje del sistema de más de ~45 caracteres se corta por los DOS costados y queda ilegible

**Archivo:** `theme/templates/base.html:723-727`

**Medido** en `/equipos/mi-equipo/` sin pareja, que dispara dos mensajes:

| Mensaje | chars | `display` | columna del grid | `clientWidth` | `scrollWidth` | caja del `<span>` |
|---|---|---|---|---|---|---|
| "Aún no tienes un equipo. ¡Crea uno!" | 35 | `grid` | 273,5 px | 306 | 306 | x 68 → 307 ✓ |
| "Debes tener una división asignada para crear un equipo. Edita tu perfil" | 72 | `grid` | 273,5 px | 306 | **390** | x **−49 → 424** ✗ |

El segundo `<span>` arranca **49 px fuera del borde izquierdo** de una pantalla de 375 y termina **49 px fuera del derecho**: se pierden las primeras y las últimas palabras. En la captura se lee literalmente *"tener una división asignada para crear un equipo. Edita tu"*.

**Causa raíz:** es exactamente la trampa que `CLAUDE.md` documenta para `.collapse`, pero en `.alert`. El CSS compilado define

```css
.alert{display:grid;grid-auto-flow:row;justify-items:center;…}
@media (min-width:640px){.alert{grid-auto-flow:column;grid-template-columns:auto minmax(auto,1fr)}}
```

Por debajo de 640 px el `.alert` es un grid de **una columna `auto`**, que se dimensiona al contenido y no lo deja envolver. El `style="…flex-wrap:wrap…"` inline y el `flex:1; min-width:0` del `<span>` **no hacen nada dentro de un grid**. Y como `justify-items:center`, el desborde sale simétrico por los dos lados.

**Por qué importa:** son los mensajes de error y confirmación de toda la app (inscripción, pagos, invitaciones, fusiones). El jugador recibe un cartel rojo que no puede leer y no tiene forma de saber qué hacer.

**Arreglo (una propiedad):** en el `style` del `.alert` de `base.html:725` agregar

```css
display: grid; grid-template-columns: minmax(0, 1fr) auto; justify-items: stretch; text-align: left;
```

(o directamente `display:flex` en el alert, no en el contenedor). Mismo remedio que ya está documentado para `.collapse`: fijar la columna en `minmax(0, …)`.

---

## A6 · La ficha del torneo nunca muestra la fecha

**Archivo:** `torneos/templates/torneos/torneo_detail.html:180` (único renderizado visible de `fecha_inicio`)

**Medido** leyendo el `innerText` de `<main>` en las tres fichas:

| Torneo | Estado | Fechas visibles en la página |
|---|---|---|
| 2 ABIERTO AL PUBLICO | AB | `Arranca en 2 semanas` — y nada más |
| 1 6TA CABALLEROS | EJ | ninguna del torneo; sólo los `09/08 09:00` de cada partido, y recién al abrir el acordeón |
| 4 TORNEO DE VERANO | FN | **ninguna** |

`fecha_inicio` sí se renderiza con formato absoluto en el `<meta name="description">` (`:28`), en el JSON-LD (`:38`) y en las etiquetas Open Graph (`:64-65`). Google sabe el día del torneo; el jugador parado en la ficha, no. `fecha_limite_inscripcion` (hasta cuándo se puede anotar) no aparece **en ningún lado** de la ficha.

Los cupos tampoco: `torneo_detail.html:177` sólo los muestra si quedan **5 o menos** (`¡Últimos N cupos!`). En el listado la tarjeta sí dice "6 / 16". La ficha, que es la página de detalle, muestra **menos** información que la tarjeta que llevó hasta ella.

**Por qué importa:** "Arranca en 2 semanas" no se puede anotar en la agenda, ni mandar por WhatsApp, ni comparar con otro torneo. Es la decisión de inscripción entera.

**Arreglo:** bajo el `h1`, una línea de datos duros siempre presente:
`📅 Sáb 24 Oct 2026 · 📍 <sede o ciudad> · 💲 <precio> · 👥 6/16 anotados · ⏳ Anotate hasta el 22/10`
con cada ítem condicionado a que el campo exista. Y en `EJ`/`FN`, la fecha del torneo igual.

---

# MEDIO

## M1 · PG / DS / DG sin ninguna leyenda, y la versión críptica le toca justo a mobile

**Archivos:** `torneos/templates/torneos/torneo_detail.html:652-655` · `torneos/templates/torneos/torneo_vivo.html:35-45`

**Medido:** en la ficha los encabezados son `Equipo | PG | DS | DG`, **sin `title`, sin leyenda, sin nota al pie** (verificado leyendo los atributos de cada `<th>` en runtime: `title: null` en las cinco zonas). En `/vivo/` sí hay `title="Diferencia de sets"`, pero los `title` no existen en touch; y el texto largo está puesto al revés:

```django
<span class="sm:hidden">DS</span><span class="hidden sm:inline">Dif. Sets</span>
```

mobile → "DS"; desktop → "Dif. Sets". La app se usa casi toda desde el celular y es el celular el que recibe la abreviatura.

Falta además **PJ** (partidos jugados) y cualquier noción de puntos, así que un jugador no puede verificar su propia posición: ve `PG 0 · DS -1 · DG -3` y no sabe si jugó uno o tres partidos. Y nada dice que **pasan los dos primeros** — está codificado sólo con color (ver A2).

**Arreglo:** encabezados en palabras, que entran: `Pareja | PJ | PG | Sets | Games`. Y un renglón de leyenda debajo de cada zona, en `text-xs text-base-content/70`:
*"PJ: jugados · PG: ganados · Sets/Games: diferencia a favor. Pasan los 2 primeros."*
Nada de `title`.

## M2 · `/torneos/mis-torneos/` desborda la pantalla y las pestañas se rompen

**Archivo:** `torneos/templates/torneos/mis_torneos.html:37-45`

**Medido:** `document.documentElement.scrollWidth = 383` con `clientWidth = 375` → la página **scrollea a lo ancho 8 px**, en los dos temas. Es `div.tabs.tabs-lifted.tabs-lg` con tres botones cuyos rótulos incluyen el contador: "En Juego (0)" se parte en **tres renglones** ("En" / "Juego" / "(0)") y "Historial (0)" queda cortado contra el borde derecho (ver `shots/mis-torneos-corporate-full.png`).

Además, la pestaña activa por defecto cuando el jugador no tiene nada es "En Juego", cuyo estado vacío dice *"¡Revisá las inscripciones abiertas para sumarte a uno!"* **sin ningún botón** (`:70-74`). El panel de al lado sí tiene su CTA ("Ver Torneos Disponibles", `:101`). El callejón sin salida le toca justo al caso más común.

**Arreglo:** `tabs-sm` en mobile y rótulos cortos con el contador como badge (`En juego ·0`), o `grid grid-cols-3 text-xs sm:text-base` con `truncate`. Y copiar el `<a class="btn btn-primary">Ver Torneos Disponibles</a>` al estado vacío de "En Juego". (Typo de paso: "algun torneo" → "algún", `:129`.)

## M3 · Modo oscuro: el panel "Sistema de Puntuación" del ranking es negro sobre negro

**Archivo:** `accounts/templates/accounts/ranking_jugadores_list.html:226-243`

**Medido:** `class="alert bg-info/10 … text-info-content"`. `getComputedStyle().color` devuelve `oklch(0 0 0)` — negro puro — en **los dos temas**, sobre un fondo compuesto de `rgb(24,45,45)` en oscuro → **1,45:1** (mínimo 4,5). Confirmado visualmente en `shots/rankings-business-full.png`: el bloque con los 600/360/180/90/45/15 puntos es un rectángulo verde oscuro casi vacío.

Es la misma familia que el hallazgo #3 (`text-white` sobre tarjeta blanca) pero en espejo: `*-content` está pensado para ir sobre el color **sólido** (`bg-info`), no sobre `bg-info/10`.

**Arreglo:** `text-base-content` en lugar de `text-info-content` (se adapta solo a los dos temas), o `bg-info text-info-content` a secas. Vale revisar con un grep si hay más `bg-*/10` combinados con `text-*-content`.

## M4 · `/equipos/mi-equipo/` sin pareja: redirección con dos carteles, uno ilegible, y un callejón sin salida

**Archivo:** `equipos/views.py:165-176`

**Medido:** el jugador sin pareja que toca "Mi equipo" es redirigido y recibe dos `messages` encimados; el segundo es el que desborda (ver A5). El mensaje pide *"una división asignada"* y manda a "Edita tu perfil", pero no lleva ahí: hay que descartar el toast, encontrar el perfil y buscar el campo.

**Arreglo:** reemplazar los dos toasts por un estado vacío en la propia pantalla, con el motivo y el botón: "Todavía no tenés pareja. Para armarla necesitás elegir tu división." + `[Elegir mi división]` apuntando al form. De paso, los textos están en "tú" ("tienes", "Edita tu"), misma inconsistencia del hallazgo #31 pero originada en las vistas, no en `base.html`.

## M5 · Los listados ponen el filtro antes que los resultados y la primera tarjeta queda fuera del pliegue

**Archivos:** `torneos/templates/torneos/torneo_abierto_list.html:84` · `torneo_en_juego_list.html:38` (`_filtros_torneos.html`)

**Medido:** en `/torneos/en-juego/` con **2 torneos en la lista**, el orden es: banners (308) → "Volver" → título a dos renglones (y=540) → formulario Ciudad/División/Categoría + botón Filtrar (≈250 px) → **primera tarjeta a y=905**, fuera de los 812. En `/torneos/abiertos/`, a y=875.

**Por qué importa:** con dos resultados, el filtro es puro costo. El jugador abre "Torneos en juego" y ve un formulario donde esperaba ver su torneo.

**Arreglo:** colapsar los filtros en mobile detrás de un `<details>` "Filtrar" de una línea, o renderizarlos sólo si hay más de N torneos (`{% if torneos|length > 4 %}`).

## M6 · En la lista de partidos de la zona no se ve quién ganó

**Archivo:** `torneos/templates/torneos/torneo_detail.html:702-710`

El resultado se pinta **siempre** `text-success` (verde, gane o pierda) y ninguno de los dos nombres cambia según el ganador — el único resaltado es `text-primary` cuando el equipo es el tuyo. El separador del marcador es `<span class="opacity-50 text-[9px]">=</span>`: un "=" de **9 px al 50 % de opacidad**. Los nombres van en `text-[10px] sm:text-xs` y el bloque entero en `text-[10px]`.

Resultado práctico: se lee *"Galloo/Perez vs Barrionuevo/Sosa = 6-1 4-6 6-4"* y hay que deducir de qué lado va cada número. En el cuadro sí se marca al ganador (`bracket_match_content.html:8`); en las zonas no.

**Arreglo:** poner el ganador en `font-bold` y el perdedor en `text-base-content/60`, subir el cuerpo a 12 px mínimo, y cambiar el "=" por un separador legible o nada.

## M7 · Una división sin jugadores en el ranking renderiza una tabla con encabezados y vacío abajo

**Archivo:** `accounts/templates/accounts/ranking_jugadores_list.html:135-204`

El `{% for item in division_ranking.jugadores %}` **no tiene `{% empty %}`**; el `{% empty %}` de la línea 209 pertenece al loop externo sobre divisiones. Con la división "Sexta" existente pero sin jugadores puntuados, la página muestra el chip "Sexta", la cabecera `Pos | Jugador | Puntos` y nada debajo (confirmado en `shots/rankings-business-full.png`).

**Arreglo:** `{% empty %}<tr><td colspan="5" class="text-center py-8 text-base-content/60">Todavía no hay puntos cargados en esta división.</td></tr>`.

## M8 · En el torneo abierto, "Compartir" pesa visualmente lo mismo que "Anotarme" y le gana el lugar

**Archivo:** `torneos/templates/torneos/torneo_detail.html:135` (barra de acciones) vs `:392-402` (CTA)

**Medido** en `/torneos/2/`: `Compartir` es un `btn-primary` **sólido verde a ancho completo** en y=556, dentro de la primera pantalla. El CTA real, `Anotarme con mi pareja`, queda en y=**913** — fuera de los 812. El jugador que entra a anotarse ve un botón verde grande que dice "Compartir".

Esto se solapa con tu hallazgo de los tres botones, pero el punto acá no es el espacio sino la **jerarquía**: hay dos botones primarios sólidos compitiendo y el que gana la posición es el secundario.

**Arreglo:** `Compartir` como `btn-ghost` o ícono solo; dejar el sólido verde reservado para la acción del estado (Anotarme / Ver en vivo).

---

# BAJO

## B1 · Objetivos táctiles por debajo de 44 px
Medido en todas las pantallas: campana de notificaciones **36×36**, avatar del menú **38×48**, `Subir foto` y `Crear pareja` **309×24**, los dos `✕` de descarte **24×24**, y en el perfil los enlaces `Subir →` 46×16, `Crear →` 47×16, `Editar →` 49×16, `Agregar →` 62×16, más el lápiz de la foto **32×32**. El mínimo de Apple es 44×44 y el de Material 48×48. Para un público que opera la app parado, con la mano con la que no sostiene la paleta, los de 16 px de alto son directamente inalcanzables. *Arreglo:* `min-height: 2.75rem` + `py-2` en esos enlaces, `btn-sm` en vez de `btn-xs` en los banners, y `btn-circle btn-sm` (40 px) para campana y ✕.

## B2 · La explicación está escondida justo en mobile
Mismo patrón en tres lugares: `base.html:775` y `:789` (`hidden sm:inline` del texto de los banners) y `torneo_vivo.html:39,42` (`DS` en mobile / `Dif. Sets` en desktop). La app se usa en el celular; el que se queda sin la explicación es el usuario real.

## B3 · La "placa del resultado" del cuadro es inalcanzable en celular
`torneos/templates/torneos/partials/bracket_match_content.html:48-50`: el enlace es `class="… opacity-0 hover:opacity-100 group-hover:opacity-60"` y la tarjeta padre **no tiene la clase `group`**, así que `group-hover` no dispara nunca; y `hover` no existe en touch. Es un target de 10 px con opacidad 0. La función existe sólo para mouse. *Arreglo:* mostrarlo siempre a `opacity-60` con tamaño de toque real, o moverlo a un menú del partido.

## B4 · `/vivo/` se recarga entera cada 20 segundos
`torneos/templates/torneos/torneo_vivo.html:106`: `setTimeout(() => location.reload(), 20000)`. **Verifiqué que el scroll SÍ se conserva** (scrollY 1.984 antes y después), así que no rompe la lectura — descarto esa hipótesis. Lo que queda es el costo: 88 KB de HTML más los assets cada 20 s en una vista pensada para TV pero enlazada desde el botón principal de la ficha, en el celular de un jugador con datos móviles en un club. Tampoco hay un "actualizado hace X" (sólo `Esta pantalla se actualiza automáticamente.` en `text-xs opacity-40`). *Arreglo:* si viene de un celular, subir el intervalo a 60 s o refrescar sólo el fragmento de las tablas por `fetch`, y mostrar la hora de la última actualización.

## B5 · Microcopy
- `torneo_en_juego_list.html:74`: el CTA de un torneo en juego dice **"Ver Resultados"**, cuando lo que el jugador va a buscar ahí es cuándo juega. Mejor "Ver el torneo" o "Zonas y horarios".
- `torneo_detail.html:122`: "🗓️ Horarios · descargar PDF" se lee como descarga (ver A3).
- `torneo_detail.html:579`: "Equipos Anotados" arranca colapsado también en un torneo **abierto**, donde ver quiénes se anotaron es prueba social para decidir.
- `mis_torneos.html:129`: "algun" sin tilde.

## B6 · El marcador del cuadro va en 10 px al 70 % de opacidad
`bracket_match_content.html:39`: `text-[10px] font-mono opacity-70`, posicionado absoluto contra el borde derecho de una tarjeta de 260 px. En la semilla no hay resultados cargados en la llave, así que no pude medirlo renderizado — lo reporto a nivel de código, no como desborde confirmado.

---

# Lo que está bien resuelto (y no hay que tocar)

- **Los estados vacíos de `/torneos/abiertos/`** (`:129-135`) usan `partials/empty_state.html` con título, explicación **y botón** diferenciados por caso ("Ningún torneo coincide" → Limpiar filtros; "No hay otros torneos" → Ver historial). Es el patrón correcto; el problema es que no se aplicó en `mis_torneos` (M2).
- **"Mis Inscripciones" arriba en `/torneos/abiertos/`** (`:49`): lo propio antes que el catálogo. Bien.
- **La planilla de horarios como `<table>`** y no como filas flex: la decisión está documentada en el template y es la correcta.
- **El scroll horizontal del cuadro es intencional y funciona** (1.328 px en 325 visibles); lo verifiqué, no es un desborde. Lo único que falta es la pista visual que ya detectaste.
- **El CTA de anotarse para el usuario sin cuenta está arriba de todo**, justo bajo el título, con la explicación "No necesitás tener cuenta: te la creamos al anotarte" (`:190-212`). Es el mejor momento de toda la auditoría.
- **La regla global que apila las barras de acciones en mobile** (`styles.css:22`) es una buena idea bien documentada: el problema es el alcance del selector, no la intención.
- **El `h1` de la ficha usa `text-base-content`**, no `text-white`: el bug del modo claro no se repitió acá.
- **Ninguna de las 13 pantallas medidas tiene desborde horizontal**, salvo `mis-torneos` (M2) y el toast (A5).
