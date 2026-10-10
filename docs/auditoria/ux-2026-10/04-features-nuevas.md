# Auditoría 04 — Funcionalidades nuevas

**Alcance:** pantalla del club para TV (43ed2da), alta en 2 pasos y aviso de jugador
existente (d3a8da4 / 1e061d4 / 72176a3), rediseño del popup de resultado (386f228),
páginas de error propias (f69d862) y la planilla de programación como pantalla.

**Entorno medido:** server en `localhost:8010`, Chromium (Playwright).
TV a **1920×1080** y **1280×720**; el resto a **375×812**, en **claro y oscuro**.
No se escribió nada en la base: los formularios se abrieron y se instanciaron en
memoria (`is_valid()` no guarda), y las placas que la semilla no produce se
renderizaron con las plantillas reales y datos armados en memoria.

**Qué NO se repite:** los 36 hallazgos de `docs/auditoria/hallazgos.json`.

---

## Cómo se midió la legibilidad de la TV

La TV mide todo en `rem` y el `rem` sale de `min(1.7vh, 0.95vw)`, así que el tamaño
**físico** de cada texto es un porcentaje fijo del alto de la pantalla
(18,24px a 1080p y 12,16px a 720p = el mismo tamaño físico en la misma tele; eso
está bien resuelto y no es un hallazgo).

Para traducirlo a "¿se lee a 3 metros?" se usó la regla AVIXA/ANSI **1:200**
(distancia máxima ≈ altura de mayúscula × 200) y la altura de mayúscula de Inter
(0,727 em). Alto útil de pantalla: 43" = 535 mm, 50" = 623 mm, 55" = 685 mm,
65" = 810 mm.

| Elemento | % del alto | 50" | 55" | 65" |
|---|---|---|---|---|
| Título de la placa (`h2`) | 4,06 % | 3,7 m | 4,0 m | 4,8 m |
| Nombre del club | 3,38 % | 3,1 m | 3,4 m | 4,0 m |
| Cancha: pareja (3–6 canchas) | 2,91 % | **2,6 m** | 2,9 m | 3,4 m |
| Resultados / Próximos: pareja | 2,87 % | **2,6 m** | 2,9 m | 3,4 m |
| Zonas: pareja (3–4 zonas) | 2,78 % | **2,5 m** | 2,8 m | 3,3 m |
| Llave: pareja, 2–3 rondas | 2,84 % | **2,6 m** | 2,8 m | 3,3 m |
| Zonas: pareja (5–6 zonas) | 2,28 % | **2,1 m** | 2,3 m | 2,7 m |
| Cancha: pareja (7–8 canchas) | 2,33 % | **2,1 m** | 2,3 m | 2,7 m |
| **Llave: pareja, 4 rondas (16 equipos)** | 1,59 % | **1,4 m** | 1,6 m | 1,9 m |
| **Llave: pareja, 5 rondas (32 equipos)** | 0,81 % | **0,7 m** | 0,8 m | 1,0 m |
| **Llave: pareja, 6 rondas (48 equipos)** | 0,41 % | **0,4 m** | 0,4 m | 0,5 m |
| Línea "Después" (7–8 canchas) | 1,76 % | 1,6 m | 1,8 m | 2,1 m |
| Lista de torneos / marca TodoPadel | 1,69 % | 1,5 m | 1,7 m | 2,0 m |

**Respuesta directa:** los **títulos** sí se leen a 3 m. Los **datos** (quién juega,
el marcador, la tabla) **no** llegan a 3 m en una tele de 50"; empatan recién en una
de 65". Y la llave, en cuanto el cuadro pasa de 8 equipos, se va a menos de 1,5 m.
Si la tele del club es de 50" o menos, hay dos caminos: subir el `rem` base
(de `min(1.7vh, 0.95vw)` a ~`min(2.2vh, 1.2vw)`, mostrando menos cosas por placa) o
paginar más (menos canchas y menos zonas por placa).

---

## ALTO

### A1. La llave se vuelve ilegible en cuanto el cuadro crece (y es la placa más larga)
`torneos/templates/torneos/pantalla/pantalla.html:278-296` (`ajustarLlave`) ·
`torneos/pantalla.py:373-387` (`_placas_llave`)

`ajustarLlave` calcula `esc = Math.min(mw/w, 1.6)` y, si no entra de alto, lo
**reemplaza** por `mh/h` sin ningún piso. La altura natural crece lineal con la
cantidad de partidos de la primera ronda, así que la escala se derrumba.

Medido renderizando la placa real con 2 a 6 rondas:

| Rondas (equipos) | Escala aplicada | Texto efectivo @1080p | % del alto | Se lee desde (50") |
|---|---|---|---|---|
| 2 (4) | 1,600 | 30,6 px | 2,84 % | 2,6 m |
| 3 (8) | 1,598 | 30,6 px | 2,83 % | 2,6 m |
| 4 (16) | **0,894** | 17,1 px | 1,59 % | **1,4 m** |
| 5 (32) | **0,456** | 8,7 px | 0,81 % | **0,7 m** |
| 6 (48) | **0,230** | 4,4 px | 0,41 % | **0,4 m** |

Idéntico a 1280×720 (0,882 / 0,450 / 0,227). El producto soporta cuadros FAP de
hasta 48 equipos (`torneos/formats.py:FAP_LLAVES`, `_BRACKET_TYPE_POR_RONDAS` llega
a `16vos`), así que 5 y 6 columnas son casos reales, no teóricos. Encima la placa de
llave dura **20 s**, la más larga de todo el carrusel (`pantalla.py:50-52`).

**Por qué importa:** la gente se para frente a la tele justamente a buscar su partido
en la llave. Hoy, en un torneo de 16 equipos, hay que acercarse a metro y medio.

**Arreglo concreto:** paginar la llave como ya se pagina todo lo demás (`_paginar`):
máximo 3 columnas por placa (p. ej. "16vos y octavos" / "cuartos, semis y final"),
con `clave` estable (`llave-{pk}-1`, `llave-{pk}-2`). Y en `ajustarLlave`, poner un
piso de escala (≈0,85): si no entra, es señal de que hay que partir la placa, no de
que haya que encoger la letra.

### A2. La TV marca mal quién clasifica en los formatos FAP
`torneos/pantalla.py:352` → `clasifican = fp.clasifican_por_grupo if fp else 2`

Cuando el torneo **no** tiene formato personalizado —que es exactamente cuando se usa
el cuadro oficial FAP— la TV pinta en verde sólo al 1° y al 2° de cada zona. Pero los
cuadros FAP que trae la app meten terceros al play-in. Leído de
`torneos/formats.py:FAP_LLAVES`:

- **16 equipos** (zonas de 4,3,3,3,3): Zona A clasifican las posiciones **[1, 2, 3]**;
  B, C, D y E, [1, 2].
- **20 equipos**: Zonas A y B **[1, 2, 3]**; C a F, [1, 2].
- En total, **25 de los tamaños FAP** (16, 20, 32, 48…) llevan algún 3° al cuadro.

Y la contradicción queda **en la misma pantalla**: `_PLACEHOLDER_ZONA`
(`pantalla.py:55` y `:144`) convierte el placeholder `3A` en "**3° Zona A**" y lo
muestra en la placa de llave. O sea: la placa de llave dice "va a jugar el 3° de la
Zona A" y la placa de zonas, dos placas antes, muestra a ese mismo 3° sin marcar.

**Por qué importa:** es un dato público, en la tele del club, sobre quién sigue en
carrera. Una pareja que está 3ª y sí clasifica se ve "afuera" y se va del club.

**Arreglo concreto:** derivar las posiciones por zona en vez de hardcodear 2. Sin
queries extra: `armar_pantalla` ya tiene `llaves` (todos los `Partido` del torneo) en
la mano — basta juntar los `placeholder_e1`/`placeholder_e2` que matcheen
`^\d+[A-Za-z]$`, agruparlos por letra de zona y marcar esas posiciones; si no hay
placeholders (cuadro ya poblado), leer `formats.FORMATS[n]`. Dejar el 2 sólo como
último recurso.

### A3. El popup de zona no acepta super tie-break, y con W.O. queda trabado en silencio
`torneos/forms.py:326` (`'max': '7'`) · `torneos/templates/torneos/partials/_form_resultado.html:150`

Dos cosas, las dos verificadas en el navegador con el popup real.

**(a) El set a 10 no entra, y sólo en el popup de zona.** Medido con 10-8 en el set 3:

| Popup | `max` de los casilleros | `form.checkValidity()` | Campos inválidos |
|---|---|---|---|
| Zona (`/torneos/admin/grupo/4/resultado/`) | `7` | **False** | `e1_set3=10`, `e2_set3=8` — *"Value must be less than or equal to 7"* |
| Llave (`/torneos/admin/partido/1/resultado/`) | *(vacío)* | **True** | ninguno |

htmx no manda un form que falla la validación nativa, así que el mismo marcador se
guarda desde la llave y se rechaza desde la zona, con dos popups que se ven iguales.
El modelo no tiene ese techo (`PositiveSmallIntegerField`, `torneos/models.py:432-436`)
y el propio módulo de la TV documenta `[(6, 4), (3, 6), (10, 8)]` como ejemplo de sets
(`torneos/pantalla.py:71`). También quedan afuera los 8-6 y 9-7 de algunos formatos.

**(b) Con "Walkover" el guardar no hace nada y no dice nada.** `verCasoEspecial()`
oculta el bloque de sets pero **no deshabilita** los inputs. Medido tras elegir W.O.
con 10-8 ya tipeado:

```
sets ocultos: True · deshabilitados: False · valores siguen: 6,4,4,6,10,8
form.checkValidity(): False · reportValidity(): False
consola: "An invalid form control with name='e1_set3' is not focusable."
          "An invalid form control with name='e2_set3' is not focusable."
```

El organizador toca "Guardar resultado" y la pantalla no se mueve: el navegador no
puede mostrar el globito porque el campo inválido está oculto. Al borde de la cancha,
eso se lee como "la app se colgó". (El servidor ya limpia los sets en W.O.,
`forms.py:350-358`: el problema es 100 % del lado del cliente.)

**Arreglo concreto:** sacar `'max': '7'` y validar en `clean()` con un mensaje legible
("Un set no puede tener más de 7 games, salvo el super tie-break"); y en
`_form_resultado.html`, deshabilitar los inputs de sets cuando `resolucion === 'W'`,
que es exactamente el truco que ya usa `_form_sin_cuenta.html:280` ("un `required`
invisible bloquea el submit sin que se vea por qué" — la lección está escrita en el
repo, falta aplicarla acá).

### A4. La contraseña que genera el alta tiene 9.000 combinaciones y el login no tiene throttle
`accounts/identidad.py:32-36` (`generar_password`) · `accounts/views.py:50-78` (`CustomLoginView`)

```python
def generar_password(nombre):
    base = re.sub(r'[^a-z]', '', _sin_acentos(nombre).strip().lower())[:12] or 'padel'
    return f"{base}{secrets.randbelow(9000) + 1000}"
```

La parte variable son 4 dígitos: **9.000 posibilidades**, y la parte fija es el nombre
de la persona, que viaja en el mismo WhatsApp (`mensaje_credenciales`, línea 235).
`CustomLoginView` no tiene ningún límite de intentos — y no es que el patrón no exista
en el repo: el código de 6 dígitos del mail sí lo tiene (8 intentos / 15 min,
`accounts/views.py:132`) y el buscador público también (60 / 10 min,
`torneos/views.py:3002`). Falta justamente en el login con contraseña.

`debe_cambiar_password` cierra la ventana recién cuando la persona entra por primera
vez, y la mitad de estas cuentas se crean para gente que nunca va a entrar.

**Arreglo concreto:** subir la entropía (8 caracteres de un alfabeto sin ambiguos,
`'23456789abcdefghjkmnpqrstuvwxyz'` → ~10^12, sigue siendo dictable por WhatsApp) y
agregar throttle por `email+IP` en `CustomLoginView.form_invalid`, copiando el patrón
de cache de `BuscarCompaneroPublicoView`.

---

## MEDIO

### M1. `?t=` no filtra las inscripciones: una TV dedicada a una categoría muestra otra
`torneos/pantalla.py:316` y `:390-397` (`_placas_inscripcion(organizacion)`)

`?t=12,15` está documentado como "dedicar una TV a ciertas categorías"
(`pantalla.py:400-402`), pero `_placas_inscripcion` no recibe `torneo_ids`: lista
**todos** los torneos ABIERTO del club. Medido:

- `/tv/club-demo/?t=3` (torneo 3 = EN JUEGO, sin zonas ni partidos) → placas: **sólo
  `inscripcion`**, y el torneo que muestra es el **2**, que no es el que se pidió.
- `/tv/club-demo/?t=4` (FINALIZADO fuera de ventana) → lo mismo.

Y hay un efecto de arrastre: como esa placa igual se agrega, `placas` nunca queda
vacío y **la placa `vacia` jamás aparece**. Una TV apuntada a una categoría a la que
todavía no le cargaron nada no dice "todavía no arrancó": muestra las inscripciones de
otro torneo.

**Arreglo:** pasarle `torneo_ids` a `_placas_inscripcion` y filtrar; y chequear el
estado vacío *después* de aplicar el filtro.

### M2. La tabla de posiciones se recorta en la placa de zonas
`torneos/templates/torneos/pantalla/pantalla.html` → `.zona { overflow: hidden }` y
`.grilla-zonas.n3 .zona, .grilla-zonas.n4 .zona { font-size: 1.65rem }`

Barrido de 108 combinaciones (1–6 zonas × 3–5 parejas × 3 largos de nombre, en 1080p y
720p): **24 recortan la tabla**, siempre independiente del largo del nombre.

| Viewport | Zonas × parejas | Px cortados | Equivale a |
|---|---|---|---|
| 1920×1080 | **4 × 4** | 22 px (fila = 61 px) | media fila |
| 1920×1080 | **4 × 5** | 83 px | 1,4 filas |
| 1920×1080 | 5 × 5 y 6 × 5 | 15 px (fila = 51 px) | 0,3 filas |
| 1280×720 | **4 × 4** | 16 px (fila = 41 px) | media fila |
| 1280×720 | **4 × 5** | 57 px | 1,4 filas |

La causa es el `font-size` por **cantidad de zonas**: con `n4` la grilla es 2 columnas
× 2 filas, o sea celdas de 911×355 px — el mismo alto que `n5`/`n6`, que usan
1,35rem — pero `n4` usa 1,65rem. Y zonas de 4 no es un caso raro:
`Torneo.equipos_por_grupo` es un campo libre (`torneos/models.py:116`) y existe
`formato_grupos_4`.

**Arreglo:** que el `font-size` dependa de las **filas de la grilla** y no de la
cantidad de zonas (`n4` → 1,35rem igual que `n5`/`n6`), o usar
`clamp()` con el alto de la celda. Y como red de seguridad, un test que falle si
`.zona` tiene `scrollHeight > clientHeight` en cualquier combinación.

### M3. La placa estrella no aparece nunca si nadie carga la cancha, y nada lo avisa
`torneos/pantalla.py:211-213` · `torneos/templates/torneos/schedule_form.html:20-26`

`armar_canchas` saltea cualquier partido sin `cancha` (`if not p.cancha: continue`), así
que "En cancha ahora" simplemente **no existe** como placa. En la base de desarrollo
**0 de 22 partidos** tiene cancha cargada, y la placa efectivamente no apareció en
`/tv/club-demo/` (placas reales: `resultados-1`, `resultados-2`, `llave-1`,
`inscripcion`).

El campo está bien hecho (opcional, con `<datalist>` y botones de las canchas ya
usadas), pero el único lugar donde se explica que de ahí sale la pantalla del club es
un **comentario de plantilla invisible**:

```
{% comment %} ... Con hora y cancha cargadas, la pantalla del club (/tv/)
muestra el partido en esa cancha. {% endcomment %}   ← schedule_form.html:23-26
```

Lo que el organizador ve es "Cancha *(opcional)*".

**Arreglo:** mover esa frase al `help_text` visible, y cuando la TV no tenga ninguna
cancha mostrar la placa `vacia` con el texto accionable: "Cargá la cancha al programar
los partidos y acá vas a ver qué se juega en cada una".

*(Verificado aparte: con datos en memoria la placa de canchas renderiza bien con 1 a 8
canchas. Con 7-8 el texto baja a 2,33 % del alto — ver la tabla de legibilidad — y la
línea "Después" se corta con elipsis: 592 px de texto en 405 px de columna.)*

### M4. El aviso de "ya está cargado" no ofrece la acción que promete
`accounts/templates/accounts/dummy_user_form.html:30-55` y `:101-108`

El panel funciona: con el mismo email, `is_valid()` da False, `coincidencias` trae
`[('Andres Aquindo', 'Tiene ese mismo email', seguro=2)]` y no se crea nada
(28 usuarios antes y después). Contraste del panel: 12,6:1 el título, 8,9:1 el cuerpo.

El problema es qué se puede **hacer** con el aviso. Medido, las únicas tres acciones de
la pantalla son:

| Acción | Qué es | Tamaño |
|---|---|---|
| "Ver ficha" | `<a href="/accounts/jugador/1/">` **sin `target`** | 87×40 |
| "Crear igual" | `button.btn.btn-primary.btn-block` | 245×44 |
| "Cancelar" | `a.btn.btn-ghost.btn-sm` → ajustes | 245×44 |

El panel dice "**Si es alguno de estos, usalo**" y **no hay ningún botón para usarlo**.
Peor: el panel está *fuera* del `<form>` (línea 25 vs. 58), así que "Ver ficha" navega
en la misma pestaña y se pierde todo lo tipeado — y es el único camino para comprobar
si es la misma persona. Mientras tanto, "Crear igual" es el botón **primario, verde y a
todo el ancho** en una pantalla cuyo único propósito es evitar que se cree el duplicado.

**Arreglo:** (1) `target="_blank" rel="noopener"` en "Ver ficha"; (2) agregar
"**Es esta persona**" como acción primaria (lleva a la ficha, o directamente al flujo
desde donde se venía); (3) bajar "Crear igual" a `btn-outline btn-warning`. El checkbox
"es otra persona" ya está y está bien: lo que falla es la jerarquía visual.

### M5. Los radios que deciden toda la rama del paso 2 son los nativos de 13×13 px
`torneos/templates/torneos/partials/_form_sin_cuenta.html:102-107` ·
`torneos/forms.py:1117-1120`

`companero_tiene_cuenta` se declara `widget=forms.RadioSelect` sin `attrs`, y la
plantilla imprime `{{ opcion.tag }}` crudo. Medido a 375×812: **13×13 px** cada radio,
en una fila de label de ~28 px de alto. El `<label>` envuelve el radio (el área de
toque es la fila), pero el control que la persona *ve y apunta* mide 13 px, y no se
parece a ningún otro control de la app: la pantalla hermana de alta de jugador sí usa
`class="checkbox checkbox-warning"` (`dummy_user_form.html:92`).

Es la decisión más importante del paso 2 —"ya tiene cuenta" vs "no tiene cuenta",
que es lo que evita el duplicado— tomada con el control más chico de la pantalla.

**Arreglo:** `widget=forms.RadioSelect(attrs={'class': 'radio radio-primary'})` y
`py-3` en el label para llegar a 44 px.

### M6. `buscar_coincidencias` recorre toda la tabla de usuarios en cada alta
`accounts/identidad.py:175-179`

```python
con_tel = vivos.exclude(numero_telefono='').exclude(numero_telefono__isnull=True)
for u in con_tel:                                   # ← sin slice, sin filtro
    if _cola_telefono(u.numero_telefono) == cola:
```

`vivos` trae `select_related('division')` y **todas** las columnas (incluido el hash de
contraseña y la imagen). Verificado: el SQL generado **no tiene LIMIT**. Esto corre en
el `clean()` del form, o sea una vez por cada alta de jugador.

Contradice su propio docstring, tres líneas más arriba (`identidad.py:147-149`): *"La
consulta está acotada a propósito —mail exacto, teléfono exacto y apellidos que
empiezan igual— para no recorrer la base entera en cada alta"*. El bloque de nombre sí
está acotado (`[:200]`); el de teléfono no.

Y la función de al lado ya lo hace bien: `buscar_jugador` (`identidad.py:104-109`) usa
`.values_list('id', 'numero_telefono')` y después trae sólo el match.

**Arreglo:** copiar ese patrón (dos columnas, filtrar en Python, `filter(pk__in=ids)`).
Son dos líneas. *(En desarrollo hay 0 jugadores con teléfono, así que hoy no se nota:
es un problema de producción.)*

---

## BAJO

### B1. El indicador de paso casi no se ve, y es lo único que dice dónde estás
`torneos/templates/torneos/partials/_form_sin_cuenta.html:37-41` y `:214-218`

Medido con contraste real (canvas, no parseando oklch):

| Elemento | Claro | Oscuro |
|---|---|---|
| "Paso 1 de 2 · Tus datos" (12 px, `opacity-60`) | 4,54:1 | **3,45:1** ← falla AA |
| Rayita inactiva (`oklch(var(--bc) / .18)`, 26×4 px) | 1,18:1 | — |

AA pide 4,5:1 para texto normal menor a 24 px. En oscuro no llega. Y el refuerzo
visual son dos rayitas de 26×4 px, una de ellas casi invisible.

**Arreglo:** `text-sm font-semibold` sin `opacity` (o `opacity-80`), y subir la
inactiva a `oklch(var(--bc) / .35)` con 6 px de alto.

### B2. La página 500 pide que avisen y no da por dónde, y "ya quedó registrado" es a medias
`templates/500.html:66-72` · `padel_project/settings.py:360-389`

Dice *"Ya quedó registrado"* y *"Si sigue pasando, avisanos y lo miramos"*, sin ningún
canal: ni WhatsApp, ni mail. Y como la página se renderiza sin `request` (bien
documentado en el comentario), no puede armar un link dinámico.

Sobre "ya quedó registrado": `LOGGING` tiene un solo handler, `console`. No hay
`ADMINS` ni `mail_admins`, ni Sentry. El traceback va al stream de logs de Render y
nadie recibe nada.

**Arreglo:** hardcodear el link de WhatsApp que ya usa el footer
(`https://wa.me/5492236886313`) y, o se enchufa reporte de errores, o se suaviza la
frase a "Lo vamos a ver".

### B3. Contraste del botón blanco sobre el verde de marca
Medido: el único botón del 500 ("Volver al inicio", blanco 15 px bold) da **3,64:1** en
claro y **2,76:1** en oscuro. En el 404, el label "O buscá lo que necesitás" (12 px) da
**3,18:1**.

Aviso importante: blanco sobre `btn-primary` mide **2,54:1** en toda la app — los
botones de base.html incluidos ("Ir al inicio", "Buscar", "Instalar la app"). O sea
que esto es una decisión de tema, no de estas pantallas; lo anoto acá porque toca a las
páginas nuevas, pero merece una pasada aparte y no un parche local.

### B4. La placa vacía afirma algo que no siempre es cierto
`torneos/pantalla.py:322-323` · `torneos/templates/torneos/pantalla/_placas.html:174`

La placa `vacia` siempre dice "Por ahora no hay partidos en juego". Reproducido con
`/tv/club-demo/?solo=sponsors` (el club no tiene sponsors cargados): la placa aparece
con ese texto cuando el motivo real es el filtro `?solo=` / que no hay sponsors.
Cuatro líneas de copy condicional según por qué quedó vacío.

### B5. Un alias mal escrito en la TV cae en el 404 del celular
`torneos/pantalla.py:424` (`get_object_or_404`)

`/tv/no-existe/` → 404 → `templates/404.html`, que extiende `base.html`: en la tele del
club aparece la navbar, el drawer, "📲 Instalar la app" y "Esta página no existe", sin
una palabra sobre el alias. Es el error más probable al montar la TV por primera vez.

**Arreglo:** atajarlo en `get_context_data` y renderizar el layout de la TV con
"No encontramos el club «no-existe». Revisá el alias en Ajustes de la organización".

### B6. "Sin division" sin tilde en el buscador de compañero
`torneos/services/alta_sin_cuenta.py:145` → `'Sin division'`

El fallback de la plantilla (`_form_sin_cuenta.html:121`) y `services/placas.py:30`
dicen `'Sin división'`. La misma persona ve las dos formas: medido en vivo, buscando
"pacheco" el buscador devolvió **"Martin Pacheco — Sin division"**, y si el form vuelve
con error se re-pinta como "Sin división".

### B7. Faltan tildes en los rótulos del botón de programar
`torneos/templates/torneos/partials/_grupo_panel.html:191-192` ·
`torneos/templates/torneos/partials/_bracket.html:59-60`

`aria-label="Programar dia y hora del partido"` y `title="Programar dia y hora"`. Un
lector de pantalla lee "dia". De paso, el rótulo no menciona la cancha, que es el otro
campo del modal (y el que alimenta la TV, ver M3).

### B8. "Descargar PDF" abre el diálogo de imprimir
`torneos/templates/torneos/torneo_programacion.html` → `onclick="window.print()"`
(botón medido: 311×44 px)

En Android Chrome el destino por defecto es "Guardar como PDF", así que termina
funcionando; en iOS sale la hoja de compartir. Pero el rótulo promete una descarga y
entrega un diálogo de impresión, y el público es poco técnico.
Sugerencia: "Imprimir o guardar PDF".

### B9. `canchas_usadas()` escanea todo el historial del club por cada apertura del modal
`torneos/pantalla.py:125-136`

Dos `DISTINCT` sobre `PartidoGrupo` y `Partido` de toda la organización, sin cota de
fecha y sobre una columna (`cancha`) sin índice, cada vez que se abre "Programar día y
hora" — que el organizador abre una vez por partido. Hoy es irrelevante; con años de
historial deja de serlo. Cachear por organización unos minutos alcanza.

---

## Lo que está BIEN hecho (conservar)

**Pantalla de TV**

- **Es barata.** Medido con el test client de Django: `armar_pantalla` = **6 queries /
  9 ms**; el request completo `?parcial=1` = **8 queries / 11 ms**, 19 KB. Refrescar
  cada 30 s es perfectamente sostenible. *(Los ~2 s que se ven por HTTP son del
  `runserver` de desarrollo, no de la vista: no hay hallazgo de performance acá.)*
- **La rotación y el auto-refresco funcionan de verdad.** Verificado en 105 s:
  pedidos a `?parcial=1` en 31,0 / 61,1 / 91,2 s, y la secuencia de placas
  `resultados-1 → resultados-2 → llave-1 → inscripcion → resultados-1 …` con los
  tiempos declarados (14/14/20/12 = ciclo de 60 s). El carrusel **no vuelve a empezar**
  cuando llegan datos nuevos: el truco de `data-clave` + "cambiar sólo al pasar de
  placa" (`pantalla.html:320-337`) es la decisión correcta y está bien implementada.
- **El criterio técnico para el medio es muy bueno y poco común:** no usar
  Tailwind/DaisyUI a propósito (oklch no existe en el Chromium viejo de Tizen/webOS),
  todo en `vh` para que el tamaño físico no dependa de la resolución, reloj del
  servidor (las TVs tienen la hora mal), `wakeLock`, "Mandar a la TV" con la Window
  Management API, recarga cada 3 h **condicionada a que haya conexión**, y el cartel
  "Sin conexión · mostrando lo último". Cero errores de JS en todas las corridas.
- Nombres largos: en canchas, resultados y zonas el nombre **envuelve**
  (`overflow-wrap: break-word`), que es lo correcto. Sólo la llave trunca con elipsis
  (columna fija de 19rem): con el nombre más largo que hay en la base real
  ("Fernandez Vidal/Villanueva", 26 caracteres) todavía entra; con 37 se corta a la
  mitad (667 px de texto en 319 px). Es una decisión defendible, pero si se pagina la
  llave (A1) sobra ancho para dos renglones.

**Alta en 2 pasos**

- **El buscador público está bien defendido** (`torneos/views.py:2988-3020`,
  `services/alta_sin_cuenta.py:90-148`): mínimo 3 caracteres, máximo 8 resultados,
  email y teléfono **exactos** (no `icontains`), nunca devuelve mail ni teléfono, y
  throttle de 60 búsquedas / 10 min por IP. Es raro ver esto hecho bien.
- **El enganche por teléfono se arregló de verdad:** `DIGITOS_TELEFONO = 10` y
  "con más de un candidato no se adivina" (`identidad.py:44` y `:110-112`) cierran el
  hallazgo conocido #5 ("últimos 8 dígitos y primer match"). El normalizador cubre
  `+54 9`, el `0` de larga distancia y el `15` viejo.
- **El flujo de 2 pasos se comporta.** Verificado en claro y oscuro, a 375×812:
  - "Cargar mi compañero/a" con los campos vacíos **no avanza** (se queda en el paso 1
    y reporta el primer campo inválido).
  - "← Volver a mis datos" vuelve al paso 1 **con los datos intactos** (`nombre` seguía
    siendo lo tipeado), y el rótulo y las rayitas vuelven a "Paso 1 de 2".
  - La rama "ya tiene cuenta" oculta el bloque manual **y le deshabilita los inputs**
    (`manualDeshabilitado: True`), para que un `required` invisible no trabe el submit.
  - El buscador anda: "pacheco" → 2 resultados, se elige uno y queda fijado con el
    nombre, el detalle y "Cambiar" (`companero_id=17`).
  - Si el servidor devuelve errores del compañero, abre directo en el paso 2.
  - Sin scroll horizontal ni elementos fuera de pantalla en ninguno de los dos pasos,
    en ninguno de los dos temas. Cero errores de JS.
- **La detección de duplicados funciona y no escribe nada:** con el mismo email,
  `is_valid()` = False, motivo "Tiene ese mismo email" con `seguro=2`, y la cantidad de
  usuarios no cambió. El panel se lee perfecto (12,6:1 / 8,9:1).

**Popup de resultado**

- **Sí es usable con una mano al borde de la cancha**, medido a 375×812:
  casilleros de sets de **120×56 px** (bien por encima del mínimo), 24 px de letra,
  `tabular-nums`, `inputmode="numeric"` + `type="number"` (teclado numérico), y un
  `aria-label` distinto por casillero ("Games de Galloo/Perez en el set 1").
  El modal mide 344×640 en un viewport de 812 y **entra sin scroll** (`scroll: false`);
  "Guardar resultado" ocupa 304×44 abajo, al alcance del pulgar, y "Cancelar" es
  secundario. La jerarquía de acciones quedó bien.
- **El contador en vivo anda.** Verificado: cargando 6-4 / 4-6 / 6-4 el marcador pasó a
  "2" – "1" y el nombre del que va ganando se pintó con `text-primary`. Es una buena
  idea bien ejecutada para el caso de uso que más se repite.
- **El encabezado ahora dice de qué partido se trata:** "Cargar resultado" /
  "Zona A" / "Galloo/Perez vs Barrionuevo/Sosa" — con los nombres reales, no códigos.
- Unificar los dos popups en un solo `_form_resultado.html` fue la decisión correcta:
  la duplicación era la causa del problema original. (Nota: el `max='7'` de A3 es
  justamente lo que quedó **sin** unificar entre los dos forms.)

**Páginas de error**

- **No son callejones sin salida, y están bien medidas.** 404 / 403 / 400: título de
  24 px a **14:1**, cuerpo de 16 px a **5,8:1**, botones de **343×44**; el 404 además
  trae buscador, y el 403 cambia el CTA según si hay sesión ("Acceder" vs "Mi perfil").
  Ninguna scrollea a lo ancho a 375 px.
- **El 500 está bien pensado y bien documentado:** es la única que no extiende
  `base.html`, a propósito, porque se renderiza sin `request` y porque si lo que se
  rompió es la base o los estáticos una página que depende de ellos se rompe también.
  Colores a mano, `prefers-color-scheme` incluido. Decisión correcta.
- El 0 del 404 dibujado como pelota de pádel en SVG inline es un detalle lindo y no
  cuesta nada.

**Planilla de programación (como pantalla)**

- Limpia en celular: a 375 px el `scrollWidth` es 375 (sin scroll horizontal), las tres
  tablas entran en 311 px y ningún elemento se sale. Lo único chico son los `th`
  ("Hora", "Pareja") a 10 px.

---

## Notas de método / qué no se pudo verificar en vivo

- **Las placas `canchas` y `proximos` no aparecen con la semilla actual**, y no es culpa
  del producto: **0 de 22** partidos tiene `cancha` cargada, y los partidos de llave
  tienen `fecha_hora` del 2026-08-09 (dos meses atrás, fuera de la
  `VENTANA_EN_JUEGO` de 6 h). Las medí renderizando `pantalla.html` con objetos
  `CanchaTV`/`PartidoTV` armados en memoria, sin tocar la base. Si se quiere que la
  auditoría visual futura las cubra, hace falta semilla con `cancha` y horarios de hoy.
- **La placa `zonas` tampoco aparece en el torneo 1**, y acá sí es por diseño: todas las
  zonas están jugadas y ya hay llave, y `_placas_zonas` (`pantalla.py:334-338`) las
  deja de mostrar a propósito. También la medí sintéticamente.
- Nada se guardó en la base: 28 usuarios antes y después. El formulario de alta de
  jugador se instanció en memoria, los popups se abrieron sólo con GET y la validación
  se chequeó con `checkValidity()` / `reportValidity()`, nunca con submit.
- La planilla se auditó **como pantalla**, no como impresión, según lo pedido.
