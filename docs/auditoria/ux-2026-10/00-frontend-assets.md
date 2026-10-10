# Auditoría — Peso de página, assets y terceros
Medido el 2026-10-09 sobre el server local con datos reales, a 375x812.

## Resumen
La home pesa **795 KB** en celular y la ficha de torneo **796 KB**. De eso, **556 KB son
dos imágenes** que no se pueden comprimir más de lo que están (ya son formatos
comprimidos) pero sí se pueden servir mucho más chicas. El CSS, que parecía el
sospechoso obvio, **no es el problema**: en producción viaja en 20 KB con brotli.

| Recurso | Hoy | En producción | Nota |
|---|---:|---:|---|
| `padel-court-1.jpg` | 434 KB | 434 KB | brotli no ayuda: ya es JPG |
| `tailwind.css` | 169 KB | **20 KB** | ya está bien optimizado (3 temas, compilado local) |
| `logo.png` | 122 KB | 121 KB | en TODAS las páginas |
| Inter (woff2) | 47 KB | 47 KB | origen externo |

## ALTO — El fondo del hero se sirve 2,8x más grande de lo necesario
`theme/static/img/fondos/padel-court-1.jpg` es de **1920x1440** y se muestra en una caja
de **343x793** (celular). Encima la proporción está al revés: la foto es apaisada y la
caja es vertical, así que se recorta y se tira la mayor parte de los píxeles que el
usuario pagó por bajar. Se usa en la home (`core/templates/core/home.html:33`, fondo CSS)
y en la ficha (`torneos/templates/torneos/torneo_detail.html:151`, `<img>`).

**Arreglo medido:** WebP a 828px de ancho → **434 KB a 80 KB (-82%)**.
Con `<picture>` + `srcset` para desktop (1600px → 270 KB) se cubren los dos casos.

## ALTO — El logo son 519x480 para mostrarse a 32x32
`theme/static/img/logo.png`: 122 KB, intrínseco 519x480, mostrado **32x32** (en DPR 2
necesita 64px). Es **8,1x más grande de lo necesario en cada dimensión**, o sea ~64 veces
los píxeles. Y está en el navbar de todas las páginas.

**Arreglo medido:** WebP de 64px → **122 KB a 1 KB (-99%)**. Una versión generosa de
128px queda en 3 KB. Un SVG sería aún mejor.

**Total home en celular: 700 KB → 98 KB (-86%)** solo con estas dos.

## MEDIO — 1,1 MB de fondos que no usa nadie
`padel-court-2.jpg` (363 KB) y `padel-court-3.jpg` (760 KB) no están referenciados en
ningún template ni CSS: sólo los menciona un comentario en `home.html:31`. Igual los
levanta `collectstatic` y van al deploy. No los baja el usuario, pero inflan el repo y
el build.

## ALTO — La integridad del script de HTMX está desactivada por un typo
`theme/templates/base.html:70` dice **`xintegrity=`** en vez de `integrity=`. El atributo
no existe, así que el navegador lo ignora: HTMX se baja de `unpkg.com` **sin verificación
de integridad**, en un sitio con cuentas de usuario y comprobantes de pago. Si unpkg se
compromete, corre JavaScript arbitrario con la sesión del usuario.

**Verificado:** el hash que está escrito es el correcto para htmx 1.9.10 (bajé el archivo
y calculé el sha384: coincide). O sea que **renombrar el atributo es un arreglo de una
letra y no rompe nada**. Mejor todavía: auto-hospedar htmx y sacarse el origen externo.

## MEDIO — jQuery se carga en casi todas las páginas y lo usan 2 templates
`base.html:515` carga jQuery 3.6.0 desde `code.jquery.com` dentro de `{% block extra_head %}`.
Lo usan **2 templates** (5 llamadas en total): `admin_torneo_manage.html` y
`organizador_equipo_form.html`, ambos con select2.

Dos consecuencias:
1. Todas las demás páginas pagan ~30 KB y un origen externo de más sin usarlo.
2. Como vive en un bloque, cualquier template que pise `extra_head` sin `{{ block.super }}`
   se queda sin jQuery. Ya pasa: `core/home.html` lo pisa, así que la home **no** carga
   jQuery. Hoy no molesta porque la home no tiene select2, pero es una trampa: el día que
   alguien ponga un autocompletar ahí, va a fallar con "$ is not defined".

**Arreglo:** cargar jQuery sólo donde hace falta (los 2 templates, o condicionado a
`{% if form.media %}`), y auto-hospedarlo.

## MEDIO — Cuatro orígenes externos en el camino crítico
`unpkg.com` (htmx), `fonts.googleapis.com`, `fonts.gstatic.com` y `code.jquery.com`. Cada
uno es DNS + TCP + TLS antes del primer byte. En 4G argentino eso es del orden de 300-600 ms
sumados, antes de que pinte nada. El proyecto ya se sacó jsDelivr de encima por esta misma
razón (está comentado en `tailwind.config.js`); quedan estos cuatro.

**Arreglo:** auto-hospedar htmx, jQuery e Inter (subsetear a los pesos que se usan).
Todo pasa a servirse con hash y caché infinito por whitenoise, que ya está configurado.

## BAJO — Casi no se usa `loading="lazy"`
De todos los templates, sólo `torneos/partials/torneo_card.html` tiene `loading="lazy"`.
En listados largos (torneos, rankings, perfiles con foto) conviene diferir lo que está
abajo del pliegue.

## Lo que YA está bien (no tocar)
- **El CSS está bien resuelto.** `tailwind.config.js` compila sólo 3 temas de DaisyUI y
  está comentado explicando por qué (incluido por qué se conserva `dark`). En producción
  son 20 KB con brotli.
- **Whitenoise con `CompressedManifestStaticFilesStorage`**: genera `.br` y `.gz` y
  nombres con hash, o sea caché infinito. Bien.
- **El service worker no cachea a propósito** y está documentado el motivo (no servir
  páginas viejas). Es una decisión razonable; ver abajo la oportunidad.

## Oportunidad (no es un bug)
El service worker (`theme/templates/pwa/sw.js`) hoy es pass-through: la PWA no funciona
offline ni cachea assets. Para el organizador al borde de la cancha, con señal irregular,
una estrategia *stale-while-revalidate* sólo para estáticos (que ya vienen con hash, así
que no hay riesgo de servir viejo) daría cargas casi instantáneas sin el peligro que el
comentario del archivo quiere evitar.
