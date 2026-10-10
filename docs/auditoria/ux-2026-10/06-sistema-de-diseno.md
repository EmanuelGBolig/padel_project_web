# Auditoría 06 — Sistema de diseño y accesibilidad transversal

**Alcance:** los patrones que se repiten en toda la app, no pantalla por pantalla.
**Fecha:** 2026-10-10 · **Rama:** `main` (commit `caeaf00`)

## Cómo se midió

Todo lo que dice "medido" acá salió del navegador, no de leer el CSS a ojo:

| Qué | Cómo |
|---|---|
| Tokens (radio, sombra, tipografía, botones, íconos, headings, foco) | Playwright + Chromium, **35 pantallas × 2 temas** a 390px, con login real por rol (jugador / organizador / admin) |
| Contraste | Ratio **WCAG 2.1** con luminancia relativa linealizada. El color se resuelve pintando 1px en un `<canvas>` (DaisyUI es `oklch`; leerlo con regex da cualquier cosa). Se compone el **alpha del texto** y los fondos semitransparentes de toda la cadena de ancestros |
| Inventario estático | 108 templates del repo, parseo de atributos `class="..."`, hex literales y emoji |

Scripts, JSON crudos y capturas en
`…/scratchpad/auditoria/ds/` (ver "Herramientas" al final).

> **Lo que el drawer cerrado ensucia:** el menú lateral no está `display:none`, se
> dibuja fuera de pantalla con `translate`. `checkVisibility()` dice que es visible.
> Todas las cifras de este informe lo excluyen, salvo donde se aclara.

---

# 🔴 ALTO

## A1. El esmeralda de marca no sirve ni como fondo ni como texto: 2,54:1 en los dos usos

**Medido en el navegador, tema `corporate` (el default del documento):**

| Elemento | Fondo | Texto | Ratio real | AA pide |
|---|---|---|---|---|
| `.btn-primary` / `.btn-success` | `#10b981` | `#ffffff` | **2.54:1** | 4.5:1 |
| `.badge-primary` | `#00c387` | `#f3fbf6` | **2.18:1** | 4.5:1 |
| `.text-primary` sobre `.card` | `#feffff` | `#10b981` | **2.53:1** | 4.5:1 |
| `.text-primary` sobre `bg-base-200` | `#e8e8e8` | `#10b981` | **2.07:1** | 4.5:1 |
| `.link-primary` del pie | `#e8e8e8` | `#10b981` | **1.83:1** | 4.5:1 |

No llega ni al umbral de 3:1 que se le exige al **texto grande**. Es matemáticamente
imposible que un mismo color sirva de fondo para texto blanco *y* de texto sobre fondo
blanco: `#10b981` tiene luminancia relativa 0.364, justo en el medio.

Y no es un desliz de un template: sale de una regla global en
`theme/templates/base.html:112-117`.

```css
.btn-primary, .btn-success {
    background-color: #10b981 !important;
    border-color: #10b981 !important;
    color: white !important;          /* ← 2.54:1 en claro */
}
[data-theme="business"] .btn-primary,
[data-theme="business"] .btn-success { color: #1a1a1a !important; }   /* ← 6.86:1, bien */
```

**El tema oscuro está bien (6.86:1) y el claro —que es el default— está roto.** Es
exactamente la trampa que ya documenta `CLAUDE.md` ("el modo claro casi nunca se
prueba"), pero esta vez en el color de marca, no en un `text-white` suelto.

**Alcance medido:** 166 botones primarios en 34 de 35 pantallas, más 21 cifras
`text-primary`, 34 links del pie y 20 avatares. En el barrido completo del tema claro,
**516 de 1193 nodos de texto visibles (43 %) quedan por debajo del umbral AA**, y 396
(33 %) por debajo de 3:1.

### Regla propuesta
Dos tokens, no uno. El esmeralda brillante es un color de **superficie**; para **tinta**
hace falta uno más oscuro.

```css
/* theme/static_src/src/styles.css */
:root {
    --tp-verde:        #10b981;   /* superficie: fondo de botón, badge, barra */
    --tp-verde-tinta:  #065f46;   /* tinta: texto, links, bordes sobre fondo claro */
    --tp-verde-hover:  #059669;
}
```

Candidatos medidos en el navegador (compuestos de verdad, no estimados):

| Color | sobre `#ffffff` | sobre `bg-base-200` (`#e8e8e8`) |
|---|---|---|
| `#10b981` (hoy) | 2.54:1 🔴 | 2.07:1 🔴 |
| `#047857` (emerald-700) | 5.48:1 ✅ | **4.48:1** 🔴 *(queda justo abajo)* |
| **`#065f46` (emerald-800)** | **7.68:1** ✅ | **6.27:1** ✅ |

Por eso la tinta tiene que ser `#065f46`: `#047857` pasa sobre blanco pero **falla**
sobre `bg-base-200`, que es el fondo del pie y de media app.

Para el botón hay dos caminos, los dos verificados:
- **(a)** dejar el texto blanco y bajar el fondo a `#047857` → **5.48:1** ✅;
- **(b)** dejar el fondo `#10b981` y poner tinta oscura — exactamente lo que el tema
  oscuro ya hace: `#1a1a1a` sobre `#10b981` mide **6.86:1** ✅.

La opción (b) es un cambio de **una línea** (borrar `color: white !important` y dejar que
aplique la regla de `business`, o directamente poner `color: #1a1a1a !important`) y deja
los dos temas idénticos.

---

## A2. Los avisos de Django (`messages`) son ilegibles en los cuatro tipos

`theme/templates/base.html:725` arma el alert con `... text-white border-none`.
Medido inyectando ese markup exacto contra el CSS real de la app:

| tag | Hoy (`text-white`) | Sacando `text-white` (DaisyUI usa su `*-content`) |
|---|---|---|
| `warning` | `#fff` sobre `#ffbe00` = **1.66:1** 🔴 | `#000` sobre `#ffbe00` = **12.62:1** ✅ |
| `success` | `#fff` sobre `#00c387` = **2.29:1** 🔴 | 2.18:1 🔴 *(hay que tocar `--suc`)* |
| `info` | `#fff` sobre `#00b5ff` = **2.32:1** 🔴 | `#000` sobre `#00b5ff` = **9.05:1** ✅ |
| `error` | `#fff` sobre `#ff5861` = **3.08:1** 🔴 | `#000` sobre `#ff5861` = **6.82:1** ✅ |

Un aviso amarillo a **1.66:1** es prácticamente un rectángulo amarillo vacío. Y es el
canal por el que la app confirma *todo*: "Resultado guardado", "Inscripción
confirmada", "Faltan partidos de zona".

### Arreglo
1. Sacar `text-white` y `border-none` de `base.html:725`. Resuelve `warning`, `info` y `error`.
2. Para `success`, el proyecto fuerza `--suc: 98% 0.01 163` (casi blanco) en **los dos**
   temas (`base.html:88-97`). En `corporate` tiene que ser oscuro, igual que ya hace con
   `--pc` en `business`:
   ```css
   :root, html[data-theme="corporate"] { --suc: 15% 0.02 163 !important; }
   ```

---

## A3. 496 declaraciones de "texto atenuado" con 20 valores distintos, y 305 de ellas son ilegibles

No existe un token de "texto secundario". Hay dos mecanismos conviviendo y veinte
niveles:

| Mecanismo | Valores usados | Declaraciones |
|---|---|---|
| `opacity-NN` | 0, 10, 30, 40, 45, 50, 60, 70, 75, 80, 90, 100 | 301 |
| `text-base-content/NN` | 15, 20, 25, 30, 40, 50, 60, 70, 80, 90 | 195 |

En **83 de los 108 templates**. **305 declaraciones están en 60 % o menos** (fallan en
los dos temas) y otras **126 están en 70 %**, que pasa en claro y falla en oscuro
(4.16:1 sobre una tarjeta).

Contraste medido, componiendo el alpha de verdad:

| Alpha efectivo | Claro, sobre `#ffffff` | Claro, sobre `#e8e8e8` | Oscuro, sobre la tarjeta `#1d232a` |
|---|---|---|---|
| 82 % | 9.9:1 ✅ | 8.49:1 ✅ | 5.20:1 ✅ |
| 80 % | — | — | 4.99:1 ✅ |
| **78 %** | 8.6:1 ✅ | **7.48:1** ✅ | **4.84:1** ✅ |
| 75 % | — | — | 4.61:1 ✅ *(al filo)* |
| 72 % | 6.86:1 ✅ | 6.18:1 ✅ | **4.36:1** 🔴 |
| 70 % | — | 5.2:1 ✅ | **4.16:1** 🔴 *(se cae en oscuro)* |
| 60 % | 4.52:1 ✅ *(al filo)* | **4.21:1** 🔴 | **3.46:1** 🔴 |
| 50 % | **3.34:1** 🔴 | **3.18:1** 🔴 | — |
| 40 % | **2.51:1** 🔴 | — | — |
| 24 % (`opacity-40` × `opacity-60` anidados) | **1.66:1** 🔴 | — | — |

El piso seguro para **los dos temas** es **78 %**, no 70: a 72 % el tema oscuro ya baja
de 4.5:1 sobre una tarjeta.

Casos concretos verificados:

- **Pie de página, las 34 pantallas** (`base.html`): "TodoPadel © 2026" a **3.18:1**,
  "Desarrollado por" a **2.43:1**, el link del autor a **1.83:1**.
- **Logros del perfil** (`accounts/_logros.html:8`): el bloqueado lleva
  `opacity-40 grayscale` y adentro `text-xs opacity-60` → el título a **2.47:1** y la
  descripción a **1.66:1**. Atenuar está bien; atenuar hasta 1.66:1 es borrar.
- En el tema oscuro pasa lo mismo: **482 de 1193 nodos (40 %)** por debajo de AA.
  Este problema **no depende del tema**.

### Regla propuesta
Un solo token, y que el mínimo sea **78 %**.

```css
/* styles.css — un único nivel de texto secundario, legible en los dos temas */
.texto-secundario { color: oklch(var(--bc) / 0.78); }   /* 7.48:1 claro · 4.84:1 oscuro */
```

Y para los estados "bloqueado/deshabilitado", atenuar el **ícono**, no el texto:
`.logro-bloqueado svg { opacity: .35 } .logro-bloqueado { filter: grayscale(1) }`.

---

## A4. 62 emoji conviven con 223 SVG, en 9 tamaños y sin `aria-hidden`

| | Cuántos | Tamaños renderizados | `aria-hidden` |
|---|---|---|---|
| Íconos SVG | 223 en el repo / 681 renderizados | **5**, pero 676 de 681 (99 %) caen en **3**: 20px (533), 16px (96), 24px (47) | — |
| Emoji como ícono | **62 distintos en el repo**, 182 usos en 38 templates · 34 distintos y 178 apariciones en las 35 pantallas medidas | **9**: 12, 14, 15, 16, 18, 20, 24, 30, 36px | **0 de 52** combinaciones |

El set de SVG está muy bien disciplinado (tres tamaños, `flex-shrink:0` global). El
problema es que al lado hay un segundo sistema de iconografía, multicolor, sin control
de tamaño y que **el lector de pantalla lee en voz alta** ("pelota de tenis", "teléfono
móvil con flecha").

Peor: hay duplicación semántica dentro del propio set de emoji — `✓` (13) vs `✅` (5),
`✕` (12) vs `❌` (1), y siete flechas distintas (`→ ← ↑ ↓ ⬆ ⬇ ↻`).

Casos que más pegan:

- `📲` a 14px dentro de un `.btn-primary`, en **34 de 35 pantallas** (`base.html:1215`).
- `✕` como botón de cerrar: `btn-xs btn-circle` de **24×24px** y fuente de **12px**
  (`base.html:748` y 5 lugares más). Es el control de descarte de los banners.
- `🎾` a 24px en el banner de registro, al lado de SVG monocromos de 20px.

### Regla propuesta
**Una sola fuente de iconografía: SVG inline, en 3 tamaños.** Emoji solo dentro de
texto corrido escrito por un usuario, nunca como control ni como ícono de UI.

```css
/* styles.css */
.ico     { width: 1.25rem; height: 1.25rem; flex-shrink: 0; }  /* 20px, el default */
.ico-sm  { width: 1rem;    height: 1rem; }                      /* 16px, en línea con texto */
.ico-lg  { width: 1.5rem;  height: 1.5rem; }                    /* 24px, cabeceras */
```

Migración por orden de impacto:
1. El `✕` de cerrar → `<button class="btn btn-sm btn-circle btn-ghost" aria-label="Cerrar">`
   con el SVG `x-mark` de Heroicons (ya hay 223 en el repo con ese estilo). **12 lugares.**
2. El `📲` del botón de instalar → ícono `device-phone-mobile`. **2 lugares, 34 pantallas.**
3. Las flechas `→`/`←` de "Ver más" → `arrow-right` / `arrow-left`. **~25 lugares.**
4. Lo que quede como decoración (`🏆`, `🥇` en podios) → envolverlo en
   `<span aria-hidden="true">` y fijarle tamaño con `.ico-*`.

---

## A5. El menú lateral cerrado se queda en el orden de tabulación: 347 de 809 paradas van fuera de pantalla

Verificado tabulando de verdad en `/torneos/abiertos/` (jugador, 390px):

```
17  A  drawer=False  left=  49   "Ver e Inscribirse"
18  A  drawer=True   left=-296   "Inicio"            ← el foco se va de la pantalla
19  A  drawer=True   left=-296   "En Juego"
…
29  SUMMARY drawer=True left=-296 "Rankings"
```

`.drawer-side` no tiene `inert` ni `aria-hidden`, así que sus ~12 links siguen siendo
focusables aunque el menú esté cerrado. **347 de las 809 paradas de tabulación medidas
(43 %) caen ahí.** Quien navega con teclado —o con un switch, o con VoiceOver— queda
sin referencia visual durante una docena de Tabs en **todas** las pantallas.

Es además la causa del otro falso positivo clásico: la mitad de lo que marcan los
scripts de auditoría viven en ese menú invisible.

### Arreglo
```html
<!-- base.html, el aside del drawer -->
<aside class="drawer-side" id="menu-lateral" {% comment %}...{% endcomment %}>
```
```js
// junto al script del drawer
const toggle = document.querySelector('.drawer-toggle');
const lado   = document.querySelector('.drawer-side');
const sync = () => { lado.inert = !toggle.checked; };
toggle.addEventListener('change', sync); sync();
```
`inert` lo saca del orden de tabulación y del árbol de accesibilidad de una sola vez, y
está soportado en todos los navegadores que usa el público de la app.

---

# 🟡 MEDIO

## M1. 80 `<label>` sin `for`: el 63 % de las etiquetas no está asociada a su campo

| | Cantidad |
|---|---|
| `<label>` en templates | 127 |
| con `for=` | 43 |
| que envuelven el control | 4 |
| **huérfanos** | **80**, en 22 templates |

Medido en runtime: **32 de 88 inputs visibles no tienen nombre accesible** (ni `for`, ni
`aria-label`, ni estar dentro del `<label>`). Las peores:

| Pantalla | Inputs sin label |
|---|---|
| `/torneos/admin/crear/` | **13 de 17** |
| `/accounts/organizacion/ajustes/` | **9 de 13** |
| `/accounts/usuarios/merge/` | 2 de 3 |
| `/equipos/admin/listado/` | 2 de 3 |

El patrón es siempre el mismo (`torneos/admin_torneo_form.html:39`):

```django
<label class="label py-1"><span class="label-text ...">{{ form.nombre.label }}</span></label>
{{ form.nombre }}
```

En el **mismo archivo**, línea 146, está hecho bien:
`<label class="label py-1" for="{{ form.precio_inscripcion.id_for_label }}">`. O sea que
no es una decisión, es un olvido repetido.

**Por qué importa acá más que en otras apps:** el label es el blanco táctil más grande de
un formulario. Sin `for`, tocarlo no hace nada; el organizador tiene que apuntarle al
input, parado al borde de la cancha.

### Arreglo
Un único partial y usarlo en los 22 templates:

```django
{# theme/templates/partials/campo.html #}
<div class="form-control w-full">
    <label class="label py-1" for="{{ campo.id_for_label }}">
        <span class="label-text font-medium text-sm">{{ etiqueta|default:campo.label }}</span>
    </label>
    {{ campo }}
    {% if ayuda %}<span class="label-text-alt text-base-content/70 text-xs mt-1">{{ ayuda }}</span>{% endif %}
    {% for e in campo.errors %}<span class="text-error text-xs mt-1">{{ e }}</span>{% endfor %}
</div>
```
`{% include "partials/campo.html" with campo=form.nombre %}`

---

## M2. El borde de los campos de formulario mide 1,5:1 contra el fondo

WCAG 1.4.11 pide **3:1** para el límite de un componente. Medido sobre 88 inputs:

| Tema | Ratio del borde | Cuántos |
|---|---|---|
| `corporate` | 1.50 – 1.52:1 | **65 de 88** |
| `business` | 1.48 – 1.49:1 | **64 de 88** |
| ambos | sin borde dibujado | 23 |

Es el `--b3` de DaisyUI (`#d1d1d1` en claro) sobre `--b1` (`#ffffff`). Al sol, un campo
con borde a 1.5:1 directamente no se ve: no se distingue "dónde hay que tocar".

### Arreglo (una regla global)
Alphas probados contra los dos temas:

| Alpha | sobre `#ffffff` (claro) | sobre la tarjeta `#1d232a` (oscuro) |
|---|---|---|
| `--b3` actual (`#d1d1d1`) | **1.53:1** 🔴 | **1.48:1** 🔴 |
| 0.45 | 2.87:1 🔴 | 2.54:1 🔴 |
| 0.50 | 3.34:1 ✅ | 2.83:1 🔴 |
| **0.55** | **3.86:1** ✅ | **3.12:1** ✅ |

```css
/* styles.css */
.input-bordered, .select-bordered, .textarea-bordered, .file-input-bordered {
    border-color: oklch(var(--bc) / 0.55);   /* 3.86:1 claro · 3.12:1 oscuro */
}
.input-bordered:focus, .select-bordered:focus, .textarea-bordered:focus {
    border-color: oklch(var(--p));
}
```

---

## M3. "Matar el azul" está incompleto: hay una tarjeta magenta en el perfil del organizador

El override de `base.html:121-136` cubre `.btn-*`, `.badge-*`, `.text-*` y `.bg-*/10` de
`secondary / accent / info`. **No cubre** `bg-secondary`, `alert-info`, `bg-info`,
`border-*`, `ring-*`, `stroke-*`, `to-*`. En uso hoy: **13 declaraciones en 11 archivos**.

La peor, verificada en el navegador y capturada:

`accounts/templates/accounts/perfil.html:417` → `<div class="card bg-secondary text-secondary-content">`

| Tema | `--s` resuelve a | Qué se ve |
|---|---|---|
| `corporate` | `#7b92b2` | tarjeta **gris azulada** |
| `business` | `#ff52d9` | tarjeta **rosa chicle** |

Visible para **organizador y admin** (es la tarjeta "Inscritos Hoy").
Captura: `ds/shot_secondary_dark.png`.

Además, `alert-info` (5 archivos + el safelist de Tailwind, o sea los `messages` de
Django) renderiza en `#00b5ff`, **azul**, en una app cuyo sistema visual se llama
literalmente "matar el azul".

### Arreglo
En vez de ir agregando selectores, redefinir los **tokens** una sola vez — que es lo que
el proyecto ya hace con `--p`:

```css
:root, html[data-theme="corporate"], html[data-theme="business"] {
    --s:  72% 0.16 163 !important;   /* secondary  -> esmeralda */
    --a:  72% 0.16 163 !important;   /* accent     -> esmeralda */
    --in: 72% 0.16 163 !important;   /* info       -> esmeralda */
    --sc: 15% 0.02 163 !important;   /* y su tinta oscura */
    --ac: 15% 0.02 163 !important;
    --inc:15% 0.02 163 !important;
}
```
Con esto se pueden **borrar** las 14 líneas de override de `.btn-secondary` /
`.badge-*` / `.text-*` de `base.html:121-136`, y ningún `bg-*`, `border-*` o
`alert-*` futuro vuelve a escaparse.

---

## M4. Rojo con tres significados distintos

De 13 usos de `btn-error`, **3 no son destructivos**:

| Dónde | Texto | Qué hace en realidad |
|---|---|---|
| `torneos/admin_torneo_manage.html:193` | **Finalizar Torneo** | cerrar el torneo: el final feliz del flujo |
| `torneos/americano_manage.html:31` | **Finalizar** | ídem |
| `torneos/torneo_detail.html:79` | **Ver en vivo** | navegar; rojo acá significa "en el aire" |

Los otros 10 sí son destructivos (Eliminar, Disolver, Cancelar inscripción). El resultado
es que el organizador ve el mismo rojo para "borrar el torneo" y para "terminar el
torneo", que son acciones vecinas en la misma pantalla.

Lo mismo con el "en vivo": `base.html:140-149` define `.live-dot` / `.live-badge` en
`#FF5861`, y después hay `text-error` y `btn-error` usados para lo mismo — tres formas
de pintar "en vivo".

### Regla propuesta
```
rojo (--er)   = destructivo e irreversible. Nada más.
ámbar (--wa)  = advertencia, el usuario puede seguir.
esmeralda     = acción principal, incluida "Finalizar Torneo".
.live-badge   = el ÚNICO "en vivo". Nunca text-error ni btn-error.
```
3 botones a cambiar + unificar los "en vivo" en `.live-badge`.

---

## M5. La escala tipográfica tiene 17 tamaños, 9 de ellos fuera de la escala de Tailwind

Medido sobre 1544 nodos de texto en 35 pantallas:

```
8.0  10.0  10.5  11.0  11.5  12.0  14.0  14.4  15.0  16.0  17.0  18.0  20.0  24.0  30.0  33.0  36.0
 ✗    ✗     ✗     ✗     ✗     ·     ·     ✗     ✗     ·     ✗     ·     ·     ·     ·     ✗     ·
                                 (✗ = fuera de la escala de Tailwind)
```

Origen estático: **58 usos de `text-[…]` arbitrario** —
`text-[10px]` (22), `text-[1.1rem]` (14), `text-[11px]` (11), `text-[0.65rem]` (4),
`text-[9px]` (3), `text-[0.6rem]` (2), `text-[8px]` (2).

**33 de esos usos son de menos de 11px.** El mínimo absoluto medido: **8px**
("Organiza", en la home). Para un público mayormente de más de 40 años leyendo al sol,
8px es decorativo, no informativo.

Peso: 6 valores (`font-bold` 284, `font-medium` 153, `font-black` 73, `font-semibold`
32, `font-extrabold` 15, `font-normal` 3). `black`/`extrabold`/`bold`/`semibold` son
cuatro grados de "fuerte" para la misma intención.

### Regla propuesta
Seis escalones y un piso duro de 12px.

| Token | px | Uso |
|---|---|---|
| `text-xs` | 12 | metadatos, nunca información necesaria |
| `text-sm` | 14 | cuerpo por defecto en mobile |
| `text-base` | 16 | cuerpo largo |
| `text-lg` | 18 | título de tarjeta |
| `text-2xl` | 24 | título de pantalla |
| `text-4xl` | 36 | hero |

```css
/* styles.css — piso de legibilidad */
@media (max-width: 767px) { :where(body) * { font-size: max(0.75rem, revert); } }
```
y eliminar los 7 valores arbitrarios (58 ocurrencias). Pesos: quedarse con
`font-medium` (500), `font-bold` (700) y `font-black` (900) para el hero; borrar
`semibold` y `extrabold`.

---

## M6. Target táctil: la regla del repo funciona, pero tiene tres agujeros

La regla de `styles.css` (`.btn-sm` → `min-height: 2.5rem`) **anda**: 73 botones a 40px
exactos. Lo que no cubre:

| Caso | Tamaño real | Cuántos | Por qué se escapa |
|---|---|---|---|
| `btn-sm.btn-circle` / `.btn-square` | **36×36** | 92 | la propia regla les pone 2.25rem |
| `btn-xs` | **24×24** (y 324×**24** a ancho completo) | 37 | excluido a propósito |
| `<a>` de texto como acción ("Editar →", "Agregar →", "Ya tengo cuenta") | **16px de alto** | 7 | no son `.btn` |
| Puntos del carrusel de la home | **8×8** | 2 | `w-2 h-2` |

Totales sobre 440 botones visibles: **72 % por debajo de 44px** (Apple HIG / WCAG AAA),
**36 % por debajo de 40px**, **2 % por debajo de 24px** (fallo duro de WCAG 2.5.8 AA).

Lo más grave no son los 36px sino los **`btn-xs` de 24px de alto usados como CTA a ancho
completo** ("Subir foto", "Crear pareja" en los banners de `base.html`): 324px de ancho y
24 de alto es una franja, no un botón.

### Arreglo
```css
@media (max-width: 767px) {
    /* los redondos quedan a la par del resto */
    .btn-sm.btn-circle, .btn-sm.btn-square { min-height: 2.5rem; min-width: 2.5rem; }

    /* btn-xs sigue valiendo dentro de tablas; fuera de una tabla, no */
    .btn-xs:not(table .btn-xs) { min-height: 2.5rem; height: auto; padding-inline: .75rem; }

    /* un <a> que es una acción se toca como un botón */
    .accion-texto { display: inline-flex; align-items: center; min-height: 2.5rem; }
}
```
Y los puntos del carrusel: agrandar el área táctil sin agrandar el punto
(`padding: 10px; background-clip: content-box`).

---

## M7. 12 de 35 pantallas no tienen `<h1>`, y el tamaño no sigue al nivel

| Problema | Cuántas pantallas |
|---|---|
| Sin ningún `<h1>` | **12 de 35** |
| Salto `h1 → h3` | 6 |
| Jerarquía correcta | 17 |

Sin `<h1>`: Torneos abiertos / en juego / finalizados, Login, Registro, Alta sin cuenta,
Perfil, Mi pareja, Crear pareja, Crear torneo, Crear pareja (org), Parejas admin.
El título de la pantalla está maquetado como `<h2>` o como `<div>`.

Y el tamaño visual no acompaña al nivel semántico:

```
h1: 15, 24, 30, 33, 36 px      ← hay un h1 de 15px, más chico que casi cualquier h3
h2: 16, 18, 20, 24, 30 px
h3: 16, 18, 20 px
```

24px es `h1` en 7 pantallas y `h2` en 12. Un lector de pantalla y el buscador ven una
estructura; el ojo ve otra.

### Arreglo
Un bloque en `base.html` para el título de pantalla, y que los templates lo llenen:

```django
{% block titulo_pantalla %}{% endblock %}
→ <h1 class="text-2xl md:text-3xl font-black text-base-content">…</h1>
```
```css
/* styles.css — el tamaño sale del nivel, no de clases sueltas */
h1 { font-size: 1.5rem; font-weight: 900; }   /* 24px */
h2 { font-size: 1.25rem; font-weight: 700; }  /* 20px */
h3 { font-size: 1.125rem; font-weight: 700; } /* 18px */
```

---

## M8. El fix del `color-scheme` al imprimir se aplicó a una sola pantalla

`CLAUDE.md` dice: *"En todo `@media print` va `html { color-scheme: light !important; }`"*.
Está en **1 de 3** bloques `@media print` del proyecto.

| Archivo | `@media print` | `color-scheme: light` |
|---|---|---|
| `torneos/templates/torneos/torneo_programacion.html:192` | sí | ✅ |
| `theme/static_src/src/styles.css` (global, aplica a todas) | sí | ❌ |
| `accounts/templates/accounts/print/organizacion_programacion.html:105` | sí | ❌ |

Medido emulando `media=print` con el celular en oscuro:

| Pantalla | `color-scheme` al imprimir | fondo de `<html>` |
|---|---|---|
| `/torneos/2/` (ficha con la llave) | **dark** | `oklch(0.2533 0.0159 252)` 🔴 |
| `/torneos/2/vivo/` | **dark** | `oklch(0.2533 0.0159 252)` 🔴 |
| `/torneos/2/programacion/` | light | `#fff` ✅ |

O sea: el margen de la hoja sale negro en cualquier pantalla que **no** sea la planilla —
y la ficha con el cuadro de la llave es justamente lo que el club pega en la pared.

### Arreglo (3 líneas, en el bloque print que ya existe)
```css
@media print {
    html { color-scheme: light !important; }
    html, body { background: #fff !important; }
    /* … lo que ya está … */
}
```

---

# 🟢 BAJO

## B1. Once valores de sombra y nueve de radio para tres jerarquías

**Radios** — 9 valores computados / 18 clases `rounded-*` distintas en los templates:

| Computado | Elementos | De dónde sale |
|---|---|---|
| 12px | 495 | `rounded-xl` |
| 8px | 316 | `--rounded-btn: 0.5rem` |
| 9999px | 223 | `rounded-full` |
| 16px | 128 | `--rounded-box: 1rem` / `rounded-2xl` |
| 30.4px | 48 | `--rounded-badge: 1.9rem` |
| 24px | 26 | `rounded-3xl` |
| 6px, 999px, `0px 16px 16px 16px` | 12 | sueltos |

`999px` y `9999px` son dos formas de escribir "pastilla"; `rounded-2xl` (86 usos),
`rounded-xl` (78) y `rounded-3xl` (64) compiten para la misma cosa — una tarjeta.

**Sombras** — 18 valores computados, de los cuales 279 elementos tienen la "sombra nula"
de Tailwind y 6 variantes son anillos de foco. Quedan **11 tratamientos reales de
elevación**: `shadow-sm` (182), `shadow-xl` (36), `shadow-lg shadow-primary/30` (34),
`shadow-md` (32), `shadow` (21), `shadow-lg` (8), `shadow-2xl` (2), más tres resplandores
esmeralda a medida y un `shadow-[0_0_15px_rgba(16,185,129,0.2)]`.

### Regla propuesta
3 radios y 3 elevaciones, fijados en los tokens de DaisyUI para que no haya que tocar
templates:

```css
[data-theme="corporate"], [data-theme="business"] {
    --rounded-box: 1rem;      /* 16px — tarjetas, paneles, modales */
    --rounded-btn: 0.75rem;   /* 12px — botones, inputs, badges */
    --rounded-badge: 9999px;  /* pastilla */
}
```
| Nivel | Clase | Para qué |
|---|---|---|
| 0 | `shadow-none` + `border-base-300` | tarjeta en reposo |
| 1 | `shadow-sm` | tarjeta elevada / sticky |
| 2 | `shadow-xl` | modal, dropdown, drawer |

El resplandor esmeralda queda **solo** para la acción principal de la pantalla.

---

## B2. 108 colores hex literales, de los cuales 25 son verdes

289 apariciones de hex literal en 18 archivos. Los emails y la página de impresión
standalone lo justifican (ahí no hay variables CSS). El resto no:

| Archivo | Hex |
|---|---|
| `theme/templates/base.html` | 44 |
| `core/templates/core/para_organizadores.html` | 40 |
| `torneos/templates/torneos/placa.html` | 28 |
| `torneos/templates/torneos/pantalla/pantalla.html` | 25 |
| `theme/templates/partials/empty_state.html` | 11 |

**Hay 25 verdes distintos** (87 apariciones). Los que pretenden ser el mismo verde de
marca:

```
#10b981 (25)   #00c896 (17)   #059669 (6)   #009e73 (4)
#4caf50 (4)    #00cdb7 (2)    #34d9a0 (1)   #14b17c (1)
#00996a (1)    #34d399 (1)
```

Y está **verificado en el navegador** que el botón y el badge usan verdes distintos:

```
btn-primary   fondo #10b981   (hardcodeado en base.html)
badge-primary fondo #00c387   (el token --p: 72% 0.16 163)
mismo verde btn vs badge: False
```

Dos verdes a cinco puntos de distancia, uno al lado del otro en la misma tarjeta.

### Arreglo
Elegir **uno** y que el token y el literal coincidan. Lo más limpio es borrar los
`!important` con hex de `base.html:112-136` y dejar que mande `--p`; si se prefiere
conservar `#10b981`, hay que redefinir `--p` con su equivalente oklch exacto en vez de
`72% 0.16 163` (que resuelve a `#00c387`).

Para el resto de los verdes sueltos (`#00c896` en los mails, `#4caf50` en login/registro,
`#009e73`, `#00cdb7`, `#34d9a0`, `#14b17c`, `#00996a`, `#34d399`): dejar **uno** para
email —donde no hay variables CSS— y borrar los demás.

---

## B3. Tres hojas de estilo que no las carga nadie

| Archivo | Referencias en templates/py |
|---|---|
| `theme/static/css/tooltips.css` | **0** |
| `theme/static/css/select2-mobile.css` | **0** (sin versionar) |
| `staticfiles/custom.css` + `staticfiles/core/custom.css` | **0** (sin versionar) |

`tooltips.css` arregla los tooltips de nombres largos y les da comportamiento de *tap* en
mobile — pero no está enlazado, y el JS que agrega la clase `.active` que esa hoja espera
tampoco existe. Resultado: los 3 `data-tip` de la app (`_grupo_panel.html`,
`estadisticas_card.html`) **nunca se muestran en un celular**, porque en touch no hay
`:hover`.

`select2-mobile.css` además estiliza `[data-theme="dark"]`, un tema que la app nunca
setea (usa `corporate` / `business`).

### Arreglo
Borrar las tres, y mover a `styles.css` lo poco de `tooltips.css` que sigue haciendo
falta. Para los 3 `data-tip`: pasar la información a texto visible o a un `<details>`,
porque en mobile un tooltip es información que no existe.

---

## B4. `animate-pulse` infinito en 5 llamados a la acción, sin `prefers-reduced-motion`

5 de los 12 `animate-pulse` del repo están sobre el botón principal de la pantalla:
`base.html:747`, `base.html:1215`, `core/instalar.html:37`,
`torneos/torneo_detail.html:432`, `accounts/public_profile.html:87`.

`animate-pulse` oscila la opacidad entre 1 y 0.5, **para siempre**. Medido en el
momento bajo del ciclo:

| Tema | Botón quieto | En el valle del pulso |
|---|---|---|
| `corporate` | 2.54:1 | **1.57:1** |
| `business` | 6.86:1 | **2.60:1** |

Además `prefers-reduced-motion` está respetado en **un solo** lugar
(`base.html:156`, para `.live-dot`), y no para `animate-pulse`, `animate-ping`,
`.animate-gradient-x`, `.card-elevate`, `.toast-slide-in` ni `.content-fade-in`.

### Arreglo
```css
/* styles.css */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: .01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: .01ms !important;
    }
}
```
Y para destacar el CTA sin animar la opacidad, un `box-shadow` fijo con el esmeralda
(que ya existe como `shadow-primary/30`).

---

## B5. `ARQUITECTURA.md` quedó desactualizado en el stack de estilos

La sección **1.2 "DaisyUI 4.7.2 y los temas"** dice que DaisyUI se carga por CDN desde
jsDelivr en `base.html:64`. En el código actual eso ya no pasa: `tailwind.config.js:38`
tiene `plugins: [require('daisyui')]` y compila `corporate`, `business` y `dark` dentro
de `theme/static/css/tailwind.css` (173 KB). El `base.html` real ni menciona jsDelivr.

También conviene documentar ahí el motivo por el que `dark` sigue compilado
(está explicado en el comentario de `tailwind.config.js:39-52` pero no en el documento).

---

# 🛠 Herramientas: los scripts de auditoría dan falsos positivos (y falsos negativos)

Versiones corregidas en `…/scratchpad/auditoria/ds/`. **Ninguna toca el repo ni la base.**

## H1. `verificar_mobile.py` — confirmado: el "lobo" eran botones invisibles… y el login

**Dos bugs, no uno.**

### (a) El login no entra, y nadie se entera

```python
pag.fill('input[name=username]', 't@t.com')
pag.fill('input[name=password]', 'test12345')
```

Ese usuario no existe. El POST **no lanza excepción**, así que el `except` no salta y el
script sigue como anónimo. Verificado:

```
despues del login -> http://localhost:8010/accounts/login/      ← no entró
  /torneos/admin/2/gestionar/   status=200  url_final=http://localhost:8010/
  /torneos/admin/listado/       status=200  url_final=http://localhost:8010/
  /torneos/admin/dashboard/     status=200  url_final=http://localhost:8010/
  /torneos/admin/embudo/        status=200  url_final=http://localhost:8010/
  /equipos/admin/listado/       status=200  url_final=http://localhost:8010/
  /accounts/perfil/             status=200  url_final=.../accounts/login/?next=/accounts/perfil/
```

**El script dice que audita 15 pantallas y en realidad mide la home 6 veces.** Como el
status es 200, no hay ninguna señal de que algo anda mal. Por eso todas las filas del
informe salen con los mismos números (`barras=3/4 desal=2`).

### (b) Los botones invisibles cuentan como barra desalineada

El bloque de `desalineadas` no filtra por visibilidad (el filtro `r.width === 0` solo
está en el bucle de `fuera`). El `Registrarse` del navbar es `hidden md:inline-flex`:
a 375px mide **0px** y rompe el conteo de cualquier barra que lo contenga.

**Reproducido lado a lado, mismas 15 rutas:**

```
                                   calculo ACTUAL      ->  ignorando invisibles
/                                  2/4 barras mal          0/1
/torneos/abiertos/                 2/3                     0/0
/torneos/circuitos/                2/3                     0/0
…
paginas marcadas como problematicas:
  con el script actual : 7/15      (y 15/15 con su propio login roto)
  ignorando invisibles : 0/15
```

### Arreglo → `ds/verificar_mobile_corregido.py`

1. Login por rol con las cuentas que sí existen, y **assert**: si la URL sigue siendo
   `/accounts/login`, aborta en vez de seguir mudo.
2. Después de cada `goto`, compara `pg.url` con la ruta pedida; si redirigió, lo dice y
   **no la cuenta**.
3. `visible()` real: descarta `width/height = 0`, `checkVisibility()` y lo que está fuera
   de pantalla (el drawer).
4. Si al filtrar queda **un solo** botón, no es una barra: no se evalúa.
5. Cuando sí hay desalineación, imprime los anchos y los textos, para que sea accionable.

**Resultado del script corregido: `0/15` pantallas con problemas, y las 15 medidas de
verdad.** El layout mobile está sano; lo que estaba roto era el medidor.

---

## H2. `auditoria_ui.py` — mismo login roto: los totales están inflados por repetición

Hereda las dos cuentas inexistentes. De sus 16 rutas, 6 terminan en la home y 1 en el
login. Comparación de los totales:

| Métrica | Original (16 "pantallas") | Corregido (19 pantallas reales) |
|---|---|---|
| Botones auditados | 266 | **190** |
| Target < 40px | 57 | **47** |
| Texto < 11px | 73 | **15** |
| Inputs sin label | — | **30 de 42** |

La diferencia en "texto < 11px" (73 → 15) es casi toda la home contada seis veces más el
menú lateral cerrado. El hallazgo de fondo es correcto (hay texto de 8px en la home), pero
la magnitud no.

### Arreglo → `ds/auditoria_ui_corregido.py`
Login verificado por rol, detección de redirección, filtro de visibilidad que excluye el
drawer, y encima:
- target contra los **tres** umbrales que importan (24px WCAG AA / 40px regla del repo /
  44px HIG);
- inventario de cuántos radios, sombras, tamaños de texto y alturas de botón distintos
  hay (que es la métrica de "sistema de diseño");
- emoji usados como ícono, con su tamaño renderizado, al lado del inventario de SVG;
- jerarquía de headings;
- `sys.stdout.reconfigure(encoding='utf-8')`, porque en Windows el reporte con emoji
  revienta con `UnicodeEncodeError`.

---

## H3. `auditoria_modo_claro.py` — el "0 de 27" es un falso negativo

El script reporta 0 pantallas con texto ilegible. El barrido WCAG real sobre las mismas
pantallas da **516 de 1193 nodos por debajo de AA en el tema claro**. Cuatro causas:

| # | Problema | Efecto medido |
|---|---|---|
| 1 | Usa una **resta** de luminancias gamma con umbral 45/255 en vez del ratio WCAG | Dos grises separados 45 puntos dan **1.76:1** y pasan el filtro |
| 2 | **Ignora el alpha del color del texto**. `text-base-content/50` se mide como si fuera opaco | El pie de página entero (34 pantallas) pasa, midiendo **3.18:1** y **1.83:1** |
| 3 | No compone fondos semitransparentes (`bg-base-200/50`) sobre su ancestro | fondos mal estimados |
| 4 | Solo mide **tema claro**, a **1280px** (escritorio) | el tema oscuro, con 482 nodos por debajo de AA, nunca se mira; y la app se usa en el celular |

> El comentario del script sobre oklch y el `<canvas>` es **correcto** y está bien
> resuelto. El problema no es cómo lee el color: es qué hace con él después.

### Arreglo → `ds/auditoria_contraste_corregido.py` (+ `audit_contraste.py`, `reporte_contraste.py`)
- Ratio WCAG 2.1 de verdad: luminancia relativa con canales linealizados.
- Alpha del texto × opacidad heredada de toda la cadena, compuesto sobre el fondo.
- Fondo efectivo = composición de **todas** las capas semitransparentes hasta la primera
  opaca; si hay imagen o gradiente de fondo, se **descarta** el nodo (no se inventa).
- Umbral por tamaño: 3:1 para texto grande (≥24px, o ≥18.66px y bold), 4.5:1 para el resto.
- Corre los **dos temas**, a **390px**.
- Mide también el borde de los controles (WCAG 1.4.11).
- Marca aparte lo que está dentro del drawer cerrado, para no mezclar lo que el usuario
  ve hoy con lo que verá al abrir el menú.
- Agrupa por **causa** (combinación color/fondo), no por nodo: 55 combinaciones explican
  los 516 fallos, y arreglando las 6 primeras se resuelven ~290.

---

# Lo que está bien (para no tocarlo)

Vale decirlo porque son decisiones que **funcionan** y conviene no romper al arreglar lo demás:

- **No hay desborde horizontal en ninguna de las 15 pantallas** medidas a 375px
  (`desborde=0px` en todas). Las reglas de `styles.css` cumplen su función.
- **Foco visible**: de 809 paradas de tabulación, **808 cambian de estilo al enfocarse**
  (outline en 495, outline + fondo en 313). Mirando además el *color* del outline,
  **41 quedan sin indicador real** (outline transparente y sin cambio de fondo) — casi
  todos `ul.dropdown-content`, que no deberían ser focusables, más un
  `summary.collapse-title` en la ficha de torneo. El indicador del menú lateral es flojo
  (un tinte al 10 %, ~1.2:1) pero existe. **No hay un problema sistémico de foco**: el
  que sí hay es el del drawer cerrado (A5).

  > Ojo al medir esto: el indicador de DaisyUI entra con una transición de 0.2s. Si se
  > lee `getComputedStyle` inmediatamente después del `Tab`, se lee el valor intermedio
  > y parece que no hay foco. Los scripts de `ds/` congelan las transiciones antes de
  > medir.
- **Íconos SVG**: 681 renderizados, el 99 % en **3 tamaños** (20/16/24px). Es el
  subsistema más consistente de la app.
- **Botones de solo ícono**: **0 sin nombre accesible** — todos tienen `aria-label` o
  `title`.
- **Imágenes**: **0 sin `alt`** (53 en templates, 37 visibles en el barrido).
- **Una sola familia tipográfica** (Inter) en 1543 de 1544 nodos.
- **`lang="es"`** en todas las pantallas.
- **Tema oscuro**: el `.btn-primary` mide 6.86:1 y el `.badge-primary` 8.54:1. El
  problema de color es del tema claro, no del oscuro.

---

# Orden sugerido

| # | Qué | Dónde | Esfuerzo | Qué resuelve |
|---|---|---|---|---|
| 1 | Sacar `text-white` de los alerts + arreglar `--suc` | `base.html:725`, `:88-97` | 2 líneas | A2 — 4 tipos de aviso ilegibles |
| 2 | Tinta oscura en `.btn-primary` del tema claro | `base.html:115` | 1 línea | A1 — 166 botones, 34 pantallas |
| 3 | `#065f46` como tinta para `text-primary` / links | `styles.css` + `base.html:136` | ~10 líneas | A1 — texto y links de marca |
| 4 | Piso de 78 % para el texto atenuado | `styles.css` | ~6 líneas | A3 — 305 declaraciones |
| 5 | `inert` en el drawer cerrado | `base.html` | ~5 líneas | A5 — 43 % del orden de tabulación |
| 6 | Redefinir `--s`, `--a`, `--in` y borrar los overrides | `base.html:121-136` | neto: −10 líneas | M3 — tarjeta magenta, alerts azules |
| 7 | Borde de inputs a 3:1 | `styles.css` | 4 líneas | M2 — 65 de 88 campos |
| 8 | `color-scheme: light` en el `@media print` global | `styles.css` | 1 línea | M8 — margen negro al imprimir |
| 9 | Partial `campo.html` + `for=` | 22 templates | medio | M1 — 80 labels |
| 10 | Migrar el `✕` y el `📲` a SVG | 14 lugares | medio | A4 — la parte más visible |
| 11 | Un `<h1>` por pantalla | 12 templates | medio | M7 |
| 12 | Target: `btn-circle` 40px, `btn-xs` fuera de tablas | `styles.css` | ~8 líneas | M6 — 136 controles |

Los primeros 8 son todos reglas globales en `styles.css` / `base.html`, que es la
convención del proyecto: **~40 líneas de CSS resuelven los cinco hallazgos de impacto alto.**

---

# Anexo: qué hay en `scratchpad/auditoria/ds/`

Nada de esto toca el repo ni la base de datos. Todo corre contra
`http://localhost:8010` con el venv del proyecto (`./venv/Scripts/python.exe`).

## Reemplazos de los scripts del repo

| Script | Reemplaza a | Qué arregla |
|---|---|---|
| `verificar_mobile_corregido.py` | `verificar_mobile.py` | login real + detección de redirección + filtro de visibilidad. **15/15 → 0/15** |
| `auditoria_ui_corregido.py` | `auditoria_ui.py` | lo mismo + inventario de tokens, emoji vs SVG, headings, 3 umbrales de target |
| `auditoria_contraste_corregido.py` | `auditoria_modo_claro.py` | ratio WCAG real, alpha del texto, fondos compuestos, los dos temas, 390px |

## Motores y datos

| Archivo | Para qué |
|---|---|
| `paginas.py` | lista de 35 pantallas + cuentas + helper de login por rol |
| `audit_tokens.py` | barrido de tokens, botones, íconos, headings y foco (`<tema> <salida.json>`) |
| `audit_contraste.py` | barrido de contraste WCAG (`<tema> <salida.json>`) |
| `reporte_tokens.py` / `reporte_contraste.py` | resúmenes legibles de los JSON |
| `inventario_estatico.py` | parseo de los 108 templates (clases, hex, emoji, labels) |
| `verif_verdes.py` | prueba que `btn-primary` y `badge-primary` usan verdes distintos |
| `verif_alertas.py` | mide los 4 tipos de alert con y sin `text-white` |
| `diag_verificar_mobile.py` | reproduce el cálculo viejo y el nuevo lado a lado |
| `tokens_*.json`, `contraste_*.json`, `rep_*.txt` | datos crudos y reportes de esta corrida |
| `shot_secondary_dark.png` | la tarjeta rosa del perfil del organizador (M3) |
| `shot_home_light.png`, `shot_drawer_focus.png` | capturas de apoyo |

Para reproducir todo:

```bash
# el server ya tiene que estar en 8010
./venv/Scripts/python.exe scratchpad/auditoria/ds/verificar_mobile_corregido.py
./venv/Scripts/python.exe scratchpad/auditoria/ds/auditoria_ui_corregido.py
./venv/Scripts/python.exe scratchpad/auditoria/ds/auditoria_contraste_corregido.py
```
