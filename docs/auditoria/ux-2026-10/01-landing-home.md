# Auditoría de diseño — Home (`/`) y landing comercial (`/para-organizadores/`)

Fecha: 2026-10-09 · Medido con Playwright a **375×812**, UA de Android, `color_scheme` claro
y oscuro, caché frío. Capturas en `./shots/`. Scripts de medición en esta misma carpeta
(`cap.py`, `contraste_real.py`, `medir_landing.py`, `fab.py`, `desperdicio.py`, `banner.py`,
`sinjs.py`, `lightbox.py`). Ninguno escribe en la base.

**Nada de acá repite los 36 hallazgos de `docs/auditoria/hallazgos.json`** ni los cinco que ya
habías encontrado vos (dos banners apilados, emoji como iconografía, "1 Torneos"/"0 Partidos",
texto de 8/10px en las tarjetas, 795 KB de la home). Donde toco esos temas es porque medí algo
distinto por debajo: no es el mismo hallazgo, es la causa o una consecuencia que no estaba.

---

## Lectura de conjunto, antes de la lista

Las dos páginas están hechas por dos manos distintas y se nota.

La **landing es buena**. El `h1` dice en siete palabras qué hace el producto
("Publicá el torneo y las parejas se anotan solas"), el CTA es concreto y gratis, hay sistema de
color propio, tipografía elegida, un sprite de 14 íconos monolínea dibujados a mano, microcopy
rioplatense real ("perseguir señas", "¿a qué hora juego?", "te cuesta el domingo") y un visor de
capturas con auto-zoom que resuelve bien un problema difícil. Pasa el test de los 5 segundos.
No huele a plantilla.

La **home sí huele a plantilla de DaisyUI**: Title Case anglicada, emoji en vez de íconos,
`alert` + `card` + `badge` de catálogo, verde de marca usado como color de texto sin chequear
contraste, y seis descripciones distintas del producto entre `<title>`, `og:`, `twitter:`,
`meta description` y JSON-LD — ninguna de ellas la de la landing.

El problema de marca no es que la home sea fea: es que **la landing promete un producto que la
home no entrega visualmente**. Un dueño de club convence en `/para-organizadores/`, toca
"Ver la plataforma en vivo" y cae en una pantalla cuyo 56% superior es barra + dos carteles de
autopromoción, uno de los cuales no se puede cerrar.

Y arriba de todo eso: **en el celular la landing esconde justamente las pruebas** (tabla
comparativa, modo en vivo, las cuatro pantallas de celular, las placas, los números del
"cómo está hecho", 2 de 5 filas de producto y 6 de 9 preguntas), dejando títulos que anuncian
evidencia que no está.

---

# ALTO

## A1 · El cartel de "Crear Cuenta" no se puede cerrar en el celular — nunca

**Qué pasa.** El `✕` del banner de registro tiene `hidden sm:flex`. A 375px (todo el tráfico real)
el botón mide **0×0 con `display:none`**. Medido en claro y en oscuro:

```
#banner-instalar  ✕ → 24×24  display:flex
#banner-registro  ✕ →  0× 0  display:none   ← clases: "... hidden sm:flex"
```

El hermano (`banner-instalar`) sí tiene su `✕` visible, así que no es una decisión consciente de
"en mobile no se cierra": es la clase mal puesta en uno de los dos.

**Por qué importa acá.** Es el cartel más grande de la primera pantalla, aparece en **todas** las
páginas para cualquiera que no esté logueado, y no hay forma de sacárselo de encima. El `sessionStorage`
que lo recuerda nunca se escribe porque nunca se puede hacer clic. Un jugador que entra por el link
de un torneo que le pasaron por WhatsApp se come 180px de "creá tu cuenta" en cada pantalla, cuando
el producto se vende diciendo que **no hace falta cuenta** para anotarse.

**Archivo.** `theme/templates/base.html:839-840`

**Arreglo.** Sacar `hidden sm:flex` y dejar el botón siempre visible (igual que el de instalar), y
subirlo de `btn-sm btn-circle` (32px) a un target de 44px:
```html
<button onclick="dismissBanner('banner-registro')" aria-label="Cerrar"
        class="btn btn-ghost btn-circle shrink-0 opacity-60 hover:opacity-100
               min-h-11 h-11 w-11">✕</button>
```

---

## A2 · Los dos banners no son sólo dos: están rotos por dentro

Esto es distinto de "hay dos banners". Medí **cómo** se arman, y la respuesta es: mal, porque
`.alert` de DaisyUI y las clases `flex items-center gap-3` del template se pelean abajo de `sm`.

**Banner de instalar** — computado `flex-direction: column`, así que los cuatro hijos se apilan:

```
📲                     @33,91   309×32   ← emoji solo, centrado
¡Llevá TodoPadel…      @33,135  309×20
[ Instalar ]           @33,167  309×44   ← el CTA ocupa TODO el ancho
✕                      @33,223   24×24   ← huérfano, en su propia fila, abajo a la izquierda
                                   total: 178px de alto
```

El `✕` queda como un glifo suelto al pie de un bloque de 178px, sin relación visual con nada.
Y el botón "Instalar" se ve tan importante como un CTA principal de página.

**Banner de registro** — se queda en `row`, y entonces el texto se mete en una columna de **127px**:

```
🎾                     @37,364   33×32
"¡Sumate a la comunidad TodoPadel! Crea tu cuenta gratis…"
                       @82,303  127×154  ← 127px de ancho → 6 líneas, centrado y desflecado
[ Crear Cuenta ]       @221,358 117×44
                                   total: 180px de alto
```

Juntos: **y=80 a y=470 → 390px de 812**. Con la navbar fija de 64px, **el 56% de la primera
pantalla es barra + autopromoción**. El `h1` de la home arranca en **y=609px**.

**Por qué importa acá.** Es literalmente la primera impresión del producto, en el dispositivo
donde está el 90% del tráfico. No se ve "cargado": se ve **roto**. Y el `CLAUDE.md` del repo ya
avisa de esto ("`w-full` dentro de una fila flex… va `flex-1 min-w-0`"); acá el `flex-1` está pero
le falta `min-w-0` y le sobra `.alert`.

**Archivos.** `theme/templates/base.html:740-748` y `:829-842`

**Arreglo.** Sacar `.alert` de los dos (no aporta nada y es la que mete `flex-direction:column`,
`justify-items:center` y `text-align:center` abajo de 640px) y armar la fila a mano:

```html
<div id="banner-instalar"
     class="print:hidden flex flex-row items-center gap-3 text-left
            bg-primary/15 border border-primary/30 rounded-2xl py-2.5 px-4 mb-2">
  <svg class="w-6 h-6 shrink-0 text-primary">…</svg>
  <div class="flex-1 min-w-0 text-sm">…</div>
  <a class="btn btn-primary btn-sm shrink-0">Instalar</a>
  <button class="btn btn-ghost btn-circle shrink-0 min-h-11 h-11 w-11">✕</button>
</div>
```
Con eso cada banner baja de ~180px a ~56px y los dos juntos pasan de 390px a ~130px.
(Y si querés ir más lejos: mostrar uno solo por sesión, el de instalar sólo después de la
segunda visita.)

---

## A3 · El verde de marca como color de texto no pasa contraste en el hero — y el velo sobre la foto no protege nada

Medido pintando los píxeles reales en un `<canvas>` (el método de `auditoria_modo_claro.py`, para
no caer en la trampa del `oklch` que documenta `CLAUDE.md`): screenshot del recorte con el texto y
sin el texto, y comparación de los dos.

### Modo claro (el tema por defecto)

| Elemento | Tamaño | Ratio medido | Mínimo AA | |
|---|---|---|---|---|
| "TORNEOS POR CATEGORÍAS · ARGENTINA" | 12px / 700 | **1.89 : 1** | 4.5 | ❌ |
| "1 / 26 / 0" (números del stat) | 24px / 900 | **1.62 : 1** | 3.0 | ❌ |
| "Torneos / Jugadores / Partidos" | 12px / 700 | **1.89 : 1** | 4.5 | ❌ |
| `h1` "Tu próximo torneo…" | 36px / 900 | 14.20 : 1 | 3.0 | ✅ |

El `#10B981` sobre blanco puro ya da 2.48:1 — **falla incluso para texto grande**. Sobre la foto
del hero (que el velo deja en ~#DCDFE1 arriba y ~#C7D1CC donde está la cancha) baja a 1.6-1.9.
Las tres métricas de prueba social de la home son, en el tema por defecto, **verde sobre verde
claro**.

### Modo oscuro

| Elemento | Tamaño | Ratio medido | Mínimo AA | |
|---|---|---|---|---|
| "Armá tu pareja, inscribite y seguí…" | 18px / 400 | **3.42 : 1** | 4.5 | ❌ |
| `h1` | 36px / 900 | 3.94 : 1 | 3.0 | ⚠️ justo |

Acá el problema es el inverso: el velo es `bg-base-100/75` y la foto abajo es **clara**, así que
el fondo efectivo detrás del texto queda en gris medio (61-76) y el `text-base-content/80` también
es gris medio. Gris sobre gris.

**Por qué importa acá.** Jugadores amateur, en la cancha, de día, con el sol pegando en la
pantalla. 1.89:1 no se lee ni en una habitación oscura. Y la plata del hallazgo es que **el único
caso que el velo resuelve es el `h1`**: todo lo demás del hero queda desprotegido en uno u otro tema.

**Archivos.** `core/templates/core/home.html:69` (el velo), `:73` (eyebrow), `:94-96` (stats)

**Arreglo (dos partes).**

1. El velo tiene que ser sólido debajo de la columna de texto en mobile, no translúcido:
   ```html
   <!-- antes -->
   <div class="absolute inset-0 bg-base-100/75 md:bg-gradient-to-r …"></div>
   <!-- después: opaco en mobile, degradado recién en md -->
   <div class="absolute inset-0 bg-base-100 md:bg-gradient-to-r
               md:from-base-100/95 md:via-base-100/80 md:to-transparent"></div>
   ```
   (En mobile la foto igual se ve detrás de la card del carrusel y en los bordes.)

2. El verde deja de ser color de texto chico. Eyebrow y rótulos de stat a `text-base-content/70`;
   los números a `text-base-content` con el verde sólo como acento de fondo:
   ```html
   <span class="… text-base-content/70">Torneos por categorías · Argentina</span>
   <div class="text-2xl md:text-3xl font-black text-base-content">{{ … }}</div>
   ```
   Si querés conservar el verde en los números, hay que oscurecerlo: `#059669` sobre blanco da
   3.7:1 (pasa para texto grande, sigue sin pasar para 12px).

---

## A4 · El botón flotante de WhatsApp tapa 43 elementos de la landing — entre ellos 4 CTAs

Pregunta directa que me hiciste: sí, tapa. Lo medí geométricamente: intersección del rectángulo del
FAB (56×56, `right:22 bottom:22`) contra todos los `h1..h4, p, li, summary, a.btn, td, footer a`,
recorriendo la página de 120 en 120px.

**43 elementos distintos quedan debajo.** Los que duelen:

| scrollY | Qué queda tapado | Superposición |
|---|---|---|
| 5400 | **`a` "Quiero el plan Club"** — el CTA principal del bloque de precios | 25×21 px |
| 6480 | **`a` "Escribir por WhatsApp"** — el CTA final | 39×27 px |
| 6600 | **`a` "Ver la plataforma en vivo"** | 39×23 px |
| 4560 | `h2` "El primer torneo lo hacemos juntos y no te cuesta nada" | 56×37 px |
| 5880 / 6000 / 6120 | las 3 `summary` del FAQ (son tappables) | hasta 56×56 px |
| 3360 | `h2` "No competimos con las apps de reservar cancha" | 56×18 px |
| 480 | `h2` "Organizar un torneo no debería ser un trabajo de oficina" | 56×56 px |

Verificado además a ojo en las capturas: `shots/landing-dark-v06.png` (el FAB sentado sobre el
título de la sección de precios) y `shots/landing-dark-v08.png` (sobre la tercera pregunta).

**Por qué importa acá.** El FAB y el botón "Quiero el plan Club" **hacen exactamente lo mismo**
(abren el mismo WhatsApp con el mismo texto). Que uno tape al otro no es sólo feo: en un pulgar
grande, el tap sobre el borde del CTA cae en el FAB. Y el `h2` de precios tapado es el momento
de la página donde se habla de plata.

**Archivos.** `core/templates/core/para_organizadores.html:660-666` (CSS `.fab`), `:1214` (el `<a class="fab">`)

**Arreglo.** En el celular, convertir el FAB en una barra inferior fija y reservarle el espacio,
que además lo vuelve un CTA permanente en vez de un estorbo:

```css
@media(max-width:620px){
  .fab{
    right:0; left:0; bottom:0; width:auto; height:auto; border-radius:0;
    display:flex; gap:10px; padding:14px; font-weight:800; color:#04120C;
  }
  .fab::after{content:'Escribinos por WhatsApp'}
  body{padding-bottom:64px}   /* nada vuelve a quedar debajo */
}
```
Si preferís mantener el círculo: `body{padding-bottom:96px}` no alcanza (el choque es lateral, no
sólo al pie) — habría que achicarlo a 48px y ocultarlo mientras el CTA del hero o el de `#contacto`
estén en pantalla con un `IntersectionObserver`.

---

## A5 · En el celular la landing se queda sin pruebas, pero deja los títulos que las anuncian

El bloque `@media(max-width:620px)` de `core/templates/core/para_organizadores.html:564-580` apaga,
medido en vivo (`display: none`, alto 0):

| Se apaga | Qué era |
|---|---|
| `#envivo` | la pantalla en vivo proyectable, con captura |
| `#roles` | las dos pestañas Organizador / Jugador y los 13 beneficios del bento |
| `#mobile` | **las 4 capturas de celular** de la sección "se usa con una mano al lado de la red" |
| `#placas` | las placas 1080×1920 para Instagram |
| `#diferencia .tablewrap` | **la tabla comparativa de 9 filas × 5 columnas** |
| `#tech .tech` | los 4 números (23 / +200 / 109 / 0) |
| `#producto .frow` 1 y 5 | zonas automáticas y ranking |
| `#faq details` 4 a 9 | **6 de 9 preguntas** |

Las preguntas que se apagan son, exactamente:
*¿Cuánto sale y qué incluye?* · *¿Me atan con un contrato?* · *¿Puedo traer los torneos que ya
tengo en Excel?* · *¿Quién carga los resultados el día del torneo?* · *¿Sirve para americanos?* ·
*¿Los torneos quedan públicos en Google?*

Son **las seis objeciones de compra de un dueño de club**. Quedan las tres más blandas.

Y el efecto más visible: **los títulos sobreviven a su evidencia.**

- `#diferencia` queda como un `h2` que afirma "**No competimos con las apps de reservar cancha**",
  la bajada que lo explica (`.lead.solo-desk`) apagada, la tabla que lo prueba apagada, y debajo
  dos tarjetas con emoji. Es una afirmación pelada. (`shots/landing-dark-v05.png`)
- `#tech` queda como "**No es una demo: es un sistema que ya está andando**" seguido de cinco
  chips genéricos ("Conexión segura", "Tus datos respaldados") porque los cuatro números que lo
  sostenían se apagaron. (`shots/landing-dark-v06.png`)
- `#mobile` es la ironía redonda: la sección que demuestra que el producto está pensado para el
  celular **es la que se esconde en el celular**.

Y encima no ahorra nada de scroll que valga la pena: la página en mobile **igual mide 7739px**.

**Por qué importa acá.** El supuesto de esta decisión ("en el teléfono la página tiene que invitar,
no agotar; el que tiene dudas pregunta por WhatsApp", dice el comentario del CSS) es razonable para
un visitante impulsivo, pero el visitante acá es un tipo que está por cambiar cómo organiza sus
torneos y pagar $70.000/mes. Ese tipo **sí** lee, y lee desde el celular. Lo que no hace es
levantarse a buscar una computadora para leer una tabla comparativa.

**Clasificación.** Decisión de diseño, no bug. Pero es la decisión de mayor impacto de la página.

**Arreglo.** En vez de `display:none`, **condensar**:
- La tabla comparativa ya tiene `overflow-x:auto` y un `.swipe-hint`: mostrarla y dejar que se
  deslice de costado, igual que ya hacés con `.steps`, `.plans`, `.path` y `.bento`.
- `#faq`: mostrar las 9. Un `<details>` cerrado cuesta ~56px; nueve son 500px en una página
  de 7739. Si hay que cortar, cortar las blandas, nunca precio ni contrato.
- `#tech`: si se apagan los números, apagar también el título. Mejor: mostrar los números
  (son 4 cajitas de ~70px) y apagar los chips.
- `#mobile`: las 4 capturas de celular ya están en grilla de 2×2 en mobile — son la prueba
  más legible de toda la página (ver A7). Dejarlas y apagar otra cosa.

---

## A6 · La landing y la home cuentan dos historias distintas con los mismos tres números

La landing muestra, hardcodeado en el template:

```html
<!-- core/templates/core/para_organizadores.html:717-719 -->
<div class="stat"><b data-count="27">0</b><span>Torneos gestionados</span></div>
<div class="stat"><b data-count="380">0</b><span>Jugadores</span></div>
<div class="stat"><b data-count="532">0</b><span>Partidos cargados</span></div>
```

La home calcula los mismos tres contra la base (`core/views.py:33-40`, cacheados 1h) y los muestra
dos veces (en el hero y al pie).

El CTA secundario del bloque final de la landing es
`<a class="btn btn-ghost" href="{% url 'core:home' %}">Ver la plataforma en vivo</a>`
(`:1193`). O sea: **el prospecto lee "27 torneos · 380 jugadores · 532 partidos", toca el botón, y
aterriza en la página que muestra los reales**. Sean los que sean, no van a ser 27/380/532, porque
uno se mueve solo y el otro está escrito a mano.

Hay una tercera versión del mismo dato: la captura del hero de la landing
(`02-inicio-de-todopadel-en-escritorio…webp`) es un screenshot de la home que **muestra 27/380/532
en el hero** — otro dataset más.

**Por qué importa acá.** Un dueño de club es desconfiado por oficio y el salto de "380 jugadores"
a lo que diga la home es exactamente el tipo de cosa que hace cerrar la pestaña. No es un problema
de que los números sean bajos: es de que **haya dos fuentes de verdad y la landing te invite a
compararlas**.

**Clasificación.** Bug de contenido (el hardcodeo garantiza la divergencia).

**Arreglo.** `ParaOrganizadoresView` es un `TemplateView` pelado. Darle contexto con la misma
función cacheada que usa la home:

```python
class ParaOrganizadoresView(TemplateView):
    template_name = "core/para_organizadores.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx['stats'] = obtener_stats_home()   # extraer de core.views.home a una función
        return ctx
```
```html
<div class="stat"><b data-count="{{ stats.torneos_jugados }}">0</b><span>Torneos gestionados</span></div>
```
Y si los números reales todavía son chicos para vender: cambiar la métrica, no el número.
"Clubes que ya lo usan", "torneos corridos este año", o directamente sacar el bloque de stats del
hero y dejar sólo el testimonio. Un número chico honesto vende más que uno grande que el botón de
al lado desmiente.

---

## A7 · La captura estrella del hero de la landing es ilegible en el celular, y la que sí se leería está apagada

El `.showcase` del hero muestra un screenshot de escritorio dentro de un marco de navegador.
Medido:

| Imagen | Mostrada | Natural | Factor |
|---|---|---|---|
| `02-inicio-de-todopadel-en-escritorio…webp` | **341×213** | 1440×900 | **×4.2** |
| `05-cuadro-final…webp` | 341×120 | 1500×529 | ×4.4 |
| `06-bloque-de-como-pagar…webp` | 341×112 | 1400×461 | ×4.1 |
| `07-programacion-del-torneo…webp` | 341×289 | 1400×1185 | ×4.1 |

Un texto de 14px del screenshot original cae a **3.3px efectivos**. Es una mancha gris
(`shots/landing-dark-v01.png`: se ve el marco del navegador y adentro, nada legible).

Y al lado, el `.phone-float` — el mockup de celular con `03-todopadel-en-el-celular.webp`, que a
341px **sí se leería porque es una captura de celular** — tiene
`@media(max-width:760px){.phone-float{display:none}}` (`:148`). Se apaga justo donde serviría, y
aun así se descarga (45 KB, ver A9).

**Por qué importa acá.** Primera pantalla, primer segundo, 100% del tráfico mobile. El eslogan
dice "las parejas se anotan solas" y la única prueba visual que lo acompaña es un rectángulo gris.

**Arreglo.** Invertir la regla: en mobile mostrar el `.phone` y esconder el `.browser`.

```css
@media(max-width:760px){
  .showcase .browser{display:none}
  .phone-float{position:static; display:block; width:min(260px,70%); margin:0 auto; animation:none}
}
```

---

# MEDIO

## M1 · En el celular, el CTA del nav de la landing queda pegado al logo con 147px de vacío a la derecha

`.navlinks` tiene `margin-left:auto` (`:109`) — y `.navlinks{display:none}` abajo de 900px (`:115`).
**El auto-margin que empuja el CTA a la derecha vive en el elemento que se esconde.** Medido:

```
nav ancho: 343   CTA "Empezar gratis": x=74 … 212   vacío a la derecha: 147px
wordmark <b>: display none   navlinks: display none
```

Encima, `@media(max-width:430px){nav .brand b{display:none}}` (`:107`) esconde la palabra
"**TodoPadel**", así que en el celular el nav es: un ícono de paleta, un botón verde, y un tercio
de barra vacío. Es lo primero que se ve de un producto del que nadie oyó hablar, y no dice cómo se
llama. (`shots/landing-dark-v00.png`)

**Arreglo.**
```css
@media(max-width:900px){ .navlinks{display:none} header nav .btn{margin-left:auto} }
@media(max-width:430px){ nav .brand b{display:block; font-size:16px} }  /* en vez de ocultarlo */
```

## M2 · El plan recomendado queda 82% fuera de pantalla

Los planes se vuelven carrusel horizontal en mobile (`:487-497`). Medido al cargar:

```
.plans  scrollWidth=900  clientWidth=375  scrollLeft=0
.plan.feat ("Club", $70.000, "Recomendado")  x=309  →  sólo 66px visibles de 309
```

Lo primero que ve el prospecto en la sección de precios es "Piloto · Gratis" con un botón
**ghost** (bajo contraste, `btn-ghost`). El plan con la plata, la insignia "Recomendado" y el
único `btn-primary` de la sección está casi entero fuera. Hay un `.swipe-cue` ("deslizá para ver
las 3"), pero pide un gesto para llegar al pitch.

*(Verifiqué si la insignia "Recomendado" quedaba recortada por el `padding-top:4px` del carrusel:
**no**, se ve entera. `shots/landing-plan-feat.png`.)*

**Arreglo.** Arrancar el carrusel centrado en el destacado:
```js
const p = document.querySelector('.plans'), f = p.querySelector('.plan.feat');
if (f && getComputedStyle(p).overflowX === 'auto')
  p.scrollLeft = f.offsetLeft - (p.clientWidth - f.offsetWidth) / 2;
```
O, más simple: en mobile poner "Club" primero en el DOM con `order`.

## M3 · Las filas de producto alternan imagen-texto / texto-imagen al apilarse

En desktop `.frow.rev` invierte las columnas; en mobile `.frow.rev .ftext{order:0}` (`:237`) deja el
orden del DOM, que para las `.rev` es imagen primero. Medido (posición Y de cada bloque):

| Fila visible en mobile | Imagen Y | Texto Y | Orden |
|---|---|---|---|
| El cuadro sale en un click | 2595 | 2735 | imagen → texto |
| La seña entra antes… | 3340 | 3042 | texto → imagen |
| Cada pareja ve su horario | 3482 | 3740 | imagen → texto |

Dos de las tres filas arrancan con una captura ilegible y sin rótulo; recién después aparece el
"ANTES" y el título que dicen qué estás mirando. El ritmo de lectura se rompe fila por fila.

**Arreglo.**
```css
@media(max-width:900px){ .frow.rev .ftext{order:0} .frow.rev .shot{order:1} }
```

## M4 · Toda la landing cuelga de un solo `<script>`: si no corre, es una pantalla verde vacía

95 elementos tienen `.rv` / `.rv-l` / `.rv-r`, que arrancan en `opacity:0` y sólo se encienden
cuando el `IntersectionObserver` les pone `.in`. Con JS deshabilitado la página queda **en blanco**
salvo el botón del nav y el FAB: ni `h1`, ni bajada, ni CTA, ni precios.
(`shots/landing-sin-js.png` — lo medí con `java_script_enabled=False`.)

Y es **un solo bloque `<script>`** al final del body que hace nav + reveal + swipe-cues + barra de
progreso + contadores + visor + pestañas. Una excepción en cualquier punto anterior al
`io.observe(...)` deja las 95 cajas invisibles para siempre.

**Por qué importa acá.** No es sólo el caso raro del JS apagado: es que no hay red de contención.
Un navegador in-app raro, un bloqueador agresivo o un error en una línea de arriba y la página
comercial muestra la nada.

**Arreglo.** El patrón estándar: visible por defecto, invisible sólo si el JS está vivo.
```html
<script>document.documentElement.classList.add('js')</script>  <!-- en el <head> -->
```
```css
.js .rv{opacity:0; transform:translateY(28px)}
.rv{opacity:1; transform:none}   /* sin JS, todo visible */
```

## M5 · "Soy organizador →" es un botón 100% transparente, y es la única puerta a la landing desde la home

Medido en `.home-hero .btn-ghost`:
```
background-color: rgba(0, 0, 0, 0)
border-color:     rgba(0, 0, 0, 0)  /  1px
tamaño:           293 × 44
```
Sin fondo, sin borde, encima de la foto del hero. Se lee como una línea de texto, no como un
control. (`shots/home-light-v01.png`.)

Peor: **`/para-organizadores/` no está linkeada desde `theme/templates/base.html` en ningún lado**
— ni navbar, ni drawer, ni footer (`grep para_organizadores base.html` → 0 resultados). Las únicas
dos puertas están en la home: este botón fantasma y el bloque "¿Organizás torneos?", que además
sólo se muestra `{% if not user.is_authenticated or user.tipo_usuario == 'PLAYER' %}`.

O sea: **un organizador logueado, o cualquier visitante en cualquier página interna, no tiene forma
de llegar a la página de ventas.** Y el canal de crecimiento del producto es justamente "el dueño
del club ve la app funcionando en un torneo y la quiere".

**Arreglo.**
1. `core/templates/core/home.html:89` → darle forma de botón: `class="btn btn-outline gap-1"`.
2. Agregar "Para clubes" al footer de `base.html` (al lado de "Instalar la app") y al drawer.
   El atajo `/clubes/` ya existe en `core/urls.py` y no se usa en ningún link.

## M6 · La landing se baja 291 KB de imágenes que en el celular no se muestran nunca

Medido con caché frío a 375px, cruzando cada `<img>` contra su visibilidad computada:

```
Imágenes visibles en celular:                      122 KB
Imágenes descargadas y NUNCA mostradas:            291 KB   (70% del payload de imágenes)
Total de la landing:                               629 KB
```

Las ocultas que igual se bajan — ninguna tiene `loading="lazy"` (hay **0** en los dos templates):

| KB | Sección | Archivo |
|---|---|---|
| 48.3 | `#producto` (frow apagada) | `04-pantalla-de-zonas…webp` |
| 45.3 | `.phone-float` | `03-todopadel-en-el-celular.webp` |
| 39.2 | `#mobile` | `12-detalle-del-torneo…webp` |
| 30.6 | `#producto` (frow apagada) | `08-ranking-de-jugadores…webp` |
| 26.5 | `#mobile` | `14-pantalla-para-instalar-la-app.webp` |
| 25.3 | `#envivo` | `09-pantalla-en-vivo…webp` |
| 23.1 / 20.4 | `#mobile` | `11-listado…`, `13-resultados-en-vivo…` |
| 18.3 | `#placas` | `15-placa-para-historias…webp` |
| 14.5 | `#roles` | `10-perfil-publico-del-organizador…webp` |

`display:none` **no** impide que Chrome baje un `<img src>` (a diferencia de un
`background-image`). Son ~1.5s de 4G argentino tirados.

Además: **30.6 KB de JetBrains Mono** (`tDbv2o-flEE…woff2`, confirmado contra la API de Google
Fonts) se bajan para **un solo string de 12px**: el `todopadel.club` del marco de navegador falso
(`.browser .url`, `:157-160`). `.stack code` hace `font-family:inherit`, así que no hay otro uso.

**Arreglo.**
- `loading="lazy"` + `decoding="async"` en todas las capturas menos la del hero.
- Sacar `JetBrains Mono` del `<link>` de Google Fonts y poner `font-family: ui-monospace, monospace`
  en `.browser .url`. Son 30.6 KB y un preconnect menos, a cambio de nada.
- Si A5 se aplica (dejar de esconder secciones), el lazy ya resuelve el resto.

## M7 · Title Case anglicada, y la misma acción escrita de dos formas en la misma pantalla

```
core/templates/core/home.html:177  "Organizadores Destacados"
core/templates/core/home.html:221  "Ver Perfil"
core/templates/core/home.html:261  "Inscripciones Abiertas"
core/templates/core/home.html:343  "Ver Detalles"
core/templates/core/home.html:346  "Ver e Inscribirse"
core/templates/core/home.html:392  "Jugando Ahora"
core/templates/core/home.html:457  "Cargar Resultados"
theme/templates/base.html:838      "Crear Cuenta"
```

En castellano sólo va mayúscula la primera palabra. Es el tic visual más fuerte de "plantilla
traducida del inglés" que tiene la home — y convive, en la misma pantalla, con la forma correcta:
el hero dice "**Crear cuenta gratis**" y el banner, 500px más arriba, "**Crear Cuenta**". La misma
acción, dos escrituras, a la vez en pantalla. (`shots/home-light-v00.png` + `v01.png`.)

**Arreglo.** Pasar las ocho a mayúscula inicial sola, y unificar el rótulo de la acción de registro
("Crear cuenta gratis" en los dos lugares).

## M8 · Tuteo peninsular en la home (distinto de lo ya anotado en `base.html:834`)

```
core/templates/core/home.html:393  "Sigue los resultados y clasificaciones en vivo"   → "Seguí"
core/templates/core/home.html:7    (meta description) "…sigue partidos en vivo y consulta rankings…"
                                                                            → "seguí" / "mirá"
core/templates/core/home.html:484  "¡Vaya! La cancha está vacía"                      → "¡Uy!"
```

"¡Vaya!" no lo dice nadie en Argentina; es el "Oops!" traducido en España. Y rompe en el mismo
párrafo donde el resto sí está bien ("¡Volvé pronto para el próximo saque!").

Contrasta fuerte con la landing, donde el castellano rioplatense está **muy** bien resuelto
("perseguir señas", "te cuesta el domingo", "séptima damas", "recién ahí hablamos de plata").
La landing tiene voz; la home todavía no.

---

# BAJO

## B1 · La landing usa emoji justo en las dos tarjetas de `#diferencia`, al lado de su propio sprite de 14 íconos

`:1060` y `:1064`: `<h3>🔗 El canal es el link…</h3>` y `<h3>📍 Hecho acá, para cómo se juega acá</h3>`.
El resto de la página usa un sprite SVG dibujado a mano (`#i-trophy`, `#i-link`, `#i-live`… 14
símbolos) con el verde de marca. El 🔗 renderiza en gris rosado de plataforma y el 📍 en rojo: dos
colores que no están en la paleta. (`shots/landing-dark-v05.png`.)

Y el detalle fino: **`#i-link` ya existe en el sprite** y es exactamente el ícono de cadena que el
emoji está imitando. Reemplazo directo:
```html
<h3><span class="ic"><svg viewBox="0 0 24 24"><use href="#i-link"/></svg></span> El canal es el link…</h3>
```
(Para el 📍 habría que dibujar un `#i-pin`, o usar `#i-club`.)

Es el mismo *tipo* de problema que ya anotaste en la home, pero acá la pena es mayor: la landing
**tiene** el sistema y no lo usa en dos lugares.

## B2 · "deslizá para ver las 3" — concordancia de género

`:1247`: `cue.textContent='deslizá para ver las ' + g.children.length;`

Los cuatro grupos que lo reciben son masculinos: **los** 3 pasos (`.steps`), **los** 3 planes
(`.plans`), **los** 3 pasos comerciales (`.path`), **los** bloques del bento. En mobile se ve tres
veces, siempre mal.

**Arreglo.** Pasarle el sustantivo:
```js
const rotulos = {steps:'los 3 pasos', plans:'los 3 planes', path:'los 3 pasos', bento:'todo'};
cue.textContent = 'deslizá para ver ' + (rotulos[clave] || 'más');
```

## B3 · El visor ofrece 14 capturas cuando la página muestra 4

El lightbox arma su galería con `.browser img, .phone img, .shot img, .live-wrap img` (`:1277`),
**sin filtrar por visibilidad**. Medido en mobile: **14 imágenes en el visor, 4 visibles en la página.**
Al tocar la primera captura visible (el cuadro) el pie dice "**4 DE 14**", y deslizando se llega a
capturas de secciones apagadas (`#envivo`, `#mobile`, `#placas`, `#roles`).

No rompe nada — de hecho **es mejor que la página**: el auto-zoom del visor para capturas apaisadas
funciona muy bien y es la única forma en que un usuario de celular ve el cuadro legible
(`shots/landing-lightbox.png`). Pero el contador miente y el recorrido es desorientador.

**Arreglo.** Si se aplica A5 el problema desaparece solo. Si no:
`const imgs=[...document.querySelectorAll(sel)].filter(i => i.offsetParent !== null);`

## B4 · `<button>Ver Perfil</button>` adentro de un `<a href>`

`core/templates/core/home.html:221`. Contenido interactivo anidado: HTML inválido.
**Probado: el click sí navega** (`/` → `/accounts/organizador/1/`), así que no está roto para el
mouse. Pero con teclado el foco para dos veces en el mismo destino y un lector de pantalla
anuncia un botón dentro de un link. Las tarjetas de torneo de más abajo ya lo hacen bien
(`<a class="btn">`): es sólo esta.

**Arreglo.** `<span class="btn btn-primary btn-sm btn-outline w-full mt-auto">Ver Perfil</span>`.

## B5 · "Desarrollado por Emanuel Gomez Bolig" en el pie, en verde y negrita, con link saliente

`theme/templates/base.html:1236-1245`. Clase `link link-hover text-primary font-bold`, `target="_blank"`
a un portfolio de github.io. Es el elemento más destacado del footer después de los dos botones.

Un dueño de club que está evaluando pagar $70.000/mes lee, al pie de cada pantalla, "esto lo hizo
un tipo, acá está su portfolio". La landing construye con cuidado la idea de empresa
("No es una demo: es un sistema que ya está andando") y el footer de la app la desarma. Además es
el único link que saca tráfico fuera del producto.

**Arreglo.** Pasarlo a `text-base-content/40 font-normal` sin negrita ni verde, o moverlo a
`/instalar` o a un "Acerca de". El crédito es legítimo; el peso visual no.

## B6 · La home repite los mismos tres números al principio y al final

Hero (`:92-99`) y bloque de prueba social (`:487-502`): `torneos_jugados`, `jugadores`,
`partidos_jugados`, idénticos, con los mismos rótulos apenas reformulados ("Torneos" vs "Torneos
jugados"). En mobile se ven con 2.400px de scroll de distancia, así que no choca — pero la página
**cierra** con lo mismo con lo que abrió, y el bloque de testimonios que debería acompañarlo
(`{% if testimonios %}`) desaparece entero si no hay ninguno cargado, dejando tres números solos
como toda la "prueba social".

**Arreglo.** Sacarlos del hero (donde encima fallan contraste, ver A3) y dejarlos sólo en el bloque
de abajo. Y darle al bloque un estado digno sin testimonios: una frase, el logo de un club, algo.

## B7 · Detalles menores confirmados

- **`og:` de la home sin personalizar.** `home.html` pisa `title` y `meta_description` pero no
  `og_title`, `og_description`, `twitter_title` ni `twitter_description`, así que la preview de
  WhatsApp de `todopadel.club` dice "TodoPadel - Gestión de Torneos / La plataforma definitiva para
  tus torneos de pádel." — relleno de SaaS, en español de España ("tus"), mientras la landing dice
  "Publicá el torneo y las parejas se anotan solas". Contando `<title>`, `meta description`,
  `og:title`, `og:description`, `twitter:title`, `twitter:description` y el JSON-LD, hay **seis
  descripciones distintas del producto** entre las dos páginas, dos de ellas con "la plataforma
  líder/definitiva" sin nada que lo respalde. *(Verifiqué que `og-image.png` existe y es 1200×630:
  la tarjeta no está rota, sólo mal escrita.)*
- **El ícono de 48px de los encabezados de sección queda descentrado** cuando el `h2` entra en dos
  líneas, que a 375px es siempre ("Organizadores Destacados", "Inscripciones Abiertas"). Es
  `flex items-center` contra un bloque de dos renglones. Arreglo: `items-start` + `mt-0.5` en el ícono.
- **Pie de la landing con targets de 23px de alto**: "todopadel.club" (96×23), "Instagram" (64×23),
  "WhatsApp" (67×23). Arreglo: `footer a{display:inline-block; padding:10px 0}`.
- **"Organización verificada en TodoPadel."** como descripción por defecto de cualquier club sin
  texto (`home.html:219`). Afirma una verificación que el producto no hace. Mejor:
  "Todavía no cargó su presentación." o directamente no mostrar el párrafo.
- **La landing ignora el tema del sistema** (paleta oscura fija) mientras el resto de la app lo
  respeta. No es un bug — es una página comercial y está bien que tenga su arte propio — pero el
  usuario en modo claro pasa de un negro profundo a un blanco total al tocar "Ver la plataforma en
  vivo". Vale un pequeño puente: que la home respete un `?from=landing` y arranque en oscuro, o
  simplemente asumirlo.

---

# Lo que está bien (y no habría que tocar)

- **El hero de la landing pasa el test de los 5 segundos.** Qué es, para quién, qué hace y cuánto
  sale, en el primer scroll, sin jerga. El `h1` es específico y en voz activa rioplatense.
- **El visor de capturas con auto-zoom.** Detecta pantalla angosta + imagen apaisada y la abre ya
  acercada en vez de mostrar una tira ilegible, con swipe para cambiar y flechas abajo para no
  tapar la imagen con el dedo. Es la pieza mejor resuelta de las dos páginas.
- **`prefers-reduced-motion` contemplado en los dos lados** (el rebote del carrusel del hero de la
  home y las 95 revelaciones + orbes + shine de la landing). No es habitual.
- **El `.swipe-cue`** generado por JS debajo de cada grupo que se vuelve carrusel: decirle al
  usuario que hay más de costado es exactamente lo que hay que hacer (sólo falta el género, B2).
- **El sprite de 14 íconos monolínea** de la landing: coherente, en la paleta, y mucho más barato
  que Font Awesome.
- **`og-image` de 1200×630 presente en las dos páginas**, con `og:locale=es_AR` y `canonical` en la
  landing. La parte técnica de compartir está bien.
- **El carrusel con *peek*** y el desborde del cuadro son a propósito, como avisaste: los medí y no
  los cuento como hallazgo.
