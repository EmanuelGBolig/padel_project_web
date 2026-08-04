# Backlog de mejoras — TodoPadel

> **Estado (2026-08-03): implementado casi todo.** Ver el historial de git —
> commits `de19196`, `916763f`, `6c941a7`, `e38d17f`, `5b6ab1f`.
>
> **Lo que queda pendiente y por qué:**
>
> | Ítem | Por qué sigue abierto |
> |---|---|
> | S1 — contraseña del superusuario | El usuario pidió **no tocar ninguna contraseña**. Se sacó el script de los deploys y se quitó el valor por defecto, pero la cuenta quedó como estaba. |
> | S2 — backups en el historial de git | Sacados del índice y agregados a `.gitignore`, pero **siguen en el historial**. Reescribirlo (`git filter-repo`) es destructivo y requiere el OK del usuario. |
> | P5 — bundle de DaisyUI desde CDN | Requiere reconfigurar el build de Tailwind y volver a verificar todos los estilos. Alto riesgo visual, conviene hacerlo aislado. |
> | U1 — carga de resultados sin recargar | Se atacó la pérdida de contexto (se preservan zonas abiertas y scroll). El swap parcial por HTMX del panel entero quedó pendiente por riesgo. |
> | F4–F8 — placas, recordatorios, cobros… | Features nuevas de mayor tamaño, no correcciones. |
> | Deuda 1 — partir `torneos/views.py` | Refactor grande; conviene hacerlo solo, con la suite verde como red. |

Generado a partir de la auditoría completa del código del 2026-08-03.
Cada ítem tiene **impacto** (para el usuario o el negocio) y **esfuerzo** estimado.

Leyenda: 🔴 crítico · 🟠 alto · 🟡 medio · ⚪ bajo

---

## 🔴 Seguridad — resolver antes que nada

Estos cuatro están **verificados a mano**, no son sospechas.

### S1. Contraseña de superusuario hardcodeada, en un repo público
`scripts/create_initial_superuser.py:17-19` tiene como fallback la contraseña literal
`emanuel2001` para el superusuario `egomezbolig@gmail.com`, y `build.sh` **ejecuta ese script en
cada deploy**. El repo es público, así que la credencial es de acceso libre. Si
`DJANGO_SUPERUSER_PASSWORD` no está seteada en Render, esa contraseña es la real.

**Qué hacer:** cambiar la contraseña de esa cuenta ahora, revisar su `last_login`, y hacer que el
script falle en vez de usar un default. Esfuerzo: ⚪ minutos.

### S2. Dumps de producción con datos personales versionados
Nueve archivos `backup_*.json` commiteados, con **103 usuarios reales**: email, nombre, teléfono,
género y hash de contraseña (PBKDF2, que es lento de crackear pero no invulnerable).

**Qué hacer:** repo a privado, `git rm --cached backup_*.json`, agregarlos a `.gitignore`, y decidir
si se reescribe el historial con `git filter-repo` (destructivo, requiere force-push). Esfuerzo: ⚪ bajo
(salvo la reescritura de historial: 🟡).

### S3. IDOR entre organizaciones
El aislamiento multi-club se hace filtrando en `get_queryset()`, pero tres vistas de mutación no lo
implementan y resuelven el objeto solo por `pk`. `AdminRequiredMixin` de `torneos` acepta `ORGANIZER`,
así que **un organizador puede editar partidos de torneos de otro club**.
Verificado en `torneos/views.py:2411` (`ReplacePartidoTeamsView` sin `get_queryset`), y ocurre lo
mismo en las vistas de `torneos/views.py:2428` y `:2516`.

**Qué hacer:** extraer un `OrgScopedQuerysetMixin` con el patrón que ya está repetido 6 veces y
aplicarlo a todas las vistas de mutación. Esfuerzo: ⚪ bajo.

### S4. El endpoint de push permite pisar la suscripción de otro
`accounts/views.py:779` hace `PushSubscription.objects.filter(endpoint=endpoint).delete()` sin filtrar
por usuario, y el `update_or_create` de la línea 787 reasigna el `user`. Con el endpoint de otra
persona se le puede cortar las notificaciones o redirigirlas.

**Qué hacer:** agregar `user=request.user` a ambas operaciones. Esfuerzo: ⚪ una línea.

### Otros de seguridad (menor severidad)
- **Throttle de login evadible** (`accounts/forms.py:165`): toma el *primer* valor de `X-Forwarded-For`,
  que el cliente controla. Usar el último salto o `REMOTE_ADDR`, y sumar el email a la clave.
  Registro y reset de contraseña no tienen throttle.
- **`crear_torneo_prueba`** (`torneos/views.py:2332`): está bien restringida a `ADMIN`, pero es un **GET**
  que ejecuta dos `.delete()` masivos por patrón de nombre. Al ser GET no tiene protección CSRF.
  Ya existe el equivalente correcto como management command → borrar la vista y su ruta.
- **Uploads sin límite de tamaño**: los 6 `ImageField` no tienen validadores. Agregar uno que limite
  peso y dimensiones.
- **Fusión de cuentas**: el hardening que restringe fusionar cuentas reales a `ADMIN` está solo en
  `PosiblesDuplicadosView`; `MergeUserView` (`accounts/views.py:718`) sigue aceptando `ORGANIZER` con
  querysets sin filtrar por organización. Mover el chequeo adentro de `merge_users()`.

---

## 🟠 Rendimiento

### P1. La tabla de posiciones se recalcula entera en cada resultado
`torneos/signals.py:36-77`: cada `PartidoGrupo` guardado recorre todos los `EquipoGrupo` del grupo y
por cada uno lanza un `.count()` más una iteración completa del queryset. Son ~12 queries por carga
de resultado, justo en la acción que el organizador repite decenas de veces por torneo.
**Solución:** una sola query agregada por grupo + `bulk_update`. Baja a ~3 queries. Esfuerzo: 🟡.

### P2. Cero índices en toda la base de datos
No existe ni un `db_index=True` ni un `Meta.indexes` en las cuatro apps: solo están los índices
implícitos de FK y unique. Las columnas más filtradas (`Torneo.estado`, `Torneo.ciudad`,
`CustomUser.tipo_usuario`, `CustomUser.division`) no están indexadas.
**Solución:** índices compuestos alineados a las consultas reales. Esfuerzo: ⚪ (una migración).

### P3. N+1 en el home (la página más visitada)
`core/views.py:10-16` trae los torneos sin `select_related`; el template accede a
`torneo.organizacion.logo`, `.division.nombre` e `inscripciones.count` por tarjeta → 4 queries extra
por torneo.
**Solución:** `.select_related('organizacion','division').annotate(n_inscriptos=Count('inscripciones'))`.
Esfuerzo: ⚪ dos líneas.

### P4. `Partido.nombre_ronda` hace un `aggregate` por instancia
`torneos/models.py:425` ejecuta `Max('ronda')` cada vez que se lee la property, y se la llama dentro
de loops en la vista de programación y en los perfiles. Ya existe el templatetag
`nombre_ronda_dinamico` que recibe el total; usarlo. Esfuerzo: ⚪.

### P5. DaisyUI completo + jQuery desde CDNs externos
`base.html:60-73` carga `daisyui@4.7.2/dist/full.min.css` desde jsDelivr: son los 30+ temas (~190 KB)
cuando la app usa dos. Más htmx, Google Fonts desde dos orígenes y jQuery 3.6.
**Solución:** instalar DaisyUI como plugin de Tailwind con `themes: ['corporate','business']`; el
bundle baja a ~20-30 KB y desaparecen 3 orígenes externos del critical path. Esfuerzo: 🟡.

### P6. Imágenes de Cloudinary sin transformar
Todas las imágenes se sirven con la URL cruda aunque se rendericen en avatares de 32×32.
**Solución:** un template filter que inserte `w_128,h_128,c_fill,f_auto,q_auto` en la URL. Esfuerzo: ⚪.

### P7. Threads fire-and-forget que filtran conexiones a Postgres
Cinco lugares hacen `threading.Thread(...).start()` sin cerrar la conexión de base
(`torneos/signals.py:16`, `torneos/emails.py:137` y `:219`, `accounts/utils.py:618`,
`accounts/push.py:75`). El de signals corre en **cada** carga de resultado.
**Solución inmediata:** `try/finally: connection.close()`. **Correcta:** una cola real (django-q2 o
huey, que andan con Postgres y no necesitan Redis). Esfuerzo: ⚪ / 🟠.

### P8. Otros
- El caché de rankings **nunca se invalida**: la clave que se borra (`torneos/signals.py:14`) no es la
  que se escribe (`accounts/utils.py:11`, que agrega el sufijo `_gen_`).
- `AdminTorneoManageView` (`torneos/views.py:221`) trae **todos** los equipos de la base y filtra en
  Python; se puede filtrar en la query.
- Listados de admin sin paginación (`AdminTorneoListView`, `OrganizacionListView`).
- Falta `prefetch_related('partidos_grupo__ganador')` en el panel de gestión (una línea).

---

## 🟠 UX / UI

### U1. Cargar resultados recarga la página entera
Al guardar, la vista responde con `window.location.reload()`: se recarga un template de 939 líneas +
jQuery + Select2 desde CDN + el loader de 800 ms, y los grupos vuelven a colapsarse, así que el
organizador pierde el lugar. Es la acción que más repite, al borde de la cancha.
**Solución:** respuesta HTMX que actualice solo la fila y la tabla del grupo, con un toast de
confirmación. Esfuerzo: 🟡. **Es la mejora de UX de mayor impacto real.**

### U2. La llave en el celular es un scroll horizontal a ciegas
Columnas de 260 px fijos dentro de un scroll horizontal: en un teléfono de 360 px entra una sola
columna y no hay ninguna señal de que haya más a la derecha.
**Solución:** en mobile, cambiar a un selector de rondas (chips: Octavos · Cuartos · Semi · Final) que
muestre una ronda como lista vertical a ancho completo. Esfuerzo: 🟡.

### U3. Los mensajes de éxito/error nunca se cierran
El contenedor de mensajes no tiene la clase `.toast`, pero el script de auto-cierre busca
`.toast .alert` — así que **el auto-cierre nunca se ejecuta** y los avisos quedan fijos tapando
contenido. Como efecto secundario, `hasAlerts` siempre es `null` y el loader siempre espera 800 ms.
**Solución:** agregar la clase o cambiar el selector, más un botón de cerrar. Esfuerzo: ⚪ minutos,
arregla dos bugs de una.

### U4. "¿Contra quién juego y a qué hora?" está escondido
Para un jugador inscripto esa es *la* pregunta, y vive dentro de un `<details class="dropdown">` con
un `animate-pulse` infinito.
**Solución:** card fija arriba con el próximo partido (hora, rival, zona) en tipografía grande.

### U5. Loader artificial de 800 ms en cada navegación
Overlay opaco a pantalla completa con delay fijo. En "En vivo", además, el refresh cada 20 s hace un
flash de pantalla completa.
**Solución:** ocultar en `DOMContentLoaded` sin `setTimeout`; en vivo, refrescar solo el fragmento.

### U6. El home móvil esconde lo más valioso
La card del torneo en vivo está envuelta en `hidden md:block`: en celular —la mayoría del tráfico—
directamente no existe. Y el home es idéntico para un visitante y para un jugador inscripto.

### U7. Otros
- El detalle del torneo abre con **7 botones** del mismo peso visual; definir una sola acción primaria
  por estado (AB → Inscribirme, EJ → Ver en vivo, FN → Ver resultados).
- **Accesibilidad**: labels sin `for` en registro, los 6 inputs de sets sin nombre accesible
  (un lector de pantalla anuncia seis campos idénticos), errores en 10 px.
- **No se puede filtrar torneos** por ciudad, división ni categoría: un jugador de 5ta en Rosario
  scrollea todo el país.
- **El idioma mezcla tú y vos**: "Armá tu pareja" convive con "Únete", "Inscríbete", "Conoce".
  Fijar voseo y hacer un barrido.
- **Onboarding del organizador**: se le piden latitud y longitud a mano.

---

## 🟢 Funcionalidades nuevas

Ordenadas por relación valor/esfuerzo.

### F1. Cupos con tope real + lista de espera ⚪
`cupos_totales` se muestra pero **no se valida al inscribirse**: un POST directo entra igual, y dos
inscripciones simultáneas pueden pasarse del límite. Al arreglarlo, ofrecer "anotarme en la lista de
espera" en vez de rebotar, con aviso automático al liberarse un lugar.

### F2. Centro de contacto del organizador ⚪
Tres cosas chicas de altísimo uso diario: **exportar inscriptos a CSV** (con teléfono, email y estado
de pago), **WhatsApp de 1 click** por pareja, y **aviso masivo a los inscriptos** (cambio de horario,
recordatorio). Hoy no existe ningún export en todo el repo.

### F3. Circuitos autogestionados ⚪
El motor de `Circuito` está completo (ranking acumulado, ascensos y descensos), pero **el organizador
no lo puede tocar**: solo hay rutas de lectura. Falta el CRUD, con el mismo patrón que ya usás para
`FormatoPersonalizado`. Es funcionalidad terminada esperando una pantalla.

### F4. Placas de jugador y de resultado 🟡
El sistema de placas 9:16 ya está resuelto de punta a punta (export 1080×1920, share sheet nativo).
Los 4 tipos existentes son todos de torneo. Agregar **placa de ficha del jugador** (división, ranking,
win rate, racha) y **placa de resultado de partido** convierte cada partido en un posteo. Viralidad
casi gratis sobre infraestructura ya construida.

### F5. Recordatorios automáticos + "Mi próximo partido" + calendario 🟡
Hoy **toda** la notificación es reactiva a un evento; no hay nada disparado por tiempo. Un management
command `enviar_recordatorios` con un cron de Render a T-24h y T-2h, más un `.ics` descargable.

### F6. Americano 2.0 🟡
Es el formato de mayor frecuencia real en un club (semanal), y hoy tiene tres techos que lo vuelven
casi inusable: exige múltiplo exacto de 4 jugadores, ignora `num_canchas`, y no suma al perfil.

### F7. Cobro de inscripción 🟠
Hoy el torneo se cobra 100% fuera de la app y el organizador persigue transferencias por WhatsApp.
Fase 1 barata: `precio_inscripcion` + `estado_pago` + subir comprobante (Cloudinary ya está).
Fase 2: link de Mercado Pago. Es la vía de monetización más directa.

### F8. Otros
- **Temporadas**: el ranking es un acumulado eterno; no hay campeón del año ni histórico.
- **Head-to-head**: toda la data de enfrentamientos está en la base y no se explota en ningún lado.
- **Preferencias de notificación**: los mails de torneo nuevo **no tienen link de baja** (riesgo de
  que los marquen como spam y se queme el dominio).
- **Sponsors vendibles**: el modelo está construido pero solo se usa en un carrusel; ponerlos al pie
  de las placas les da valor real de venta.

---

## 🧹 Deuda técnica

1. **`torneos/views.py` tiene 2.692 líneas**, con `AdminTorneoManageView` ocupando ~1.000 (16 acciones
   POST despachadas por una cadena de `elif`). Extraer un paquete `torneos/services/` empezando por
   `seeding.py` (funciones puras, es solo mover código) y siguiendo por `grupos.py` y `bracket.py`.
2. **~40 scripts de debug en la raíz** que corren contra la base real y borran datos por patrón.
   Mover a `scripts/legacy/` o borrar. Tres matchean el patrón de descubrimiento de tests.
3. **`requirements.txt` en UTF-16** y con dependencias que no se usan (`cookiecutter`, `arrow`,
   `pylint`, `isort`…) instalándose en cada build. Falta `playwright`, que sí se usa.
4. **Tests de autorización**: hay ~90 tests que cubren muy bien el dominio (brackets, byes, W.O.,
   formatos) pero **solo 2 de aislamiento multi-club, ambos de lectura**. Dado S3, es la brecha de
   cobertura más peligrosa.
5. **Integridad**: falta `UniqueConstraint(['grupo','equipo'])` en `EquipoGrupo`; la unicidad se
   sostiene solo con `get_or_create` a nivel aplicación.

---

## Orden sugerido

| Sprint | Qué |
|---|---|
| **Ahora** | S1, S2 (repo privado + rotar credencial) |
| **1** | S3, S4 + tests de aislamiento (4) · U3 (arregla 2 bugs en minutos) · P2, P3 |
| **2** | U1 (carga de resultados sin reload) · F1 (cupos + lista de espera) · P1 |
| **3** | U2 (llave en mobile) · F2 (contacto del organizador) · F3 (circuitos) |
| **4** | P5 (bundle CSS) · F4 (placas) · F5 (recordatorios) |
| **Después** | F7 (cobros) · deuda técnica 1 |
