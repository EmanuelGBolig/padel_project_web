# Arquitectura de TodoPadel

> **Documento vivo.** Es la referencia técnica completa del proyecto: modelo de datos, lógica de
> torneos, roles, páginas, frontend, infraestructura y convenciones.
> **Si cambiás el código, actualizá la sección correspondiente en el mismo commit** (ver `CLAUDE.md`).

| | |
|---|---|
| **Proyecto** | TodoPadel — gestión de torneos de pádel |
| **Producción** | https://todopadel.club (Render) |
| **Repositorio** | `EmanuelGBolig/padel_project_web`, rama de trabajo `main` |
| **Stack** | Django 5.2.16 · Python 3.11 · PostgreSQL (prod) / SQLite (local) · Tailwind + DaisyUI 4.7.2 · WhiteNoise · Cloudinary |
| **Apps** | `core`, `accounts`, `equipos`, `torneos` (+ `theme` para Tailwind) |
| **Tests** | 221 tests (`python manage.py test`, ~10 min) |
| **Última auditoría completa** | 2026-08-04 |

## Cómo leer este documento

1. **Modelo de datos** — todas las tablas, campos y relaciones. Empezá por acá.
2. **Subsistema de torneos** — el corazón de la app: zonas, tabla de posiciones y generación de la llave.
3. **Subsistema de cuentas** — los tres roles, permisos, jugadores dummy y fusión de cuentas.
4. **Subsistemas de equipos y core** — parejas, invitaciones, ranking, home y SEO.
5. **Frontend** — templates, Tailwind/DaisyUI, bracket, placas y PWA.
6. **Infraestructura** — settings, variables de entorno, deploy y testing.
7. **Anexo** — entorno de desarrollo, scripts sueltos y convenciones.

## Mapa mental en 30 segundos

Un **organizador** (rol `ORGANIZER`, atado a una `Organizacion`) crea un `Torneo`. Los **jugadores**
(`PLAYER`) se inscriben como `Equipo` (pareja de dos jugadores). Al iniciar el torneo, el sistema
reparte las parejas en `Grupo`s (zonas) y genera los `PartidoGrupo` de todos contra todos. Cada
resultado cargado dispara un signal que **recalcula la tabla de posiciones completa** de esa zona
(`EquipoGrupo`). Cuando las zonas terminan, se genera la **fase eliminatoria**: una cadena de
`Partido` enlazados por `siguiente_partido`, donde cada slot arranca como una etiqueta
(`placeholder_e1` = `"1A"`, `"2B"`…) y se resuelve al equipo real cuando su zona cierra. Los cruces
salen de las **llaves oficiales FAP** (`torneos/formats.py`, 6 a 48 parejas) o de un
`FormatoPersonalizado` que el organizador se guarda. Al ganarse la final, `Partido.save()` cierra el
torneo y marca al campeón.

---

> **Nota de mantenimiento (2026-08-03).** Se aplicó una tanda de mejoras que toca varias
> secciones de este documento. Los cambios estructurales:
>
> - **Seguridad**: `OrgScopedQuerysetMixin` (`torneos/permisos.py`, re-exportado desde `views.py`) que acota por
>   organización las vistas de mutación; se eliminó el endpoint `crear-torneo-prueba`;
>   `validar_imagen` (`core/validators.py`) aplicado a los 6 `ImageField`.
> - **Rendimiento**: el signal `actualizar_tabla_de_posiciones` pasó de 2 queries por
>   equipo a 3 fijas (agregación + `bulk_update`); se agregaron 8 índices de base;
>   `Partido.__init__` guarda `ganador_id` en vez del objeto.
> - **Deploy**: `build.sh` ya no corre `create_initial_superuser.py` ni
>   `reparar_rankings` (este último borraba Equipos en cada deploy).
> - **Features nuevas**: `ExportarInscriptosView` (CSV), validación real de cupos y
>   CRUD de circuitos (`circuito_admin_list`, `circuito_crear`, `circuito_editar`,
>   `circuito_eliminar`).
> - **Dependencias**: `requirements.txt` reescrito en UTF-8, 22 paquetes, sin CVEs.
> - **Bugs corregidos**: `AdminEquipoListView` (NameError en cada request) y `Http404`
>   sin importar en `torneos/views.py`.
>
> El detalle de cada cambio está en `MEJORAS.md` y en el historial de git.

---

## Índice

- [Modelo de datos](#modelo-de-datos)
- [Subsistema de torneos](#subsistema-de-torneos)
- [Subsistema de cuentas, roles y organizaciones](#subsistema-de-cuentas-roles-y-organizaciones)
- [Subsistemas de equipos y core](#subsistemas-de-equipos-y-core)
- [Frontend, templates y PWA](#frontend-templates-y-pwa)
- [Infraestructura, configuracion, deploy y testing](#infraestructura-configuracion-deploy-y-testing)
- [Anexo: entorno, tooling y convenciones](#anexo-entorno-tooling-y-convenciones)

---

## Modelo de datos

Django 5.2, `AUTH_USER_MODEL = accounts.CustomUser`. Cuatro apps con modelos: **accounts**, **equipos**, **torneos**, **core**. Todos los modelos usan `BigAutoField` como PK (`default_auto_field` en los cuatro `apps.py`).

Estado de migraciones (en sync — `makemigrations --check --dry-run` → *No changes detected*):

| App | Última migración | Nº archivos |
|---|---|---|
| `accounts` | `0018_pushsubscription` | 18 |
| `torneos` | `0024_formatopersonalizado_cruces_manuales` | 24 |
| `equipos` | `0009_busquedacompanero` | 9 |
| `core` | `0002_initial` | 2 |

---

#### Diagrama de relaciones

```mermaid
erDiagram
    Division ||--o{ CustomUser : "division SET_NULL"
    Division ||--o{ Equipo : "division PROTECT"
    Division ||--o{ Torneo : "division PROTECT"
    Division ||--o{ RankingJugador : "division CASCADE"
    Division ||--o{ BusquedaCompanero : "division CASCADE"

    Organizacion ||--o{ CustomUser : "miembros SET_NULL"
    Organizacion ||--o{ Sponsor : "sponsors CASCADE"
    Organizacion ||--o{ Torneo : "torneos CASCADE"
    Organizacion ||--o{ Circuito : "circuitos SET_NULL"
    Organizacion ||--o{ Americano : "americanos SET_NULL"
    Organizacion ||--o{ FormatoPersonalizado : "formatos CASCADE"
    CustomUser ||--o| Organizacion : "receptor_notificaciones"

    CustomUser ||--o{ PushSubscription : "push_subscriptions CASCADE"
    CustomUser ||--o{ Notificacion : "notificaciones CASCADE"
    CustomUser ||--o{ MergeAuditLog : "actor/target SET_NULL"
    CustomUser ||--o| CustomUser : "merged_into SET_NULL"
    CustomUser ||--o{ Equipo : "jugador1/jugador2 CASCADE"
    CustomUser ||--o{ Invitation : "inviter/invited CASCADE"
    CustomUser ||--o{ RankingJugador : "rankings_jugador CASCADE"
    CustomUser ||--o{ BusquedaCompanero : "busquedas_companero CASCADE"
    CustomUser ||--o{ JugadorAmericano : "participaciones SET_NULL"
    CustomUser ||--o{ FormatoPersonalizado : "creado_por SET_NULL"

    Torneo ||--o{ Inscripcion : "inscripciones CASCADE"
    Equipo ||--o{ Inscripcion : "inscripciones CASCADE"
    Torneo ||--o{ Grupo : "grupos CASCADE"
    Grupo ||--o{ EquipoGrupo : "tabla CASCADE"
    Equipo ||--o{ EquipoGrupo : "CASCADE"
    Grupo ||--o{ PartidoGrupo : "partidos_grupo CASCADE"
    Equipo ||--o{ PartidoGrupo : "e1/e2/ganador"
    Torneo ||--o{ Partido : "partidos CASCADE"
    Equipo ||--o{ Partido : "e1/e2/ganador SET_NULL"
    Partido ||--o| Partido : "siguiente_partido SET_NULL"
    Equipo ||--o| Torneo : "ganador_del_torneo SET_NULL"
    FormatoPersonalizado ||--o{ Torneo : "formato_personalizado SET_NULL"
    Circuito }o--o{ Torneo : "M2M circuitos"
    Torneo ||--o{ BusquedaCompanero : "CASCADE"

    Americano ||--o{ JugadorAmericano : "jugadores CASCADE"
    Americano ||--o{ RondaAmericano : "rondas CASCADE"
    RondaAmericano ||--o{ PartidoAmericano : "partidos CASCADE"
    JugadorAmericano ||--o{ PartidoAmericano : "a1 a2 b1 b2 CASCADE"
```

---

### App `accounts`

#### `Division` — `accounts/models.py:16`

Catálogo de categorías de juego. **Vive en `accounts`, no en `equipos`**: el comentario del código indica que se movió "para romper la dependencia circular" (`accounts/models.py:14-16`).

| Campo | Tipo | Nulo/Blank | Default | Notas |
|---|---|---|---|---|
| `nombre` | `CharField(50)` | no | — | `unique=True`. Ej: "3ra", "4ta", "5ta" |
| `orden` | `PositiveSmallIntegerField` | no | — | `unique=True`, `help_text="Octava=8, Séptima=7, ..., Primera=1"` |

- **Meta**: `ordering=['orden']` (de mayor categoría a menor), `verbose_name_plural="Divisiones"`.
- **Evolución**: `orden` se agregó en `accounts/migrations/0003_add_division_orden.py` con default temporal 999, se pobló por `RunPython` mapeando nombres ("Primera"/"1ra"/"1a"→1 … "Octava"/"8va"→8) con contador de fallback desde 100 para nombres desconocidos, y recién después se hizo `unique`.

#### `CustomUserManager` — `accounts/models.py:31`

- `create_user(email, password=None, **extra)`: exige email (`ValueError('El email es obligatorio')`), normaliza con `normalize_email`, hashea con `set_password`.
- `create_superuser`: fuerza `is_staff=True`, `is_superuser=True` y **`tipo_usuario='ADMIN'`**; valida ambos flags.

#### `CustomUser` — `accounts/models.py:54`

Hereda de `AbstractBaseUser + PermissionsMixin`. `USERNAME_FIELD='email'`, `REQUIRED_FIELDS=['nombre','apellido']`.

**Choices anidados**

| Clase | Valores |
|---|---|
| `TipoUsuario` (`:56`) | `PLAYER`='Jugador', `ADMIN`='Admin', `ORGANIZER`='Organizador' |
| `Genero` (`:61`) | `MASCULINO`, `FEMENINO`, `OTRO` |
| `Posicion` (`:67`) | `D`='Drive', `R`='Revés', `A`='Ambas' |
| `Mano` (`:72`) | `D`='Diestra', `Z`='Zurda' |

**Campos**

| Campo | Tipo | Nulo/Blank | Default | Notas |
|---|---|---|---|---|
| `email` | `EmailField` | no | — | `unique=True` — es el login |
| `nombre` | `CharField(100)` | no | — | |
| `apellido` | `CharField(100)` | no | — | |
| `numero_telefono` | `CharField(20)` | `blank` | `''` | |
| `imagen` | `ImageField` | `null,blank` | — | `upload_to='perfiles/'` |
| `posicion_cancha` | `CharField(1)` | `blank` | `''` | choices `Posicion` (ficha TP-19.3) |
| `mano_habil` | `CharField(1)` | `blank` | `''` | choices `Mano` |
| `club` | `CharField(120)` | `blank` | `''` | |
| `ciudad` | `CharField(100)` | `blank` | `''` | |
| `juega_desde` | `PositiveSmallIntegerField` | `null,blank` | — | `help_text="Año en que empezó a jugar"` |
| `instagram` | `CharField(50)` | `blank` | `''` | `help_text="Usuario de Instagram, sin @"` |
| `bio` | `TextField(max_length=280)` | `blank` | `''` | |
| `verification_code` | `CharField(6)` | `null,blank` | — | código de verificación por email |
| `is_verified` | `BooleanField` | — | `False` | |
| `division` | FK → `accounts.Division` | `null,blank` | — | `on_delete=SET_NULL`, sin `related_name` (→ `customuser_set`) |
| `genero` | `CharField(10)` | **no blank** | **sin default** | choices `Genero`. El default `'MASCULINO'` se quitó en `0011_remove_genero_default` |
| `tipo_usuario` | `CharField(10)` | no | `PLAYER` | `ORGANIZER` se agregó en `0006_alter_customuser_tipo_usuario` |
| `organizacion` | FK → `accounts.Organizacion` | `null,blank` | — | `SET_NULL`, `related_name='miembros'` |
| `is_dummy` | `BooleanField` | — | `False` | `verbose_name="Es Jugador Creado por Organizador"`; jugador de relleno sin cuenta real |
| `merged_into` | FK → `self` | `null,blank` | — | `SET_NULL`, `related_name='cuentas_fusionadas'`. Deduplicación TP-20 |
| `is_active` / `is_staff` | `BooleanField` | — | `True` / `False` | |
| `date_joined` | `DateTimeField` | — | `timezone.now` | |
| `groups` | M2M → `auth.Group` | `blank` | — | **redeclarado** con `related_name="custom_user_groups"`, `related_query_name="user"` (fix E304) |
| `user_permissions` | M2M → `auth.Permission` | `blank` | — | `related_name="custom_user_permissions"` |

- **Meta**: `verbose_name="un usuario"`, `verbose_name_plural="usuarios"` (seteado en `0002_alter_customuser_options`). **Sin `ordering`**.
- **`__str__`** → `email`.

**Properties / métodos**

| Miembro | Línea | Qué hace |
|---|---|---|
| `full_name` | `:179` | `"{nombre} {apellido}"` |
| `telefono_numero` | `:183` | `re.sub(r'\D','',numero_telefono)` — para links `wa.me/<numero>` |
| `save()` | `:189` | **Sólo llama a `super().save()`** — override vacío, código muerto |
| `get_avatar_url` | `:193` | `self.imagen.url` o `None` (el template hace el fallback) |
| `equipo` | `:199` | Import local de `equipos.Equipo`; devuelve el primer equipo **activo** donde es `jugador1`, si no el primero donde es `jugador2` |

> **Nota sobre dummies y fusión**: `merged_into` se usa en `accounts/auth_backends.py:16-21` para seguir la cadena hasta la cuenta canónica (tope anti-ciclos de 10 saltos), y en `accounts/utils.py` para excluir cuentas absorbidas de los rankings (`jugador__merged_into__isnull=True`, `accounts/utils.py:33`, `:67`, `:101`, `:231`). `merge_users()` (`accounts/utils.py:768-850`) **elimina** la cuenta origen si `is_dummy`, o la desactiva y le setea `merged_into` si es real.

#### `Organizacion` — `accounts/models.py:213`

| Campo | Tipo | Nulo/Blank | Notas |
|---|---|---|---|
| `nombre` | `CharField(150)` | no | `unique=True` |
| `alias` | `SlugField(150)` | no | `unique=True`, `help_text="URL amigable (ej: club-padel-mdq)"` |
| `descripcion` | `TextField` | `blank` | |
| `ciudad` | `CharField(100)` | `blank` | |
| `direccion` | `CharField(255)` | `blank` | |
| `latitud` / `longitud` | `DecimalField(9,6)` | `null,blank` | geolocalización de la sede |
| `logo` | `ImageField` | `null,blank` | `upload_to='organizadores/logos/'` |
| `receptor_notificaciones` | FK → `CustomUser` | `null,blank` | `SET_NULL`, `related_name='organizacion_notificaciones'`, **`limit_choices_to={'tipo_usuario':'ORGANIZER'}`** |
| `whatsapp` | `CharField(20)` | `blank` | `RegexValidator(r'^\+?\d{8,15}$')` — formato internacional |

- **Meta**: `verbose_name="Organización"` / plural `"Organizaciones"`. Sin ordering.
- **Property** `whatsapp_numero` (`:248`): sólo dígitos, para `wa.me/`.
- **Evolución**: nació en `0008_organizacion_remove_sponsor_organizador_and_more` reemplazando al modelo `OrganizadorProfile` (eliminado en la misma migración). `ciudad` se agregó en `0014`, `whatsapp` en `0013`, `receptor_notificaciones` en `0012`.

#### `Sponsor` — `accounts/models.py:255`

| Campo | Tipo | Nulo/Blank | Default |
|---|---|---|---|
| `organizacion` | FK → `Organizacion` | `null,blank` | — (`CASCADE`, `related_name='sponsors'`) |
| `nombre` | `CharField(100)` | no | — |
| `imagen` | `ImageField(upload_to='sponsors/')` | no | — |
| `link` | `URLField` | `blank` | `''` |
| `orden` | `PositiveIntegerField` | — | `0` (`help_text="Orden de aparición en el carrusel"`) |

- **Meta**: `ordering=['orden']`.
- ⚠️ `__str__` (`:271-272`) hace `self.organizacion.nombre` sin guarda pese a que el FK es nullable → `AttributeError` con sponsors huérfanos.

#### `PushSubscription` — `accounts/models.py:275` (TP-11)

Suscripción Web Push por dispositivo. Un usuario puede tener varias; el docstring indica que si el endpoint devuelve 404/410 la suscripción se borra.

| Campo | Tipo | Notas |
|---|---|---|
| `user` | FK → `CustomUser` | `CASCADE`, `related_name='push_subscriptions'` |
| `endpoint` | `URLField(max_length=500)` | `unique=True` |
| `p256dh` | `CharField(255)` | clave pública del cliente |
| `auth` | `CharField(255)` | secreto de auth |
| `user_agent` | `CharField(255)` | `blank` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

- **Meta**: `verbose_name="Suscripción push"` / plural.

#### `Notificacion` — `accounts/models.py`

Aviso guardado para el panel de la campanita. Se crea sola desde
`accounts.push.send_push_to_users`, así que **todo aviso de la app cae acá** aunque el push
nunca llegue. Ver el detalle de flujo en «Subsistema de cuentas §8.1».

| Campo | Tipo | Notas |
|---|---|---|
| `usuario` | FK → `CustomUser` | `CASCADE`, `related_name='notificaciones'` |
| `titulo` | `CharField(120)` | |
| `cuerpo` | `TextField` | `blank` |
| `url` | `CharField(300)` | default `/`; a dónde lleva al tocarla |
| `leida` | `BooleanField` | `default=False` |
| `creada` | `DateTimeField` | `auto_now_add=True` |

- **Meta**: `ordering=['-creada']`, índice `notif_usuario_leida_idx` sobre `(usuario, leida)`.
- **Propiedad** `destino_seguro`: la `url` sólo si es una ruta interna (`/…`, y no `//…`); si no, `/`.

#### `MergeAuditLog` — `accounts/models.py:298` (TP-21)

Registro inmutable de fusiones de cuentas. **Denormaliza** email y nombre de origen y destino para sobrevivir al borrado de los usuarios.

| Campo | Tipo | Notas |
|---|---|---|
| `actor` | FK → `CustomUser` | `SET_NULL`, `null,blank`, `related_name='fusiones_realizadas'` |
| `actor_email` | `CharField(254)` | `blank` (copia congelada) |
| `source_id` | `IntegerField` | id del usuario absorbido (no es FK: puede haber sido borrado) |
| `source_email` / `source_nombre` | `CharField(254)` / `CharField(210)` | `blank` |
| `source_was_dummy` | `BooleanField` | `default=False` |
| `target` | FK → `CustomUser` | `SET_NULL`, `related_name='fusiones_recibidas'` |
| `target_email` / `target_nombre` | `CharField(254)` / `CharField(210)` | `blank` |
| `created_at` | `DateTimeField` | `auto_now_add=True` |

- **Meta**: `ordering=['-created_at']`, verbose names "Registro de fusión". En el admin todos los campos son `readonly` (`accounts/admin.py:91`).

---

### App `equipos`

#### `Equipo` — `equipos/models.py:6`

La **pareja** es la unidad que compite; los jugadores individuales sólo puntúan vía `RankingJugador`.

| Campo | Tipo | Nulo/Blank | Default | Notas |
|---|---|---|---|---|
| `nombre` | `CharField(100)` | `blank` | — | `unique=True`, autogenerado en `save()` |
| `jugador1` | FK → `AUTH_USER_MODEL` | `null,blank` | — | `CASCADE`, `related_name='equipos_como_jugador1'` |
| `jugador2` | FK → `AUTH_USER_MODEL` | `null,blank` | — | `CASCADE`, `related_name='equipos_como_jugador2'` |
| `division` | FK → `accounts.Division` | `null,blank` | — | **`PROTECT`**, sin `related_name` |
| `fecha_creacion` | `DateTimeField` | — | `auto_now_add` | |
| `esta_activo` | `BooleanField` | — | `True` | `verbose_name="Esta Activo"` |
| `categoria` | `CharField(1)` | — | `MIXTO` | choices `M`/`F`/`X`; **declarado después del `Meta`** (`:38-48`) |
| `es_dummy` | `BooleanField` | — | `False` | `verbose_name="Es Pareja Libre (Dummy)"`, "creado automáticamente para rellenar grupos" |

- **Meta / constraints** (`:28-36`):
  ```python
  UniqueConstraint(fields=['jugador1','jugador2'],
                   condition=Q(esta_activo=True),
                   name='unique_active_team')
  ```
  Impide dos equipos **activos** con la misma dupla. Se introdujo en `equipos/0008`, que además eliminó el viejo `unique_together`. Como los equipos dummy se crean con ambos jugadores en `NULL` (`torneos/views.py:572-575`), la constraint no los afecta.

- **`save()`** (`:56-96`) — tres efectos:
  1. Si `es_dummy` → no hace nada especial (`pass`).
  2. Si hay ambos jugadores: **normaliza el orden** intercambiando para que `jugador1_id < jugador2_id` (imprescindible para que la constraint funcione); construye `base_nombre = "ApellidoA/ApellidoB"` ordenado alfabéticamente, usando `email.split('@')[0]` como fallback si falta apellido; resuelve colisiones con sufijo `" (n)"` en un `while` sobre `Equipo.objects.filter(nombre=...)`.
  3. Si `division` está vacía, la deriva del jugador con **menor `orden`** (categoría más alta): `d1 if d1.orden <= d2.orden else d2`.
- **`__str__`** (`:98`): agrega `" [Dummies]"` si ambos jugadores son `is_dummy`, `" [Con Dummy]"` si sólo uno.

**Cómo se nombra a una pareja según dónde se la muestra:**

| Propiedad | Devuelve | Dónde va |
|---|---|---|
| `nombre` (campo) | `"Reina/Esquivel"` — sólo apellidos | Cuadro, tabla de posiciones, planilla de horarios: donde tiene que entrar en una celda |
| `nombres_jugadores` | `["Gonzalo Reina", "Dante Esquivel"]` | Listas de gestión, un jugador por renglón |
| `nombre_completo` | `"Gonzalo Reina y Dante Esquivel"` | Cuando hace falta una sola cadena (exports, mensajes) |

> Lo pidió un organizador: en la lista de inscriptos veía `Reina/Esquivel` y no
> podía saber quiénes eran. Con dos hermanos, o dos apellidos iguales en la misma
> categoría, el apellido solo no identifica a nadie. Se cambió **sólo en las
> listas de gestión** (inscriptos y cobros); el código corto sigue igual donde el
> espacio manda.

**Métodos de estadística** (todos hacen import local de `torneos.models` para evitar ciclo):

| Método | Línea | Comportamiento |
|---|---|---|
| `get_partidos_jugados()` | `:107` | dict `{eliminacion, grupos, total}` filtrando `ganador__isnull=False` |
| `get_victorias()` | `:127` | `Partido.filter(ganador=self).count() + PartidoGrupo.filter(ganador=self).count()` |
| `get_derrotas()` | `:136` | total − victorias |
| `get_win_rate()` | `:141` | % redondeado a 1 decimal; 0 si no jugó |
| `get_torneos_ganados()` | `:148` | `Torneo.filter(ganador_del_torneo=self).count()` |
| `get_racha_actual()` | `:153` | concatena bracket + grupos ordenados por `-fecha_inicio`; devuelve `{tipo,cantidad,texto}` |
| `get_ultimos_resultados(limit=5)` | `:197` | lista de dicts `{ganado, rival, torneo, tipo}` |
| `get_puntos_ranking()` | `:235` | ⚠️ docstring dice "promediados" pero hace `aggregate(Sum('puntos'))` sobre los `RankingJugador` de ambos — es una suma de todas las divisiones |

#### `Invitation` — `equipos/models.py:248`

Invitación de un jugador a otro para formar pareja.

| Campo | Tipo | Notas |
|---|---|---|
| `inviter` | FK → user | `CASCADE`, `related_name='sent_invitations'` |
| `invited` | FK → user | `CASCADE`, `related_name='received_invitations'` |
| `status` | `CharField(10)` | choices `PENDING`/`ACCEPTED`/`REJECTED`, default `PENDING` |
| `timestamp` | `DateTimeField` | `auto_now_add=True` |

- **Meta**: `unique_together=('inviter','invited','status')`, `ordering=['-timestamp']`.
- ⚠️ La terna incluye `status`: sólo puede existir **una** invitación rechazada (y una aceptada) entre el mismo par de jugadores.

#### `RankingJugador` — `equipos/models.py:279`

Tabla materializada de puntos por jugador y división (la regenera `accounts.utils.actualizar_rankings_en_bd`, agendada con debounce desde `torneos/signals.py`).

| Campo | Tipo | Default |
|---|---|---|
| `jugador` | FK → user (`CASCADE`, `related_name='rankings_jugador'`) | — |
| `division` | FK → `Division` (`CASCADE`, `related_name='rankings_jugadores_division'`) | — |
| `puntos` / `torneos_ganados` / `victorias` / `partidos_jugados` | `IntegerField` | `0` |

- **Constraint**: `UniqueConstraint(['jugador','division'], name='unique_ranking_jugador_division')`.
- **Meta**: verbose names "Ranking de Jugador"/"Rankings de Jugadores". Sin ordering propio.
- **Histórico**: existió un gemelo `RankingEquipo` creado en `equipos/0007` y **eliminado** en `equipos/0008`.

#### `BusquedaCompanero` — `equipos/models.py:298` (TP-10)

Aviso de "busco compañero/rival".

| Campo | Tipo | Nulo/Blank | Notas |
|---|---|---|---|
| `jugador` | FK → user | no | `CASCADE`, `related_name='busquedas_companero'` |
| `division` | FK → `Division` | `null,blank` | `CASCADE`, `related_name='busquedas'` |
| `ciudad` | `CharField(100)` | `blank` | |
| `torneo` | FK → `torneos.Torneo` | `null,blank` | `CASCADE`, `related_name='busquedas_companero'` |
| `nota` | `TextField` | `blank` | `help_text="Contanos qué buscás (nivel, disponibilidad, etc.)"` |
| `activa` | `BooleanField` | — | `default=True` |
| `fecha_creacion` | `DateTimeField` | — | `auto_now_add` |

- **Meta**: `ordering=['-fecha_creacion']`, verbose "Búsqueda de compañero".

---

### App `torneos`

#### `FormatoPersonalizado` — `torneos/models.py:8`

Plantilla de formato guardable y reutilizable por el organizador (modo "semi-automático").

| Campo | Tipo | Nulo/Blank | Default | Notas |
|---|---|---|---|---|
| `nombre` | `CharField(80)` | no | — | sin unicidad |
| `organizacion` | FK → `Organizacion` | `null,blank` | — | `CASCADE`, `related_name='formatos'` |
| `creado_por` | FK → user | `null,blank` | — | `SET_NULL`, `related_name='formatos_creados'` |
| `sizes` | `JSONField` | no | `list` | Tamaños de cada zona, ej `[3,3,3,3,2]`; `len(sizes)` = nº de zonas |
| `clasifican_por_grupo` | `PositiveSmallIntegerField` | no | `2` | "Cuántas parejas pasan de cada zona a la fase final" |
| `cruces_manuales` | `JSONField` | `blank` | `list` | Pares de etiquetas de 1ra ronda, ej `[["1A","2B"],["1C","2D"]]`. Vacío ⇒ seeding estándar automático |
| `fecha_creacion` | `DateTimeField` | — | `auto_now_add` | |

- **Meta**: `ordering=['nombre']`, verbose "Formato personalizado".
- **Properties**: `num_grupos` = `len(sizes)`; `total_parejas` = `sum(sizes)`; `resumen` = `"5 zonas (3-3-3-3-2)"`.
- **`__str__`**: `"{nombre} ({total_parejas} parejas)"`.
- **Evolución**: creado en `0023`; `cruces_manuales` agregado en `0024`.

#### `ResolucionPartido` (TextChoices compartido) — `torneos/models.py:55`

`N`='Normal', `W`='Walkover (no se presentó)', `A`='Abandono (se retiró)'. Lo usan **`PartidoGrupo`** y **`Partido`** (TP-18, migración `0021`).

#### `Torneo` — `torneos/models.py:65`

**Choices anidados**

| Clase | Valores |
|---|---|
| `Estado` (`:66`) | `AB`='Inscripción Abierta', `EJ`='En Juego', `FN`='Finalizado' |
| `TipoTorneo` (`:71`) | `E`='Eliminación Directa', `G`='Fase de Grupos + Eliminatoria' |
| `FormatoZonas4` (`:103`) | `RR`='Todos contra todos (3 partidos)', `LL`='Llaves internas (2 rondas, Ganadores/Perdedores)' |
| `Categoria` (`:114`) | `M`='Masculino', `F`='Femenino', `X`='Mixto' |

**Campos**

| Campo | Tipo | Nulo/Blank | Default | Notas |
|---|---|---|---|---|
| `nombre` | `CharField(200)` | no | — | |
| `division` | FK → `Division` | `null,blank` | — | **`PROTECT`**. `help_text="Dejar vacío para torneos libres"` (nullable desde `0007_torneo_division_nullable`) |
| `fecha_inicio` | `DateField` | no | — | |
| `fecha_limite_inscripcion` | `DateTimeField` | no | — | |
| `cupos_totales` | `PositiveIntegerField` | — | `16` | |
| `equipos_por_grupo` | `PositiveIntegerField` | — | `3` | Usado sólo si no aplica una llave FAP |
| `forzar_grupos_de_3` | `BooleanField` | — | `False` | "el sistema exigirá que el total de equipos sea divisible por 3" |
| `estado` | `CharField(2)` | — | `AB` | choices `Estado` |
| `tipo_torneo` | `CharField(1)` | — | `G` | choices `TipoTorneo` |
| `formato_grupos_4` | `CharField(2)` | — | `RR` | choices `FormatoZonas4`; sólo afecta zonas de 4 |
| `categoria` | `CharField(1)` | — | `X` (Mixto) | choices `Categoria` |
| `ganador_del_torneo` | FK → `Equipo` | `null,blank` | — | `SET_NULL`, `related_name='torneos_ganados'` |
| `foto_campeones` | `ImageField` | `null,blank` | — | `upload_to='torneos/campeones/'` |
| `cover_image` | `ImageField` | `null,blank` | — | `upload_to='torneos/portadas/'` (ficha TP-03) |
| `ciudad` | `CharField(100)` | `blank` | — | |
| `sede_nombre` | `CharField(150)` | `blank` | — | |
| `sede_direccion` | `CharField(255)` | `blank` | — | |
| `premio` | `CharField(255)` | `blank` | — | "Ej: Trofeos + $100.000 + indumentaria" |
| `reglamento` | `TextField` | `blank` | — | texto libre |
| `estructura_manual` | `BooleanField` | — | `False` | Si se editó/agregó una zona a mano, la estructura deja de coincidir con `get_format(cupos)` y el bracket usa la lógica genérica |
| `formato_personalizado` | FK → `FormatoPersonalizado` | `null,blank` | — | `SET_NULL`, `related_name='torneos'` |
| `organizacion` | FK → `Organizacion` | `null,blank` | — | **`CASCADE`**, `related_name='torneos'` |
| `equipos_inscritos` | M2M → `Equipo` | — | — | `through='Inscripcion'`, `related_name='torneos_participados'` |

- **Sin `class Meta`** → sin `ordering` por defecto y sin constraints declaradas.
- **`__str__`**: `"{nombre} ({division.nombre or 'Libre/General'})"`.
- **`get_absolute_url()`** → `torneos:detail`.
- **`fecha_fin`** (`:184`): sólo si `estado == FINALIZADO`; toma el `fecha_hora` del último partido con ganador (`order_by('-fecha_hora').first()`), con fallback a `fecha_inicio`.
- **`cupos_disponibles`** (`:196`): `max(0, cupos_totales - inscripciones.count())`.
- **Evolución destacada**: `0011` agregó `organizador` (FK a user) y `0012` lo reemplazó por `organizacion`; `0018` agregó el bloque de ficha vendedora (`ciudad`, `cover_image`, `premio`, `reglamento`, `sede_*`).

#### `Inscripcion` — `torneos/models.py:202`

Tabla `through` del M2M Torneo↔Equipo.

| Campo | Tipo | Notas |
|---|---|---|
| `equipo` | FK → `Equipo` | `CASCADE`, `related_name='inscripciones'` |
| `torneo` | FK → `Torneo` | `CASCADE`, `related_name='inscripciones'` |
| `fecha_inscripcion` | `DateTimeField` | `auto_now_add=True` |

- **Constraint**: `UniqueConstraint(['equipo','torneo'], name='inscripcion_unica')`.

#### `Grupo` — `torneos/models.py:225`

| Campo | Tipo | Nulo/Blank | Notas |
|---|---|---|---|
| `torneo` | FK → `Torneo` | no | `CASCADE`, `related_name='grupos'` |
| `nombre` | `CharField(100)` | no | Ej: `"Grupo A"` o `"Zona A"` |
| `fecha_inicio_default` | `DateField` | `null,blank` | fecha predeterminada de los partidos de la zona (mig. `0014`) |
| `equipos` | M2M → `Equipo` | — | `through='EquipoGrupo'`, `related_name='grupos_asignados'` |

- **Sin Meta**. El nombre importa funcionalmente: la vista extrae la **letra** con `nombre.split(' ')[-1].upper()` para armar los labels `1A`/`2A`/`3A` (`torneos/views.py:1092-1106`).

#### `EquipoGrupo` — `torneos/models.py:243` (tabla de posiciones)

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| `grupo` | FK → `Grupo` | — | `CASCADE`, `related_name='tabla'` |
| `equipo` | FK → `Equipo` | — | `CASCADE`, sin `related_name` |
| `numero` | `PositiveSmallIntegerField` | `0` | posición nominal 1,2,3,4 para formar A1, A2 (mig. `0005`) |
| `partidos_jugados` / `partidos_ganados` / `partidos_perdidos` | `PositiveSmallIntegerField` | `0` | |
| `sets_a_favor` / `sets_en_contra` | `PositiveSmallIntegerField` | `0` | |
| `games_a_favor` / `games_en_contra` | `PositiveSmallIntegerField` | `0` | |
| `diferencia_sets` / `diferencia_games` | `IntegerField` (con signo) | `0` | campos de desempate |

- **Meta**: `ordering = ['-partidos_ganados', '-diferencia_sets', '-diferencia_games']` — las reglas de desempate de pádel están codificadas **en el ordering del modelo**, no en la vista.
- **Sin unique constraint sobre `(grupo, equipo)`**: la unicidad se sostiene sólo con `get_or_create` en `torneos/views.py:1073`.
- **Evolución**: `0016` introdujo un campo `prioridad_llave` con ordering `['-prioridad_llave','-partidos_ganados','-sets_a_favor','sets_en_contra']`; `0017` lo **eliminó** y cambió al ordering actual por diferencias.

##### Cómo se calcula la tabla

No hay lógica en el modelo: la recalcula íntegramente el signal `post_save` de `PartidoGrupo` (`torneos/signals.py:27-84`). Para **cada** `EquipoGrupo` del grupo:

1. Toma los `PartidoGrupo` del grupo con `ganador__isnull=False` donde el equipo aparece como `equipo1` o `equipo2`.
2. **Resetea a 0** ganados/perdidos/sets/games y setea `partidos_jugados = count()`.
3. Suma `e1_sets_ganados`/`e2_sets_ganados` y `e1_games_ganados`/`e2_games_ganados` según el equipo sea local o visitante.
4. Calcula `diferencia_sets` y `diferencia_games` y guarda.
5. Si el partido tiene ganador, invalida el caché de rankings de la división y de los jugadores, y **agenda** `actualizar_rankings_en_bd(division)` (ver debounce abajo).

Un segundo receiver, `check_llaves_internas_generacion` (`torneos/signals.py:97-143`), cuando `formato_grupos_4 == 'LL'` y la zona tiene 4 equipos con exactamente 2 partidos ya resueltos, crea automáticamente la Ronda 2: **Ganador vs Ganador** y **Perdedor vs Perdedor**.

#### `PartidoGrupo` — `torneos/models.py:280`

| Campo | Tipo | Nulo/Blank | Notas |
|---|---|---|---|
| `grupo` | FK → `Grupo` | no | `CASCADE`, `related_name='partidos_grupo'` |
| `equipo1` | FK → `Equipo` | no | `CASCADE`, `related_name='partidos_grupo_e1'` |
| `equipo2` | FK → `Equipo` | no | `CASCADE`, `related_name='partidos_grupo_e2'` |
| `e1_set1..e1_set3`, `e2_set1..e2_set3` | `PositiveSmallIntegerField` | `null,blank` | games de cada set (hasta 3) |
| `fecha_hora` | `DateTimeField` | `null,blank` | mig. `0006` |
| `ganador` | FK → `Equipo` | `null,blank` | `SET_NULL`, `related_name='partidos_grupo_ganados'` |
| `resolucion` | `CharField(1)` | — | choices `ResolucionPartido`, default `N` (mig. `0021`) |
| `e1_sets_ganados` / `e2_sets_ganados` | `PositiveSmallIntegerField` | — | default 0; "se llenan al guardar" (los llena el form) |
| `e1_games_ganados` / `e2_games_ganados` | `PositiveSmallIntegerField` | — | default 0 |

- **Sin Meta** (sin ordering; en la práctica se ordena por `id`, ver `torneos/signals.py:117`).
- **`resultado`** (property, `:313`): `"W.O."` si walkover; `"Abandono"` si abandono sin parcial; si no, `"6-4 6-2"` concatenando los sets cargados y agregando `" (abandono)"` cuando corresponde.
- **`etiqueta_resolucion`** (property, `:332`): `''` / `'W.O.'` / `'Abandono'` para el badge de UI.

#### `Partido` — `torneos/models.py:354` (cuadro de eliminación directa)

| Campo | Tipo | Nulo/Blank | Notas |
|---|---|---|---|
| `torneo` | FK → `Torneo` | no | `CASCADE`, `related_name='partidos'` |
| `ronda` | `PositiveSmallIntegerField` | no | comentario: `4=Final, 3=Semi, 2=Cuartos, 1=Octavos` (relativo: el nombre real se deriva del máximo) |
| `orden_partido` | `PositiveSmallIntegerField` | no | ⚠️ en el camino FAP se usa el **id de partido de la llave oficial** (33-64), no un índice 1..n (`torneos/views.py:792`) |
| `equipo1` / `equipo2` | FK → `Equipo` | `null,blank` | `SET_NULL`, `related_name='partidos_bracket_e1'/'_e2'` |
| `ganador` | FK → `Equipo` | `null,blank` | `SET_NULL`, `related_name='partidos_bracket_ganados'` |
| `resultado` | `CharField(100)` | `null,blank` | texto: `"6-4, 6-2"`, `"W.O."`, `"... (abandono)"`, `"Bye"` |
| `resolucion` | `CharField(1)` | — | choices `ResolucionPartido`, default `N` |
| `fecha_hora` | `DateTimeField` | `null,blank` | |
| `sets_local` / `sets_visitante` | `JSONField` | `blank` | `default=list`; games por set (mig. `0002`/`0004`) |
| `placeholder_e1` / `placeholder_e2` | `CharField(50)` | `null,blank` | etiquetas de cruce `"1A"`, `"2B"`, `"3A"` mostradas antes de que clasifiquen (mig. `0013`) |
| `siguiente_partido` | FK → `self` | `null,blank` | `SET_NULL`, `related_name='partidos_previos'` |

- **Meta**: `ordering = ['ronda', 'orden_partido']`.
- **`__init__`** (`:414`): cachea `self.__original_ganador = self.ganador`. ⚠️ Accede al **objeto** relacionado (no a `ganador_id`), y como `select_related` se puebla después de `from_db()`, **cada instanciación con ganador dispara una query extra**.
- **`nombre_ronda`** (property, `:418`): hace `torneo.partidos.aggregate(Max('ronda'))` y traduce la distancia a la final → `Final` / `Semifinal` / `Cuartos de Final` / `Octavos de Final` / `16vos de Final` / `Ronda N`. Es una query por llamada (N+1 en listados).
- **`etiqueta_resolucion`** (property, `:488`): igual que en `PartidoGrupo`.

##### `Partido.save()` — lógica de avance (`torneos/models.py:445-486`)

1. **Cierre del torneo**: si `self.ganador` y `siguiente_partido is None` (es decir, la final) y el ganador cambió respecto al del torneo:
   - setea `torneo.ganador_del_torneo`, fuerza `torneo.estado = 'FN'` (string literal, equivalente a `Estado.FINALIZADO`) y guarda el torneo;
   - **desactiva TODAS las parejas inscriptas**: `Equipo.objects.filter(id__in=inscripciones.values_list('equipo_id')).update(esta_activo=False)` — "para que los jugadores queden libres"; esto libera la constraint `unique_active_team`;
   - envía push a los campeones vía `accounts.push.send_push_to_users`, envuelto en `try/except Exception: pass`.
   - **1.b (auditoría)**: si se BORRA el ganador de la final, se limpia `torneo.ganador_del_torneo` y el torneo vuelve a `EJ`. Las parejas disueltas **no** se reactivan a propósito: para entonces los jugadores pueden tener pareja nueva y chocaría con `unique_active_team`.
2. **Avance en el cuadro**: si `self.ganador_id != self.__original_ganador_id` —en **cualquier** sentido: cargar, corregir o borrar— llama a `_propagar_ganador()`, que:
   - escribe el ganador (o `None`) en `siguiente.equipo1` si `orden_partido % 2 == 1`, o en `siguiente.equipo2` si es par (`_slot_en_siguiente`);
   - si ese `siguiente` **ya tenía ganador**, lo invalida con `limpiar_resultado(guardar=False)` porque cambiaron sus participantes, y la cascada sigue hacia adelante sola;
   - corta a `profundidad > 12` como guarda contra un cuadro con ciclos por datos corruptos.
3. Recién entonces llama a `super().save(*args, **kwargs)` y refresca `__original_ganador_id`.

> El `siguiente.save()` ocurre **antes** del `super().save()` del propio partido.

> ⚠️ **Antes de la auditoría** el paso 2 tenía `and self.ganador_id is not None` y no
> tocaba el resultado de la ronda siguiente. Eso dejaba dos agujeros: borrar un
> resultado dejaba a la pareja ya avanzada metida en la ronda siguiente, y corregir
> un resultado con la ronda siguiente ya jugada dejaba un partido cuyo ganador ya no
> lo estaba jugando (el "campeón fantasma" si pasaba en la final). Lo cubre
> `torneos.tests.CorreccionResultadoBracketTests`.

`Partido.limpiar_resultado(guardar=True)` es la forma correcta de borrar un
resultado: deja los equipos donde están, limpia ganador/resultado/sets/resolución
y, al guardar, propaga el borrado hacia adelante.

##### Resolución de placeholders y byes (vistas)

- Al "avanzar clasificados" de una zona, la vista ordena `grupo.tabla` (que ya viene ordenada por el `Meta`), toma 1º/2º/3º y hace `Partido.objects.filter(torneo=..., placeholder_e1='1A').update(equipo1=c1)` (y sus variantes para `placeholder_e2`, `2A`, `3A`) — `torneos/views.py:1104-1121`.
- `_resolver_byes()` (`torneos/views.py:1134-1154`): en la ronda mínima, si un lado tiene equipo real y el otro no tiene ni equipo ni placeholder, asigna `ganador` y `resultado="Bye"` y guarda, dejando que `Partido.save()` propague.
- En formato Llaves (`formato_grupos_4='LL'`) con zona de 4, la vista exige 4 partidos terminados antes de permitir el avance (`torneos/views.py:1047-1050`).

##### Origen de los cruces: `torneos/formats.py`

Las llaves de la fase final son las **oficiales de la FAP** para 6 a 48 parejas, hardcodeadas en `FAP_LLAVES` (`torneos/formats.py:43-506`) como tuplas `(id_partido, t1, t2, id_siguiente)` con etiquetas `'1A'`, `'2B'`, `'3A'` (o `None` = lo ocupa el ganador del partido previo). `_build_format()` calcula la `round` de cada partido como distancia a la final. `fap_sizes(n)` reparte `n // 3` zonas dando 4 parejas a las primeras `n % 3`. `calcular_estructura_grupos()` es la fuente de verdad única compartida entre la generación real y la vista previa del alta.

#### `Circuito` — `torneos/models.py:506` (TP-12)

Agrupa varios torneos en una liga con ranking acumulado.

| Campo | Tipo | Nulo/Blank | Default | Notas |
|---|---|---|---|---|
| `nombre` | `CharField(150)` | no | — | |
| `descripcion` | `TextField` | `blank` | — | |
| `organizacion` | FK → `Organizacion` | `null,blank` | — | `SET_NULL`, `related_name='circuitos'` |
| `torneos` | M2M → `Torneo` | `blank` | — | `related_name='circuitos'` (sin `through`) |
| `activo` | `BooleanField` | — | `True` | |
| `cupos_ascenso` | `PositiveSmallIntegerField` | — | `0` | "Cuántos primeros del circuito ascienden (0 = sin ascensos)" |
| `cupos_descenso` | `PositiveSmallIntegerField` | — | `0` | "Cuántos últimos descienden (0 = sin descensos)" |
| `fecha_creacion` | `DateTimeField` | — | `auto_now_add` | |

- **Meta**: `ordering=['-fecha_creacion']`, verbose "Circuito".
- **`tabla_posiciones()`** (`:536`): llama a `accounts.utils.calcular_puntos_por_jugador(torneo_ids)`, arma filas `{jugador, puntos, victorias, partidos, torneos_ganados, win_rate, posicion, asciende, desciende}`, ordena por `(puntos, torneos_ganados, win_rate)` descendente y marca ascenso/descenso por posición.
- El esquema de puntos vive en `accounts/utils.py`: 15 pts por victoria de zona (`:165-166`, `:312`), y por ronda alcanzada en el cuadro 45 (octavos) / 90 (cuartos) / 180 (semis) / 360 (finalista) / 600 (campeón) — `accounts/utils.py:210-219`, `:360-365`.

#### Americano / Mexicano (TP-09)

Formato a nivel de **jugador individual** (no de pareja): se rota de compañero y el puntaje de cada jugador es la suma de games ganados.

##### `Americano` — `torneos/models.py:574`

| Campo | Tipo | Default | Notas |
|---|---|---|---|
| `nombre` | `CharField(150)` | — | |
| `organizacion` | FK → `Organizacion` | — | `SET_NULL`, `null,blank`, `related_name='americanos'` |
| `tipo` | `CharField(1)` | `A` | `A`='Americano (rotación fija)', `M`='Mexicano (por ranking)' |
| `num_canchas` | `PositiveSmallIntegerField` | `1` | |
| `estado` | `CharField(2)` | `IN` | `IN`='Inscripción abierta', `EJ`='En juego', `FN`='Finalizado' |
| `codigo` | `CharField(8)` | autogenerado | `unique=True`, `blank=True`; "Código para el link de inscripción" |
| `fecha_creacion` | `DateTimeField` | `auto_now_add` | |

- **Meta**: `ordering=['-fecha_creacion']`, verbose "Americano/Mexicano".
- **`save()`** (`:606`): si no hay `codigo`, genera uno de **6 caracteres** con `secrets.choice(ascii_uppercase + digits)` reintentando mientras exista.
- **`tabla()`** (`:621`): `jugadores.order_by('-puntos','-partidos_jugados','nombre')`.
- **`recalcular_puntos()`** (`:624`): recorre los `PartidoAmericano` con `cargado=True`, acumula `games_a` para `a1/a2` y `games_b` para `b1/b2`, y guarda con `update_fields=['puntos','partidos_jugados']` sólo si cambió. Idempotente.
- **`get_absolute_url()`** → `torneos:americano_detail`.

##### `JugadorAmericano` — `torneos/models.py:645`

| Campo | Tipo | Notas |
|---|---|---|
| `americano` | FK → `Americano` | `CASCADE`, `related_name='jugadores'` |
| `nombre` | `CharField(100)` | nombre libre (permite anotar gente sin cuenta) |
| `user` | FK → user | `SET_NULL`, `null,blank`, `related_name='participaciones_americano'` |
| `puntos` / `partidos_jugados` | `IntegerField` | default `0` |
| `orden` | `PositiveSmallIntegerField` | default `0` |

- **Meta**: `ordering=['-puntos','nombre']`.

##### `RondaAmericano` — `torneos/models.py:663`

`americano` (FK `CASCADE`, `related_name='rondas'`) + `numero` (`PositiveSmallIntegerField`). **Meta**: `ordering=['numero']`.

##### `PartidoAmericano` — `torneos/models.py:674`

| Campo | Tipo | Notas |
|---|---|---|
| `ronda` | FK → `RondaAmericano` | `CASCADE`, `related_name='partidos'` |
| `cancha` | `PositiveSmallIntegerField` | default `1` |
| `a1`, `a2`, `b1`, `b2` | FK → `JugadorAmericano` | `CASCADE`, **todos con `related_name='+'`** (sin relación inversa) |
| `games_a` / `games_b` | `PositiveSmallIntegerField` | `null,blank` |
| `cargado` | `BooleanField` | default `False`; sólo los cargados suman en `recalcular_puntos()` |

- **Meta**: `ordering=['ronda__numero','cancha']`.
- La generación de rondas está en `torneos/americano.py:35-58`: cada ronda parte los jugadores en grupos de 4; en Americano el pairing rota entre 3 combinaciones según `(numero-1) % 3` (`(a,b)v(c,d)`, `(a,c)v(b,d)`, `(a,d)v(b,c)`); en Mexicano siempre `(a,d)` vs `(b,c)` sobre el orden por ranking.

---

### App `core`

#### `Testimonio` — `core/models.py:4` (TP-04)

Prueba social del home.

| Campo | Tipo | Nulo/Blank | Default |
|---|---|---|---|
| `autor` | `CharField(100)` | no | — |
| `rol` | `CharField(100)` | `blank` | — (`help_text="Ej: Jugador 7ma · Organizador"`) |
| `texto` | `TextField` | no | — |
| `foto` | `ImageField(upload_to='testimonios/')` | `null,blank` | — |
| `activo` | `BooleanField` | — | `True` |
| `orden` | `PositiveIntegerField` | — | `0` |

- **Meta**: `ordering=['orden']`, verbose "Testimonio"/"Testimonios".
- `core/migrations/0001_unaccent_extension.py` aplica `UnaccentExtension()` (búsqueda sin acentos en Postgres); en SQLite local la operación no hace nada.

---

### Señales y efectos colaterales transversales

| Origen | Archivo | Efecto |
|---|---|---|
| `post_save` de `PartidoGrupo` | `torneos/signals.py:27` | Recalcula la tabla completa del grupo; invalida caché de rankings de la división y de los jugadores |
| `post_save` de `PartidoGrupo` | `torneos/signals.py:97` | En formato Llaves de zona de 4, crea automáticamente Ronda 2 (G-vs-G y P-vs-P) |
| `post_save` de `Partido` | `torneos/signals.py:87` | Invalida caché de rankings si hay ganador |
| `post_save`/`post_delete` de `Partido`, `PartidoGrupo`, `Torneo` | `equipos/signals.py:6` | Borra `rankings_jugadores_all` y las claves por división |
| `Partido.save()` | `torneos/models.py:445` | Avance de ganador, cierre del torneo, desactivación masiva de equipos, push a campeones |
| `Equipo.save()` | `equipos/models.py:56` | Normaliza orden de jugadores, genera nombre único, deriva división |
| `Americano.save()` | `torneos/models.py:606` | Genera código único de 6 caracteres |
| `merge_users()` | `accounts/utils.py:768` | Traspasa equipos/inscripciones/EquipoGrupo/partidos y setea `merged_into` (o borra el dummy) |

`_mover_historial_equipo()` (`accounts/utils.py:737-765`) es la pieza que reapunta el historial entre equipos al fusionar: reasigna `Inscripcion` y `EquipoGrupo` evitando duplicados por torneo/grupo, y hace `update()` masivo sobre `PartidoGrupo.equipo1/equipo2/ganador`, `Partido.equipo1/equipo2/ganador` y `Torneo.ganador_del_torneo`.

---

### Observaciones sobre el estado del esquema

- **Sin índices explícitos**: no hay ni un `db_index=True` ni un `Meta.indexes` en los cuatro `models.py`. Todo índice existente es implícito (PKs, FKs, `unique=True`, `UniqueConstraint`). Consultas frecuentes como `Partido.filter(torneo=..., placeholder_e1=...)` o los agregados de ranking corren sin índice de apoyo sobre esas columnas.
- **Constraints declaradas** (sólo 4 en todo el proyecto): `unique_active_team` (equipos), `unique_ranking_jugador_division` (equipos), `Invitation.unique_together` (equipos), `inscripcion_unica` (torneos).
- **Modelos/campos eliminados que quedaron en el historial**: `RankingEquipo` (equipos `0007`→`0008`), `OrganizadorProfile` (accounts `0007`→`0008`), `Torneo.organizador` (torneos `0011`→`0012`), `EquipoGrupo.prioridad_llave` (torneos `0016`→`0017`).
- **Acoplamiento frágil**: `equipos/signals.py:29` importa `Division` desde `equipos.models`, donde no está definida — funciona sólo porque `equipos/models.py:3` la reexporta implícitamente.

---

## Subsistema de torneos

Es el núcleo funcional de TodoPadel: modela el ciclo de vida completo de un torneo de pádel por parejas (inscripción → zonas → resultados → tabla → llave → campeón), más dos formatos satélite (Americano/Mexicano y Circuitos).

Todas las URLs están bajo el prefijo `/torneos/` (`padel_project/urls.py:32`), namespace `torneos` (`torneos/urls.py:4`).

#### Archivos

| Archivo | Líneas | Rol |
|---|---:|---|
| `torneos/views.py` | 2692 | Vistas + toda la lógica de generación de zonas y llave |
| `torneos/models.py` | 689 | `Torneo`, `Inscripcion`, `Grupo`, `EquipoGrupo`, `PartidoGrupo`, `Partido`, `FormatoPersonalizado`, `Circuito`, modelos Americano |
| `torneos/formats.py` | 715 | Llaves oficiales FAP (6–48 parejas) y cálculo/descripción de estructura |
| `torneos/forms.py` | 868 | Alta de torneo, carga de resultados (Normal/W.O./Abandono), reemplazos, formatos |
| `torneos/signals.py` | 143 | Recálculo de tabla de posiciones, invalidación de caché, llaves internas |
| `torneos/americano.py` | 201 | Vistas y scheduler del formato Americano/Mexicano |
| `torneos/emails.py` | 219 | Notificaciones a jugadores elegibles y a organizadores |
| `torneos/admin.py` | 171 | Django admin |
| `torneos/templatetags/torneo_extras.py` | 167 | Helpers de template (nombres de ronda, batch, setvar) |
| `torneos/social.py` | 70 | Placa de campeones vía overlays de Cloudinary |
| `torneos/urls.py` | 124 | Ruteo |

---

### 1. Modelo de datos

#### 1.1 `Torneo` (`torneos/models.py:65-199`)

| Campo | Tipo | Notas |
|---|---|---|
| `estado` | `AB`/`EJ`/`FN` | Inscripción Abierta / En Juego / Finalizado (`models.py:66-69`) |
| `tipo_torneo` | `E`/`G` | Eliminación directa / Fase de grupos + eliminatoria (`models.py:71-73`) |
| `division` | FK nullable | `null` = torneo "libre" (cualquier división) |
| `categoria` | `M`/`F`/`X` | Masculino / Femenino / Mixto |
| `cupos_totales` | int (def. 16) | Alimenta la vista previa de estructura |
| `equipos_por_grupo` | int (def. 3) | Tamaño de zona objetivo cuando no hay llave FAP |
| `forzar_grupos_de_3` | bool | Exige que el total sea divisible por 3 |
| `formato_grupos_4` | `RR`/`LL` | Round-robin (3 partidos) vs Llaves internas (`models.py:103-112`) |
| `estructura_manual` | bool | Si es `True`, la generación de llave IGNORA `get_format(cupos)` y va por la vía genérica (`models.py:152-154`) |
| `formato_personalizado` | FK nullable | Plantilla de zonas + cruces guardada por el organizador |
| `ganador_del_torneo` | FK Equipo | Lo setea `Partido.save()` |

Propiedades: `fecha_fin` (fecha del último partido con ganador, `models.py:184-194`) y `cupos_disponibles` (`models.py:196-199`).

#### 1.2 `FormatoPersonalizado` (`torneos/models.py:8-52`)

Plantilla reutilizable por organización:
- `sizes`: JSON con el tamaño de cada zona, ej. `[3,3,3,3,2]` → 5 zonas, 14 parejas.
- `clasifican_por_grupo`: cuántos pasan por zona (default 2).
- `cruces_manuales`: JSON `[["1A","2B"],["1C",""],...]`. Si está vacío, los cruces se arman con el seeding estándar. Un par con segundo elemento vacío = **bye**.
- Propiedades derivadas: `num_grupos`, `total_parejas`, `resumen` (ej. `"5 zonas (3-3-3-3-2)"`).

#### 1.3 Fase de zonas

- `Grupo` (`models.py:225-240`): pertenece al torneo, tiene `nombre` ("Zona A"/"Grupo A") y `fecha_inicio_default`.
- `EquipoGrupo` (`models.py:243-277`): **es la tabla de posiciones**. Guarda PJ/PG/PP, sets y games a favor/en contra y las diferencias. El orden de mérito está en `Meta.ordering` (`models.py:271-277`):
  1. `-partidos_ganados`
  2. `-diferencia_sets`
  3. `-diferencia_games`
  Cualquier `grupo.tabla.all()` ya viene ordenado por mérito; de ahí sale el "1º/2º/3º de la zona".
- `PartidoGrupo` (`models.py:280-348`): hasta 3 sets (`e1_set1..e2_set3`), `fecha_hora`, `ganador`, `resolucion` (Normal/W.O./Abandono) y totales pre-calculados (`e1_sets_ganados`, `e1_games_ganados`, …). Property `resultado` formatea `"6-4 6-2"`, `"W.O."` o `"… (abandono)"`.

#### 1.4 Fase eliminatoria — `Partido` (`torneos/models.py:354-503`)

- `ronda` (1 = ronda inicial … N = final), `orden_partido`.
- `equipo1`/`equipo2` nullable + `placeholder_e1`/`placeholder_e2` (etiquetas `"1A"`, `"2B"`, `"3A"`) para mostrar el cuadro antes de que se conozcan los clasificados.
- `siguiente_partido`: self-FK que arma el árbol.
- `sets_local` / `sets_visitante`: `JSONField` con los games por set.

**`Partido.save()` es el motor de avance** (`models.py:445-486`):

```python
# 1) Si es la final (siguiente_partido is None) y hay ganador -> campeón
if self.ganador and self.siguiente_partido is None:
    if self.torneo.ganador_del_torneo != self.ganador:
        self.torneo.ganador_del_torneo = self.ganador
        self.torneo.estado = 'FN'
        self.torneo.save()
        Equipo.objects.filter(id__in=equipos_ids).update(esta_activo=False)  # disuelve TODAS las parejas
        # + push "🏆 ¡Felicitaciones, campeones!"

# 2) Avance en el bracket (solo si CAMBIÓ el ganador)
if self.ganador != self.__original_ganador and self.ganador is not None:
    if self.siguiente_partido:
        if self.orden_partido % 2 == 1:  # orden IMPAR -> equipo1 del siguiente
            siguiente.equipo1 = self.ganador
        else:
            siguiente.equipo2 = self.ganador
        siguiente.save()
```

> **Invariante clave:** *el partido de `orden_partido` impar alimenta `equipo1` del siguiente*. Toda la generación de llave (manual, FAP y genérica) respeta esta paridad; ver `es_equipo1 = (i % 2 == 0)` en `views.py:689` y `views.py:1002` (índice 0-based → `orden_partido` = i+1).

`nombre_ronda` (`models.py:418-443`) calcula el nombre legible por distancia al `max(ronda)` del torneo: 0=Final, 1=Semifinal, 2=Cuartos, 3=Octavos, 4=16vos.

---

### 2. `torneos/formats.py` — llaves oficiales FAP

#### 2.1 `TournamentFormat` (`formats.py:23-36`)

```python
@dataclass
class TournamentFormat:
    teams: int
    groups: int
    teams_per_group: Union[int, List[int]]   # nº fijo, o lista de tamaños por zona
    bracket_type: str                        # 'semis'|'quarters'|'octavos'|'16vos'|'custom'
    crossings: Optional[List[...]] = None    # LEGACY, nunca se llena
    bracket_structure: Optional[List[dict]] = None  # [{'id','round','t1','t2','next'}, ...]
    group_names: Optional[List[str]] = None
```

**`crossings` vs `bracket_structure`:**

| | `crossings` | `bracket_structure` |
|---|---|---|
| Forma | lista de pares `(('A',1), ('B',2))` | lista de dicts `{'id','round','t1','t2','next'}` |
| Cuadro | simétrico y completo (todas las posiciones de la ronda 1 son partido) | asimétrico: cada partido declara explícitamente su `next`, y los `t1/t2 = None` son "lo llena el ganador del partido previo" |
| Estado real | **Nunca se popula**: `_build_format` (`formats.py:551-557`) solo setea `bracket_structure` | Es lo que usan todas las llaves FAP |

Consecuencia: la rama legacy de `generar_octavos_logica` (`views.py:817-899`) es código muerto.

#### 2.2 `FAP_LLAVES` y `FORMATS` (`formats.py:43-506`, `formats.py:561`)

Tabla compacta `{parejas: [(id_partido, t1, t2, id_siguiente), ...]}` donde `'1A'` = 1º de la Zona A y `None` = lo ocupa el ganador del partido previo. El partido con `next=None` es la final.

Cubre **exactamente 43 tamaños contiguos: 6 a 48 parejas**. Fuera de ese rango `get_format()` devuelve `None` (`formats.py:564-565`).

Numeración FAP conservada como `id`/`orden_partido` (`formats.py:8-11`):

| Rango de id | Ronda |
|---|---|
| 33–48 | 16avos |
| 49–56 | Octavos |
| 57–60 | Cuartos |
| 61–62 | Semifinales |
| 64 | Final |

Ejemplo (7 parejas, `formats.py:48-52`):
```
(58, '3A', '2B', 61)        # play-in
(61, '1A',  None, 64)       # 1A espera al ganador del 58
(62, '2A', '1B', 64)
(64,  None, None, None)     # FINAL
```

`_build_format` (`formats.py:524-557`):
1. Calcula `depth(mid)` = distancia a la final recursivamente.
2. `round = total_rondas - depth + 1` (la final es la ronda más alta).
3. `_parse_seed('1A')` → `('A', 1)` (`formats.py:511-515`).
4. Tamaños de zona vía `fap_sizes(n)` (`formats.py:518-521`): `n // 3` zonas, las primeras `n % 3` tienen 4 parejas y el resto 3.
5. `bracket_type` según total de rondas: `{2:'semis', 3:'quarters', 4:'octavos', 5:'16vos'}` (`formats.py:508`).

#### 2.3 `calcular_estructura_grupos(count, *, forzar_grupos_de_3, equipos_por_grupo)` (`formats.py:591-623`)

**Fuente de verdad única** compartida entre la generación real y la vista previa del alta. Devuelve `(num_grupos, sizes, nombres, custom_format)`:

- Si existe llave FAP para `count`: usa `custom_format.groups` y `teams_per_group`, nombres `"Zona A".."Zona Z"`.
- Si `forzar_grupos_de_3`: `epg = 3`, `num_grupos = count // 3`.
- Si no: `epg = equipos_por_grupo or 3`, `num_grupos = ceil(count / epg)`, y reparte greedy hasta agotar; nombres `"Grupo A".."Grupo Z"`.

> El prefijo del nombre cambia (`Zona` vs `Grupo`) según haya o no llave FAP — relevante porque el mapeo letra→grupo de la generación de llave hace `nombre.split(' ')[-1]`.

#### 2.4 `describir_estructura(num_equipos, tipo, *, forzar3, equipos_por_grupo)` (`formats.py:626-715`)

Proyección **legible y JSON-serializable** para la vista previa del alta (no decide nada real). Devuelve `{ok, nivel('ok'|'warn'), titulo, flujo[], zonas[[letra,tam]], byes, mensaje}`.

- `tipo='E'` (eliminación directa): calcula `size = _proxima_potencia_de_2(n)` y `byes = size - n`; nombra la ronda inicial con `_RONDA_POR_TAMANO` (`formats.py:578-581`). Advierte si `n < 2`.
- `tipo='G'`: bloquea con `nivel='warn'` si `n < 4`, o si `forzar3` y `n % 3 != 0` (sugiere el múltiplo de 3 más cercano). Si hay llave FAP, etiqueta la ronda vía `_BRACKET_LABELS`; si no, dice `cuadro de nextPow2(max(4, num_grupos*2))` y aclara que no es una llave oficial.

Se consume desde `PreviewEstructuraView` (`views.py:1592-1612`) por `GET /torneos/admin/preview-estructura/?n=&tipo=&forzar3=&epg=` y como `preview_inicial` server-side en el alta/edición (`views.py:1717-1719`, `views.py:1763-1768`).

---

### 3. Inventario de vistas

#### 3.1 Vistas públicas / de jugador

| Vista | URL name | Ruta | Clase base / permisos | Qué hace |
|---|---|---|---|---|
| `TorneoAbiertoListView` (`views.py:2104`) | `abierto_list` | `/torneos/abiertos/` | `ListView`, público | Torneos `AB`, paginado 10. Excluye aquellos donde el equipo del usuario ya está inscripto y expone `mis_torneos` / `mis_torneos_juego` |
| `TorneoEnJuegoListView` (`views.py:2094`) | `en_juego_list` | `/torneos/en-juego/` | `ListView`, público | Torneos `EJ`, paginado 10 |
| `TorneoFinalizadoListView` (`views.py:2053`) | `finalizado_list` | `/torneos/finalizados/` | `ListView`, público | Torneos `FN`, paginado 12, con filtros `?year=` y `?organizacion=` |
| `TorneoPorCiudadView` (`views.py:1984`) | `ciudad` | `/torneos/ciudad/<ciudad>/` | `ListView`, público | SEO local (TP-14): `ciudad__iexact` |
| `MisTorneosView` (`views.py:2575`) | `mis_torneos` | `/torneos/mis-torneos/` | `TemplateView` + `PlayerRequiredMixin` | Agrupa las inscripciones del usuario en abiertos/en juego/finalizados |
| `TorneoDetailView` (`views.py:1832`) | `detail` | `/torneos/<pk>/` | `DetailView`, público | Ficha completa: zonas + tablas, cuadro, `puede_inscribirse`, "Mis partidos" (pendientes/jugados), `share_url` y `placa_url` |
| `TorneoProgramacionView` (`views.py:2610`) | `programacion` | `/torneos/<pk>/programacion/` | `DetailView`, público | Fixture unificado (zonas + bracket) partido en `partidos_con_fecha` (ordenados cronológicamente) y `partidos_sin_fecha`. El template lo renderiza como **tabla** (hora · zona/fase · pareja · pareja) agrupada por día, con **botón «Descargar PDF»** (`window.print()`) y hoja `@media print` propia. |
| `TorneoVivoView` (`views.py:2004`) | `vivo` | `/torneos/<pk>/vivo/` | `DetailView`, público | Scoreboard para TV con auto-refresh (TP-13) |
| `PlacaView` (`views.py:1435`) | `placa` / `placa_app` | `/torneos/<pk>/placa/`, `/torneos/placa/` | `TemplateView`, **público, sin login** | Placa 9:16 para redes. `?tipo=anuncio|campeones|vivo|app`; si no se pasa, se deduce del estado (`AB→anuncio`, `EJ→vivo`, `FN→campeones`). `_featured_match` elige el partido destacado |
| `CircuitoListView` (`views.py:2030`) | `circuito_list` | `/torneos/circuitos/` | `ListView`, público | Circuitos con `activo=True` |
| `CircuitoDetailView` (`views.py:2040`) | `circuito_detail` | `/torneos/circuito/<pk>/` | `DetailView`, público | Ranking acumulado (`Circuito.tabla_posiciones()`) |
| `InscripcionCreateView` (`views.py:2182`) | `inscribirse` | `/torneos/<torneo_pk>/inscribirse/` | `CreateView` + `LoginRequiredMixin` | Ver §4.2 |
| `InscripcionDeleteView` (`views.py:2298`) | `cancelar_inscripcion` | `/torneos/<torneo_pk>/cancelar-inscripcion/` | `DetailView` + `LoginRequiredMixin` + `UserPassesTestMixin` | POST borra la inscripción; `test_func` exige `estado == AB` |

#### 3.2 Vistas de administración / organizador

Todas usan `AdminRequiredMixin` (`views.py:65-71`): `tipo_usuario in ['ADMIN','ORGANIZER']`, si no → mensaje de error + redirect a `core:home`.

| Vista | URL name | Ruta | Scoping por organización | Qué hace |
|---|---|---|---|---|
| `AdminTorneoListView` (`views.py:1383`) | `admin_list` | `/torneos/admin/listado/` | Sí (`get_queryset`, 1388-1396) | Staff ve todo; ORGANIZER solo los suyos; sin organización → vacío |
| `AdminTorneoCreateView` (`views.py:1701`) | `admin_crear` | `/torneos/admin/crear/` | Asigna `organizacion` del user | Alta con `TorneoAdminForm`; dispara `notificar_nuevo_torneo` en `form_valid` |
| `AdminTorneoUpdateView` (`views.py:1737`) | `admin_editar` | `/torneos/admin/<pk>/editar/` | Sí (1750-1757) | Edición; success → `admin_manage` |
| `AdminTorneoDeleteView` (`views.py:1772`) | `admin_eliminar` | `/torneos/admin/<pk>/eliminar/` | Sí (1777-1784) | Baja |
| **`AdminTorneoManageView`** (`views.py:163`) | `admin_manage` | `/torneos/admin/<pk>/gestionar/` | Sí (168-175) | **Panel maestro.** GET arma el contexto de fases; POST despacha 16 acciones (§5) |
| `OrganizadorDashboardView` (`views.py:1615`) | `dashboard` | `/torneos/admin/dashboard/` | Sí (1629-1630) | Métricas: conteo por estado, inscripciones, jugadores únicos, % ocupación de abiertos, partidos jugados/pendientes, próximos y recientes |
| `FormatoPersonalizadoListView` (`views.py:1532`) | `formatos_list` | `/torneos/admin/formatos/` | Sí | Listado de plantillas |
| `FormatoPersonalizadoCreateView` (`views.py:1545`) | `formato_crear` | `/torneos/admin/formatos/nuevo/` | Asigna `creado_por` + `organizacion` | Alta de plantilla |
| `FormatoPersonalizadoUpdateView` (`views.py:1562`) | `formato_editar` | `/torneos/admin/formatos/<pk>/editar/` | Sí | Edición |
| `FormatoPersonalizadoDeleteView` (`views.py:1580`) | `formato_eliminar` | `/torneos/admin/formatos/<pk>/eliminar/` | Sí | Baja |
| `PreviewEstructuraView` (`views.py:1592`) | `admin_preview_estructura` | `/torneos/admin/preview-estructura/` | — | JSON de `describir_estructura`; `n` acotado a `[0, 200]` |
| `EmbudoInscripcionView` | `embudo` | `/torneos/admin/embudo/` | — (métrica de plataforma) | Embudo de inscripción (`services/embudo.py`). Para quien no tiene shell en Render |
| `RevisarTorneosView` | `revisar_torneos` | `/torneos/admin/revisar/` | Sí (acota a los torneos del club) | **Diagnóstico de sólo lectura.** Inconsistencias entre la zona del PARTIDO y la de la TABLA (`services/diagnostico.py`). Para admins agrega la sección **"Impacto de los últimos cambios"** (`services/impacto.py`): a cuántos datos YA existentes los alcanzan los cambios de comportamiento —americanos sin club (que ningún organizador podría gestionar), teléfonos que dejan de engancharse solos en el alta y cuentas fusionadas—. Es la vía para revisar producción antes de un deploy, sin shell. Mismo contenido por terminal: `python scripts/impacto_auditoria.py` |
| `TorneoReplaceTeamView` (`views.py:1159`) | `torneo_reemplazar_equipo` | `/torneos/admin/<pk>/reemplazar-equipo/` | Sí, vía `PermissionDenied` en `get_form_kwargs` (1170-1174) | Reemplaza una pareja en TODO el torneo (Inscripcion, EquipoGrupo, PartidoGrupo, Partido) dentro de `transaction.atomic` |
| `AdminPartidoUpdateView` (`views.py:1303`) | `admin_partido_resultado` | `/torneos/admin/partido/<pk>/resultado/` | Sí (1309-1314) | Carga resultado de bracket (modal HTMX) + push |
| `CargarResultadoGrupoView` (`views.py:1278`) | `cargar_resultado_grupo` | `/torneos/admin/grupo/<pk>/resultado/` | Sí (1283-1288) | Carga resultado de zona (modal HTMX) + push |
| `SchedulePartidoGrupoView` (`views.py:1330`) | `schedule_partido_grupo` | `/torneos/admin/partido-grupo/<pk>/schedule/` | Sí | Programa día/hora + push |
| `SchedulePartidoView` (`views.py:1355`) | `schedule_partido` | `/torneos/admin/partido/<pk>/schedule/` | Sí | Programa día/hora + push |
| `ReplacePartidoTeamsView` (`views.py:2411`) | `replace_partido_teams` | `/torneos/admin/partido/<pk>/replace-teams/` | **No** | Cambia los equipos de un partido de bracket |
| `ReplacePartidoGrupoTeamsView` (`views.py:2428`) | `replace_partido_grupo_teams` | `/torneos/admin/partido-grupo/<pk>/replace-teams/` | **No** | Cambia equipos de un partido de zona; si el equipo entrante ya estaba en otra zona hace un SWAP completo (`_handle_team_change`, 2463-2510) |
| `SwapGroupTeamsView` (`views.py:2516`) | `swap_group_teams` | `/torneos/admin/grupo/<pk>/swap-teams/` | **No** | Intercambia dos equipos entre zonas (tabla + partidos) |
| `crear_torneo_prueba` (`views.py:2331`) | `crear_torneo_prueba` | `/torneos/admin/crear-torneo-prueba/` | `@login_required` + `tipo_usuario == 'ADMIN'` | Utilidad: borra datos previos y crea un torneo con 24 parejas ficticias |

Las vistas de modal responden a HTMX devolviendo `<script>window.location.reload();</script>` cuando llega la cabecera `HX-Request` (p. ej. `views.py:1298-1300`).

#### 3.3 Vistas Americano (`torneos/americano.py`, importadas en `views.py:2686-2692`)

| Vista | URL name | Ruta | Permisos |
|---|---|---|---|
| `AmericanoListView` (`americano.py:57`) | `americano_list` | `/torneos/americanos/` | Público |
| `AmericanoCreateView` (`americano.py:66`) | `americano_crear` | `/torneos/americano/crear/` | `AdminOrOrganizerMixin` |
| `AmericanoJoinView` (`americano.py:98`) | `americano_join` | `/torneos/americano/sumarse/<codigo>/` | **Público, sin cuenta** (solo pide nombre) |
| `AmericanoDetailView` (`americano.py:80`) | `americano_detail` | `/torneos/americano/<pk>/` | Público |
| `AmericanoManageView` (`americano.py:129`) | `americano_manage` | `/torneos/americano/<pk>/gestionar/` | `AdminOrOrganizerMixin` (sin scoping por organización) |

---

### 4. Flujo completo de un torneo

```
[1] Crear torneo (AdminTorneoCreateView)
      └─> notificar_nuevo_torneo() -> email + push a jugadores elegibles
[2] Inscripción
      ├─ jugador: InscripcionCreateView (valida división, categoría, cupos, fecha límite)
      └─ organizador: action='agregar_equipo' | 'agregar_dummy'
[3] action='iniciar_torneo'  -> crea Grupos VACÍOS + cuadro con placeholders + estado=EJ
[4] action='auto_distribuir' o 'asignar_equipo'/'quitar_equipo' -> puebla EquipoGrupo
[5] action='confirmar_grupos' -> genera todos los PartidoGrupo (round-robin por zona)
[6] Carga de resultados (CargarResultadoGrupoView)
      └─> signal actualizar_tabla_de_posiciones -> recalcula EquipoGrupo de la zona
[7] Llave:
      ├─ incremental: action='avanzar_grupo' por zona (rellena placeholders 1A/2B/3A)
      └─ de una vez:  action='generar_octavos' (exige TODAS las zonas cerradas)
[8] Carga de resultados de bracket (AdminPartidoUpdateView)
      └─> Partido.save() propaga el ganador al siguiente_partido
[9] Final resuelta -> Partido.save() fija ganador_del_torneo, estado=FN,
    desactiva las parejas y manda push de campeones
```

#### 4.1 Creación

`TorneoAdminForm` (`forms.py:127-271`):
- El queryset de `formato_personalizado` se restringe a la organización del usuario (`forms.py:173-177`).
- `foto_campeones` se elimina del formulario al CREAR (`forms.py:181-182`, TP-17.1).
- Al crear se prefijan `sede_nombre`, `sede_direccion` y `ciudad` desde la organización (`forms.py:186-191`, TP-17.4).
- `clean()` (`forms.py:244-271`) **bloquea**: cierre de inscripción posterior al inicio, y `cupos_totales < 4` cuando `tipo_torneo == 'G'`. No bloquea cupos "sin formato optimizado" (eso es solo un aviso en la preview).

#### 4.2 Inscripción — `InscripcionCreateView` (`views.py:2182-2294`)

`dispatch` valida en cascada y redirige a `torneos:detail` con `messages.warning` en cada fallo:
1. El usuario tiene equipo.
2. `es_division_permitida(equipo, torneo)`.
3. Categoría: incompatible solo si `torneo.categoria` y `equipo.categoria` difieren y **ninguna** es `'X'` (mixto es comodín).
4. `torneo.estado == AB`.
5. `timezone.now() <= torneo.fecha_limite_inscripcion`.

`form_valid` agrega chequeo anti-duplicado + captura de `IntegrityError` (constraint `inscripcion_unica`, `models.py:211-216`), invalida la caché `perfil_gestion_<id>` de los miembros de la organización y dispara `notificar_nueva_inscripcion`.

**`es_division_permitida`** (`views.py:1793-1830`):

| Caso | Regla |
|---|---|
| `torneo.division is None` | Siempre permitido (torneo libre) |
| Equipo sin ambos jugadores (dummy) | `equipo.division == torneo.division`, o `True` si el equipo no tiene división |
| Pareja "pura" (`orden_p1 == orden_p2`) | `min_orden - 1 <= orden_torneo <= max_orden + 1` (su división ±1) |
| Pareja "mixta" (divisiones distintas) | `min_orden <= orden_torneo <= max_orden` (cualquier división intermedia, inclusive) |

#### 4.3 Zonas: creación → poblado → partidos

**`iniciar_torneo_logica`** (`views.py:407-452`) — PASO 1:
1. Exige `estado == AB` y `count >= 4`.
2. Si `forzar_grupos_de_3` y `count % 3 != 0`, aborta indicando cuántos faltan.
3. Borra grupos previos si existen.
4. `_calcular_estructura_grupos(torneo, count)` → crea los `Grupo` **vacíos**.
5. `estado = EJ`; si hay `formato_personalizado`, además `estructura_manual = True` (`views.py:441-442`).
6. Llama a `generar_octavos_logica(..., solo_estructura=True)` → cuadro con placeholders.

**`_calcular_estructura_grupos`** (`views.py:389-405`): si el torneo tiene `formato_personalizado` con `sizes`, usa esos tamaños y nombres `"Zona A".."Zona Z"`; si no, delega en `formats.calcular_estructura_grupos`.

**`auto_distribuir_logica`** (`views.py:454-483`): baraja los equipos (`shuffle`) y los reparte respetando `sizes`. Bloquea si ya existen `PartidoGrupo`. Borra los `EquipoGrupo` previos.

**`asignar_equipo_logica`** / **`quitar_equipo_logica`** (`views.py:485-508`): mueven un equipo a una zona (borrando su asignación previa en el torneo) o lo devuelven al pool.

**`confirmar_grupos_logica`** (`views.py:510-534`) — PASO 2: verifica que no queden inscriptos sin zona y genera los partidos con `generar_partidos_grupos` (`views.py:150-157`), que crea **todas las `combinations(equipos, 2)`** → 3 partidos para zona de 3, 6 para zona de 4.

**`agregar_zona_logica`** (`views.py:536-620`): añade una zona a un torneo ya `EJ`. Acepta parejas nuevas por textarea (una por línea, se crean como dummy con nombre desambiguado `"Nombre (2)"`) y/o equipos ya inscriptos sin zona (checkboxes). Nombra la zona con la siguiente letra usando el prefijo detectado de las zonas existentes, genera su round-robin, setea `estructura_manual = True` y **borra la llave previa** si existía.

#### 4.4 Carga de resultados y tabla de posiciones

`CargarResultadoGrupoForm.clean` (`forms.py:312-384`) resuelve tres modos (TP-18):

| `resolucion` | Comportamiento |
|---|---|
| `N` Normal | Cuenta sets y games de los 3 parciales; gana quien tenga más sets; empate → `ganador = None` |
| `W` Walkover | Exige `lado_ganador`; limpia todos los sets, fija `sets_ganados` 2-0 y **deja los games en 0** para no distorsionar el desempate |
| `A` Abandono | Exige `lado_abandona`; conserva el parcial cargado (sets y games) pero fuerza `ganador` = el lado opuesto |

`PartidoResultadoForm` (`forms.py:387-542`) hace lo análogo para el bracket, guardando los games en `sets_local`/`sets_visitante` (JSON) y construyendo el string `resultado` (`"6-4, 6-2"`, `"W.O."`, `"6-4 (abandono)"`). Valida máximo 2 sets ganados y que ambos lados de un set se carguen juntos.

**Signal `actualizar_tabla_de_posiciones`** (`signals.py:27-84`): en cada `post_save` de `PartidoGrupo` **recalcula desde cero** todos los `EquipoGrupo` de esa zona (resetea a 0 y re-suma sobre los partidos con ganador), calculando `diferencia_sets` y `diferencia_games`. Si el partido tiene ganador, invalida cachés de ranking de la división y de los jugadores.

#### 4.5 Avance y campeón

- **Incremental**: `avanzar_grupo_logica` (`views.py:1039-1132`) valida que la zona esté cerrada (para formato `LL` con 4 equipos exige ≥4 partidos terminados), reconstruye la tabla si está vacía, deriva la letra de la zona y hace `Partido.objects.filter(torneo=..., placeholder_eX=f"{pos}{letra}").update(equipoX=...)` para 1º/2º/3º. Luego llama a `_resolver_byes`.
- **`_resolver_byes`** (`views.py:1134-1154`): en la ronda mínima del cuadro, si un partido tiene un equipo real y el otro lado no tiene ni equipo ni placeholder, marca `ganador` y `resultado = "Bye"` y guarda → `Partido.save()` propaga.
- El resto del avance es automático vía `Partido.save()`.
- La final dispara campeón + `estado=FN` + desactivación de parejas + push (`models.py:450-472`).
- `action='finalizar_torneo'` (`views.py:356-360`) permite cerrar el torneo manualmente sin campeón.

---

### 5. Acciones POST de `AdminTorneoManageView`

`post()` (`views.py:259-385`) lee `request.POST['action']` y despacha. Todas terminan en `redirect('torneos:admin_manage', pk=torneo.pk)`.

| `action` | Línea | Parámetros POST | Efecto |
|---|---:|---|---|
| `iniciar_torneo` | 263 | — | Crea las zonas vacías, pasa a `EJ`, pre-genera el cuadro con placeholders |
| `auto_distribuir` | 266 | — | Reparte los inscriptos al azar entre las zonas respetando `sizes` |
| `asignar_equipo` | 269 | `equipo_id`, `grupo_id` | Mueve un equipo a una zona (lo quita de su zona anterior) |
| `quitar_equipo` | 272 | `equipo_id` | Saca el equipo de su zona (vuelve al pool sin asignar) |
| `confirmar_grupos` | 275 | — | Valida que no falte nadie y genera los `PartidoGrupo` round-robin |
| `agregar_equipo` | 278 | `equipo_a_inscribir_id` | Inscribe un equipo existente (avisa si ya estaba) |
| `eliminar_inscripcion` | 292 | `inscripcion_id` | Borra la inscripción; solo con `estado == AB`. Si el equipo es dummy, también borra el `Equipo` |
| `agregar_dummy` | 308 | `nombre_dummy_custom` (opc.) | Crea una "Pareja Libre" (`es_dummy=True`) y la inscribe. Sin nombre, autonumera `"Pareja Libre N"` |
| `agregar_zona` | 330 | `nombres_parejas` (textarea), `equipos_sin_zona[]` | Añade una zona nueva a un torneo en juego; marca `estructura_manual` y borra la llave previa |
| `generar_octavos` | 333 | — | Genera la llave **completa** con clasificados reales (§6) |
| `avanzar_grupo` | 336 | `grupo_id` | Envía 1º/2º/3º de esa zona a sus placeholders del cuadro + resuelve byes |
| `reset_bracket` | 341 | — | Borra todos los `Partido` y regenera la llave con la configuración actual |
| `forzar_cuadro_vacio` | 348 | — | Pre-genera el cuadro solo con placeholders (no-op si ya hay partidos) |
| `finalizar_torneo` | 356 | — | Fuerza `estado = FN` |
| `notificar_jugadores` | 362 | — | Re-dispara `notificar_nuevo_torneo` (email + push a elegibles) |
| `set_grupo_date` | 374 | `grupo_id`, `fecha_inicio_default` | Fecha predeterminada de la zona (`GrupoDateForm`) |

> El template `admin_torneo_manage.html:561` emite además `action="convertir_a_llaves"` (con `grupo_id`), pero **no existe rama en `post()`** → el botón redirige sin hacer nada.

#### Contexto que arma el GET (`get_context_data`, `views.py:177-257`)

`inscripciones`, `grupos` (prefetch de tabla y partidos), `partidos_grupo_pendientes`, `fase_asignacion_grupos` (zonas creadas pero sin partidos), `equipos_sin_grupo`, `todos_equipos_asignados`, `equipos_para_inscribir` (filtrados con `es_division_permitida`, tope de 200), `todos_grupos_cargados`, `fase_eliminatoria_existente`, `partidos_eliminacion` y `total_rondas`.

---

### 6. Generación de la LLAVE en detalle

`generar_octavos_logica(request, torneo, solo_estructura=False)` (`views.py:715-1037`).

El parámetro `solo_estructura` distingue **cuadro vacío con placeholders** (`True`, usado por `iniciar_torneo` y `forzar_cuadro_vacio`) de **cuadro con equipos reales** (`False`, usado por `generar_octavos` y `reset_bracket`).

#### 6.0 Selección de rama

```python
fmt = torneo.formato_personalizado
if fmt and fmt.cruces_manuales:                       # RAMA A
    return self._generar_bracket_manual(...)
custom_format = None if torneo.estructura_manual else get_format(count)   # views.py:726
if custom_format:
    if custom_format.bracket_structure: ...           # RAMA B (FAP)
    else: ...                                         # RAMA C (legacy, inalcanzable)
# RAMA D (genérica)
```

`count` es la cantidad de **inscripciones**, no de clasificados.

#### 6.1 RAMA A — cruces manuales (`_generar_bracket_manual`, `views.py:641-713`)

Entrada: `fmt.cruces_manuales` = `[["1A","2B"], ["1C",""], ...]`.

1. Valida que `num_pos = len(cruces)` sea potencia de 2 (siempre lo es porque el form lo exige = `nextPow2(N)/2`). Si no, error + redirect (o `None` si `solo_estructura`).
2. Mapea zonas por letra: `g.nombre.split(' ')[-1].upper()`.
3. `bracket_size = num_pos * 2`, `num_rondas = log2(bracket_size)`.
4. Crea **primero** las rondas 2..N vacías y las enlaza entre sí (`siguiente = ronda+1 [i // 2]`).
5. Ronda 1, por cada posición `i`:
   - Si hay dos etiquetas → crea `Partido(ronda=1, orden_partido=i+1, placeholder_e1/2, siguiente_partido=destino)`.
   - Si hay una sola (bye) → **no crea partido**: coloca al clasificado directamente en el destino de la ronda 2, en `equipo1` si `i % 2 == 0` o en `equipo2` si es impar.
6. Si no es `solo_estructura`, llama a `_resolver_byes`.

#### 6.2 RAMA B — llave oficial FAP (`views.py:743-815`)

1. Ordena `custom_format.bracket_structure` por `round`.
2. Por cada definición crea `Partido(ronda=m['round'], orden_partido=m['id'], placeholder_eX=f"{pos}{letra}")`, resolviendo el equipo real solo si `not solo_estructura` **y** la zona está completa.
3. Segunda pasada: enlaza `siguiente_partido` usando `created_matches[next_id]`.

El `orden_partido` es el **id FAP** (33..64), no un contador. Esto es intencional y compatible con el avance: en las tablas FAP los pares que alimentan un mismo `next` son siempre `(impar, par)`, y `Partido.save()` manda el impar a `equipo1` (`models.py:479-482`).

#### 6.3 RAMA C — legacy simétrica (`views.py:817-899`)

Determina `bracket_size` por `bracket_type` (`semis`→4, `quarters`→8, `octavos`→16, default 4), crea la ronda 1 iterando `custom_format.crossings`, luego las rondas vacías y el enlace. **Inalcanzable hoy**: ningún `TournamentFormat` de `FORMATS` define `crossings`.

#### 6.4 RAMA D — genérica con byes / play-in (`views.py:901-1037`)

**a) Obtención de clasificados** (`solo_estructura=False`, `views.py:906-942`):
- Exige que **todas** las zonas estén cerradas; si no, aborta listando las zonas pendientes y sugiere usar el cuadro vacío + "Avanzar Clasificados".
- `clasif = torneo.formato_personalizado.clasifican_por_grupo or 2`, acotado a `[1, 3]` (`views.py:926`) porque `avanzar_grupo_logica` solo resuelve hasta el 3º.
- Construye `niveles`: `niveles[0]` = 1º de cada zona, `niveles[1]` = 2º, `niveles[2]` = 3º. Corta si hay `< 4` clasificados.

**b) Cuadro vacío** (`solo_estructura=True`, `views.py:954-972`): usa etiquetas en vez de equipos. `num_equipos_teorico = max(4, num_grupos * clasif)`, y `niveles_labels[k][i] = f"{k+1}{LETRAS[i]}"`.

**c) `bracket_size = 2 ** ceil(log2(num_equipos))`, `num_byes = bracket_size - num_equipos`.**

**d) `_orden_seed(niveles, num_byes)`** (`views.py:123-147`):
- Con byes (`num_byes > 0`) o con un número de niveles distinto de 2 → devuelve la lista **aplanada** `[primeros..., segundos..., terceros...]`.
- Sin byes y con exactamente 2 niveles → cruce clásico intercalado con los segundos rotados una posición: `1A, 2B, 1B, 2C, 1C, 2D, ..., 1E, 2A`.

**e) `_seed_con_byes(items, bracket_size)`** (`views.py:77-120`):

```python
num_pos  = bracket_size // 2          # posiciones de la ronda 1
byes     = bracket_size - n
pares_rr = max(0, num_pos - byes)     # cuántas posiciones serán PARTIDO
# pos_partido: pares_rr posiciones repartidas uniformemente (step = num_pos / pares_rr)
bye_items  = items[:byes]             # los MEJORES (primeros de zona) reciben bye
play_items = items[byes:]             # los PEORES juegan el play-in
```
Las posiciones de partido reciben dos items consecutivos de `play_items`; las demás reciben un item de `bye_items` y dejan `None` al lado. **Nunca se enfrentan dos byes.** Las posiciones de partido se reparten separadas para que alimenten cruces distintos de la ronda 2.

*Ejemplo verificado (5 zonas, pasan 2 → 10 clasificados, `bracket_size=16`, `byes=6`, `pares_rr=2`, `pos_partido={0,4}`):*

| pos | slots | Resultado |
|---:|---|---|
| 0 | `2B`, `2C` | Partido (orden 1) → ronda 2 [0].equipo1 |
| 1 | `1A` | Bye → ronda 2 [0].equipo2 |
| 2 | `1B` | Bye → ronda 2 [1].equipo1 |
| 3 | `1C` | Bye → ronda 2 [1].equipo2 |
| 4 | `2D`, `2E` | Partido (orden 5) → ronda 2 [2].equipo1 |
| 5 | `1D` | Bye → ronda 2 [2].equipo2 |
| 6 | `1E` | Bye → ronda 2 [3].equipo1 |
| 7 | `2A` | Bye → ronda 2 [3].equipo2 |

La ronda 1 muestra **solo 2 cruces** (2B-2C y 2D-2E); las 6 parejas con bye arrancan directamente en "cuartos" (ronda 2). `total_rondas` sigue siendo 4, así que el template rotula ronda 1 = Octavos.

**f) Construcción** (`views.py:978-1028`): crea primero las rondas 2..N vacías y las enlaza; después recorre las `bracket_size // 2` posiciones creando `Partido` **solo** donde hay dos slots, y volcando los byes directo a la ronda 2. Con `solo_estructura=True` se escriben `placeholder_eX`; con `False` se escriben `equipoX` y los placeholders quedan en `None`.

**g) `_resolver_byes(torneo)`** (`views.py:1134-1154`) al final si no es `solo_estructura`.

#### 6.5 Qué es un bye y cómo se representa

Un **bye** es un pase directo a la 2ª ronda para una pareja mejor sembrada, necesario cuando la cantidad de clasificados no es potencia de 2. Un **play-in** es el partido de la ronda 1 que sí se juega entre los peor sembrados.

Representación en el modelo:
- **No existe un `Partido` de ronda 1 para el bye.** El equipo/placeholder se escribe directamente en el `Partido` de ronda 2 correspondiente (`views.py:1013-1028`, `views.py:700-707`). Por eso la primera columna del cuadro muestra únicamente los cruces reales.
- Caso residual: si un partido de la ronda mínima queda con un equipo real y el otro lado sin equipo **ni** placeholder, `_resolver_byes` lo cierra con `ganador = <ese equipo>` y `resultado = "Bye"`, lo que dispara la propagación de `Partido.save()`.

#### 6.6 `_resolver_clasificado` y `_zona_completa`

- `_zona_completa(grupo)` (`views.py:622-624`): `not grupo.partidos_grupo.filter(ganador__isnull=True).exists()`.
- `_resolver_clasificado(label, solo_estructura, grupos_map)` (`views.py:626-639`): parsea `"2B"` → `pos=2`, `letra='B'`; devuelve `(equipo, placeholder)` asignando el equipo **solo si** la zona ya terminó; en caso contrario devuelve `(None, label)`.

---

### 7. Americano / Mexicano (TP-09)

Formato **a nivel de jugador individual** (no de pareja), donde los jugadores rotan de compañero. Se juega en canchas de 4 (cada ronda = N/4 partidos) y el puntaje de cada jugador es la **suma de games ganados**.

**Modelos** (`models.py:574-689`): `Americano` (con `tipo` A/M, `num_canchas`, `estado` IN/EJ/FN y `codigo` único de 6 chars autogenerado), `JugadorAmericano` (nombre libre, `user` opcional, `puntos`, `partidos_jugados`, `orden`), `RondaAmericano`, `PartidoAmericano` (`a1/a2` vs `b1/b2`, `games_a`, `games_b`, `cargado`).

**`generar_ronda_americano(americano, numero, jugadores)`** (`americano.py:31-54`): agrupa de a 4 y arma las parejas:
- **Mexicano**: siempre `(a,d)` vs `(b,c)` — fuerte+débil contra los dos del medio, sobre el orden por ranking recibido.
- **Americano**: `pairing = (numero - 1) % 3` → `0:(a,b)/(c,d)`, `1:(a,c)/(b,d)`, `2:(a,d)/(b,c)`, de modo que cada jugador juega con los otros 3 de su cancha.

**Acciones POST de `AmericanoManageView`** (`americano.py:147-201`):

| `action` | Efecto |
|---|---|
| `iniciar` | Exige `n >= 4` y `n % 4 == 0` y estado `IN`. Borra rondas previas. Americano → genera las 3 rondas de una vez; Mexicano → solo la ronda 1. Pasa a `EJ` |
| `siguiente_ronda` | Solo en `EJ`: `recalcular_puntos()`, ordena por `tabla()` y genera la ronda `count+1` según el ranking |
| `cargar_resultado` | `partido_id`, `games_a`, `games_b` → marca `cargado=True` y recalcula puntos |
| `finalizar` | Recalcula y pasa a `FN` |

`Americano.recalcular_puntos()` (`models.py:624-642`) es **idempotente**: reagrega desde cero sobre los partidos `cargado=True` y solo guarda los jugadores cuyo valor cambió.

Inscripción pública por link: `AmericanoJoinView` (`americano.py:98-126`) no requiere cuenta — solo el nombre; si el visitante está autenticado se enlaza el `user`.

### 8. Circuitos (TP-12)

`Circuito` (`models.py:506-562`) agrupa varios `Torneo` en una liga con ranking acumulado.

`tabla_posiciones()` (`models.py:536-562`):
1. Llama a `accounts.utils.calcular_puntos_por_jugador(torneo_ids)`.
2. Arma filas con `puntos`, `victorias`, `partidos`, `torneos_ganados` y `win_rate` (% redondeado a 1 decimal).
3. Ordena por `(puntos, torneos_ganados, win_rate)` descendente.
4. Marca `asciende` para los primeros `cupos_ascenso` y `desciende` para los últimos `cupos_descenso` (0 = sin ascensos/descensos).

Se expone en `CircuitoListView` / `CircuitoDetailView` (públicas). La administración de circuitos vive solo en el Django admin (`admin.py:148-153`, con `filter_horizontal = ('torneos',)`).

### 9. Emails, push y signals

#### 9.1 `torneos/emails.py`

**`jugadores_elegibles_para_torneo(torneo)`** (`emails.py:10-63`) — reglas de elegibilidad:
- `tipo_usuario == PLAYER`, `is_active=True`, `is_dummy=False`, con email no vacío.
- No inscriptos ya en ese torneo (excluye por `equipos_como_jugador1/2`).
- Género compatible con la categoría: `M`→MASCULINO, `F`→FEMENINO, `X`→todos.
- División dentro de `±1` del `orden` de la división del torneo (o cualquiera si el torneo es libre).
- Ciudad: si el torneo tiene ciudad, se excluye a quienes cargaron una ciudad **distinta** (comparación normalizada sin tildes/mayúsculas). Los que no cargaron ciudad reciben igual.

**`notificar_nuevo_torneo(torneo)`** (`emails.py:66-140`): manda push a los elegibles y dispara los emails en un `threading.Thread`, con `time.sleep(0.6)` entre envíos (límite de rate) usando el backend Brevo (`accounts.brevo_backend.BrevoBackend`). Retorna siempre `(0, total_elegibles)`. Se invoca desde `AdminTorneoCreateView.form_valid` (`views.py:1730`) y desde la acción `notificar_jugadores`.

**`notificar_nueva_inscripcion(inscripcion)`** (`emails.py:142-219`): notifica al `receptor_notificaciones` de la organización, con fallback al primer miembro `ORGANIZER` con email; también manda push. Envío en thread.

Templates: `torneos/templates/torneos/emails/nuevo_torneo.html` y `nueva_inscripcion.html`.

#### 9.2 Push helpers en views

`_push_resultado(partido, torneo)` (`views.py:1238-1255`) y `_push_programado(partido, torneo)` (`views.py:1258-1275`) — ambos envuelven todo en `try/except: pass` para que un fallo de push nunca rompa la carga. Se llaman desde `CargarResultadoGrupoView`, `AdminPartidoUpdateView`, `SchedulePartidoGrupoView` y `SchedulePartidoView`.

#### 9.3 `torneos/signals.py` (registrados en `TorneosConfig.ready`, `apps.py:8-9`)

| Signal | Sender | Efecto |
|---|---|---|
| `actualizar_tabla_de_posiciones` (`signals.py:27`) | `post_save` de `PartidoGrupo` | Recalcula desde cero toda la tabla de la zona; si hay ganador, invalida caché de división y de los jugadores de ambos equipos |
| `invalidar_cache_partido_bracket` (`signals.py:87`) | `post_save` de `Partido` | Invalida las mismas cachés cuando el partido de bracket tiene ganador |
| `check_llaves_internas_generacion` (`signals.py:97`) | `post_save` de `PartidoGrupo` | Para `formato_grupos_4 == 'LL'` y zona de 4: si existen exactamente 2 partidos y ambos tienen ganador, crea la Ronda 2 (Ganador vs Ganador y Perdedor vs Perdedor) |

`invalidar_cache_division` (`torneos/signals.py`) borra las tres claves de caché
de la división (`_gen_ALL` / `_MASCULINO` / `_FEMENINO`) y **agenda** el recálculo con
`_programar_recalculo(division_id)`.

**Debounce (auditoría).** Antes cada save disparaba su propio `threading.Thread` con
un recálculo COMPLETO de la división: borrar todos los `RankingJugador` y
reconstruirlos (~10 consultas pesadas + 2 por jugador). Cargar una zona de 24 partidos
—lo que hace el organizador al borde de la cancha— eran 24 recálculos completos
peleándose por la base. Ahora:

- `_programar_recalculo` agenda **uno solo por división** con un `threading.Timer` de
  `settings.RANKINGS_DEBOUNCE_SEGUNDOS` (default 8, override por env).
- Es coalescing por **flanco de entrada**: si ya hay uno agendado no agenda otro (el
  pendiente lee de la base recién cuando corre, así que ve también los cambios
  nuevos). No se posterga indefinidamente mientras siguen llegando resultados.
- El pendiente se saca del registro al **arrancar**, no al terminar: un resultado que
  llega durante el recálculo puede agendar la pasada siguiente.
- Con `RANKINGS_DEBOUNCE_SEGUNDOS = 0` corre **sincrónico** — es lo que usan los tests
  y lo que conviene en comandos de management.

**`update_fields`.** `actualizar_tabla_de_posiciones` ahora corta temprano si el save
declaró `update_fields` y todos caen en `CAMPOS_SIN_IMPACTO` (`fecha_hora`,
`recordatorios_enviados`): programar un horario o marcar un recordatorio enviado
recomputaba la tabla completa del grupo al pedo.

### 10. Template tags (`torneos/templatetags/torneo_extras.py`)

| Tag/filtro | Tipo | Uso |
|---|---|---|
| `get_team_code(equipo, torneo)` | `simple_tag` | Devuelve `equipo.nombre` (antes devolvía un código tipo "A1") |
| `get_team_info(equipo, torneo)` | `simple_tag` | `{'code','name'}`; limpia nombres legacy que contienen emails |
| `get_team_display(equipo, torneo)` | `simple_tag` | Nombre, o `"Esperando resultados"` si no hay equipo |
| `nombre_ronda_dinamico(ronda, total_rondas)` | `simple_tag` | Final/Semifinal/Cuartos/Octavos/16vos por distancia a la final |
| `split(value, delim)` | filtro | Separa un string |
| `batch(value, n)` | filtro | Parte una lista en sublistas de tamaño `n` |
| `short_name(value, max_length=20)` | filtro | Trunca con `"..."` |
| `setvar` | tag | `{% setvar var = value %}` — asigna en el contexto (usado en `admin_torneo_manage.html` para el flag `tiene_pendientes`) |

### 11. Puntos de atención detectados

| # | Ubicación | Problema |
|---|---|---|
| 1 | `views.py:2307` vs `views.py:23` | `Http404` se usa pero no está importado → `NameError` (500) si un usuario sin equipo cancela inscripción |
| 2 | `admin_torneo_manage.html:561` | `action="convertir_a_llaves"` sin handler en `post()` → botón sin efecto |
| 3 | `views.py:817-899` | Rama legacy `crossings` inalcanzable (nunca se popula `crossings`) |
| 4 | `signals.py:120` | `len(partidos_del_grupo) == 2` nunca se cumple en el flujo normal (el round-robin crea 6) → formato `LL` inoperante |
| 5 | `views.py:1118-1119` | `.update(equipoX=c3)` con `c3 = None` puede nulificar un slot ya asignado |
| 6 | `views.py:2411, 2428, 2516` | Sin scoping por organización: un ORGANIZER puede editar partidos de otras organizaciones |
| 7 | `views.py:344` | `reset_bracket` descarta el `HttpResponseRedirect` que devuelve `generar_octavos_logica` |
| 8 | `emails.py:136-137`, `signals.py:17` | Envíos y recálculo de rankings en `threading.Thread` sin control de concurrencia ni reintentos |

---

### Alta sin cuenta (anotarse sin estar registrado)

`torneos/services/alta_sin_cuenta.py` — el camino para quien llega por un flyer o
un link de WhatsApp y todavía no está en la app. Es la ÚNICA vista de inscripción
sin `LoginRequired`, a propósito: pedir cuenta para poder crearse una cuenta era
la fricción que este flujo saca.

| Paso | Qué hace |
|---|---|
| `buscar_jugador` | Enganche automático: email exacto, o teléfono normalizado a 10 dígitos. Si hay más de un candidato **no engancha** (ver más abajo) |
| `buscar_companeros` | Busca jugadores para el selector de "mi compañero ya tiene cuenta". Alimenta un endpoint **público** |
| `obtener_o_crear_jugador` | Si lo encuentra y es **dummy** del organizador, lo asciende a cuenta real **conservando su historial** (mismo id, mismos partidos, mismo ranking). Si no existe, lo crea |
| `generar_password` | `nombre` + 4 dígitos al azar. **No** `nombre123`: se dicta por WhatsApp y `nombre123` lo adivina cualquiera que sepa quién juega, y esa persona vería teléfono e historial del otro |
| `inscribir_sin_cuenta` | Arma la pareja y la inscripción en una transacción, con `select_for_update` sobre el cupo |
| `mensaje_bienvenida` | Texto del WhatsApp con los datos de acceso |

#### El compañero que ya tiene cuenta: se busca, no se recarga

El paso 2 del alta tiene dos ramas excluyentes según el radio
*"¿Tu compañero/a ya usa TodoPadel?"*:

- **Todavía no tiene cuenta** → se cargan nombre, apellido, WhatsApp y email.
- **Ya tiene cuenta** → **sólo un buscador**. Se elige a la persona de la lista y
  al form viaja únicamente `companero_id`.

El motivo del segundo camino: pedirle a alguien que reescriba datos que ya están
en la base es pedirle que los escriba distinto, y ahí nace el duplicado que
después hay que fusionar a mano.

`InscripcionSinCuentaForm.clean()` decide qué exigir según la rama; los campos
del compañero son `required=False` a nivel de campo porque su obligatoriedad
depende de esa elección. En la rama "ya tiene cuenta", `clean()` resuelve el id
contra la base (jugador vivo y no fusionado) y deja el usuario en
`cleaned_data['companero_usuario']`; `inscribir_sin_cuenta` lo usa tal cual, sin
crear nada y **sin tocarle la contraseña**.

| Vista | Nombre | Ruta | Login | Qué hace |
|---|---|---|---|---|
| `BuscarCompaneroPublicoView` | `buscar_companero_publico` | `/torneos/buscar-companero/` | **No** (igual que el alta) | JSON con los candidatos |

Al ser público está escrito para **no** ser un directorio scrapeable de la base:

- Exige 3 caracteres y devuelve como mucho 8 resultados.
- **Nunca devuelve email ni teléfono**: sólo nombre y división, que alcanza para
  distinguir homónimos.
- Email y teléfono se buscan **exactos**. Con `icontains`, escribir `@gmail`
  listaba medio padrón; así hay que saber el dato.
- Throttle por IP: 60 búsquedas cada 10 minutos (`_ip_del_cliente` toma el último
  salto de `X-Forwarded-For`, igual que el throttle del login).

**Acentos.** Los apellidos argentinos están llenos de tildes (Gómez, Martín,
Núñez) y nadie las escribe en el celular. `icontains` es literal, así que "Gomez"
no encontraba a "Gómez" y el buscador parecía roto. Se resuelve del lado de la
consulta con `_patron_sin_acentos()`, que arma un `iregex` con clases de
caracteres (`G[oó]m[eé]z`) y normaliza también lo que escribió el usuario, para
que funcione en las dos direcciones. No se usa `unaccent` de Postgres porque
obligaría a una extensión y a una migración, y en desarrollo la base es SQLite.

**Nombres con dígitos.** `_parece_telefono()` mira que la consulta **no tenga
letras**, en vez de que tenga dígitos: un apellido como "Sim1" tiene un dígito y
con el criterio anterior se iba por la rama de teléfono y no encontraba a nadie.

**Cambio de contraseña obligatorio.** Las cuentas así creadas salen con
`debe_cambiar_password=True`. `accounts.middleware.CambioDePasswordObligatorio`
redirige a `accounts:cambiar_password` hasta que la persona elija la suya: la
contraseña que viajó por un chat no queda vigente. El middleware deja pasar los
pedidos htmx/AJAX (devolver HTML donde se espera otra cosa rompe la página).

**Límite conocido.** La app **no manda WhatsApp por su cuenta**: genera links
`wa.me` que una persona toca. El envío automático necesita la API de WhatsApp
Business (cuenta verificada y costo por mensaje). El punto donde engancharlo es
`AltaListaView`, reusando `mensaje_bienvenida()`.

### El popup de cargar resultado

`torneos/templates/torneos/partials/_form_resultado.html` — **uno solo** para los
dos casos. Antes eran `cargar_resultado_grupo.html` y `admin_partido_form.html`,
casi idénticos y desincronizándose (uno tenía los casilleros en magenta y el otro
no). Ahora cada uno es una línea de `{% include %}` que pasa el partido.

Los seis campos de sets **van por parámetro** (`s1a`, `s1b`, …) y no se leen del
form: el de zona los llama `e1_setN` / `e2_setN` y el de llave
`setN_local` / `setN_visitante`. Asumir un nombre dejaba el marcador vacío.

| Parámetro | Qué es |
|---|---|
| `titulo`, `contexto` | Encabezado y de qué partido se trata ("Zona B", "Semifinal") |
| `equipo1`, `equipo2`, `torneo` | Para resolver el nombre de cada pareja |
| `form` | Resolución (normal / W.O. / abandono), lados y errores |
| `s1a`…`s3b` | Los seis casilleros, en orden |
| `idp` | Prefijo de los ids: zona y llave conviven en la misma página |
| `accion` | URL del POST |

Tres cosas del diseño que vale la pena no volver a romper:

- **Nada de `input-secondary`** en los casilleros: en este tema el secundario es
  magenta, y quedaban seis recuadros fucsia en el medio de una app verde. Borde
  neutro y `focus:input-primary`.
- El encabezado trae el **contexto del partido**. Sin eso, con el popup abierto no
  se sabía de qué zona era el resultado que se estaba cargando.
- **Contador de sets en vivo**: al tipear se muestra "2 – 0" y se pinta al que va
  ganando. Cargar resultados es lo que más se repite en un torneo y un número en
  la casilla de al lado se arrastra hasta la tabla de posiciones; verlo en el
  momento evita el error.

### Guardar sin recargar la página

Cada acción de guardado devuelve **sólo la sección que cambió**, con los headers
de htmx `HX-Retarget` / `HX-Reswap`, y un `HX-Trigger` que el front usa para
cerrar el modal y mostrar el aviso.

| Acción | Qué se refresca |
|---|---|
| Cargar resultado de zona | Sólo esa zona (`refrescar_zona`) |
| Cargar resultado de llave | Sólo la llave (`refrescar_bracket`) |
| Programar horario (zona / llave) | Sólo esa zona / la llave |
| Reemplazar parejas de un partido | Sólo esa zona / la llave |
| Reemplazar pareja en todo el torneo | **Recarga**: cambia zonas y llave a la vez |
| Intercambiar parejas entre zonas | **Recarga**: toca dos zonas, no una |
| Aceptar / rechazar invitación de pareja | Sólo esa cajita (`equipos/partials/_invitacion_resuelta.html`) |

Las invitaciones de pareja siguen el mismo criterio: los dos botones llevan
`hx-post` + `hx-swap="outerHTML"` sobre `#invitacion-<pk>`, y las vistas
`AceptarInvitacionView` / `RechazarInvitacionView` devuelven el parcial cuando
llega `HX-Request` (helper `_respuesta_invitacion`, `equipos/views.py`). Sin htmx
el `<form>` hace el POST de siempre y la vista redirige como antes.

Los parciales son `torneos/templates/torneos/partials/_grupo_panel.html` y
`_bracket.html`. La llave se refresca entera y no una tarjeta suelta porque al
cargar un resultado el ganador avanza: cambia el partido cargado **y** el de la
ronda siguiente.

Antes esto respondía `<script>window.location.reload()</script>`, o sea recargar
~300 KB por cada resultado. En un celular al borde de la cancha eso son segundos
de pantalla muerta, y el organizador carga decenas seguidos.

## Subsistema de cuentas, roles y organizaciones

App transversal del proyecto. Define el modelo de usuario (`AUTH_USER_MODEL = 'accounts.CustomUser'`, `padel_project/settings.py:281`), la autenticación completa, las organizaciones (sedes/clubes), el perfil de jugador con estadísticas, el subsistema de deduplicación de cuentas y las notificaciones Web Push. Se monta bajo `/accounts/` (`padel_project/urls.py:28`).

```
accounts/
├── models.py          (368)  CustomUser, Division, Organizacion, Sponsor, PushSubscription, Notificacion, MergeAuditLog
├── views.py           (869)  login/registro/perfil/rankings/organización/merge/push
├── forms.py           (383)  registro, perfil, login, dummy, merge, organización, sponsor
├── utils.py           (851)  rankings, stats, logros, completitud, dedupe, merge, mails
├── auth_backends.py   (60)   MergedAccountBackend (login multi-mail de cuentas fusionadas)
├── pipeline.py        (57)   save_google_profile (social-auth)
├── push.py            (91)   Web Push / VAPID
├── admin.py           (106)  CustomUserAdmin, DivisionAdmin, OrganizacionAdmin, MergeAuditLogAdmin (RO)
├── resend_backend.py / brevo_backend.py / email_backend.py   backends de email
└── tests.py           (547)  TP-02, TP-06, TP-11, TP-19, TP-20, TP-21
```

> No existe `accounts/signals.py`; `apps.py` es el AppConfig por defecto sin `ready()` (`accounts/apps.py:1-6`). La invalidación de cachés de ranking vive en `torneos/signals.py` y `equipos/signals.py`.

---

### 1. Modelo de datos

#### 1.1 `CustomUser` (`accounts/models.py:54-211`)

Hereda de `AbstractBaseUser + PermissionsMixin`. `USERNAME_FIELD = 'email'`, `REQUIRED_FIELDS = ['nombre','apellido']` (líneas 169-170). Manager propio `CustomUserManager` (líneas 31-51): `create_user` exige email y lo normaliza; `create_superuser` fuerza `is_staff=True`, `is_superuser=True` y **`tipo_usuario='ADMIN'`**.

| Grupo | Campos |
|---|---|
| Identidad | `email` (unique), `nombre`, `apellido`, `numero_telefono`, `imagen` (upload a `perfiles/`) |
| Ficha de juego (TP-19.3) | `posicion_cancha` (D/R/A), `mano_habil` (D/Z), `club`, `ciudad`, `juega_desde` (año), `instagram`, `bio` (max 280) |
| Verificación | `verification_code` (6 chars), `is_verified` |
| Juego | `division` (FK `accounts.Division`, SET_NULL), `genero` (MASCULINO/FEMENINO/OTRO, **sin default** desde la migración `0011_remove_genero_default`) |
| Rol | `tipo_usuario` (PLAYER/ADMIN/ORGANIZER, default PLAYER) |
| Organización / dummy | `organizacion` (FK, `related_name='miembros'`), `is_dummy` |
| Dedupe (TP-20) | `merged_into` (FK self, `related_name='cuentas_fusionadas'`) |
| Django | `is_active`, `is_staff`, `date_joined`, `groups`/`user_permissions` con `related_name` propio para evitar E304 (líneas 144-164) |

Propiedades: `full_name` (línea 179-181), `telefono_numero` (solo dígitos, para `wa.me`, líneas 183-187), `get_avatar_url` (193-197) y **`equipo`** — devuelve el primer equipo activo donde el usuario es `jugador1` o `jugador2` (líneas 199-211); se usa en todo el proyecto (context processor, perfil, matchmaking).

#### 1.2 Resto de modelos

| Modelo | Ubicación | Notas |
|---|---|---|
| `Division` | `models.py:16-25` | `nombre` único + `orden` único (Primera=1 … Octava=8). Vive acá para romper la dependencia circular con `equipos`; `equipos/models.py:3` la re-exporta. |
| `Organizacion` | `models.py:213-252` | `nombre`/`alias` únicos, `descripcion`, `ciudad`, `direccion`, `latitud`/`longitud`, `logo`, `receptor_notificaciones` (FK limitada a `tipo_usuario='ORGANIZER'`), `whatsapp` con `RegexValidator(r'^\+?\d{8,15}$')`. Propiedad `whatsapp_numero` → solo dígitos. |
| `Sponsor` | `models.py:255-272` | FK a `Organizacion` (**nullable**), `nombre`, `imagen`, `link`, `orden`; `Meta.ordering = ['orden']`. |
| `PushSubscription` | `models.py:275-295` | FK user (`related_name='push_subscriptions'`), `endpoint` **unique**, `p256dh`, `auth`, `user_agent`, `created_at`. Varias por usuario (celu + compu). |
| `Notificacion` | `models.py` | FK `usuario` (`related_name='notificaciones'`), `titulo`, `cuerpo`, `url`, `leida`, `creada`. Índice en `(usuario, leida)`. Es el historial de la campanita. |
| `MergeAuditLog` | `models.py:298-323` | Auditoría de fusiones (TP-21): `actor`, `actor_email`, `source_id/email/nombre`, `source_was_dummy`, `target`, `target_email/nombre`, `created_at`. Ordenado `-created_at`. |

---

### 2. Tipos de usuario y control de acceso

#### 2.1 Los tres roles

`CustomUser.TipoUsuario` (`accounts/models.py:56-59`):

| Valor | Label | Quién lo crea | Qué puede hacer |
|---|---|---|---|
| `PLAYER` | Jugador | Registro público (`CustomUserCreationForm.save()` lo fuerza, `forms.py:34-39`), Google OAuth2 y `DummyUserCreationForm` | Perfil propio, crear/aceptar pareja, inscribirse a torneos, ver rankings y "Mis torneos". Único rol que entra al ranking y a los mails/push de torneos nuevos. |
| `ORGANIZER` | Organizador | Solo desde el admin de Django | Todo lo de gestión **acotado a su `organizacion`**: crear/editar sus torneos, cargar resultados, programar partidos, formatos personalizados, ajustes de organización, sponsors, crear jugadores dummy, ver posibles duplicados y consolidar **solo dummies**. |
| `ADMIN` | Admin | `create_superuser` o el admin de Django | Todo lo del organizador **sin filtro de organización** (ve todos los torneos), más editar el perfil de cualquier usuario y **fusionar cuentas reales**. |

Ortogonales: `is_staff`/`is_superuser` (acceso al admin de Django, usados también como escape hatch en varias vistas de `torneos`), `is_dummy` (jugador de relleno sin login) y `merged_into` (cuenta absorbida).

#### 2.2 Mixins de permisos — están duplicados y NO significan lo mismo

**No hay mixins en `accounts`**: cada app definió los suyos.

| Mixin | Archivo:línea | `test_func` | Fallback |
|---|---|---|---|
| `PlayerRequiredMixin` | `torneos/views.py:56-62` | `tipo_usuario == 'PLAYER'` | msg + redirect `core:home` |
| `PlayerRequiredMixin` | `equipos/views.py:17-27` | `tipo_usuario in ['PLAYER','ADMIN']` | msg + redirect `core:home` |
| `PlayerHasNoTeamMixin` | `equipos/views.py:30-41` | lo anterior **y** `request.user.equipo is None` | redirect `equipos:mi_equipo` |
| `PlayerOwnsTeamMixin` | `equipos/views.py:44-61` | lo anterior **y** tiene equipo | redirect `equipos:mi_equipo` |
| `AdminRequiredMixin` | `torneos/views.py:65-71` | `tipo_usuario in ['ADMIN','ORGANIZER']` | msg + redirect `core:home` |
| `AdminRequiredMixin` | `equipos/views.py:64-72` | `tipo_usuario == 'ADMIN'` (**ORGANIZER excluido**) | msg + redirect `core:home` |
| `AdminOrOrganizerMixin` | `torneos/americano.py:17-28` | `is_staff or tipo_usuario in ('ADMIN','ORGANIZER')` | msg + redirect `core:home` |

Todos combinan `LoginRequiredMixin, UserPassesTestMixin`, en ese orden, así que un anónimo se redirige a login antes de evaluar `test_func`.

**Consecuencias prácticas:**
- Un `ORGANIZER` **no** entra a `equipos:admin_list` (`AdminEquipoListView`, `equipos/views.py:382`) porque ahí `AdminRequiredMixin` es ADMIN-only.
- Un `ORGANIZER` **no** entra a las vistas con `torneos.PlayerRequiredMixin` (ej. `MisTorneosView`, `torneos/views.py:2575`), pero un `ADMIN` sí entra a las de `equipos.PlayerRequiredMixin`.
- El scoping por organización se hace **dentro** de la vista, no en el mixin: patrón `if not user.is_staff and user.tipo_usuario == 'ORGANIZER': qs.filter(organizacion=user.organizacion)` (`torneos/views.py:168-175`, `1388-1396`, `1754-1756`, `1781-1783`).

#### 2.3 Gating dentro de `accounts` (inline, sin mixins)

| Vista | URL name | Gate | Línea |
|---|---|---|---|
| `CustomLoginView` / `RegistroView` / `VerifyEmailView` | `login`, `registro`, `verificar_email` | público | 49, 84, 115 |
| `CompleteGoogleProfileView` | `complete_google_profile` | `LoginRequiredMixin`; auto-redirect al home si ya tiene división y teléfono | 21-40 |
| `PerfilView` | `perfil` | `LoginRequiredMixin` — siempre edita **su propio** usuario (`get_object` devuelve `request.user`) | 212-220 |
| `PublicProfileView` | `detalle` | **público** (TP-06, compartible). Contacto detrás de `is_admin`/`is_organizer` | 359-418 |
| `AdminUserUpdateView` | `admin_user_edit` | `test_func: tipo_usuario == 'ADMIN'` (ORGANIZER **no**) | 429-430 |
| `RankingJugadoresListView` | `rankings_jugadores` | público | 283 |
| `OrganizacionListView` / `OrganizacionDetailView` / `…Programacion(Print)View` | `organizador_list`, `organizador_detalle`, `organizacion_programacion(_print)` | **público** | 451, 458, 493, 613 |
| `OrganizacionSettingsView` | `organizacion_settings` | **solo `LoginRequiredMixin`** + 404 si no tiene organización | 623-639 |
| `OrganizacionSponsorsView` / `SponsorUpdateView` / `SponsorDeleteView` | `organizacion_sponsors`, `editar_sponsor`, `eliminar_sponsor` | **solo `LoginRequiredMixin`**, acotado por queryset `organizacion=request.user.organizacion` | 643-689 |
| `DummyUserCreateView` | `crear_dummy_user` | `dispatch`: `tipo_usuario in ['ADMIN','ORGANIZER']` **y** tiene `organizacion` | 700-704 |
| `MergeUserView` | `merge_usuarios` | `test_func: in ['ADMIN','ORGANIZER']` | 723-724 |
| `PosiblesDuplicadosView` | `duplicados` | `test_func: in ['ADMIN','ORGANIZER']`; el POST **discrimina admin vs organizador** | 803-804, 825, 838 |
| `PushSubscribeView` | `push_subscribe` | `LoginRequiredMixin`, solo POST JSON | 760-764 |

En templates el gating es por string: `{% if user.tipo_usuario == 'ORGANIZER' and user.organizacion %}` (`theme/templates/base.html:946`), `{% if user.tipo_usuario == 'ADMIN' or user.tipo_usuario == 'ORGANIZER' %}` (`base.html:1013`), y en `accounts/templates/accounts/perfil.html:118` (herramientas admin) y `:144` (panel de organización).

---

### 3. Usuarios "dummy" (jugadores sin cuenta)

**Qué son.** Jugadores creados por el organizador para completar parejas de gente que no se registró. Suman puntos en el ranking pero no pueden loguear.

**Cómo se crean** — `DummyUserCreationForm.save()` (`accounts/forms.py:347-363`):
- `is_dummy = True`, `tipo_usuario = 'PLAYER'`, **`is_active = False`** (no pueden loguear).
- `organizacion` = la del creador (pasada desde `DummyUserCreateView.form_valid`, `views.py:711-715`).
- Email autogenerado para esquivar el `unique`: `f"dummy_{uuid4()[:8]}@padel.local"`.
- Campos pedidos: `nombre`, `apellido`, `genero` (obligatorio, con opción vacía forzada) y `division`.
- Sin password: `set_password(None)` nunca corre porque se usa `ModelForm.save()`, así que el hash queda inutilizable.

**Cómo se detectan / se muestran**
- `OrganizacionDetailView` expone `jugadores_dummy = organizacion.miembros.filter(is_dummy=True)` (`views.py:488`).
- Autocompletado del organizador etiqueta `" [Dummy]"` (`equipos/views.py:444-446`).
- `Equipo.__str__` marca `[Dummies]` / `[Con Dummy]` (`equipos/models.py:98-103`).
- Torneos filtran equipos de relleno con `Q(es_dummy=True) | Q(jugador1__is_dummy=True, jugador2__is_dummy=True)` (`torneos/views.py:317`, `1196`).

**Dónde SÍ y dónde NO cuentan**

| Contexto | ¿Incluye dummies? | Referencia |
|---|---|---|
| Ranking por división | **SÍ** (solo se excluye `merged_into`) | `accounts/utils.py:64-68`, `228-232` |
| Contador "jugadores" del home | NO (`is_dummy=False`) | `core/views.py:31` |
| Emails + push de torneo nuevo | NO | `torneos/emails.py:29-33` |
| Destinatarios de push por equipo | NO | `accounts/push.py:82-91` |

---

### 4. Deduplicación y fusión de cuentas (TP-20 / TP-21)

#### 4.1 Detección — `find_duplicate_candidates()` (`accounts/utils.py:660-734`)

1. Toma todos los `tipo_usuario='PLAYER'` con `merged_into__isnull=True`, ordenados por `date_joined`.
2. Clave = `_normalizar_nombre("nombre apellido")` → minúsculas, sin tildes (NFKD + descarte de combining), espacios colapsados (`utils.py:651-657`).
3. **Union-Find** con path halving sobre los índices:
   - claves idénticas → mismo grupo → confianza **`alta`**;
   - claves distintas con `difflib.SequenceMatcher(...).ratio() >= 0.88` → confianza **`media`**. Poda: se saltean pares con `abs(len(ka)-len(kb)) > 4`; tope `limit_pairs=20000`.
4. Devuelve grupos de ≥2 usuarios con `{'confianza', 'usuarios', 'sugerido_id'}`; el canónico sugerido es **la cuenta real (no dummy) más antigua**, ordenando primero los grupos de confianza alta.
5. **Nunca fusiona sola** — siempre confirma un humano (UI en `accounts/templates/accounts/duplicados.html`, radio "Principal" + checkboxes "Fusionar").

#### 4.2 Fusión — `merge_users(dummy_user, real_user)` (`accounts/utils.py:768-850`)

Precondiciones (líneas 785-788): no se puede meter una cuenta **real dentro de una dummy** (`ValueError`), ni fusionar una cuenta consigo misma. Sí se permite dummy→dummy (consolidar) y cualquiera→real.

Dentro de `transaction.atomic()`:

1. **Equipos, uno por uno** (líneas 796-835), para no romper la constraint `unique_active_team` (un `.update()` masivo la rompía a mitad de camino):
   - compañero `None` o el propio destino → se reasigna el slot al destino y el equipo se marca `esta_activo=False`;
   - ya existe un equipo `(destino, compañero)` (en cualquier orden, prefiriendo el activo) → se mueve el historial con `_mover_historial_equipo` y el equipo origen se **borra**;
   - no existe → se reasigna el equipo al destino normalizando `jugador1_id < jugador2_id` y se re-`save()` para regenerar nombre/división.
2. **Cierre del origen** (líneas 837-845):
   - `is_dummy=True` → **`delete()`** (no tiene login ni valor propio);
   - cuenta real → `is_active=False` + `merged_into=real_user` (se conserva el email para el login multi-mail).
3. **Recalculo** (auditoría): se agendan con debounce **sólo las divisiones afectadas**
   (la del destino, la del origen y las de sus equipos), y **fuera** del `transaction.atomic`
   para que el hilo vea la fusión ya comiteada. Antes era `for div in Division.objects.all():
   actualizar_rankings_en_bd(div)` sincrónico y dentro del atomic: una fusión eran 8
   recálculos completos bloqueando la respuesta, y como `PosiblesDuplicadosView.post`
   fusiona en loop, 5 duplicados eran 40 recálculos — se comía el timeout de Render.

`_mover_historial_equipo(src_id, dst_id)` (líneas 737-765): reasigna `Inscripcion` y `EquipoGrupo` **evitando duplicados** por torneo/grupo (si ya existe, borra el del origen), y reapunta con `.update()` masivo `PartidoGrupo.equipo1/equipo2/ganador`, `Partido.equipo1/equipo2/ganador` y `Torneo.ganador_del_torneo`.

#### 4.3 Puntos de entrada y permisos

| Entrada | Origen permitido | Permiso |
|---|---|---|
| `MergeUserView` (`accounts:merge_usuarios`) | `MergeUserForm`: origen `is_dummy=True`, destino `is_dummy=False, tipo_usuario='PLAYER'` (`forms.py:370-379`) | ADMIN u ORGANIZER (`views.py:723-724`). Acepta `?dummy_id=` para precargar (`views.py:726-730`) |
| `PosiblesDuplicadosView` POST (`accounts:duplicados`) | cualquier par del grupo detectado | `es_admin = tipo_usuario=='ADMIN' or is_staff`; **si el origen NO es dummy y no sos admin → se rechaza con mensaje** (`views.py:825`, `836-844`) |

Ambos escriben `MergeAuditLog` con un **snapshot del origen tomado ANTES** de fusionar (porque el dummy se borra): `views.py:736-746` y `views.py:846-858`. El admin del log es de solo lectura (`admin.py:85-97`: todos los campos readonly, `has_add_permission`/`has_change_permission` = False).

#### 4.4 Efecto sobre rankings y login

- Toda consulta de ranking filtra `merged_into__isnull=True` / `jugador__merged_into__isnull=True` (`utils.py:33`, `67`, `101`, `231`) → la cuenta absorbida desaparece del ranking (test `accounts/tests.py:249-261`).
- El login sigue funcionando con el mail viejo vía `MergedAccountBackend` (§5.4).
- `CustomLoginView.form_valid` detecta que el mail tipeado ≠ el mail de la cuenta resuelta y muestra "Unificamos tus cuentas…" (`views.py:54-69`).

---

### 5. Autenticación

#### 5.1 Login por email — `CustomLoginForm` (`accounts/forms.py:157-226`)

- Hereda `AuthenticationForm`; `USERNAME_FIELD='email'` hace que el campo `username` sea el mail.
- **Throttle anti fuerza-bruta (TP-21)**: máx **20 fallos por IP en 600 s**, clave de cache `login_fails_<ip>`, con IP tomada del primer valor de `X-Forwarded-For` o `REMOTE_ADDR` (`_client_ip`, líneas 165-172; chequeo 182-188). Testeado en `accounts/tests.py:462-467`.
- Si `authenticate()` falla, hace un segundo pase con `User.objects.get(email__iexact=username)`:
  - si la cuenta tiene `merged_into_id` → error `code='merged'` explicando que puede entrar con ese mail pero la contraseña no coincide (líneas 202-208);
  - si `check_password` OK pero `is_active=False` → guarda `request.session['verification_user_id']` y lanza `code='unverified'` (líneas 209-213);
  - si `check_password` OK y activo → login exitoso (rescata el caso "el mail estaba con otras mayúsculas", líneas 214-218).
- `CustomLoginView.form_invalid` intercepta `code='unverified'` y redirige a `accounts:verificar_email` (`views.py:71-77`).

#### 5.2 Registro — `RegistroView` + `CustomUserCreationForm`

- Campos: `email`, `nombre`, `apellido`, `numero_telefono`, `genero`, `division` (obligatoria) (`forms.py:6-20`); `save()` fuerza `tipo_usuario='PLAYER'` (líneas 34-39). Los `help_text` se anulan para no mostrar los requisitos de contraseña (línea 28).
- `RegistroView.form_valid` (`views.py:90-103`) setea **`is_active=True` e `is_verified=True`**, autologuea con `backend='django.contrib.auth.backends.ModelBackend'` y redirige al home. **No manda mail de verificación.**

#### 5.3 Verificación por código — vestigial

`VerifyEmailView` (`views.py:115-150`) pide un código de 6 dígitos, lo compara con `user.verification_code`, y al acertar activa + verifica + autologuea + limpia la sesión. Tiene **throttle de 8 intentos / 900 s** por usuario (`verify_attempts_<id>`, líneas 131-135, 148).

Ahora bien: **`verification_code` nunca se asigna ni se envía en ningún módulo Python del repo** (solo existe el campo `models.py:93` y el template `accounts/templates/accounts/emails/verification_email.html`). El único camino a esta vista es la sesión `verification_user_id` que setea `CustomLoginForm` para cuentas `is_active=False` (que en la práctica son los dummies), y el `dispatch` redirige a login si esa clave no está (`views.py:120-123`). Es decir: **el flujo quedó muerto tras pasar el registro a auto-verificado.**

#### 5.4 Backends (`padel_project/settings.py:289-294`)

```python
AUTHENTICATION_BACKENDS = [
    'social_core.backends.google.GoogleOAuth2',
    'accounts.auth_backends.MergedAccountBackend',   # TP-20
    'django.contrib.auth.backends.ModelBackend',
]
```

`MergedAccountBackend` (`accounts/auth_backends.py`):
- Busca por `email__iexact`; si la cuenta **no** tiene `merged_into_id`, devuelve `None` y deja actuar a `ModelBackend` (líneas 44-46).
- `resolver_canonica()` sigue la cadena `merged_into` con set de visitados y tope de 10 saltos (anti-ciclos, líneas 15-23) — soporta cadenas p3→p2→p1 (test `accounts/tests.py:311-320`).
- Acepta **la contraseña de la canónica O la de la cuenta vieja**, y en ambos casos devuelve la canónica (líneas 55-60). Tests: `accounts/tests.py:289-330`.

#### 5.5 Google OAuth2 (`social_django`)

- App + middleware + context processors registrados (`settings.py:102`, `120`, `138-139`); URLs bajo `/social-auth/` con namespace `social` (`padel_project/urls.py:34`).
- Credenciales por env (`GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`), scopes `openid` + email + profile, `SOCIAL_AUTH_ASSOCIATE_BY_EMAIL = True` (`settings.py:304-312`).
- Pipeline (`settings.py:315-329`): incluye `associate_by_email` (vincula si el mail ya existe) y **`accounts.pipeline.save_google_profile`** antes de `user_details`.
- `save_google_profile` (`accounts/pipeline.py:14-57`): marca `is_verified=True`, completa `nombre`/`apellido` desde `given_name`/`family_name` si están vacíos, y descarga la foto (`requests.get(picture_url, timeout=10)`, extensión según `Content-Type`) guardándola en `user.imagen`; si la foto falla, solo loguea y no rompe el login. **No hace redirects** (a esa altura el usuario aún no está en sesión).
- Redirects: nuevo usuario → `/accounts/completar-perfil/`; login normal → `/`; error → `/accounts/login/` (`settings.py:331-333`). En producción `SOCIAL_AUTH_REDIRECT_IS_HTTPS = True`.
- `CompleteGoogleProfileView` (`views.py:21-44`) usa `GoogleProfileCompletionForm` (teléfono obligatorio, género, división) y se auto-saltea si ya hay `division_id` **y** `numero_telefono`.

#### 5.6 Password reset

Rutas explícitas con las vistas nativas de Django para fijar el namespace (`accounts/urls.py:35-47`): `password_reset` (templates `registration/password_reset_email.html` + `..._html.html`), `password_reset_done`, `reset/<uidb64>/<token>/`, `reset/done/`.

#### 5.7 Envío de email

| Entorno | Backend |
|---|---|
| `DEBUG=True` | `django.core.mail.backends.console.EmailBackend` (`settings.py:385`) |
| Producción | `accounts.resend_backend.ResendBackend` — POST a `https://api.resend.com/emails` con `RESEND_API_KEY`, extrae el HTML de `message.alternatives`, timeout 15 s (`accounts/resend_backend.py`) |
| Alternativos | `accounts/brevo_backend.py` (API Brevo) y `accounts/email_backend.py::IPv4EmailBackend` (SMTP forzando AF_INET) |

`DEFAULT_FROM_EMAIL` = `noreply@<CUSTOM_DOMAIN>` con fallback `noreply@todopadel.club` (`settings.py:394-398`).

---

### 6. Organización (sedes / clubes)

| Vista | URL | Qué hace |
|---|---|---|
| `OrganizacionListView` | `/accounts/organizadores/` | listado público ordenado por nombre (`views.py:451-455`) |
| `OrganizacionDetailView` | `/accounts/organizador/<pk>/` | micrositio público: sponsors ordenados, torneos activos (`AB`,`EJ`), historial (`FN`, primeros 5 + flag `has_more_historial`), miembros `tipo_usuario='ORGANIZER'` y jugadores dummy (`views.py:458-490`) |
| `OrganizacionProgramacionView` | `/accounts/organizador/<pk>/programacion/` | grilla de partidos de la org **por día jugado**. El selector `?fecha=YYYY-MM-DD` se arma con `TruncDate` sobre las fechas de los partidos, no con `fecha_inicio` de los torneos: un torneo de sábado y domingo antes tenía una sola entrada (el sábado) y al elegirla imprimía los dos días juntos. Los partidos **sin** hora siguen colgando del torneo que arranca ese día, porque no tienen fecha propia. Mezcla `PartidoGrupo` + `Partido` en dicts normalizados y separa `partidos_con_fecha` de `partidos_sin_fecha`. Regresión cubierta por `accounts.tests.ProgramacionOrganizacionFechasTests`. |
| `OrganizacionProgramacionPrintView` | `…/programacion/imprimir/` | misma lógica, template B/N minimalista `accounts/print/organizacion_programacion.html` (`views.py:613-619`) |
| `OrganizacionSettingsView` | `/accounts/organizacion/ajustes/` | edita **la organización del usuario logueado** (`get_object` → `user.organizacion`, Http404 si no tiene). `OrganizacionForm` filtra `receptor_notificaciones` a los `ORGANIZER` de esa misma org (`forms.py:290-295`) |
| `OrganizacionSponsorsView` | `/accounts/organizacion/sponsors/` | CreateView que asigna `form.instance.organizacion = user.organizacion` y lista los existentes (`views.py:643-665`) |
| `SponsorUpdateView` / `SponsorDeleteView` | `…/sponsors/<pk>/editar|delete/` | queryset restringido a `Sponsor.objects.filter(organizacion=request.user.organizacion)` (`views.py:667-689`) |

Notificaciones al organizador: `Organizacion.receptor_notificaciones`; si está vacío, fallback al primer miembro `ORGANIZER` con email (`torneos/emails.py:155-167`).

---

### 7. Perfil de jugador

#### 7.1 Perfil propio — `PerfilView` (`views.py:212-279`)

`UpdateView` sobre `request.user` con `CustomUserProfileForm`. El form (`forms.py:74-154`) permite editar imagen, email, nombre, apellido, teléfono, género, división y la ficha TP-19.3; `password = None` lo oculta. Validaciones propias:
- `clean_instagram` normaliza el handle (saca URL, query y `@`) y valida `[A-Za-z0-9._]{1,30}` (líneas 134-144);
- `clean_juega_desde` exige un año entre 1950 y el actual (líneas 146-154).
- Para ADMIN/ORGANIZER/staff, `division` deja de ser obligatoria (líneas 130-132).

Contexto:
- `ProfileContextMixin.get_profile_context()` (`views.py:153-209`): para PLAYER arma `stats`, `achievements`, `ranking_info`, `torneos_activos`/`torneos_finalizados` y `proximos_partidos` (bracket + zona sin ganador, en torneos `AB`/`EJ`, ordenados por `fecha_hora`), todo cacheado 300 s en `perfil_stats_ctx_<id>`. Invitaciones pendientes (enviadas y recibidas) siempre, sin cachear.
- `completitud` solo para PLAYER (`views.py:230-233`).
- **Dashboard de gestión** si es su propio perfil y es ADMIN/ORGANIZER (`views.py:236-277`): ADMIN ve **todos** los torneos, ORGANIZER solo los de su organización; prefetch de inscripciones; marca `ins.alerta_division = 'SUPERIOR'|'INFERIOR'` comparando `equipo.division.orden` vs `torneo.division.orden`; cuenta inscripciones del día. Cacheado 300 s en `perfil_gestion_<id>` (invalidado en `torneos/views.py:2276`).

#### 7.2 Perfil público — `PublicProfileView` (`views.py:359-418`)

- **Sin login** (TP-06), para que sea compartible; test en `accounts/tests.py:44-47`.
- Contexto cacheado 300 s en `public_profile_ctx_<id>`: `stats`, `achievements`, `ranking_info`, torneos activos/finalizados.
- No cacheado: `can_invite` (visitante autenticado ≠ perfil, **ninguno con equipo**, misma `division_id`), `is_admin`, `is_organizer` (gatean los datos de contacto en el template) y `share_url`.
- `AdminUserUpdateView` (`views.py:421-448`) reusa el template `accounts/perfil.html` con `is_admin_editing=True` para que un ADMIN edite a otro y vuelve al perfil público del editado.

#### 7.3 Rankings — `RankingJugadoresListView` (`views.py:283-356`)

Muestra **una división por vez**. División: `?division=<id>`, si no la del usuario logueado, si no la primera. Género: `?genero=MASCULINO|FEMENINO` (cualquier otro valor → sin filtro). Delega el cálculo en `get_division_rankings`.

---

### 8. Push notifications (TP-11)

**Modelo.** `PushSubscription` (endpoint único, `p256dh`, `auth`, `user_agent`); N dispositivos por usuario.

**Config.** `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY`, `VAPID_ADMIN_EMAIL` (default `mailto:admin@todopadel.club`) por env (`settings.py:296-300`). `push_activo()` = ambas claves presentes; si no, **todo es no-op silencioso** (`accounts/push.py:16-17`, test `accounts/tests.py:522-526`).

**Flujo de alta/baja:**
1. `/instalar/` renderiza `#btn-push` con `data-vapid-key` (desde `settings.VAPID_PUBLIC_KEY`, `core/views.py:69-73`), `data-subscribe-url` y `data-csrf` (`core/templates/core/instalar.html:103-117`); solo se muestra logueado.
2. `theme/static/js/push.js` verifica soporte (`serviceWorker` + `PushManager` + `Notification`), pide permiso, hace `pushManager.subscribe({userVisibleOnly:true, applicationServerKey: urlBase64ToUint8Array(vapidKey)})` y POSTea `{endpoint, keys}` con `X-CSRFToken`. El botón alterna a "Desactivar", que hace `sub.unsubscribe()` + POST `{action:'unsubscribe', endpoint}`. Mensaje específico para iPhone (hay que instalar la PWA primero, iOS 16.4+).
3. `PushSubscribeView` (`views.py:760-796`, solo POST): parsea JSON (400 si es inválido), exige `endpoint` y `keys.p256dh`/`keys.auth`, y hace `update_or_create` por endpoint guardando user + `HTTP_USER_AGENT[:255]`. Re-suscribir el mismo endpoint no duplica (test `accounts/tests.py:493-506`).
4. El service worker (`theme/templates/pwa/sw.js`, servido en `/sw.js` para scope `/`) escucha `push` (título/body/icon/badge/tag, `data.url`) y `notificationclick` (enfoca una ventana existente que matchee la URL o abre una nueva).

**Envío** — `send_push_to_users(users, *, title, body, url='/', tag=None, guardar=True)`: acepta queryset/lista de usuarios o IDs, **guarda una `Notificacion` por destinatario** (ver §8.1) y después despacha el push en un `threading.Thread(daemon=True)` para no bloquear el request; `ttl=86400`; las suscripciones que devuelven **404/410 se borran** (`_enviar_a_suscripcion`, test `accounts/tests.py:528-541`). Helpers: `send_push_to_user`, `guardar_en_panel(user_ids, …)`, `_invalidar_contador(user_ids)` y `jugadores_de_equipos(*equipos)` (excluye dummies).

> El guardado va **antes** del `if not push_activo(): return`, a propósito: hoy VAPID no está configurado en producción, así que sin eso el panel quedaría siempre vacío. Va envuelto en `try/except` porque un aviso no puede llevarse puesta la operación que lo disparó.

**Disparadores existentes:**

| Evento | Título | Origen |
|---|---|---|
| Invitación de pareja | 🤝 Te invitaron a formar pareja | `equipos/views.py:258-269` |
| Invitación aceptada | 🎾 ¡Invitación aceptada! | `equipos/views.py:321-332` |
| Torneo nuevo | 🎾 Nuevo torneo disponible | `torneos/emails.py:85-96` |
| Nueva inscripción (al organizador) | 📝 Nueva inscripción | `torneos/emails.py:169-181` |
| Resultado cargado | 📊 Resultado cargado | `torneos/views.py:1238-1255` |
| Partido programado | 📅 Partido programado | `torneos/views.py:1258-1275` |
| Torneo finalizado (campeones) | 🏆 ¡Felicitaciones, campeones! | `torneos/models.py:461-472` |

Todos van envueltos en `try/except` para que un fallo de push nunca rompa la operación de negocio.

#### 8.1 Panel de notificaciones (la campanita)

**El problema que resuelve.** Hasta acá todo aviso era Web Push y nada más. Si el celular estaba en
silencio, si el usuario descartaba el globito, o si nunca dio permiso (o si VAPID no está
configurado, que es el caso hoy), el aviso **se perdía y no había ningún lado donde ir a buscarlo**.

**Modelo `Notificacion`** (`accounts/models.py`):

| Campo | Tipo | Notas |
|---|---|---|
| `usuario` | FK → `CustomUser` | `related_name='notificaciones'` |
| `titulo` | `CharField(120)` | Se trunca a 120 al guardar |
| `cuerpo` | `TextField(blank=True)` | |
| `url` | `CharField(300)`, default `/` | A dónde lleva al tocarla |
| `leida` | `BooleanField(False)` | |
| `creada` | `DateTimeField(auto_now_add)` | `ordering = ['-creada']` |

Índice `notif_usuario_leida_idx` sobre `(usuario, leida)`: es exactamente el filtro del contador del
navbar, que corre en **cada request** de usuario logueado.

Propiedad `destino_seguro`: devuelve `url` sólo si empieza con `/` y no con `//`; si no, `/`. Las
notificaciones las arma el código de la app, pero el redirect se limita a rutas internas para no
dejar un open redirect a mano (test `accounts.tests.PanelNotificacionesTests`).

**Vistas** (`accounts/views.py`, URLs en `accounts/urls.py`):

| Vista | URL | Qué hace |
|---|---|---|
| `NotificacionListView` | `accounts:notificaciones` | Lista paginada de a 30, `template accounts/notificaciones.html` |
| `NotificacionAbrirView` | `accounts:notificacion_abrir` | GET: marca leída (sólo las propias, si no 404) y redirige a `destino_seguro` |
| `NotificacionLeerTodasView` | `accounts:notificaciones_leer_todas` | POST: `update(leida=True)` masivo |

**Contador del navbar.** `padel_project/context_processors.py::notifications` agrega
`notificaciones_sin_leer` al contexto global. Va dentro del bloque **cacheado 60 s** en
`notifications_count_<user_id>`, así que al crear o marcar leída una notificación hay que invalidar
esa clave — de eso se ocupa `accounts.push._invalidar_contador`.

**UI.** Campanita en `base.html` (navbar-end, antes del avatar) con `indicator-item badge badge-error`
mostrando el número; entrada "Notificaciones" en el dropdown del avatar; y el service worker
(`sw.js`) ya abría la `data.url` de la notificación push al tocarla, así que las dos vías llevan al
mismo lugar.

---

### 9. `accounts/utils.py` — función por función (851 líneas)

| Función | Líneas | Qué hace |
|---|---|---|
| `get_division_rankings(division, genero=None, force_recalc=False)` | 6-279 | **Dos caminos.** Con `force_recalc=False`: lee la tabla persistida `RankingJugador` (filtrando `merged_into__isnull=True`, ordenando por `-puntos, -torneos_ganados, -victorias`), prefetchea equipos para evitar N+1, y **agrega al final con 0 pts a los jugadores de la división que no están en la tabla**. Con `force_recalc=True`: recalcula desde `Partido`/`PartidoGrupo`/`Torneo`. Cachea 300 s en `rankings_jugadores_div_<id>_gen_<ALL\|MASCULINO\|FEMENINO>`. |
| — esquema de puntos | 115-219 | 15 pts por victoria de zona; por **ronda máxima** alcanzada en la llave: 45 (octavos=1), 90 (cuartos=2), 180 (semi=3), 360 (final=4); **600 al campeón**, excluyente de los puntos de ronda. Orden final: puntos → torneos ganados → win rate → victorias. |
| `calcular_puntos_por_jugador(torneo_ids)` | 281-367 | Mismo esquema de puntos pero para un **conjunto arbitrario de torneos** (circuitos, TP-12). Devuelve `{jugador_id: {puntos, victorias, partidos, torneos_ganados}}`. Deliberadamente independiente para no tocar el ranking existente. |
| `get_user_ranking(user)` | 370-385 | Busca al usuario dentro de `get_division_rankings(user.division)`; `None` si no tiene división o no aparece. |
| `get_player_stats(jugador)` | 387-529 | Núcleo de estadísticas, cacheado 300 s en `player_stats_<id>`. Sin equipos → todo en 0. Calcula partidos/victorias/derrotas/win_rate con `.count()` directos (sin N+1) sobre `Partido` + `PartidoGrupo`; títulos vía fallback `equipos_como_jugador*.filter(torneos_ganados__isnull=False)`; `inscripciones` con `select_related` profundo; **`resultados_recientes`**: últimos 8 partidos con ganador, con rival, resultado, `gano` y etiqueta `W.O.`/`Abandono`; **`racha_actual`** y **`racha_maxima`** sobre el historial completo en orden cronológico. |
| `get_player_achievements(jugador, stats)` | 532-556 | 6 logros derivados de las stats ya cacheadas: 🏆 Campeón (`tg>0`), 🔥 Racha (`rmax>=3`), 🎾 +10 partidos (`pj>=10`), 🎯 Efectivo (`wr>=60 and pj>=5`), y dos **hardcodeados en `False`** por falta de histórico: 💯 100% en zona y ⭐ Top 10. |
| `get_profile_completeness(user)` | 559-580 | % de perfil completo + checklist con CTAs: foto, división, pareja (`user.equipo`), ficha de juego (cualquiera de posición/mano/club/ciudad/juega_desde/bio) e Instagram. |
| `send_email_async(subject, html_template, context, recipient_list, from_email=None)` | 582-619 | Renderiza el template, deriva el texto plano con `strip_tags`, usa `DEFAULT_FROM_EMAIL` si no se pasa remitente y envía en un `threading.Thread` con `fail_silently=False` (loguea con `print` + traceback). Único consumidor real: invitaciones de pareja (`equipos/views.py:240-256`). |
| `actualizar_rankings_en_bd(division)` | 621-648 | **Borra** todos los `RankingJugador` de la división, recalcula con `force_recalc=True` y persiste puntos/torneos_ganados/victorias/partidos. Se agenda con debounce desde `torneos/signals.py` y, al final de cada merge, **sólo para las divisiones afectadas**. |
| `_normalizar_nombre(s)` | 651-657 | minúsculas + sin tildes (NFKD, descarta combining) + espacios colapsados. También lo reusa el filtro por ciudad de los mails de torneo (`torneos/emails.py:24`). |
| `find_duplicate_candidates(limit_pairs=20000)` | 660-734 | Ver §4.1. |
| `_mover_historial_equipo(src_id, dst_id)` | 737-765 | Ver §4.2. |
| `merge_users(dummy_user, real_user)` | 768-850 | Ver §4.2. |

---

### 10. Caché — claves usadas

| Clave | TTL | Se escribe en | Se invalida en |
|---|---|---|---|
| `rankings_jugadores_div_<id>_gen_<X>` | 300 s | `utils.py:92, 112, 278` | `torneos/signals.py:14`, `equipos/signals.py:32` (**sin el sufijo `_gen_`**) |
| `player_stats_<id>` | 300 s | `utils.py:410, 528` | `torneos/signals.py:22-24` |
| `perfil_stats_ctx_<id>` | 300 s | `views.py:202` | — |
| `public_profile_ctx_<id>` | 300 s | `views.py:401` | — |
| `perfil_gestion_<id>` | 300 s | `views.py:276` | `torneos/views.py:2276` |
| `login_fails_<ip>` | 600 s | `forms.py:193` | — |
| `verify_attempts_<user_id>` | 900 s | `views.py:148` | — |
| `notifications_count_<id>` | 60 s | `padel_project/context_processors.py:74` | — |
| `home_stats` | 3600 s | `core/views.py:37` | — |

El context processor `notifications` (`padel_project/context_processors.py:19-75`) expone además `user_sin_foto` y `user_sin_equipo`, ambos condicionados a `tipo_usuario == 'PLAYER'`.

---

### 11. Riesgos y bugs verificados

| # | Severidad | Dónde | Detalle |
|---|---|---|---|
| 1 | Alta | `accounts/views.py:721` + `:752-753` | **`MergeUserView` revienta después de fusionar.** `success_url = reverse_lazy('accounts:organizacion_list')` no existe (la ruta se llama `organizador_list`, `urls.py:21`) → `NoReverseMatch`; y el otro branch redirige a `accounts:organizacion_detail` con `slug=alias`, ruta que tampoco resuelve (ver #2). La fusión ya se ejecutó y se auditó cuando falla la respuesta. |
| 2 | Alta | `accounts/urls.py:27` + `views.py:458-465` | La ruta `organizacion/detalle/<slug:slug>/` apunta a `OrganizacionDetailView`, pero `Organizacion` no tiene campo `slug` (usa `alias`, `models.py:215`) y la vista no define `slug_field` → `FieldError` al resolver. |
| 3 | Alta | `accounts/views.py:700-704` | `DummyUserCreateView.dispatch` lee `request.user.tipo_usuario` **antes** de `super().dispatch()`, así que `LoginRequiredMixin` nunca corre primero: un anónimo produce `AttributeError` (500) en lugar del redirect a login. |
| 4 | Media | `accounts/views.py:623, 643, 667, 678` | Las 4 vistas de gestión de organización/sponsors usan **solo `LoginRequiredMixin`**, sin chequeo de rol. Un `PLAYER` con `organizacion` asignada puede editar la organización y sus sponsors. |
| 5 | Media | `accounts/views.py:676, 688-689` + `models.py:256-261` | `Sponsor.organizacion` es nullable y las vistas filtran por `organizacion=request.user.organizacion`; un usuario **sin** organización (`None`) matchea los sponsors huérfanos y puede editarlos o borrarlos. |
| 6 | Media | `accounts/views.py:779-781` | El `unsubscribe` de push borra por endpoint **sin filtrar por `user`**: cualquier logueado que conozca un endpoint ajeno lo desuscribe. |
| 7 | Media | `accounts/utils.py:11` vs `torneos/signals.py:14`, `equipos/signals.py:32` | Las claves de ranking se escriben con sufijo `_gen_<X>` pero se invalidan sin él → los rankings filtrados por género quedan hasta 300 s desactualizados tras cargar un resultado. |
| 8 | ~~Media~~ **resuelto** | `accounts/utils.py` | Cada fusión disparaba `actualizar_rankings_en_bd` para **todas** las divisiones, síncrono y dentro del atomic. Ahora agenda con debounce sólo las afectadas. |
| 9 | Baja | `accounts/views.py:90-103`, `models.py:93` | Flujo de verificación por email **muerto**: `verification_code` no se genera ni se envía en ningún lado; el registro auto-verifica. Quedan campo, vista, form y template huérfanos. |
| 10 | Baja | `accounts/forms.py:47-52, 64-71` + `admin.py:21-25` | `CustomUserAdminForm` permite pegar un hash de contraseña arbitrario directo en `user.password` (clonar la clave de otro usuario) y el admin muestra el hash real en un campo readonly. Solo accesible desde el admin de Django, pero es una puerta de escalada. |
| 11 | Informativo | `accounts/utils.py:437-442` | El conteo de títulos usa `hasattr(Partido, 'es_final')`, campo que **no existe** en `torneos.models.Partido`; siempre corre el fallback por `equipos_como_jugador*.filter(torneos_ganados__isnull=False)`. La rama muerta invita a confusión. |
| 12 | Informativo | `torneos/views.py:56-67` vs `equipos/views.py:17-68` | Cuatro mixins con los mismos dos nombres y semánticas distintas. Conviene unificarlos en `accounts` (p. ej. `accounts/permissions.py`) y que las apps importen de ahí. |

---

## Subsistemas de equipos y core

Documentación técnica verificada contra el código en `C:\Users\egome\Documents\ClaudeCode\padel_project_web`. Django 5.2.8 (`requirements.txt`), django-autocomplete-light 3.12.1, python-dateutil 2.9.

---

### 1. App `equipos`

Registrada como `equipos.apps.EquiposConfig` (`padel_project/settings.py:106`); su `ready()` importa `equipos.signals` (`equipos/apps.py:8-9`). Montada bajo el prefijo `/equipos/` (`padel_project/urls.py:30`).

#### 1.1 Modelo `Equipo` (la pareja)

`equipos/models.py:6-245`

| Campo | Tipo | Detalle |
|---|---|---|
| `nombre` | `CharField(100, unique=True, blank=True)` | Autogenerado en `save()`. `unique=True` a nivel BD. |
| `jugador1` | `FK(AUTH_USER_MODEL, CASCADE, null, blank)` | `related_name='equipos_como_jugador1'` |
| `jugador2` | `FK(AUTH_USER_MODEL, CASCADE, null, blank)` | `related_name='equipos_como_jugador2'` |
| `division` | `FK(accounts.Division, PROTECT, null, blank)` | `PROTECT`: no se puede borrar una división con equipos. |
| `fecha_creacion` | `DateTimeField(auto_now_add=True)` | |
| `esta_activo` | `BooleanField(default=True)` | Pensado para soft-delete; ver §1.7. |
| `categoria` | `CharField(1, choices=Categoria)` | `M` Masculino / `F` Femenino / `X` Mixto. Default `MIXTO`. |
| `es_dummy` | `BooleanField(default=False)` | "Es Pareja Libre (Dummy)": equipo relleno para completar grupos. |

**Constraint** (`equipos/models.py:30-36`):

```python
models.UniqueConstraint(
    fields=['jugador1', 'jugador2'],
    condition=models.Q(esta_activo=True),
    name='unique_active_team'
)
```

Constraint parcial: los mismos dos jugadores no pueden tener dos equipos **activos** simultáneos. Introducido en `equipos/migrations/0008_remove_rankingequipo_division_and_more.py`, que a la vez eliminó el `unique_together` anterior y borró el modelo `RankingEquipo`.

##### Lógica de `save()` (`equipos/models.py:56-96`)

Se ejecuta en cuatro pasos, y **se saltea entera si `es_dummy=True`** (`equipos/models.py:58-59`):

1. **Normalización de orden** (`:62-63`) — si `jugador1_id > jugador2_id`, intercambia ambos FKs. Esto es lo que hace efectivo el `UniqueConstraint`: sin ello, `(A,B)` y `(B,A)` serían filas distintas.
2. **Nombre** (`:67-75`) — toma `apellido` de cada jugador, con fallback a `email.split('@')[0]` si el apellido está vacío; los ordena alfabéticamente y arma `"Apellido1/Apellido2"`. Solo se reasigna si el nombre actual no empieza con esa base (permite conservar sufijos de desambiguación).
3. **Desambiguación** (`:77-81`) — bucle `while` que consulta la BD y va probando `"Base (1)"`, `"Base (2)"`… hasta encontrar un `nombre` libre. Es una query por intento.
4. **División automática** (`:84-94`) — solo si `division_id` está vacío. Elige la división con **menor `orden`** entre los dos jugadores, es decir la categoría más alta (`Division.orden` es Primera=1 … Octava=8, `accounts/models.py:18`). Si solo uno tiene división, usa esa.

> **Importante:** nada de esto corre con `bulk_create`. Por eso `equipos/management/commands/seed_dev_data.py:96` precalcula el nombre a mano antes de `bulk_create` (`:107`).

##### `__str__` (`equipos/models.py:98-103`)

Sufija el nombre según los flags `is_dummy` de los usuarios:

| Situación | Salida |
|---|---|
| Ambos jugadores dummy | `Nombre [Dummies]` |
| Uno solo dummy | `Nombre [Con Dummy]` |
| Ninguno | `Nombre` |

##### Métodos de estadística

Todos hacen import diferido de `torneos.models` para evitar circularidad.

| Método | Línea | Qué devuelve |
|---|---|---|
| `get_partidos_jugados()` | `:107` | dict `{eliminacion, grupos, total}` con QuerySets de `Partido` y `PartidoGrupo` donde el equipo es `equipo1` o `equipo2` y hay `ganador`. |
| `get_victorias()` | `:127` | `count()` de `Partido` + `PartidoGrupo` con `ganador=self`. |
| `get_derrotas()` | `:136` | `total - victorias`. |
| `get_win_rate()` | `:141` | `%` redondeado a 1 decimal; `0` si no jugó. |
| `get_torneos_ganados()` | `:148` | `Torneo.objects.filter(ganador_del_torneo=self).count()`. |
| `get_racha_actual()` | `:153` | dict `{tipo, cantidad, texto}`. Concatena listas de eliminación y grupos **sin merge cronológico real** (`:167`: `partidos_elim + partidos_grupo`), así que la racha prioriza siempre los partidos de eliminación. |
| `get_ultimos_resultados(limit=5)` | `:197` | Lista de dicts `{ganado, rival, torneo, tipo}`. Misma limitación: rellena primero con eliminación y solo si sobra cupo agrega grupos. |
| `get_puntos_ranking()` | `:235` | `Sum('puntos')` sobre `RankingJugador` de ambos jugadores. |

> El docstring de `get_puntos_ranking` dice "promediados" pero el código **suma** (`aggregate(models.Sum('puntos'))`, `:242-244`) y no filtra por la división del equipo, así que un jugador con filas de ranking en varias divisiones infla el total.

#### 1.2 Modelo `Invitation` y el flujo de invitación

`equipos/models.py:248-276`

| Campo | Detalle |
|---|---|
| `inviter` | FK a usuario, `related_name='sent_invitations'` |
| `invited` | FK a usuario, `related_name='received_invitations'` |
| `status` | `PENDING` / `ACCEPTED` / `REJECTED` (TextChoices, `:249-252`) |
| `timestamp` | `auto_now_add` |

`Meta`: `unique_together = ('inviter', 'invited', 'status')`, `ordering = ['-timestamp']`.

**No existe expiración.** El modelo no tiene campo de vencimiento y no hay ningún chequeo temporal en todo el repo. Una invitación `PENDING` vive indefinidamente hasta que alguien actúe sobre ella.

##### Flujo completo

```mermaid
sequenceDiagram
    participant A as Jugador A (inviter)
    participant S as TodoPadel
    participant B as Jugador B (invited)
    A->>S: GET /equipos/crear/ (autocompleta a B)
    S->>S: EquipoCreateView.form_valid → Invitation(PENDING)
    S-->>B: email HTML (equipos/emails/invitation_email.html)
    S-->>B: push VAPID "🤝 Te invitaron a formar pareja"
    Note over A: mensaje: "El equipo se creará cuando acepte"
    B->>S: POST /equipos/invitacion/<pk>/aceptar/
    S->>S: transaction.atomic: crea Equipo, marca ACCEPTED,<br/>rechaza todas las demás PENDING de ambos
    S-->>A: push "🎾 ¡Invitación aceptada!"
    S-->>B: redirect a /equipos/mi-equipo/
```

**Paso 1 — enviar** (`EquipoCreateView.form_valid`, `equipos/views.py:217-275`):
- `dispatch` exige que el usuario tenga `division` asignada, si no redirige a perfil con error (`:187-191`).
- **No se guarda ningún `Equipo`.** Se comprueba si ya hay una `Invitation` PENDING igual (`:221-230`) y se crea una nueva (`:233-237`).
- Email asíncrono vía `accounts.utils.send_email_async` con plantilla `equipos/emails/invitation_email.html`; el `action_url` se construye a mano con `request.is_secure()` + `request.get_host()` (`:243-256`).
- Push al invitado (TP-11) envuelto en `try/except Exception: pass` mudo (`:259-269`).
- Redirige a `accounts:perfil`, donde `PerfilView` inyecta `invitaciones_enviadas` / `invitaciones_recibidas` (`accounts/views.py:206-207`).

**Paso 2 — aceptar** (`AceptarInvitacionView`, `equipos/views.py:278-335`, **POST only**):
- `get_object_or_404(Invitation, pk=pk, invited=request.user, status=PENDING)` — solo el destinatario puede aceptar.
- Valida que **ninguno de los dos** tenga ya equipo; si alguno lo tiene, marca la invitación como `REJECTED` y aborta (`:283-287`).
- Valida que el `inviter` tenga división (`:290-292`).
- Dentro de `transaction.atomic()` (`:294-319`):
  1. Crea el `Equipo` con `division=invitation.inviter.division` (**la del que invitó**, no la calculada por `save()`).
  2. **Borra** invitaciones `ACCEPTED` previas entre el mismo par — necesario porque `status` forma parte del `unique_together` (`:302-307`).
  3. Marca la invitación como `ACCEPTED`.
  4. Marca como `REJECTED` todas las demás `PENDING` que involucren a cualquiera de los dos, en cualquier rol (`:313-319`).

**Paso 3 — rechazar/cancelar** (`RechazarInvitacionView`, `equipos/views.py:338-359`, **POST only**): la misma vista sirve para que el destinatario rechace o para que el emisor cancele. Verifica que `request.user` sea uno de los dos (`:343-345`) y que siga `PENDING` (`:347-349`); el mensaje flash difiere según el rol.

#### 1.3 `RankingJugador`

`equipos/models.py:279-295`. Tabla materializada de puntos, una fila por `(jugador, division)`.

| Campo | Tipo |
|---|---|
| `jugador` | FK usuario, `related_name='rankings_jugador'` |
| `division` | FK `accounts.Division`, CASCADE |
| `puntos`, `torneos_ganados`, `victorias`, `partidos_jugados` | `IntegerField(default=0)` |

Constraint `unique_ranking_jugador_division` sobre `('jugador','division')`.

**Quién la escribe:** `accounts.utils.actualizar_rankings_en_bd()` (`accounts/utils.py:624-640`, hace `delete()` + `update_or_create` por división) y el command `migrar_rankings_historicos`. **Quién la lee:** `accounts.utils.get_division_rankings` (`accounts/utils.py:32`), `Equipo.get_puntos_ranking()` y la vista pública `accounts.views.RankingJugadoresListView` (`accounts/urls.py:17` → `/accounts/rankings/`). Nótese que la vista de rankings **no vive en `equipos`**, pese a que el modelo sí.

No está registrado en el admin (`equipos/admin.py` solo registra `Equipo`).

#### 1.4 `BusquedaCompanero` ("busco compañero", TP-10)

`equipos/models.py:298-321`. Aviso público publicado por un jugador.

| Campo | Detalle |
|---|---|
| `jugador` | FK usuario, `related_name='busquedas_companero'` |
| `division` | FK Division, `null/blank` → "Cualquier división" |
| `ciudad` | `CharField(100, blank=True)` |
| `torneo` | FK `torneos.Torneo`, `null/blank` → "Sin torneo específico" |
| `nota` | `TextField(blank=True)` — "Contanos qué buscás (nivel, disponibilidad, etc.)" |
| `activa` | `BooleanField(default=True)` |
| `fecha_creacion` | `auto_now_add` |

`Meta.ordering = ['-fecha_creacion']`. Migración `equipos/migrations/0009_busquedacompanero.py`.

El form (`equipos/forms.py:146-185`) aplica clases DaisyUI a mano según el tipo de widget, marca `division` y `torneo` como opcionales con `empty_label` custom, y **limita el selector de torneos a los que están en estado `ABIERTO`** (`:178-180`). Prefija `division` desde el usuario (`:183-185`); el comentario menciona también la ciudad, pero eso no está implementado.

El listado (`equipos/templates/equipos/busqueda_list.html`) es **público** y muestra un botón directo de WhatsApp construido con `jugador.telefono_numero` (`:50-55`). El dueño ve un botón "Cerrar" que hace POST a `eliminar_busqueda` (`:58-63`).

Tests: `equipos/tests.py:17-49` (`MatchmakingTests`) cubren listado público 200, publicación con autocompletado de división, y aparición en el listado.

#### 1.5 Mixins de permisos

`equipos/views.py:17-72`

| Mixin | Línea | `test_func` | `handle_no_permission` |
|---|---|---|---|
| `PlayerRequiredMixin` | `:17` | `tipo_usuario in ['PLAYER','ADMIN']` | msg error → `core:home` |
| `PlayerHasNoTeamMixin` | `:30` | lo anterior **y** `request.user.equipo is None` | msg warning → `equipos:mi_equipo` |
| `PlayerOwnsTeamMixin` | `:44` | lo anterior **y** `equipo is not None`; `get_object` devuelve `request.user.equipo` | msg error → `equipos:mi_equipo` |
| `AdminRequiredMixin` | `:64` | `tipo_usuario == 'ADMIN'` | msg error → `core:home` |

`CustomUser.equipo` es una `@property` que busca primero en `equipos_como_jugador1` y luego en `equipos_como_jugador2`, siempre filtrando `esta_activo=True` (`accounts/models.py:199-211`). No está cacheada, así que cada acceso son hasta 2 queries.

#### 1.6 Tabla completa de vistas de `equipos`

`app_name = 'equipos'` (`equipos/urls.py:4`), prefijo `/equipos/`.

| URL | name | Vista | Clase base | Permiso efectivo |
|---|---|---|---|---|
| `autocomplete/jugadores/` | `jugador_autocomplete` | `JugadorAutocomplete` (`views.py:78`) | `dal.autocomplete.Select2QuerySetView` | Autenticado **y** `tipo_usuario == 'PLAYER'` estricto; si no, queryset vacío |
| `mi-equipo/` | `mi_equipo` | `MiEquipoDetailView` (`:128`) | `LoginRequiredMixin` + `DetailView` | Cualquier autenticado |
| `crear/` | `crear` | `EquipoCreateView` (`:181`) | `PlayerHasNoTeamMixin` + `CreateView` | PLAYER/ADMIN sin equipo, con división |
| `disolver/` | `disolver` | `EquipoDeleteView` (`:362`) | `PlayerOwnsTeamMixin` + `DeleteView` | PLAYER/ADMIN dueño de un equipo |
| `buscar-companero/` | `buscar_companero` | `BusquedaCompaneroListView` (`:483`) | `ListView` | **Público** (anónimos incluidos) |
| `buscar-companero/publicar/` | `publicar_busqueda` | `BusquedaCompaneroCreateView` (`:510`) | `PlayerRequiredMixin` + `CreateView` | PLAYER/ADMIN |
| `buscar-companero/<pk>/eliminar/` | `eliminar_busqueda` | `BusquedaCompaneroDeleteView` (`:529`) | `LoginRequiredMixin` + `DeleteView` | Solo el dueño (queryset filtrado); GET redirige, borra por POST |
| `admin/listado/` | `admin_list` | `AdminEquipoListView` (`:382`) | `AdminRequiredMixin` + `ListView` | ADMIN — **ver §1.8, está rota** |
| `invitacion/<pk>/aceptar/` | `aceptar_invitacion` | `AceptarInvitacionView` (`:278`) | `LoginRequiredMixin` + `View` (POST) | Solo el `invited` de una PENDING |
| `invitacion/<pk>/rechazar/` | `rechazar_invitacion` | `RechazarInvitacionView` (`:338`) | `LoginRequiredMixin` + `View` (POST) | `inviter` o `invited` |
| `organizador/crear-pareja/` | `crear_pareja` | `OrganizadorEquipoCreateView` (`:449`) | `LoginRequiredMixin` + `UserPassesTestMixin` + `CreateView` | `tipo_usuario in ['ADMIN','ORGANIZER']` |
| `autocomplete/organizador-jugadores/` | `organizador_jugador_autocomplete` | `OrganizadorJugadorAutocomplete` (`:419`) | `Select2QuerySetView` | `tipo_usuario in ['ADMIN','ORGANIZER']` |

##### Detalles por vista

**`MiEquipoDetailView`** — `get_object` devuelve `request.user.equipo` con `select_related('jugador1','jugador2','division')` (`:133-141`). El `get()` bifurca (`:143-160`): si no hay equipo pero sí invitaciones PENDING (enviadas o recibidas), redirige a `accounts:perfil`; si no hay nada, a `equipos:crear`. `get_context_data` arma `stats` invocando los 7 métodos del modelo (`:162-178`), lo que dispara ~10 queries adicionales sin cachear.

**`EquipoCreateView`** — acepta `?partner=<pk>` como initial (`:200-209`), usado desde `accounts/templates/accounts/public_profile.html:82`. El form (`EquipoCreateForm`, `equipos/forms.py:10-71`) usa un `ModelMultipleChoiceField` con `ModelSelect2Multiple` y `data-maximum-selection-length: 1` (truco de UX); su `clean()` valida que haya un solo seleccionado, lo convierte a objeto único y prohíbe autoseleccionarse (`forms.py:49-71`).

**`OrganizadorEquipoCreateView`** — usa `PairCreationForm` (`equipos/forms.py:74-143`), que sí pide `jugador1`, `jugador2`, `division` y `categoria` explícitamente y **salta el sistema de invitaciones**: `form_valid` hace `form.save(commit=False)` + `equipo.save()` directo (`views.py:472-477`). El `success_url` depende de si el organizador tiene `organizacion`: `accounts:organizacion_settings` o `equipos:admin_list` (`:454-458`). El autocompletado asociado etiqueta los dummies con `[Dummy]` (`:444-446`).

#### 1.7 Notas de comportamiento

- **Disolver borra de verdad.** `EquipoDeleteView` es un `DeleteView` estándar: `form_valid` llama a `super()`, que ejecuta `self.object.delete()`. No pone `esta_activo=False`, pese a que el campo existe justamente para eso y el `UniqueConstraint` parcial fue diseñado asumiendo soft-delete. Como `Partido`/`PartidoGrupo` referencian al equipo, disolver arrastra historial.
- **La categoría elegida por el jugador se pierde.** `EquipoCreateForm` declara `categoria` en `Meta.fields` (`forms.py:34`), pero `EquipoCreateView.form_valid` solo lee `jugador2` y crea la `Invitation`; `AceptarInvitacionView` construye el `Equipo` sin `categoria` (`views.py:296-300`). Todo equipo del flujo normal queda en `MIXTO`.
- **La restricción de división es solo del autocompletado.** `JugadorAutocomplete` filtra por `division=user.division` (`views.py:94-95`), pero el queryset del campo en el form no (`forms.py:43-47`), así que un POST directo con otro `jugador2` pasa validación.
- Ambos autocompletados llevan comentarios explícitos de que se removió el filtro "sin equipo activo" (`views.py:100-101` y `:429-430`), permitiendo múltiples parejas en el buscador; el chequeo real solo ocurre al aceptar.

#### 1.8 Bugs confirmados en `equipos`

**A) `NameError` en `AdminEquipoListView`** — `equipos/views.py:388-404`:

```python
queryset = Equipo.objects.all().select_related('jugador1', 'jugador2', 'division')

# Filtro por división
if division_id:                      # ← línea 394: NUNCA se define
    queryset = queryset.filter(division_id=division_id, esta_activo=True)
```

La línea que leía `division_id = self.request.GET.get('division')` fue borrada; el `get_context_data` sí lo sigue leyendo (`:409`). Cualquier GET a `/equipos/admin/listado/` lanza `NameError: name 'division_id' is not defined` → 500. La ruta está enlazada desde el menú admin (`theme/templates/base.html:1030`) y desde `equipos/templates/equipos/organizador_equipo_form.html:46`, o sea que es alcanzable.

Fix mínimo:

```python
division_id = self.request.GET.get('division')
```

**B) `test_rankings_performance` roto** — `equipos/management/commands/test_rankings_performance.py:14` importa `RankingListView` de `equipos.views`, clase que ya no existe (en `equipos/views.py:414` quedó solo el comentario `# --- Vista de Rankings ---`, sin nada debajo, y la URL de rankings está comentada en `equipos/urls.py:21`). El command falla con `ImportError`.

**C) Import fantasma de `Division`** — `equipos/admin.py:2` (`from .models import Division, Equipo`) y `equipos/signals.py:29` importan `Division` desde `equipos.models`, cosa que solo funciona por el re-export accidental de `equipos/models.py:3`. En `admin.py` además nunca se usa.

---

### 2. App `core`

Registrada como `core.apps.CoreConfig` (`settings.py:104`), montada en la raíz (`padel_project/urls.py:26`). Contiene un solo modelo (`Testimonio`), cuatro vistas de página y una utilidad de mantenimiento.

#### 2.1 Tabla de rutas

| URL | name | Vista | Auth |
|---|---|---|---|
| `/` | `home` | `home` (FBV, `core/views.py:5`) | Público |
| `/para-organizadores/` | `para_organizadores` | `ParaOrganizadoresView` (`:60`) | Público |
| `/instalar/` | `instalar` | `InstalarAppView` (`:65`) | Público |
| `/search/` | `search` | `GlobalSearchView` (`:76`) | **Público** |
| `/trigger-migration/` | `trigger_migration` | `trigger_migration` (FBV, `:146`) | Superuser (chequeo manual, sin decorador) |

#### 2.2 Home (`core/views.py:5-51`)

Renderiza `core/templates/core/home.html` (709 líneas). Origen de cada dato del contexto:

| Clave de contexto | Origen | Sección del template |
|---|---|---|
| `torneos_abiertos` | `Torneo.objects.filter(estado=Estado.ABIERTO).order_by('fecha_inicio')` (`:10`) | Hero (slice 6) + carrusel "Inscripciones Abiertas" (`home.html:237-365`) |
| `torneos_en_juego` | `Torneo.objects.filter(estado=Estado.EN_JUEGO)` (`:14`) | Hero (slice 6) + carrusel "Jugando Ahora" (`home.html:368-471`) |
| `organizadores` | `Organizacion.objects.all()` (`:20`, import diferido) | Carrusel "Organizadores Destacados" (`home.html:156-234`) |
| `stats_home` | dict cacheado bajo `home_stats`, TTL **3600 s** (`:25-37`) | Grid de 3 contadores (`home.html:481-497`) |
| `testimonios` | `Testimonio.objects.filter(activo=True)` (`:44`) | Bloque "Lo que dicen" (`home.html:495-521`) |
| `torneos_inscritos_ids` | `set` de `torneo_id` de `Inscripcion` del equipo del usuario (`:47-50`) | Badges "Inscrito"/"Jugando" (`home.html:305`, `:436`) |

Composición de `stats_home` (`core/views.py:29-36`):

| Contador | Query |
|---|---|
| `torneos_jugados` | `Torneo.objects.filter(estado=FINALIZADO).count()` |
| `jugadores` | `CustomUser.objects.filter(tipo_usuario='PLAYER', is_dummy=False).count()` |
| `partidos_jugados` | `Partido(ganador__isnull=False).count() + PartidoGrupo(ganador__isnull=False).count()` |

Secciones adicionales del template no derivadas del contexto de la vista:
- **Hero** con foto de cancha de fondo y carrusel vertical animado en JS (`home.html:29-135`), con keyframes `hero-ball-bounce`.
- **CTA "¿Organizás torneos?"** (`home.html:138-155`), visible solo para anónimos y `PLAYER`. Apunta a `{{ organizador_whatsapp_url }}`, inyectado por el context processor `padel_project/context_processors.py:11-17` (número hardcodeado `5492236886313` en `:8`).
- **Empty state** cuando no hay torneos activos (`home.html:474-478`).

> El cache `home_stats` **no se invalida nunca**: `equipos/signals.py:24-32` solo borra `rankings_jugadores_all` y `rankings_div_{id}` / `rankings_jugadores_div_{id}`. Finalizar un torneo no mueve los contadores hasta que expira el TTL de 1 h.

#### 2.3 Modelo `Testimonio` (`core/models.py:4-19`)

| Campo | Tipo |
|---|---|
| `autor` | `CharField(100)` |
| `rol` | `CharField(100, blank)` — "Ej: Jugador 7ma · Organizador" |
| `texto` | `TextField` |
| `foto` | `ImageField(upload_to='testimonios/', blank, null)` |
| `activo` | `BooleanField(default=True)` |
| `orden` | `PositiveIntegerField(default=0)` |

`Meta.ordering = ['orden']`. Admin en `core/admin.py:6-11` con `list_editable = ('activo','orden')`. Migración `core/migrations/0002_initial.py`.

#### 2.4 Búsqueda global (`GlobalSearchView`, `core/views.py:76-141`)

`TemplateView` sobre `core/search_results.html`, alimentada por el formulario de la navbar (`theme/templates/base.html:557`). Sin login. Busca tres entidades y las corta a 10/15/10.

Pipeline por keyword (split por espacios, todas deben matchear vía `reduce(operator.and_, ...)`):

| Entidad | Campos | Límite |
|---|---|---|
| Jugadores | `nombre`, `apellido`, `email` (OR entre campos, AND entre keywords), filtrado a `tipo_usuario='PLAYER'` | 10 |
| Torneos | OR de: nombre (AND keywords), `division__nombre` (AND keywords), y `fecha_inicio` exacta por cada fecha detectada | 15 |
| Equipos | `Equipo.nombre` | 10 |

Utilidades en `core/utils.py`:

| Función | Línea | Qué hace |
|---|---|---|
| `normalize_query` | `:7` | NFKD + descarte de categoría `Mn` (quita acentos), lowercase. **Definida e importada en la vista (`views.py:85`) pero nunca invocada.** |
| `extract_dates` | `:19` | Regex `dd/mm[/aaaa]` parseada con `dateutil` (`dayfirst=True`), más búsqueda de meses en español (`enero`…`diciembre`) con patrón `(\d{1,2})\s+(?:de\s+)?<mes>`. Devuelve lista deduplicada. |
| `get_smart_filter` | `:71` | Devuelve `Q(campo__unaccent__icontains=v)` si Postgres, `Q(campo__icontains=v)` si no. |
| `is_postgres` | `:79` | `connection.vendor == 'postgresql'`. |

La extensión `unaccent` se habilita en `core/migrations/0001_unaccent_extension.py` con `UnaccentExtension()`; en SQLite local `CreateExtension` hace early-return por vendor, así que la migración es no-op y `is_postgres()` degrada el filtro a `icontains`.

> **Privacidad:** la vista es pública, busca sobre `email` (`views.py:101`) y el template imprime el email de cada jugador encontrado (`search_results.html:83`). Un anónimo puede enumerar emails con `/search/?q=@gmail`.

#### 2.5 Página para organizadores (`core/views.py:60-62`)

`TemplateView` puro sobre `core/para_organizadores.html` (81 líneas). Estructura: hero con badge + dos CTA (WhatsApp y `accounts:organizador_list`), grid de 3 beneficios ("Adiós al Excel", "Difusión que vuela", "Ranking por categorías") y CTA final a WhatsApp. Ambos CTA usan `{{ organizador_whatsapp_url }}` del context processor.

Define `meta_description`, `og_title` y `og_description` propios (`:4-6`) — es la página del proyecto con mejor SEO on-page. Cubierta por `core/tests.py:14-17`.

> **No está enlazada desde ningún template.** El único match de `para_organizadores` en todo el repo son `core/urls.py:8`, `core/views.py:62` y el test. El CTA del home va directo a WhatsApp. Tampoco figura en el sitemap.

#### 2.6 Instalar / PWA (`InstalarAppView`, `core/views.py:65-73`)

`TemplateView` que agrega `vapid_public_key` desde `settings.VAPID_PUBLIC_KEY` (`settings.py:299`, leída de env con default `''`).

El template `core/instalar.html` (172 líneas):
- Detecta plataforma por UA (`isIOS`, `isAndroid`) y muestra el bloque de pasos correspondiente, con tabs manuales (`:129-149`).
- Detecta app ya instalada vía `matchMedia('(display-mode: standalone)')` o `navigator.standalone` (`:134`, `:151-153`).
- Botón de instalación directa que consume `window.deferredPWAPrompt` capturado del evento `beforeinstallprompt` (`:161-168`).
- Bloque de notificaciones push: si está autenticado, botón con `data-vapid-key`, `data-subscribe-url` (`accounts:push_subscribe`) y `data-csrf`, manejado por `static/js/push.js` (`:104-107`, `:171`); si no, link al login con `?next=`.

Assets PWA servidos desde la **raíz** para que el scope del SW sea `/` (`padel_project/urls.py:22-24`):

| Ruta | Template | Content-Type |
|---|---|---|
| `/sw.js` | `pwa/sw.js` | `application/javascript` |
| `/manifest.webmanifest` | `pwa/manifest.webmanifest` | `application/manifest+json` |

El manifest declara `display: standalone`, `orientation: portrait`, `theme_color #10B981`, `start_url: /?utm_source=pwa` y 3 iconos (192, 512, 512-maskable). El service worker (`theme/templates/pwa/sw.js`) es deliberadamente pass-through: `skipWaiting` + `clients.claim`, un handler `fetch` no-op (solo para cumplir el requisito de instalabilidad de Chrome/Android, sin cachear) y handlers `push` / `notificationclick`.

Tests PWA en `core/tests.py:49-73`.

---

### 3. SEO

#### 3.1 Sitemaps (`padel_project/sitemaps.py`, montado en `/sitemap.xml`, `padel_project/urls.py:20`)

| Clase | Línea | `changefreq` | `priority` | Items |
|---|---|---|---|---|
| `StaticViewSitemap` | `:5` | `daily` | `0.5` | 8 URLs por name: `core:home`, `accounts:login`, `accounts:registro`, `accounts:rankings_jugadores`, `torneos:circuito_list`, `torneos:abierto_list`, `torneos:en_juego_list`, `torneos:finalizado_list` |
| `TorneoSitemap` | `:24` | `weekly` | `0.8` | `Torneo.objects.all()`; `lastmod` = `fecha_inicio` |
| `CitySitemap` (TP-14) | `:37` | `weekly` | `0.6` | Ciudades distintas no vacías de `Torneo`, reverseadas a `torneos:ciudad` |

Registrados en el dict `sitemaps` de `padel_project/urls.py:10-14` con las claves `static`, `torneos`, `ciudades`.

Notas:
- `django.contrib.sites` **no** está instalado (solo `django.contrib.sitemaps`, `settings.py:90`) y no hay `SITE_ID`: el framework cae al fallback `RequestSite`, o sea que el dominio del sitemap sale del header `Host`.
- `CitySitemap.location` hace `reverse('torneos:ciudad', args=[item])` sobre el valor crudo del campo; la ruta es `ciudad/<str:ciudad>/` (`torneos/urls.py:20`) y el conversor `str` no matchea `/`, así que una ciudad con barra rompería el sitemap entero con `NoReverseMatch`.

#### 3.2 `robots.txt` (`templates/robots.txt`, servido por `TemplateView` en `padel_project/urls.py:18`)

```
User-agent: *
Disallow: /admin/
Disallow: /accounts/
Allow: /

Sitemap: https://todopadel.club/sitemap.xml
```

> **Conflicto:** el sitemap publica `accounts:login`, `accounts:registro` y `accounts:rankings_jugadores`, que resuelven a `/accounts/login/`, `/accounts/registro/` y `/accounts/rankings/` (`accounts/urls.py:9,11,17`) — las tres bloqueadas por `Disallow: /accounts/`. La más grave es la de rankings, que es contenido indexable de valor.
>
> **Huecos:** el sitemap no incluye `core:para_organizadores`, `core:instalar` ni `equipos:buscar_companero`, aunque las dos primeras tienen meta description propia.

#### 3.3 Meta tags (`theme/templates/base.html:24-58`)

| Elemento | Bloque sobreescribible | Default |
|---|---|---|
| `<title>` | `head_title` (prefijo) | `TodoPadel - Tu gestión de torneos` |
| `description` | `meta_description` | "Organiza y participa en los mejores torneos de pádel…" |
| `keywords` | `meta_keywords` | `padel, torneos, ranking, deporte, argentina, …` |
| `canonical` | — | `{{ request.build_absolute_uri }}` |
| `og:type` / `og:title` / `og:description` / `og:image` | `og_type`, `og_title`, `og_description`, `og_image` | `website`, "TodoPadel - Gestión de Torneos", …, `static 'img/og-image.png'` |
| `twitter:card` | — | `summary_large_image` (fijo) |
| `twitter:title` / `:description` / `:image` | `twitter_title`, `twitter_description`, `twitter_image` | |
| JSON-LD | `structured_data` | vacío |

Además: `author`, favicons (192/ico), `theme-color #10B981`, `mobile-web-app-capable`, `apple-mobile-web-app-*` con `status-bar-style: black` (comentado en `:21` como fix para que el contenido no scrollee detrás del reloj).

El home aporta un JSON-LD de tipo `Organization` con `sameAs` a Instagram y Facebook (`core/templates/core/home.html:14-27`).

> **Bug SEO:** `base.html:26` define el bloque `head_title`, pero `home.html:3`, `search_results.html:3`, `para_organizadores.html:3` y `equipos/templates/equipos/busqueda_list.html:3` sobreescriben `{% block title %}`, que **no existe en base**. Esas cuatro páginas se sirven todas con el mismo `<title>` genérico. Solo `instalar.html:3` usa el bloque correcto.
>
> **Menor:** el `<script type="application/ld+json">` de `base.html:56-58` se emite siempre, incluso vacío, en toda página que no sobreescriba `structured_data`.

---

### 4. Management commands (todas las apps)

8 commands en total. Ninguna app define commands de negocio recurrente: todos son de seeding, simulación o reparación puntual.

| Command | Archivo | Para qué sirve |
|---|---|---|
| `seed_dev_data` | `equipos/management/commands/seed_dev_data.py` | **Destructivo.** Crea/obtiene la división "Septima", **borra** todos los `PLAYER` de esa división y **borra `Equipo.objects.all()`** (`:88`), luego crea 32 jugadores (`jugador{i}@ejemplo.com`, password `test1234`) y los empareja en 16 equipos vía `bulk_create`. Nombres precalculados a mano porque `bulk_create` no llama a `save()`. Todo el `handle` está envuelto en un `try/except Exception` que solo imprime el error (`:114-115`). |
| `create_test_tournament` | `equipos/.../create_test_tournament.py` | Depende de `seed_dev_data`. Crea el torneo "Torneo Copa Test Final" (16 cupos, `equipos_por_grupo=2`, tipo GRUPOS, inicio +7d), borra torneos homónimos previos, crea/obtiene `admin@test.com` / `admin1234` como superuser e inscribe los primeros 16 equipos con `bulk_create`. Todo en `transaction.atomic()`. |
| `simulate_group_results` | `equipos/.../simulate_group_results.py` | Toma el **último** torneo `EN_JUEGO` y completa todos los `PartidoGrupo` sin ganador con sets y games aleatorios plausibles (2-0 o 2-1, ganador siempre 6, perdedor 0-4). Recalcula `e1/e2_games_ganados` sumando los sets. |
| `test_rankings_performance` | `equipos/.../test_rankings_performance.py` | Mide tiempo y nº de queries de la vista de rankings en 3 escenarios (sin cache, con cache, filtrado por división) usando `RequestFactory`. **ROTO:** importa `RankingListView` de `equipos.views` (`:14`), clase que ya no existe. |
| `crear_torneo_24` | `torneos/management/commands/crear_torneo_24.py` | **Destructivo.** Borra torneos `nombre__startswith="Torneo 24 Equipos"` y **todos** los usuarios con `@ejemplo.com` en el email (`:33`). Crea un torneo de 24 cupos con `equipos_por_grupo=3`, 48 jugadores y 24 parejas inscriptas. **No** simula resultados; imprime los pasos manuales siguientes. |
| `simular_torneo_24` | `torneos/.../simular_torneo_24.py` | Simulación end-to-end: crea el torneo, 24 equipos, 8 grupos de 3 con round-robin, simula todos los partidos de grupo, arma el bracket de 16 con el top-2 de cada grupo y simula 16vos → Cuartos → Semis → Final, dejando el torneo en `FINALIZADO` con campeón. |
| `migrar_rankings_historicos` | `torneos/.../migrar_rankings_historicos.py` | Migración one-off: recorre todas las `Division`, llama a `get_division_rankings(division, force_recalc=True)` y persiste el resultado con `RankingJugador.objects.update_or_create`. Es el command que dispara la vista `/trigger-migration/`. Hace `django.setup()` a nivel de módulo (`:1-4`) y parchea el cache global con `@patch` (`:15-16`, argumentos `mock_set, mock_get` invertidos respecto al orden de decoradores). |
| `reparar_rankings` | `torneos/.../reparar_rankings.py` | Herramienta de saneamiento. Detecta parejas duplicadas agrupando por `tuple(sorted([j1_id, j2_id]))`, fusiona cada grupo en un equipo canónico moviendo `Inscripcion`, `EquipoGrupo`, referencias en `PartidoGrupo`/`Partido` (equipo1/equipo2/ganador) y `Torneo.ganador_del_torneo`, y borra los sobrantes. Después re-guarda todos los equipos no-dummy para forzar la normalización de `save()` y llama a `actualizar_rankings_en_bd(division)` por cada división. |

Notas de packaging: `equipos/management/` y `equipos/management/commands/` **no tienen `__init__.py`** (a diferencia de `torneos/management/commands/__init__.py`, que sí existe). Funciona por namespace packages de Python 3, pero es una inconsistencia entre apps.

---

### 5. Resumen de problemas detectados

| # | Severidad | Ubicación | Problema |
|---|---|---|---|
| 1 | **Alta** | `equipos/views.py:394` | `NameError: division_id` → 500 seguro en `/equipos/admin/listado/`, ruta enlazada desde el menú admin |
| 2 | **Alta** | `equipos/management/commands/test_rankings_performance.py:14` | `ImportError`: `RankingListView` ya no existe en `equipos.views` |
| 3 | **Media** | `core/views.py:76,101` + `search_results.html:83` | Búsqueda pública sin login expone emails de jugadores |
| 4 | **Media** | `base.html:26` vs `home.html:3` y otros 3 templates | `{% block title %}` inexistente en base → 4 páginas comparten el mismo `<title>` |
| 5 | **Media** | `padel_project/sitemaps.py:12-14` vs `templates/robots.txt:3` | El sitemap publica 3 URLs que robots.txt bloquea |
| 6 | **Media** | `core/views.py:146-154` | `/trigger-migration/`: GET sin CSRF que dispara recálculo global de rankings; devuelve `str(e)` crudo en el 500 |
| 7 | **Media** | `equipos/views.py:362-376` | Disolver hace hard-delete en vez de `esta_activo=False`, arrastrando historial de partidos |
| 8 | Baja | `equipos/views.py:217-237` + `:296-300` | La `categoria` elegida en el form se descarta; todo equipo queda MIXTO |
| 9 | Baja | `core/views.py:37` vs `equipos/signals.py:24-32` | `home_stats` (TTL 1 h) nunca se invalida al finalizar torneos |
| 10 | Baja | `equipos/views.py:21` vs `:86-89` | Un ADMIN puede abrir `/equipos/crear/` pero su autocompletado devuelve siempre vacío |
| 11 | Baja | `equipos/models.py:235-245` | `get_puntos_ranking` suma (no promedia, pese al docstring) y no filtra por división |
| 12 | Baja | `padel_project/sitemaps.py:9-19` | Faltan `core:para_organizadores`, `core:instalar` y `equipos:buscar_companero` en el sitemap |
| 13 | Baja | `core/urls.py:8` | La landing `/para-organizadores/` es huérfana: sin links entrantes ni entrada en el sitemap |
| 14 | Baja | `equipos/admin.py` | `RankingJugador` y `BusquedaCompanero` sin registrar en el admin (imposible moderar avisos) |
| 15 | Baja | `equipos/views.py:259-269`, `:322-332` | Envío de push envuelto en `except Exception: pass` mudo, sin log |
| 16 | Baja | `core/views.py:85` | `normalize_query` se importa pero nunca se usa |
| 17 | Baja | `padel_project/sitemaps.py:50` | `reverse('torneos:ciudad', args=[ciudad])` rompe si una ciudad contiene `/` |

---

## Frontend, templates y PWA

> Auditoría sobre el código real del repo. Todas las rutas son relativas a la raíz del proyecto.

### 0. Convenciones de UI en mobile (leer antes de tocar layout)

La app se usa **mayormente desde el celular**, y el organizador la usa parado al
borde de la cancha. Las reglas viven en `theme/static_src/src/styles.css`, no
repartidas por los templates: son ~68 barras de botones y 200 SVG, y mantenerlas
a mano quedaba inconsistente.

| Regla | Qué hace | Por qué |
|---|---|---|
| `.flex:has(> .btn + .btn)` | Hasta 639px apila los botones a ancho completo | Con anchos distintos hacían escalera |
| `.barra-acciones` | Lo mismo para la cabecera, incluyendo dropdowns y forms | El "⋮" quedaba suelto entre botones anchos |
| `.collapse { grid-template-columns: minmax(0,1fr) }` | Impide que el panel se estire al contenido | La columna medía 399px dentro de un panel de 309 y cortaba el último botón |
| `svg:not(.w-full):not(.h-full):not(.absolute)` | `flex-shrink: 0` | 170 de 200 íconos se aplastaban al lado de textos largos |
| `.btn-sm` con `min-height: 2.5rem` en mobile | Área táctil de 40px | 32px es chico para el dedo |
| `.tabs-boxed .tab` con `height: auto` | La pestaña crece si el texto envuelve | La altura fija de DaisyUI dejaba el segundo renglón dibujado FUERA de la pastilla |
| `form .select2-container` con `min-width: 0 !important; width: 100% !important` | El autocompletar ocupa el ancho de su tarjeta | El CSS de django-autocomplete-light trae `min-width: 20em` (320px), que le gana a cualquier `width` y desbordaba 60px las tarjetas de 260px. Scopeado a `form` para no romper el desplegable que select2 cuelga del `body` |

**Trampas que ya nos mordieron:**

- Una grilla con `md:grid-cols-2` **sin** `grid-cols-1` no tiene columnas
  declaradas en mobile: se dimensiona al contenido y desborda. Poné siempre la
  clase base.
- `w-full` dentro de una fila flex es el 100% del contenedor: sumado a lo que
  tenga al lado, se pasa. Usá `flex-1 min-w-0`.
- Un `<label>` con `whitespace-nowrap` al lado de un input fuerza el ancho.

**Cómo verificar** (necesita el server en el puerto 8010):

```bash
python verificar_mobile.py    # desbordes y alineación en 15 pantallas a 375px
python auditoria_ui.py        # targets táctiles, labels, alt, consistencia
python auditoria_inputs.py    # inputs/selects/select2 que se pasan de su tarjeta, en 24 pantallas con formularios (loguea por rol)
```

### 1. Stack de estilos

#### 1.1 Cadena de compilación

| Pieza | Dónde | Detalle |
|---|---|---|
| App de tema | `theme/` (`theme/apps.py`) | App Django registrada en `padel_project/settings.py:95`; `tailwind` (django-tailwind 4.4.1) en `settings.py:96` |
| Config | `settings.py:341` | `TAILWIND_APP_NAME = 'theme'` |
| npm binario | `settings.py:76` / `:79` | `NPM_BIN_PATH = r"C:\Program Files\nodejs\npm.cmd"` en Windows, `'npm'` en Linux/Render |
| Fuente CSS | `theme/static_src/src/styles.css` | Solo las 3 directivas: `@tailwind base; components; utilities;` |
| Config Tailwind | `theme/static_src/tailwind.config.js` | Tailwind **v3** |
| Script de build | `theme/static_src/package.json:6` | `tailwindcss -i ./src/styles.css -o ../static/css/tailwind.css --minify` |
| Salida | `theme/static/css/tailwind.css` | ~40 KB minificados |
| Deploy | `build.sh:8-9` | `python manage.py tailwind install` → `python manage.py tailwind build` → `collectstatic` |
| Servido por | WhiteNoise | `settings.py:113` middleware; `STATIC_ROOT = staticfiles/` (`settings.py:270`) |

`theme/static_src/tailwind.config.js` en detalle:

```js
content: ['../../core/**/*.{html,py}', '../../accounts/**/*.{html,py}',
          '../../equipos/**/*.{html,py}', '../../torneos/**/*.{html,py}',
          '../../padel_project/**/*.py', '../../theme/templates/**/*.html',
          '../../templates/**/*.html'],
darkMode: 'class',
theme: { extend: { fontFamily: { sans: ['Inter','sans-serif'] },
                   colors: { primary: '#10b981' } } },
plugins: []
```

El comentario de cabecera aclara que este archivo **reemplaza el antiguo `cdn.tailwindcss.com` inline**, replicando su config.

> ⚠️ **Inconsistencia**: existe un segundo `theme/package.json` (fuera de `static_src`) que declara `tailwindcss ^4.1.17`, `autoprefixer` y `postcss`. No participa del build de django-tailwind y es un leftover confuso.

#### 1.2 DaisyUI 4.7.2 y los temas

DaisyUI **no** se compila: se carga por CDN en `theme/templates/base.html:64`:

```html
<link href="https://cdn.jsdelivr.net/npm/daisyui@4.7.2/dist/full.min.css" rel="stylesheet" />
```

`full.min.css` trae **todos** los temas de DaisyUI. El proyecto usa dos:

| Tema | Rol | Dónde se fija |
|---|---|---|
| `corporate` | Claro (default del documento) | `base.html:3` → `<html lang="es" data-theme="corporate">` |
| `business` | Oscuro | Script de detección `base.html:75-81` |

Lógica de detección (`base.html:76-80`):

```js
if (localStorage.getItem('theme') === 'corporate' ||
    (!('theme' in localStorage) && window.matchMedia('(prefers-color-scheme: light)').matches)) {
    document.documentElement.setAttribute('data-theme', 'corporate');
} else {
    document.documentElement.setAttribute('data-theme', 'business');
}
```

Es decir: **el default efectivo es oscuro (`business`)** salvo que el SO declare preferencia clara o el usuario haya guardado `corporate`.

Overrides sobre `corporate` (`base.html:159-163`) — solo geometría:

```css
[data-theme="corporate"] { --rounded-box: 1rem; --rounded-btn: 0.5rem; --rounded-badge: 1.9rem; }
```

#### 1.3 ⚠️ CRÍTICO: las variables DaisyUI del proyecto son **oklch**, no hsl

DaisyUI 4 abandonó HSL y define sus tokens de color como **tripletes oklch sin la función envolvente**. En este repo se ve literalmente en `base.html:85-97`:

```css
:root, html[data-theme="corporate"], [data-theme="corporate"] {
    --p:  72% 0.16 163 !important;   /* Primary Emerald  -> L C H */
    --pc: 98% 0.01 163 !important;   /* Primary Content  */
    --su: 72% 0.16 163 !important;
    --suc:98% 0.01 163 !important;
}
html[data-theme="business"], [data-theme="business"] {
    --p:  72% 0.16 163 !important;
    --pc: 15% 0.02 163 !important;   /* contenido oscuro sobre verde */
    ...
}
```

**Por qué importa al escribir CSS custom:**

1. `var(--p)` a secas **no es un color**: es `72% 0.16 163`. Hay que envolverlo → `oklch(var(--p))`.
2. La convención vieja de DaisyUI 3 era `hsl(var(--p))`. **Copiar snippets de DaisyUI 3 rompe el color** (produce un valor inválido y el navegador descarta la declaración).
3. La opacidad se aplica dentro de la función con slash: `oklch(var(--bc) / 0.2)`, **no** `var(--bc)/0.2` ni `rgba()`.
4. Para mezclas hay que usar `color-mix(in oklch, ...)`.
5. DaisyUI 4 provee `--fallback-*` (colores literales ya resueltos) para navegadores sin soporte oklch. El patrón defensivo del repo es `var(--fallback-b1, oklch(var(--b1)/1))`.

Ejemplos reales en el código, todos correctos:

| Uso | Archivo:línea |
|---|---|
| `background-color: oklch(var(--b1)) !important` | `theme/templates/base.html:174` |
| `border: 1px solid oklch(var(--bc) / 0.2) !important` | `base.html:175` |
| `background: oklch(var(--bc) / 0.2)` (scrollbar thin) | `base.html:456` |
| `color-mix(in oklch, var(--fallback-bc, oklch(var(--bc)/1)), transparent 90%)` | `base.html:244`, `:302` |
| `var(--fallback-p, oklch(var(--p)/1))` (chip Select2) | `base.html:393` |
| `path.setAttribute('stroke', 'oklch(var(--bc) / 0.15)')` (líneas del bracket, desde JS) | `torneos/templates/torneos/torneo_detail.html:737` |
| `border: 1px solid oklch(var(--bc) / .18)` (preview de llave) | `torneos/templates/torneos/formato_form.html:84` |
| `background-color: oklch(var(--b1)); border-color: oklch(var(--b3))` | `equipos/templates/equipos/equipo_form.html:6-7` |

#### 1.4 Sistema visual "TP-16": matar el azul

Todo el CSS de marca vive **inline en `<style>` dentro de `base.html:83-506`** (no hay hoja de estilos propia más allá de `tailwind.css`). Puntos clave:

| Regla | Línea | Qué hace |
|---|---|---|
| `.btn-primary, .btn-success` → `#10b981 !important` | `base.html:105-117` | Fuerza esmeralda ignorando el token del tema |
| `.btn-secondary/.btn-accent/.btn-info` → esmeralda | `base.html:121-132` | "Matar el azul": secundario/acento/info pasan a la familia verde |
| `.badge-secondary/.badge-accent/.badge-info` → `#0f6e50` | `base.html:133-135` | Verde oscuro para badges |
| `.text-info/.text-secondary/.text-accent` → `#10b981` | `base.html:136` | |
| `.live-dot` / `.live-badge` + `@keyframes tp-pulse` | `base.html:140-149` | Indicador "en vivo" en rojo `#FF5861`, con `prefers-reduced-motion` respetado |
| `.card-elevate` | `base.html:152-153` | `translateY(-3px)` + sombra al hover |
| `.section-tint` | `base.html:156` | Banda con degradado verde tenue |
| `.skeleton` + `@keyframes skeleton-pulse` | `base.html:239-247` | Placeholder de carga |
| `.toast` + `@keyframes toast-slide-in` | `base.html:258-264` | Animación de entrada de alerts |
| `.content-fade-in` | `base.html:267-273` | Fade del `<main>` |
| `.animate-gradient-x` | `base.html:429-443` | Gradiente animado |
| `.scrollbar-thin::-webkit-scrollbar*` | `base.html:446-462` | Scrollbar fina temática |
| `[data-theme="business"] .google-map-embed` | `base.html:100-102` | Modo oscuro para mapas embebidos vía `filter: invert(100%) hue-rotate(180deg)` |
| Select2 temático completo (~80 líneas) | `base.html:170-211` y `:275-426` | Todo con `!important` "para ganarle al CSS por defecto de select2 (que carga después)" |

Fuente: **Inter** (300–900) desde Google Fonts con `preconnect` (`base.html:68-71`), aplicada vía `font-sans` en el `<body>`.

---

### 2. `base.html` — anatomía

**1311 líneas.** Es el layout único de la app (lo extienden 73 de los 81 templates).

#### 2.1 Bloques disponibles

| Bloque | Línea | Default | Notas |
|---|---|---|---|
| `head_title` | 26 | vacío (se concatena `TodoPadel - Tu gestión de torneos`) | **El único que afecta el `<title>`** |
| `meta_description` | 31 | copy genérico | |
| `meta_keywords` | 33 | lista de keywords | |
| `og_type` | 38 | `website` | |
| `og_title` | 41 | `TodoPadel - Gestión de Torneos` | |
| `og_description` | 43 | genérico | |
| `og_image` | 45 | `static img/og-image.png` absoluta | |
| `twitter_title` | 50 | `TodoPadel` | Card `summary_large_image` |
| `twitter_description` | 52 | genérico | |
| `twitter_image` | 54 | `og-image.png` | |
| `structured_data` | 56 | vacío | Dentro de `<script type="application/ld+json">` |
| `extra_head` | 507 | **carga jQuery 3.6.0 + `form.media.css`** | Sobrescribirlo sin `block.super` deja la página sin jQuery (lo hace `core/home.html:9-10`) |
| `content_title` | 693 | vacío | Se renderiza arriba de los banners |
| `back_button` | 818 | botón "Volver" con `window.history.back()` | Envuelto en un `{% if %}` que lo oculta en `/`, `/accounts/login/` y `/accounts/registro/` |
| `header_actions` | 835 | vacío | Barra de acciones alineada a la derecha |
| `content` | 839 | vacío | Cuerpo principal |
| `extra_js` | 1192 | `form.media.js` | Al final del `<body>` |

> ⚠️ **No existe `{% block title %}`**. 39 templates lo definen (p. ej. `torneos/templates/torneos/torneo_detail.html:18`, `core/templates/core/home.html:3`) y su contenido se descarta silenciosamente. Solo 8 usan `head_title`.

#### 2.2 `<head>` — orden de carga

```
favicons (192px + apple-touch + .ico)   base.html:8-15
manifest + theme-color + apple-*        base.html:17-23
SEO / canonical / OG / Twitter          base.html:24-54
JSON-LD                                 base.html:56-58
1) HTMX 1.9.10 (unpkg)                  base.html:60-62
2) DaisyUI 4.7.2 CSS (jsdelivr)         base.html:64-66
   Google Fonts Inter                   base.html:68-71
3) tailwind.css compilado (local)       base.html:73
Script de detección de tema (bloqueante) base.html:75-81
<style> de marca (~420 líneas)          base.html:83-506
{% block extra_head %} -> jQuery        base.html:507-510
```

Nota sobre iOS: `apple-mobile-web-app-status-bar-style` es `"black"` (no `black-translucent`) con comentario explícito en `base.html:21` — con translucent el contenido scrolleaba por detrás del reloj/batería en la app instalada.

#### 2.3 `<body>` y navbar

`base.html:512-513` — el `<body>` inyecta el CSRF a todo HTMX:

```html
<body class="min-h-screen bg-base-200 font-sans ..." hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
```

**Global loader** (`base.html:515-524`): overlay `z-[9999]` con el logo pulsando, removido por JS (`:1275-1289`) tras 800 ms.

**Navbar** (`base.html:525-672`), fija, `z-[100]`, `backdrop-blur-md`, `print:hidden`:

| Zona | Contenido | Línea |
|---|---|---|
| `navbar-start` | Hamburguesa (`label for="my-drawer"`, oculta en `2xl`) + marca con logo | 527-554 |
| `navbar-center` | Buscador global (`GET` a `core:search`), oculto en mobile | 556-574 |
| `navbar-end` | Toggle de tema (`swap swap-rotate`, oculto < `sm`) | 578-590 |
| `navbar-end` | Avatar + dropdown si autenticado; badge rojo si `notification_count > 0` | 591-662 |
| `navbar-end` | Botones "Acceder" / "Registrarse" si anónimo | 663-670 |

El dropdown del avatar muestra condicionalmente **Invitaciones** (`pending_invitations_count`) y **Prox. Partidos** (`upcoming_matches_count`), y cierra sesión con un `<form method="post">` (botón con clase `no-loader` para saltar el spinner global).

Esos contadores vienen del context processor `padel_project.context_processors.notifications` (`settings.py:136`), cacheado 60 s por usuario.

#### 2.4 Menús por tipo de usuario (sidebar / drawer)

Drawer DaisyUI (`base.html:673-1150`), `lg:drawer-open`, con menú en `base.html:850-1120`:

| Sección | Visible para | Items | Línea |
|---|---|---|---|
| (público) | Todos | Inicio, En Juego, Inscripciones, Buscar (`2xl:hidden`) | 851-902 |
| **Tu Gestión** | Autenticados | (título de sección) | 904 |
| ↳ | `tipo_usuario == 'PLAYER'` o `'ADMIN'` | Mi Pareja, Buscar compañero, Mis Torneos | 905-945 |
| ↳ **Mi Organización** (`<details>`) | `tipo_usuario == 'ORGANIZER'` **y** `user.organizacion` | Ajustes, Sponsors, Horarios · PDF, Perfil Público | 946-981 |
| ↳ | Autenticados | Mi Perfil; toggle "Modo Oscuro" (`sm:hidden`) | 982-1012 |
| ↳ **Administración** (`<details>`) | `ADMIN` o `ORGANIZER` | Parejas (**solo `user.is_staff`**), Listar Torneos, Crear Torneo, Crear Jugador, Crear Pareja | 1013-1053 |
| **Competición** | Todos | Organizadores, Historial, Rankings (`<details>`), Circuitos, Americanos | 1055-1120 |
| Pie del sidebar | Todos | CTA WhatsApp "Creá tu torneo", iconos WhatsApp/Instagram, `TodoPadel · v1.0` | 1122-1147 |

El estado activo se resuelve con `request.resolver_match.url_name` o substring de `request.path`, y se estiliza con un indicador lateral grueso (`border-left: 4px solid #10b981`, `base.html:299-328`).

El CTA de WhatsApp usa `{{ organizador_whatsapp_url }}`, del context processor `contacto` (`padel_project/context_processors.py:12-18`, número `5492236886313`).

#### 2.5 Mensajes y banners

**Mensajes de Django** (`base.html:682-692`): contenedor `position: fixed` centrado con estilos inline; mapea `message.tags` a `alert-success` / `alert-error` / `alert-warning` / `alert-info`.

> ⚠️ El contenedor **no** lleva clase `toast`, pero el script de auto-dismiss (`base.html:1229-1242`) y el cálculo del delay del loader (`base.html:1278`) buscan `.toast .alert`. **Los mensajes nunca se auto-ocultan.** Además las clases `animate-in slide-in-from-top-2 fade-in duration-300` (`base.html:686`) son de `tailwindcss-animate`, que no está en `plugins: []` → no existen en el CSS compilado.

Tres banners condicionales, todos descartables:

| Banner | Condición | Persistencia | Línea |
|---|---|---|---|
| 📲 Instalar app | mobile UA && no standalone && no en `/instalar` | `localStorage['tp_install_dismiss']` | 696-721 |
| 📸 Agregá tu foto | `user_sin_foto` (context processor) | `sessionStorage['dismissed_banner-foto']` | 725-738 |
| 🤝 Formá tu pareja | `user_sin_equipo` | `sessionStorage['dismissed_banner-equipo']` | 739-752 |
| 🎾 Sumate a la comunidad | `not user.is_authenticated` | `sessionStorage['dismissed_banner-registro']` | 777-812 |

#### 2.5.b Páginas de error

En `templates/` (que está en `TEMPLATES['DIRS']`), así que **Django las toma
solas**: no hacen falta `handler404` ni `handler500`. Sólo se ven con
`DEBUG=False`; en desarrollo Django muestra su propia página de depuración.

| Archivo | Cuándo | Qué ofrece |
|---|---|---|
| `404.html` | Página inexistente | El 0 del "404" es una pelota. Casi todos los 404 vienen de links viejos de WhatsApp, así que da salidas: torneos abiertos, inicio y buscador |
| `403.html` | Sin permiso | Cambia el mensaje según haya sesión o no: si está logueado, le dice con qué cuenta; si no, lo manda a entrar (suele ser sesión vencida) |
| `400.html` | Pedido inválido | Explica que suele ser una página vieja recargada |
| `500.html` | Error del servidor | **No extiende `base.html`** (ver abajo) |

> ⚠️ **`500.html` va suelta a propósito.** Django la renderiza con un contexto
> vacío y **sin `request`** (`django.views.defaults.server_error`), así que los
> context processors no corren y todo lo que `base.html` espera llegaría vacío.
> Y sobre todo: si lo que se rompió es la base o los estáticos, una página de
> error que depende de ellos falla también y el usuario termina viendo el error
> crudo igual. Por eso lleva su CSS inline, sin imágenes y sin consultas.

Cubiertas por `core.tests.PaginasDeErrorTests`, que además verifica que la 500
renderice sin contexto.

#### 2.5.c Íconos (favicon, PWA)

Los genera `generar_iconos.py` a partir de `docs/reporte/iconos/original/favicon.png`.
La regla es **según quién aplica la máscara**:

| Archivo | Forma | Por qué |
|---|---|---|
| `apple-touch-icon.png` | Cuadrado opaco, a sangre | iOS rellena de **blanco** lo transparente y después redondea. Mandarlo ya redondeado deja un halo blanco alrededor del verde |
| `pwa-512-maskable.png` | Cuadrado opaco + zona segura | Android lo recorta con la forma del launcher (círculo, gota, squircle) |
| `favicon.ico`, `favicon.png`, `favicon_192.png`, `pwa-512.png` | **Redondeado**, transparente afuera | La pestaña del navegador y el manifest lo muestran tal cual: acá va la pastilla con las esquinas de la marca |

El redondeo no se dibuja a mano: se conserva el **canal alfa del archivo
original**, que ya trae la silueta exacta del logo.

#### 2.6 Footer

`base.html:1152-1189`, `footer-center`, `print:hidden`, con clase `.app-footer` que en ≥1536px se desplaza `margin-left: 20rem` para no quedar bajo el sidebar fijo (`base.html:500-503`). Contiene:
- Copyright con `{% now "Y" %}`
- Botón "📲 Instalar la app" → `core:instalar`
- Dropdown **Compartir** (`data-share` + `data-share-url/title/text`) con: Compartir nativo (oculto hasta que `share.js` detecte `navigator.share`), WhatsApp (anchor puro), Copiar link, y "🎨 Crear placa para redes" → `torneos:placa_app`
- Crédito del desarrollador

#### 2.7 Scripts globales al final del `<body>`

| Script | Línea | Función |
|---|---|---|
| `js/share.js` (defer) | 1191 | Web Share API + copiar link |
| Theme controller | 1195-1226 | Sincroniza todos los `.theme-controller`, persiste en `localStorage`, actualiza el texto "Modo Claro/Oscuro" |
| Auto-dismiss alerts | 1229-1242 | *(código muerto, ver 2.5)* |
| Loading global de forms | 1247-1255 | Agrega `.loading` al `button[type=submit]` salvo que tenga `.no-loader` |
| Loading HTMX | 1258-1272 | `htmx:beforeRequest` / `htmx:afterOnLoad` |
| Loader logic | 1276-1288 | Quita `#global-loader` a los 800 ms |
| PWA | 1291-1308 | Registra `/sw.js`; captura `beforeinstallprompt` en `window.deferredPWAPrompt`, agrega `.pwa-installable` al `<html>` y dispara un evento custom `pwa-installable`; limpia en `appinstalled` |

#### 2.8 Hacks de layout del drawer

`base.html:465-504` — dos media queries que reescriben el comportamiento de DaisyUI:

- **1024px – 1535.98px**: se anula `lg:drawer-open` forzando el `.drawer-side` a `position:fixed; visibility:hidden` salvo con el toggle checkeado (comportamiento de overlay en tablet).
- **≥1536px**: `grid-template-columns: 20rem 1fr`, y el `.drawer-side` pasa a `position:fixed; top:4rem; width:20rem; height:calc(100vh - 4rem); overflow-y:auto` — "barra lateral FIJA estilo YouTube".

---

### 3. El bracket / llave

Se renderiza en `torneos/templates/torneos/torneo_detail.html:635-779`, dentro de un `<details open>` (no de un `collapse` DaisyUI).

#### 3.1 Estructura

```
<details open>
  <summary> icono trofeo + "Cuadro Final" + chevron .bracket-chevron </summary>
  <div style="overflow-x:auto; overflow-y:visible; -webkit-overflow-scrolling:touch">   ← torneo_detail.html:659-660
    <div id="bracket-container" class="w-full pb-6 relative">
      <svg id="bracket-lines-svg" class="absolute top-0 left-0 w-full h-full pointer-events-none" style="z-index:0">
      <div class="flex gap-12 min-w-max px-4 pr-32 relative z-10">
        {% regroup partidos_eliminacion|dictsort:"ronda" by ronda as rondas_list %}
        {% for ronda in rondas_list %}                                                 ← una columna por ronda
          <div class="flex flex-col min-w-[260px] max-w-[260px] gap-6 {% if forloop.last %}last-round{% endif %}">
            <div>{% nombre_ronda_dinamico ronda.grouper total_rondas %}</div>           ← "Final"/"Semifinal"/"Cuartos"...
            <div class="flex flex-col justify-around flex-grow gap-4">
              {% for partido in ronda.list %}
                <div class="card ... bracket-match-card" id="match-{{ partido.id }}"
                     data-next-match="match-{{ partido.siguiente_partido.id }}">
                  {% include "torneos/partials/bracket_match_content.html" %}
```

Detalle deliberado: el contenedor del bracket es un `<div>` plano, **sin** `collapse-content`, con comentario en `torneo_detail.html:658` — esa clase de DaisyUI aplica `overflow:hidden` y cortaría el scroll horizontal.

El nombre de ronda lo calcula el simple tag `nombre_ronda_dinamico` (`torneos/templatetags/torneo_extras.py:99-123`) por distancia a la final: `diff 0 → Final`, `1 → Semifinal`, `2 → Cuartos`, `3 → Octavos`, `4 → 16vos`.

#### 3.2 Dibujo de las líneas (`drawBracketLines`, `torneo_detail.html:695-743`)

1. Aborta si el `<details>` está cerrado (`:701-702`).
2. Redimensiona el SVG a `container.scrollWidth × scrollHeight` (`:707-708`).
3. Por cada `.bracket-match-card` con `data-next-match`, resuelve la card destino por id.
4. Calcula coordenadas absolutas dentro del contenedor scrolleable:
   ```js
   startX = rect1.right - containerRect.left + container.scrollLeft;
   startY = rect1.top + rect1.height/2 - containerRect.top + container.scrollTop;
   ```
5. Genera un `path` con **curva Bézier cúbica** (`curveOffset = (endX - startX) / 2`), `stroke: 'oklch(var(--bc) / 0.15)'`, `stroke-width: 2.5`, `stroke-linecap: round`.

Se re-dispara en: `DOMContentLoaded` +100 ms, `resize`, `toggle` de **cualquier** `<details>` de la página, y `htmx:afterSwap` (`:745-763`). El chevron rota 180° según `bracketDetails.open`, seleccionado con `details:has(#bracket-container)` (`:766`).

#### 3.3 `partials/bracket_match_content.html` (42 líneas)

Contenido de cada tarjeta de partido:

| Elemento | Línea | Detalle |
|---|---|---|
| Badge de horario | 2-6 | `absolute -top-3` centrado, `badge-sm badge-primary`, formato `d/m H:i` |
| Equipo 1 / Equipo 2 | 8-33 | Con `{% get_team_info %}`; `title` con el nombre completo y `truncate max-w-[160px]` |
| Estilo condicional | 8, 22 | Ganador → `font-bold text-success`; equipo propio → `font-extrabold text-primary` |
| Placeholder | 14, 28 | `placeholder_e1/e2` en itálica `opacity-30` (p. ej. "Ganador SF1"); fallback `...` |
| Divider | 20 | `divider my-1 h-px` |
| Resultado | 35-42 | `absolute top-0 right-0`, `font-mono text-[10px]`; badge `badge-warning` si hay `etiqueta_resolucion` (W.O. / abandono) |

El tag `get_team_info` (`torneos/templatetags/torneo_extras.py:16-45`) devuelve `{'code','name'}` y **sanea nombres legacy que contienen emails**, quedándose con la parte previa a `@`.

#### 3.4 Otras representaciones de la llave

| Vista | Estilo |
|---|---|
| `torneos/templates/torneos/torneo_vivo.html:66-93` | Lista vertical compacta con `{% ifchanged p.ronda %}` como separador — pensada para pantallas/TV |
| `torneos/templates/torneos/admin_torneo_manage.html:687+` | Bracket administrable con botones HTMX de cargar resultado / programar / reemplazar |
| `torneos/templates/torneos/formato_form.html:63-89` | Preview del cuadro construida 100 % en JS con clases `.bk-wrap/.bk-cols/.bk-col/.bk-match/.bk-team` (CSS local con `oklch(var(--bc)/.18)`) |

---

### 4. La "placa" para redes (`torneos/templates/torneos/placa.html`)

**Página standalone** (214 líneas): **no extiende `base.html`**, no carga Tailwind ni DaisyUI. Todo el CSS es propio (`placa.html:7-96`) con la paleta de marca duplicada como custom properties (`--green:#10B981`, `--base:#15191E`, `--live:#FF5861`, …).

#### 4.1 Los 4 tipos de placa

Resueltos en `torneos/views.py:1434-1491` (`PlacaView`). Si no viene `?tipo=`, se deriva del estado del torneo (`views.py:1457`): `AB → anuncio`, `EJ → vivo`, `FN → campeones`; sin `pk` → `app`.

| Tipo | Contenido | Línea en `placa.html` |
|---|---|---|
| `anuncio` | Organizador, badge "Inscripción abierta", título, chips (división/categoría/cupos), fecha, sede, premio, alerta de últimos cupos, CTA + QR | 109-133 |
| `campeones` | Trofeo, badge "Campeones", avatares con iniciales, nombres, score de la final, torneo·división | 135-149 |
| `vivo` | Badge rojo pulsante, ronda del cruce destacado, marcadores por set en cajas, CTA + QR | 151-179 |
| `app` (genérica) | "Tu pádel, sin Excel.", 3 propuestas de valor, 2 CTAs, QR | 181-200 |

Formato: `.placa` de **360 px** con `aspect-ratio: 9/16` (`placa.html:22`) → con `scale: 3` exporta exactamente **1080×1920**.

#### 4.2 Detalle html2canvas: fondos como divs reales

`placa.html:25` documenta el workaround:

```css
/* Fondos como divs reales (html2canvas renderiza mal los ::before/::after) */
.bg-grid { position:absolute; inset:0; z-index:-2; background-image:linear-gradient(...) }
.bg-glow { position:absolute; inset:0; z-index:-1; background:radial-gradient(...) }
```

#### 4.3 `theme/static/js/placa.js` — caching del `File` para el share sheet

El comentario de cabecera (`placa.js:4-6`) explica el problema: *"la imagen se PRE-GENERA al cargar y se cachea, así al tocar 'Compartir' llamamos a `navigator.share()` dentro del gesto del usuario (si no, se pierde la 'activación' mientras html2canvas trabaja y el selector de redes no abre)"*.

Flujo:

1. **QR** (`placa.js:13-21`): `qrcode(0,'M')` sobre `data-url`, insertado como `qr.createImgTag(3, 0)` → un `<img src="data:image/gif;base64,…">`.
2. **`_render()`** (`:30-49`): html2canvas con
   ```js
   { scale: 3, backgroundColor: '#15191E', logging: false,
     width: w, height: h, windowWidth: w, windowHeight: h, imageTimeout: 8000 }
   ```
   luego `canvas.toBlob(...)` → `new File([b], 'todopadel-placa.png', {type:'image/png'})`.
3. **`buildFile()`** (`:51-63`): memoiza en `cachedFile` y deduplica llamadas concurrentes con la promesa `building`.
4. **Pre-generación** (`:83-85`): en `window.load` + 300 ms, silenciando errores.
5. **Click en Compartir** (`:88-121`):
   - Desktop (`esMobile === false`, detectado por `maxTouchPoints` + UA en `:79-80`) → descarga directa.
   - Mobile con `cachedFile` listo y `navigator.canShare({files:[file]})` → **`navigator.share()` sincrónico, sin `await` previo** (`:100-103`). Este es el camino feliz: el share sheet abre.
   - Mobile sin cache → genera, y recién ahí comparte o descarga. Aquí el sheet puede no abrir en algunos navegadores; por eso existe la pre-generación.
   - `AbortError` (usuario canceló) se ignora; cualquier otro error cae a descarga.

#### 4.4 ⚠️ Por qué **no** se usa `useCORS`

`placa.js:36-38` **no pasa** `useCORS`, `allowTaint` ni `proxy`. Es correcto y deliberado: **todo lo que se pinta dentro de `#placa` es same-origin o data-URI**:

| Recurso | Origen |
|---|---|
| Logo (`.logo-img`) | `{% static 'img/logo.png' %}` → servido por WhiteNoise desde el mismo host (`placa.html:112, 136, 154, 182`) |
| QR | `data:image/gif;base64,…` generado en el cliente (`placa.js:19`) |
| Avatares de campeones | Divs con **iniciales de texto**, no fotos (`placa.html:141`) |
| Logo del organizador | **No se renderiza** |

La prueba está en el backend: `torneos/views.py:1464` calcula `'org_logo': org.logo.url if (org and org.logo) else ''`, pero `placa.html` **nunca usa `placa.org_logo`** — en su lugar dibuja `{{ placa.org_iniciales }}` (`placa.html:111` y `:153`). Ese logo vive en **Cloudinary** en producción (`settings.py:200-234`), es decir un origen distinto: incluirlo tainteaŕia el canvas y `canvas.toBlob()` lanzaría `SecurityError`. `useCORS: true` tampoco lo salvaría de forma confiable (requiere `Access-Control-Allow-Origin` correcto en cada respuesta y un `crossorigin` en el `<img>`), y agrega latencia y modos de falla. La decisión de diseño fue **eliminar el cross-origin del árbol**, no compensarlo con CORS.

#### 4.5 Segunda placa: Cloudinary server-side

Independiente de la anterior, `torneos/social.py` genera una **placa de campeones 1080×1080** aplicando overlays de texto de Cloudinary sobre la foto de campeones subida por el organizador (`build_placa_url`: crop fill, `brightness:-35`, "CAMPEONES" en `#10b981`, nombres, torneo y marca). Devuelve `None` de forma defensiva si Cloudinary no está activo, el torneo no está finalizado o falta foto/ganador. Se consume en `torneos/templates/torneos/torneo_detail.html:234-247` como botón "Descargar placa".

---

### 5. PWA

#### 5.1 Servido desde la raíz

`padel_project/urls.py:24-25` — con comentario *"servidos en la raíz para que el scope del service worker sea `/`"*:

```python
path('sw.js',  TemplateView.as_view(template_name="pwa/sw.js",
                                    content_type="application/javascript")),
path('manifest.webmanifest', TemplateView.as_view(template_name="pwa/manifest.webmanifest",
                                    content_type="application/manifest+json")),
```

Ambos son **templates Django** (usan `{% load static %}` para resolver iconos con hash de WhiteNoise).

#### 5.2 `theme/templates/pwa/manifest.webmanifest`

| Campo | Valor |
|---|---|
| `name` / `short_name` | "TodoPadel — Torneos de pádel" / "TodoPadel" |
| `lang` | `es-AR` |
| `start_url` | `/?utm_source=pwa` (permite medir aperturas desde la app instalada) |
| `scope` | `/` |
| `display` | `standalone` |
| `orientation` | `portrait` |
| `background_color` / `theme_color` | `#15191E` / `#10B981` |
| `icons` | 192 `any`, 512 `any`, 512 `maskable` |

Meta relacionadas en `base.html:17-23`: `theme-color #10B981`, `mobile-web-app-capable`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style="black"` (comentario en `:21`: con `black-translucent` el contenido scrolleaba por detrás del reloj/batería), `apple-mobile-web-app-title="TodoPadel"`.

#### 5.3 `theme/templates/pwa/sw.js` — 48 líneas, sin caché

```js
self.addEventListener('install',  e => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
// Handler de fetch (requisito de instalabilidad en Android/Chrome). Pass-through.
self.addEventListener('fetch', function (event) { /* no-op */ });   // sw.js:16-18
```

El comentario de cabecera es explícito: *"No cachea agresivo para no servir páginas viejas"*. El handler `fetch` vacío existe **solo** para satisfacer el criterio de instalabilidad de Chrome.

**Consecuencia**: la app no funciona offline, y DaisyUI, HTMX, jQuery, Inter, html2canvas y Select2 siguen siendo dependencias de red hacia CDNs de terceros.

Push (`sw.js:21-48`):
- `push` → parsea el JSON del payload (con fallback a `text()`), muestra `showNotification` con `icon`/`badge` = `favicon_192.png`, `data.url` y `tag` opcional.
- `notificationclick` → cierra, busca una ventana ya abierta cuya URL contenga el destino y la enfoca; si no, `openWindow(url)`.

#### 5.4 Instalación

**Captura del prompt** (`base.html:1291-1308`): registra el SW en `load`, guarda el evento `beforeinstallprompt` en `window.deferredPWAPrompt`, agrega la clase `pwa-installable` al `<html>` y emite un evento custom `pwa-installable`; en `appinstalled` limpia ambos.

**Página `/instalar`** (`core/templates/core/instalar.html`, 172 líneas):
- Hero con icono, badges de beneficios y grid verde de fondo.
- Detección de plataforma (`instalar.html:131-136`): iOS (incluye el caso iPad `MacIntel` + `maxTouchPoints > 1`), Android, desktop; selecciona la pestaña de pasos automáticamente y permite cambiarla a mano.
- Alert "✅ Ya tenés la app instalada" si `display-mode: standalone` (`:151-153`).
- Botón "⬇️ Instalar la app ahora" (`#btn-install`) que aparece solo si hay `deferredPWAPrompt` o al recibir el evento `pwa-installable`, y dispara `prompt()` + `userChoice` (`:161-168`).
- Instrucciones específicas por plataforma, con aviso de que en iPhone la instalación es **solo desde Safari**.

**Banner de instalación** en `base.html:696-721`, mobile-only, oculto en standalone y descartable vía `localStorage['tp_install_dismiss']`.

#### 5.5 Push notifications en el cliente (`theme/static/js/push.js`, 101 líneas)

Se carga **solo** en `/instalar` (`core/templates/core/instalar.html:171`) y engancha el botón `#btn-push`, configurado con `data-vapid-key="{{ vapid_public_key }}"`, `data-subscribe-url="{% url 'accounts:push_subscribe' %}"` y `data-csrf` (`instalar.html:104-107`), solo para usuarios autenticados.

| Paso | Línea | Detalle |
|---|---|---|
| Detección de soporte | `push.js:15` | `serviceWorker` + `PushManager` + `Notification` |
| Sin soporte / sin VAPID | `:48-53` | Deshabilita el botón y explica; mensaje específico para iPhone (instalar primero desde Safari) |
| `urlBase64ToUint8Array` | `:28-35` | Conversión estándar de la clave VAPID pública |
| Estado inicial | `:56-61` | `serviceWorker.ready` → `pushManager.getSubscription()` → pinta "activadas/desactivadas" |
| Desactivar | `:68-75` | `sub.unsubscribe()` + `POST {action:'unsubscribe', endpoint}` |
| Activar | `:78-92` | `Notification.requestPermission()` → `pushManager.subscribe({userVisibleOnly:true, applicationServerKey})` → `POST {endpoint, keys}` |
| Transporte | `:37-46` | `fetch` con `X-CSRFToken` y `credentials:'same-origin'` |

Backend: `pywebpush==2.3.0` está en `requirements.txt`.

---

### 6. Librerías JS/CSS de terceros

| Librería | Versión | Origen | Dónde se carga | Para qué |
|---|---|---|---|---|
| **HTMX** | 1.9.10 | unpkg | `theme/templates/base.html:60-62` | Modales de resultado/programación del panel admin |
| **DaisyUI** | 4.7.2 | jsdelivr | `base.html:64-66` | Sistema de componentes completo |
| **Google Fonts Inter** | 300–900 | fonts.googleapis.com | `base.html:68-71` | Tipografía |
| **Tailwind CSS** | 3.4.17 | **local, compilado** | `base.html:73` | Utilidades |
| **jQuery** | 3.6.0 | code.jquery.com | `base.html:508` (dentro de `{% block extra_head %}`) | Dependencia de Select2 |
| **Select2** | 4.1.0-rc.0 | jsdelivr (CSS + JS) | `torneos/templates/torneos/admin_torneo_manage.html:926-927` | Selector de parejas (`.select2-enable`, init en `:930-937` con `dropdownParent: $('body')`) |
| **html2canvas** | 1.4.1 | jsdelivr | `torneos/templates/torneos/placa.html:210` | Export de la placa a PNG |
| **qrcode-generator** | 1.4.4 | jsdelivr | `placa.html:211` | QR de la placa |
| **django-autocomplete-light** (`dal`, `dal_select2`) | 3.12.1 | server (`form.media`) | `base.html:509` / `:1193` | Autocompletados en formularios |
| **crispy-forms + crispy-tailwind** | 2.5 / 1.0.3 | server | `settings.py:345-346` | Render de formularios (`{% crispy %}` en `admin_partido_form.html`, `cargar_resultado_grupo.html`, `inscripcion_form.html`, …) |
| **django-widget-tweaks** | 1.5.0 | server | `torneos/templates/torneos/admin_torneo_form.html:3` | Ajuste de widgets |

**JS propio** (`theme/static/js/`, sin bundler ni módulos — todos IIFE en ES5):

| Archivo | Cargado en | Función |
|---|---|---|
| `share.js` | Global, `base.html:1191` (defer) | Web Share API + Clipboard con fallback a `execCommand` |
| `placa.js` | `placa.html:212` | QR + html2canvas + share/download |
| `push.js` | `instalar.html:171` (defer) | Suscripción Web Push |
| `torneo_preview.js` | `admin_torneo_form.html:221` (defer) | Preview en vivo de la estructura del torneo (debounce 220 ms contra `torneos:admin_preview_estructura`) + botón "usar datos de mi organización" |

`theme/static/css/tooltips.css` existe pero **ningún template lo referencia** (huérfano).

---

### 7. Patrones de UI reutilizables

#### 7.1 Partials incluibles

| Partial | Parámetros | Consumidores |
|---|---|---|
| `theme/templates/partials/_share_button.html` | `share_url`, `share_title`, `share_text`, `btn_class` (opcional) | `torneo_detail.html:116`, `americano_detail.html:22`, footer de `base.html:1160-1177` (inline) |
| `theme/templates/partials/empty_state.html` | `title`, `message`, `action_url`, `action_text`, `action_icon` | `core/home.html:476` y listados |
| `torneos/templates/torneos/partials/torneo_card.html` | `torneo` | Tarjeta de torneo con badge de estado |
| `torneos/templates/torneos/partials/bracket_match_content.html` | `partido`, `torneo`, `equipo` | `torneo_detail.html:685` |
| `accounts/templates/accounts/_stats.html` / `_ficha.html` / `_historial.html` / `_logros.html` | `stats`, `perfil_usuario`, `achievements` | `perfil.html`, `public_profile.html` |
| `equipos/templates/equipos/estadisticas_card.html` / `torneos_card.html` | `stats`, `torneos_jugados` | `mi_equipo_detail.html` |
| `torneos/templates/torneos/_preview_estructura.html` | `preview` | `admin_torneo_form.html` (fallback server-side de `torneo_preview.js`) |

#### 7.2 `_share_button.html` — mejora progresiva en 3 niveles

```html
<div class="dropdown dropdown-end" data-share
     data-share-url="{{ share_url }}" data-share-title="{{ share_title }}" data-share-text="{{ share_text }}">
```

1. **Sin JS**: el link de WhatsApp es un `<a href="https://wa.me/?text=...|urlencode">` que funciona igual (`_share_button.html:44`).
2. **Con `share.js`**: se quita `.hidden` de `.js-share-native` solo si existe `navigator.share` (`share.js:56-60`).
3. **Copiar link**: `navigator.clipboard.writeText` con fallback a un `<textarea>` + `execCommand('copy')` (`share.js:23-38`), y feedback "¡Link copiado!" durante 2 s (`share.js:40-52`).

La delegación de eventos es global (`document.addEventListener('click', …)`), por lo que funciona con contenido inyectado por HTMX.

#### 7.3 `empty_state.html` — ilustración animada

153 líneas: una escena de pádel construida con SVG inline (paleta teardrop con agujeros, grip, cordón) más una pelota con costuras, animadas con `@keyframes ball-bounce`, `racket-swing`, `shadow` y `fade-in` definidos **dentro del propio partial** (`empty_state.html:121-153`). Defaults: título "¡Cancha Libre!" y mensaje "No hay partidos en este momento."

#### 7.4 Cards

| Patrón | Clases típicas | Ejemplo |
|---|---|---|
| Card de sección | `bg-base-100 p-6 md:p-8 rounded-3xl border border-base-300 shadow-sm` | `core/home.html:157`, `:238`, `:369` |
| Card clickeable | `card ... hover:shadow-xl hover:-translate-y-1 transition-all duration-300` | `home.html:192`, `:276` |
| Card elevable (utilidad global) | `.card-elevate` | `base.html:152`, usado en `home.html:106` |
| Card de métricas | `card bg-base-100 border border-base-200 shadow-sm rounded-2xl` | `torneos/templates/torneos/dashboard.html:21-50` |
| Stat DaisyUI | `stat bg-base-100 shadow-md rounded-2xl border border-base-200` | `accounts/templates/accounts/_stats.html` |
| Sección colapsable | `details.collapse.collapse-arrow` + icono en cuadrado redondeado | `torneo_detail.html:491`, `:535` |

#### 7.5 Badges

| Uso | Clases | Ejemplo |
|---|---|---|
| Estado de torneo | `badge badge-lg badge-secondary/accent/neutral/outline` | `torneo_detail.html:143-156` |
| Urgencia de cupos | `badge badge-warning badge-lg` "¡Últimos N cupos!" | `torneo_detail.html:162` |
| En vivo | `.live-badge` + `.live-dot` (rojo `#FF5861` pulsante) | `base.html:141-148`, usado en `home.html:108`, `:432`, `:445` |
| Estado en tarjeta | `badge badge-warning/success/info absolute top-2 right-2` | `partials/torneo_card.html:2-8` |
| Sets/resultado | `badge badge-xs badge-ghost font-mono font-bold` | `torneo_detail.html:436` |
| Resolución especial (W.O.) | `badge badge-xs badge-warning` | `bracket_match_content.html:38` |
| Indicador de notificaciones | `indicator-item badge badge-error badge-xs` | `base.html:597` |

#### 7.6 Modales

Dos convenciones conviven:

- **`<dialog>` nativo + `.modal` de DaisyUI**, abierto con `id.showModal()`: `login_required_modal` y `create_team_modal` (`torneo_detail.html:782-813`), `cancel_inscription_modal` (`:273-296`), `photo-zoom-modal` (`perfil.html`, `public_profile.html`).
- **`<dialog>` + HTMX**: `resultado_modal` con target `#modal_content` y `schedule_modal` con target `#schedule_modal_content` (`admin_torneo_manage.html:808-835`). Los formularios cargados (`admin_partido_form.html`, `cargar_resultado_grupo.html`, `schedule_form.html`, `replace_teams_form.html`) hacen `hx-post="{{ request.path }}"` contra el mismo target, cerrando el ciclo.

#### 7.7 Otros patrones

- **Carruseles infinitos** (`core/home.html:545-707`): clonado triple de items (`clonesCount = items.length < 3 ? 0 : 3`), salto de scroll en los bordes, dots generados dinámicamente y flechas ocultas si el contenido entra en desktop.
- **Carrusel vertical del hero** (`home.html:39-64` + `:527-543`): rota cards con `@keyframes hero-ball-bounce` (squash & stretch tipo pelota), intervalo por `data-interval` (4500 ms), con `prefers-reduced-motion` respetado.
- **Buscador en cliente** (`admin_torneo_manage.html:850-918`): filtra zonas, rondas y partidos por `.filter-text` y auto-expande los `<details>`/checkboxes que contienen coincidencias.
- **`print:hidden`**: navbar, footer, banners de incentivo/instalar/registro y la barra de «Volver + acciones». Los avisos (`.toast`) llevan `display:flex` **inline**, que le gana a la clase por especificidad, así que se ocultan desde el `@media print` global de `styles.css` con `!important`. Además hay una plantilla dedicada de impresión sin Tailwind (`accounts/templates/accounts/print/organizacion_programacion.html`).
- **Programación**: `torneo_programacion.html` ya **no** usa `data-theme="business"` scoped; hereda el tema de la app y define su propio `@media print`.

---

### 8. Inventario completo de templates (81 archivos)

#### `theme/` (3 HTML + 2 no-HTML)

| Archivo | Descripción |
|---|---|
| `theme/templates/base.html` | Layout único de la app: head SEO/OG/PWA, navbar, drawer con menús por rol, mensajes, banners, footer y todos los scripts globales (1311 líneas). |
| `theme/templates/partials/_share_button.html` | Dropdown de compartir reutilizable (nativo / WhatsApp / copiar link) con mejora progresiva. |
| `theme/templates/partials/empty_state.html` | Estado vacío ilustrado con paleta y pelota de pádel animadas en SVG. |
| `theme/templates/pwa/manifest.webmanifest` | Manifest PWA (template Django, servido en `/manifest.webmanifest`). |
| `theme/templates/pwa/sw.js` | Service worker: instalabilidad + push, sin caché (servido en `/sw.js`). |

*(Existe también `theme/templates/base.html.backup`, no cuenta como template activo.)*

#### `templates/` raíz (7)

| Archivo | Descripción |
|---|---|
| `googleed7ca9e7f31e28a7.html` | Archivo de verificación de propiedad de Google Search Console (una línea). |
| `registration/password_reset_form.html` | Formulario para pedir el email de reseteo de contraseña. |
| `registration/password_reset_done.html` | Confirmación de "te enviamos el mail". |
| `registration/password_reset_confirm.html` | Formulario de nueva contraseña desde el link del mail. |
| `registration/password_reset_complete.html` | Confirmación final de contraseña cambiada. |
| `registration/password_reset_email.html` | Cuerpo de texto plano del mail de reseteo. |
| `registration/password_reset_email_html.html` | Versión HTML del mail de reseteo (tabla, fondo `#0f1117`). |

*(También `templates/robots.txt`, no-HTML.)*

#### `core/` (4)

| Archivo | Descripción |
|---|---|
| `core/home.html` | Landing: hero con foto de cancha y carrusel vertical de torneos, métricas, CTA organizadores y 3 carruseles infinitos (organizadores / abiertos / en juego) + testimonios. |
| `core/instalar.html` | Guía de instalación de la PWA por plataforma con auto-detección, botón de instalación nativo y activación de notificaciones push. |
| `core/para_organizadores.html` | Landing SEO de captación de organizadores con CTA a WhatsApp. |
| `core/search_results.html` | Resultados de la búsqueda global (jugadores, torneos, parejas). |

#### `accounts/` (22)

| Archivo | Descripción |
|---|---|
| `login.html` | Inicio de sesión con Google OAuth2 + credenciales. |
| `registro.html` | Alta de cuenta con Google OAuth2 + formulario crispy. |
| `complete_profile.html` | Completar datos obligatorios tras registrarse con Google. |
| `verification_form.html` | Envío/carga del código de verificación de cuenta. |
| `perfil.html` | Panel del propio perfil: avatar editable con zoom, edición de datos, stats, ficha, historial y logros (580 líneas). |
| `public_profile.html` | Perfil público de un jugador con OG dinámico, stats e historial. |
| `_stats.html` | Partial: grid de 6 stats DaisyUI (partidos, victorias, derrotas, win rate, torneos, títulos). |
| `_ficha.html` | Partial: ficha de juego (bio, posición, mano hábil, club, ciudad, Instagram). |
| `_historial.html` | Partial: resultados recientes y torneos finalizados del jugador. |
| `_logros.html` | Partial: grilla de logros/achievements con los bloqueados en grayscale. |
| `ranking_jugadores_list.html` | Ranking individual con filtro por división (select que navega). |
| `organizacion_list.html` | Listado público de organizadores. |
| `organizador_detail.html` | Perfil público de una organización con sus torneos y sponsors. |
| `organizacion_settings.html` | Ajustes de la organización (datos, logo, sede). |
| `organizacion_sponsors.html` | ABM de sponsors de la organización. |
| `sponsor_edit.html` | Edición de un sponsor puntual. |
| `organizacion_programacion.html` | Programación global de todos los torneos de la organización (look oscuro). |
| `print/organizacion_programacion.html` | Versión imprimible de la programación: HTML standalone, CSS propio, blanco y negro. |
| `dummy_user_form.html` | Alta de jugador "dummy" (sin cuenta) para rellenar torneos. |
| `duplicados.html` | Detección de posibles cuentas duplicadas. |
| `merge_users.html` | Fusión de dos jugadores duplicados. |
| `emails/verification_email.html` | Mail HTML de verificación de cuenta (tabla, fondo `#0f1117`). |

#### `equipos/` (10)

| Archivo | Descripción |
|---|---|
| `mi_equipo_detail.html` | Detalle de la pareja propia; incluye las cards de estadísticas y torneos. |
| `equipo_form.html` | Alta/edición de pareja con Select2 multiple estilizado con `oklch(var(--b1))`. |
| `equipo_confirm_delete.html` | Confirmación de baja de pareja. |
| `organizador_equipo_form.html` | Creación manual de pareja por el organizador (jugadores reales o dummies). |
| `admin_equipo_list.html` | Listado administrativo de parejas con filtros. |
| `busqueda_form.html` | Publicar un aviso de "busco compañero / rival". |
| `busqueda_list.html` | Listado de avisos con contacto por WhatsApp (con meta SEO propia). |
| `estadisticas_card.html` | Partial: card de estadísticas de la pareja. |
| `torneos_card.html` | Partial: tabla de torneos jugados por la pareja. |
| `emails/invitation_email.html` | Mail HTML de invitación a formar pareja. |

#### `torneos/` (35)

| Archivo | Descripción |
|---|---|
| `torneo_detail.html` | Página estrella del torneo: hero, inscripción/cancelación con modales, "Mis Partidos", zonas, y el bracket con líneas SVG (818 líneas). |
| `torneo_vivo.html` | Vista "en vivo" para pantallas/TV: zonas y llave en formato compacto, auto-refresh cada 20 s. |
| `torneo_programacion.html` | Planilla de horarios como tabla agrupada por día. Botón «Descargar PDF» (`window.print()`) + `@media print` propio (A4, negro sobre blanco, `thead` repetido por hoja, `break-inside: avoid` por fila). |
| `accounts/notificaciones.html` | Panel de la campanita: historial de avisos; cada ítem linkea a `notificacion_abrir`, que lo marca leído y redirige a su destino. |
| `equipos/partials/_invitacion_recibida.html` | Cajita de una invitación de pareja: nombre arriba, Aceptar/Rechazar en dos columnas iguales, ambos con `hx-post`. |
| `equipos/partials/_invitacion_resuelta.html` | Lo que reemplaza a la cajita después de aceptar/rechazar, sin recargar la página. |
| `torneo_abierto_list.html` | Listado de torneos con inscripción abierta. |
| `torneo_en_juego_list.html` | Listado de torneos en juego. |
| `torneo_finalizado_list.html` | Historial de torneos finalizados. |
| `torneo_ciudad_list.html` | Landing SEO por ciudad con JSON-LD `ItemList`. |
| `mis_torneos.html` | Torneos del jugador logueado. |
| `inscripcion_form.html` | Confirmación de inscripción de la pareja al torneo. |
| `placa.html` | Placa 9:16 para redes (standalone, sin `base.html`), 4 variantes, exportada a PNG 1080×1920. |
| `dashboard.html` | Panel del organizador: 4 tarjetas de métricas, próximos torneos con `progress` de ocupación y últimos finalizados. |
| `admin_torneo_list.html` | Listado administrativo de torneos. |
| `admin_torneo_form.html` | Alta/edición de torneo en secciones numeradas, con preview en vivo de la estructura y "Opciones avanzadas". |
| `admin_torneo_manage.html` | Consola de gestión: iniciar torneo, generar bracket, cargar resultados y programar vía HTMX, buscador en cliente y Select2 (939 líneas). |
| `admin_torneo_confirm_delete.html` | Confirmación de borrado de torneo. |
| `admin_torneo_replace_team.html` | Formulario de reemplazo de una pareja en todo el torneo. |
| `admin_partido_form.html` | Fragmento HTMX: carga del resultado de un partido de llave (normal / walkover / abandono). |
| `cargar_resultado_grupo.html` | Fragmento HTMX: carga del resultado de un partido de zona. |
| `schedule_form.html` | Fragmento HTMX: programar fecha y hora de un partido. |
| `replace_teams_form.html` | Fragmento HTMX: reemplazar equipos de un partido puntual. |
| `formatos_list.html` | Listado de formatos de torneo personalizados guardados. |
| `formato_form.html` | Constructor visual de formato: zonas con +/−, preview textual y preview del cuadro final, cruces manuales opcionales (374 líneas, JS propio). |
| `formato_confirm_delete.html` | Confirmación de borrado de formato. |
| `_preview_estructura.html` | Partial: panel de preview de estructura renderizado server-side (fallback sin JS de `torneo_preview.js`). |
| `circuito_list.html` | Listado de circuitos. |
| `circuito_detail.html` | Ranking acumulado del circuito con cupos de ascenso/descenso. |
| `americano_list.html` | Listado de americanos / mexicanos. |
| `americano_form.html` | Alta de americano / mexicano. |
| `americano_detail.html` | Detalle del americano: ranking, link de inscripción compartible con `_share_button`. |
| `americano_join.html` | Sumarse a un americano vía código público. |
| `americano_manage.html` | Gestión del americano (rondas, resultados, estado). |
| `partials/torneo_card.html` | Partial: tarjeta de torneo con badge de estado, logo del organizador y cupos. |
| `partials/bracket_match_content.html` | Partial: contenido de una tarjeta de partido del bracket (equipos, horario, resultado, W.O.). |
| `emails/nuevo_torneo.html` | Mail HTML de difusión de torneo nuevo (CSS propio, degradado verde). |
| `emails/nueva_inscripcion.html` | Mail HTML simple al organizador cuando se inscribe una pareja. |

---

### 9. Deuda técnica detectada en el frontend

| # | Problema | Ubicación | Impacto |
|---|---|---|---|
| 1 | `{% block title %}` no existe en `base.html`; 39 templates lo usan | `base.html:26` vs. `torneo_detail.html:18`, `home.html:3`, … | Títulos de página descartados → SEO y UX de pestañas |
| 2 | Auto-dismiss de alerts busca `.toast .alert`, pero el contenedor no tiene esa clase | `base.html:1230` / `:1278` vs. `:683` | Los mensajes quedan fijos en pantalla indefinidamente |
| 3 | `hide-scrollbar` no está definida en ningún lado | `core/home.html:188`, `:273`, `:404` | Scrollbars horizontales visibles en los 3 carruseles |
| 4 | `animate-in slide-in-from-top-2 fade-in` requieren `tailwindcss-animate`, no instalado | `base.html:686` vs. `tailwind.config.js:25` (`plugins: []`) | Alerts sin animación de entrada |
| 5 | `xintegrity` en lugar de `integrity` | `base.html:61` | SRI de HTMX inactivo |
| 6 | Dos versiones de Tailwind declaradas (3.4.17 en `static_src`, 4.1.17 en `theme/`) | `theme/static_src/package.json` vs. `theme/package.json` | Confusión / riesgo en futuros builds |
| 7 | `tooltips.css` huérfano | `theme/static/css/tooltips.css` | Peso muerto en `collectstatic` |
| 8 | 6 dependencias frontend por CDN sin caché de SW | `base.html:60-71`, `admin_torneo_manage.html:926-927`, `placa.html:210-211` | La app no funciona offline pese a ser PWA instalable; corte de CDN = sitio sin estilos |
| 9 | ~420 líneas de CSS inline en `base.html` (con muchos `!important`) | `base.html:83-506` | No cacheable por separado; alto acoplamiento y difícil de mantener |

---

## Infraestructura, configuracion, deploy y testing

Monolito Django 5.2.8 desplegado en Render, con PostgreSQL en producción y SQLite en desarrollo. Todo el comportamiento de entorno vive en un único `padel_project/settings.py` (398 líneas) sin split `base/dev/prod`: las diferencias se resuelven con `if` sobre variables de entorno.

### 1. Topología

```
Internet
  → Render (proxy TLS, setea X-Forwarded-Proto)
      → Gunicorn (gthread, 2 workers × 4 threads, timeout 120s)
          → WhiteNoise (estáticos comprimidos + manifest)
              → Django 5.2.8 (padel_project.wsgi:application)
                  ├── PostgreSQL (DATABASE_URL, ssl_require, conn_max_age=600)
                  ├── DatabaseCache (tabla django_cache)
                  ├── Cloudinary (media, si CLOUDINARY_URL)
                  ├── Resend / Brevo (email transaccional, vía HTTP API)
                  └── pywebpush + VAPID (notificaciones push, en thread daemon)
```

Nota: WSGI, no ASGI. `padel_project/asgi.py` existe pero nada lo usa (`WSGI_APPLICATION = 'padel_project.wsgi.application'`, `padel_project/settings.py:145`).

---

### 2. `settings.py` por secciones

#### 2.1 Apps instaladas (`settings.py:83-108`)

| Grupo | Apps |
| :--- | :--- |
| Django core | `admin`, `auth`, `contenttypes`, `sessions`, `messages`, `sitemaps`, `staticfiles` |
| Postgres | `django.contrib.postgres` — para búsqueda con `unaccent` |
| Estáticos | `whitenoise.runserver_nostatic` |
| Frontend | `theme` (app de django-tailwind), `tailwind`, `crispy_forms`, `crispy_tailwind`, `widget_tweaks` |
| Autocompletado | `dal`, `dal_select2` |
| Auth social | `social_django` |
| Propias | `core.apps.CoreConfig`, `accounts.apps.AccountsConfig`, `equipos.apps.EquiposConfig`, `torneos.apps.TorneosConfig` |

`django.contrib.postgres` se carga **siempre**, también con SQLite. Es inocuo porque la migración `core/migrations/0001_unaccent_extension.py` (`UnaccentExtension()`) es no-op fuera de PostgreSQL, y `core/utils.py:79-81` (`is_postgres()`) decide en runtime si usar `__unaccent__icontains` o `__icontains` (`core/utils.py:71-77`, `core/views.py:94-115`).

**Orden incorrecto:** `whitenoise.runserver_nostatic` está en la línea 93, *después* de `django.contrib.staticfiles` (línea 91). WhiteNoise exige que vaya **antes** para desactivar el servido de estáticos de `runserver`; tal como está, no tiene efecto.

#### 2.2 Middleware (`settings.py:110-121`)

| # | Middleware | Rol |
| :-- | :--- | :--- |
| 1 | `django.middleware.gzip.GZipMiddleware` | Compresión de respuestas dinámicas |
| 2 | `django.middleware.security.SecurityMiddleware` | Aplica HSTS, SSL redirect, nosniff, referrer-policy |
| 3 | `whitenoise.middleware.WhiteNoiseMiddleware` | Sirve `/static/` sin nginx |
| 4 | `SessionMiddleware` | Sesiones |
| 5 | `CommonMiddleware` | Normalización de URLs |
| 6 | `CsrfViewMiddleware` | CSRF |
| 7 | `AuthenticationMiddleware` | `request.user` |
| 8 | `MessageMiddleware` | Django messages |
| 9 | `XFrameOptionsMiddleware` | Anti-clickjacking |
| 10 | `social_django.middleware.SocialAuthExceptionMiddleware` | Errores de OAuth |

#### 2.3 Templates (`settings.py:125-143`)

`DIRS = [BASE_DIR / 'templates']` + `APP_DIRS=True`. Context processors extra:

- `padel_project.context_processors.notifications` — contador global de invitaciones + partidos pendientes, cacheado 60s en `notifications_count_{user.id}` (`context_processors.py:19-75`).
- `padel_project.context_processors.contacto` — link de WhatsApp del dueño para los CTA de captación. El número está **hardcodeado**: `ORGANIZADOR_WHATSAPP = '5492236886313'` (`context_processors.py:8`).
- `social_django.context_processors.backends` y `.login_redirect`.

#### 2.4 Base de datos (`settings.py:151-160`)

La decisión Postgres vs SQLite es **puramente por presencia de la env var**, no por `DEBUG` ni por un flag explícito:

```python
if 'DATABASE_URL' in os.environ:
    DATABASES = {'default': dj_database_url.config(conn_max_age=600, ssl_require=True)}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
                             'NAME': BASE_DIR / 'db.sqlite3'}}
```

- `conn_max_age=600` → conexiones persistentes 10 min (importante con el free tier de Render, que limita conexiones).
- `ssl_require=True` → se aplica **siempre** que haya `DATABASE_URL`, incluso si apuntás a un Postgres local sin TLS.

Migraciones existentes: **53** (`accounts` 18, `torneos` 24, `equipos` 9, `core` 2).

#### 2.5 Autenticación (`settings.py:281-337`)

| Setting | Valor |
| :--- | :--- |
| `AUTH_USER_MODEL` | `accounts.CustomUser` |
| `LOGIN_URL` | `accounts:login` |
| `LOGIN_REDIRECT_URL` / `LOGOUT_REDIRECT_URL` | `core:home` |

Backends, **en orden** (`settings.py:289-294`):

1. `social_core.backends.google.GoogleOAuth2`
2. `accounts.auth_backends.MergedAccountBackend` — TP-20: permite entrar con **cualquiera** de los mails de una persona cuyas cuentas se fusionaron. Sigue la cadena `merged_into` con tope anti-ciclos de 10 saltos (`accounts/auth_backends.py:15-23`) y acepta tanto la contraseña de la cuenta canónica como la de la vieja (`accounts/auth_backends.py:58`).
3. `django.contrib.auth.backends.ModelBackend`

Google OAuth2:

- Claves: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (default `''` → login social simplemente no anda si faltan).
- Scopes: `openid`, `userinfo.email`, `userinfo.profile`.
- `SOCIAL_AUTH_ASSOCIATE_BY_EMAIL = True` + `associate_by_email` en el pipeline: vincula al usuario existente si el mail coincide.
- Pipeline custom con `accounts.pipeline.save_google_profile` (guarda nombre/apellido, marca verificado) intercalado antes de `user_details` (`settings.py:315-329`). El comentario del código aclara que **no** se redirige desde el pipeline porque el usuario todavía no está logueado.
- `SOCIAL_AUTH_NEW_USER_REDIRECT_URL = '/accounts/completar-perfil/'`, `SOCIAL_AUTH_LOGIN_ERROR_URL = '/accounts/login/'`.
- `SOCIAL_AUTH_REDIRECT_IS_HTTPS = True` sólo si `not DEBUG` (`settings.py:336-337`).

Anti fuerza bruta (TP-21): `accounts/forms.py:182-193` limita a **20 intentos fallidos por IP cada 600 s**, usando el `DatabaseCache` con clave `login_fails_<ip>`. La IP sale del **primer** valor de `X-Forwarded-For` sin validación (`accounts/forms.py:170-172`), por lo que el throttle es evitable spoofeando el header.

#### 2.6 Archivos estáticos — WhiteNoise (`settings.py:268-273`)

| Setting | Valor |
| :--- | :--- |
| `STATIC_URL` | `/static/` |
| `STATIC_ROOT` | `BASE_DIR / 'staticfiles'` |
| `STORAGES['staticfiles']` | `whitenoise.storage.CompressedManifestStaticFilesStorage` (en **ambas** ramas: `settings.py:231` y `:245`) |
| `STATICFILES_DIRS` | **no definido** — los estáticos vienen de `theme/static/` por `APP_DIRS` |

`CompressedManifestStaticFilesStorage` genera hashes + `.gz`/`.br`, lo que implica que **`{% static %}` falla si no se corrió `collectstatic`**. De ahí que las 4 apps de tests hagan `@override_settings(STORAGES=TEST_STORAGES)` con `StaticFilesStorage` plano.

`staticfiles/` está **commiteado al repo**: `git ls-files staticfiles` devuelve 1003 archivos y el directorio no figura en `.gitignore`.

#### 2.7 Media — Cloudinary vs local (`settings.py:193-248`)

La decisión es por presencia de `CLOUDINARY_URL`, con limpieza defensiva de comillas y espacios (`settings.py:197`):

| Condición | Comportamiento |
| :--- | :--- |
| `CLOUDINARY_URL` presente | Agrega `cloudinary_storage` y `cloudinary` a `INSTALLED_APPS` en caliente (`:200-201`); parsea la URL con regex `cloudinary://<key>:<secret>@<cloud_name>` (`:205`); arma `CLOUDINARY_STORAGE`; `STORAGES['default'] = MediaCloudinaryStorage` |
| Regex no matchea | Fallback a `CLOUDINARY_CLOUD_NAME` / `CLOUDINARY_API_KEY` / `CLOUDINARY_API_SECRET` sueltas (`:219-221`) |
| Sin `CLOUDINARY_URL` | `MEDIA_URL='/media/'`, `MEDIA_ROOT=BASE_DIR/'media'`, `STORAGES['default'] = FileSystemStorage` |

> **Bug latente.** La rama Cloudinary **no define `MEDIA_URL` ni `MEDIA_ROOT`**. Si alguien corre local con `DEBUG=True` **y** `CLOUDINARY_URL` seteada, `padel_project/urls.py:39` ejecuta `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` con prefijo `''`, y `django.conf.urls.static.static` levanta `ImproperlyConfigured("Empty static prefix not permitted")` **antes** de chequear `DEBUG`. El proyecto no arranca. En Render no se nota porque `DEBUG` siempre es `False`.

Ambas ramas hacen `print(...)` al importar settings (`:214`, `:216`, `:234`, `:236`, `:248`), lo que ensucia los logs de arranque.

#### 2.8 Caché (`settings.py:253-262`)

```python
'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
'LOCATION': 'django_cache', 'TIMEOUT': 300, 'OPTIONS': {'MAX_ENTRIES': 1000}
```

Elegido explícitamente (comentario en `:252`) porque `LocMemCache` sería per-process y hay 2 workers de Gunicorn. Requiere `python manage.py createcachetable` — presente en `build.sh:12`.

Consumidores: rankings por división, `get_player_stats`, el context processor de notificaciones y el throttle de login.

#### 2.9 Email (`settings.py:383-398`)

| Entorno | Backend |
| :--- | :--- |
| `DEBUG=True` | `django.core.mail.backends.console.EmailBackend` |
| Producción | `accounts.resend_backend.ResendBackend` (POST a `https://api.resend.com/emails`, timeout 15 s, `accounts/resend_backend.py:45-50`) |

`DEFAULT_FROM_EMAIL` sale de `noreply@{CUSTOM_DOMAIN}` si existe, si no el fijo `noreply@todopadel.club`.

**Inconsistencia real:** aunque `EMAIL_BACKEND` es Resend, `torneos/emails.py:74` y `torneos/emails.py:201` fuerzan `get_connection('accounts.brevo_backend.BrevoBackend')`, salteando la configuración global. En la práctica conviven dos proveedores y hay que setear **ambas** API keys.

#### 2.10 Seguridad

Siempre activo:

- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` (`:44`) — necesario detrás del proxy de Render.
- `ALLOWED_HOSTS` dinámico (`:26-41`): `RENDER_EXTERNAL_HOSTNAME` + `CUSTOM_DOMAIN` + `www.CUSTOM_DOMAIN`; `127.0.0.1`/`localhost` sólo si **ninguna** de las dos está seteada.
- `CSRF_TRUSTED_ORIGINS` (`:47-53`): `https://<render-host>`, `https://<dominio>` y `https://www.<dominio>`, normalizando el prefijo `www.` si venía incluido.

Bloque `if not DEBUG:` (`settings.py:56-69`):

| Flag | Valor | Efecto |
| :--- | :--- | :--- |
| `SECURE_SSL_REDIRECT` | `True` | Redirige HTTP → HTTPS |
| `SESSION_COOKIE_SECURE` | `True` | Cookie de sesión sólo por HTTPS |
| `CSRF_COOKIE_SECURE` | `True` | Cookie CSRF sólo por HTTPS |
| `SECURE_HSTS_SECONDS` | `31536000` | HSTS 1 año |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` | Aplica a subdominios |
| `SECURE_HSTS_PRELOAD` | `True` | Elegible para la lista de preload |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` | Anti MIME-sniffing |
| `SECURE_REFERRER_POLICY` | `'same-origin'` | No filtra la URL a terceros |
| `SESSION_COOKIE_HTTPONLY` | `True` | Sesión no accesible por JS |

**Fail-safe de `DEBUG`** (`settings.py:20-23`): `DEBUG` sale de la env var (default `'True'`), pero si existe la variable `RENDER` se fuerza `DEBUG = False` pase lo que pase. Esto blinda todo el bloque anterior contra un `DEBUG` mal seteado en el panel de Render.

No configurado: CSP (los CDN de terceros lo harían difícil sin ajustes), `X_FRAME_OPTIONS` explícito (queda el default `DENY`), `SECURE_CROSS_ORIGIN_OPENER_POLICY` explícito.

#### 2.11 Logging (`settings.py:349-380`)

Un único handler `console` (`StreamHandler`, formato `{levelname} {asctime} {module} {message}`). `root` en `INFO`; logger `django` en `INFO` y `django.request` en `ERROR`, ambos con `propagate=False`. No hay handler de archivo, rotación ni integración con Sentry/APM: la observabilidad es el stream de logs de Render.

#### 2.12 i18n / timezone (`settings.py:185-188`)

`LANGUAGE_CODE='es-ar'`, `TIME_ZONE='America/Argentina/Buenos_Aires'`, `USE_I18N=True`, `USE_TZ=True`. Las fechas se guardan en UTC y se muestran en hora de Buenos Aires.

#### 2.13 Otros

- `DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'` (`:278`).
- `NPM_BIN_PATH` según plataforma: `C:\Program Files\nodejs\npm.cmd` en Windows, `npm` en Linux (`:73-79`).
- `TAILWIND_APP_NAME='theme'`, `CRISPY_TEMPLATE_PACK='tailwind'`, `INTERNAL_IPS=['127.0.0.1']` (`:341-346`).

---

### 3. Variables de entorno (inventario completo)

| Variable | Dónde | Default | Efecto |
| :--- | :--- | :--- | :--- |
| `SECRET_KEY` | `settings.py:17` | `'django-insecure-tu-secret-key-local'` | Firma de sesiones/CSRF. **Obligatoria en prod.** |
| `DEBUG` | `settings.py:20` | `'True'` | `'True'` activa modo debug. Comparación estricta contra el string `'True'`. |
| `RENDER` | `settings.py:22` | — | Si existe (cualquier valor), fuerza `DEBUG=False`. La setea Render sola. |
| `RENDER_EXTERNAL_HOSTNAME` | `settings.py:27` | — | Se agrega a `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS`. |
| `CUSTOM_DOMAIN` | `settings.py:31` | — | Dominio propio (`todopadel.club`): `ALLOWED_HOSTS` (+ `www.`), `CSRF_TRUSTED_ORIGINS` y `DEFAULT_FROM_EMAIL`. |
| `DATABASE_URL` | `settings.py:151` | — | Si existe → PostgreSQL vía `dj_database_url` (SSL forzado, `conn_max_age=600`). Si no → SQLite. |
| `CLOUDINARY_URL` | `settings.py:193` | — | Si existe → media en Cloudinary; si no → filesystem local. Formato `cloudinary://key:secret@cloud_name`. |
| `CLOUDINARY_CLOUD_NAME` | `settings.py:219` | — | Fallback si la regex de `CLOUDINARY_URL` falla. |
| `CLOUDINARY_API_KEY` | `settings.py:220` | — | Ídem. |
| `CLOUDINARY_API_SECRET` | `settings.py:221` | — | Ídem. |
| `VAPID_PRIVATE_KEY` | `settings.py:298` | `''` | Clave privada Web Push. Vacía → push no-op silencioso. |
| `VAPID_PUBLIC_KEY` | `settings.py:299` | `''` | Clave pública; se expone al front en `core/views.py:72` para `pushManager.subscribe`. |
| `VAPID_ADMIN_EMAIL` | `settings.py:300` | `'mailto:admin@todopadel.club'` | Claim `sub` de VAPID. Debe llevar el prefijo `mailto:`. |
| `GOOGLE_CLIENT_ID` | `settings.py:304` | `''` | Client ID de Google OAuth2. |
| `GOOGLE_CLIENT_SECRET` | `settings.py:305` | `''` | Client secret de Google OAuth2. |
| `RESEND_API_KEY` | `settings.py:389` | `None` | API key de Resend (backend por defecto en prod). |
| `BREVO_API_KEY` | `settings.py:390` | `None` | API key de Brevo (usada por `torneos/emails.py`). |
| `DJANGO_SUPERUSER_USERNAME` | `scripts/create_initial_superuser.py:17` | `'emanuel'` | Usuario del superadmin creado en cada build. |
| `DJANGO_SUPERUSER_EMAIL` | `scripts/create_initial_superuser.py:18` | `'egomezbolig@gmail.com'` | Email del superadmin. |
| `DJANGO_SUPERUSER_PASSWORD` | `scripts/create_initial_superuser.py:19` | `'emanuel2001'` | **Contraseña del superadmin.** Setear sí o sí. |
| `DJANGO_SETTINGS_MODULE` | `wsgi.py:14`, `manage.py:9` | `'padel_project.settings'` | Módulo de settings. |
| `PYTHON_VERSION` | `deployment_guide.md:36` | — | Convención de Render. Recomendado `3.11.9`. |
| `WEB_CONCURRENCY` | `render.yaml.disabled:19` | `4` | Convención de Gunicorn. Contradice el `workers=2` del `Procfile`. |

> No existe `.env.example`. `python-dotenv==1.2.1` figura en `requirements.txt` pero **nadie llama a `load_dotenv()`**: las variables deben venir del entorno del proceso.

---

### 4. Deploy en Render

#### 4.1 Configuración del servicio

El blueprint está **deshabilitado** (el archivo es `render.yaml.disabled`, no `render.yaml`), así que el servicio se configura a mano según `deployment_guide.md`:

| Campo | Valor |
| :--- | :--- |
| Runtime | Python 3 (`PYTHON_VERSION=3.11.9` recomendado) |
| Branch | `main` |
| Build Command | `./build.sh` |
| Start Command | `gunicorn padel_project.wsgi:application` |
| Base de datos | PostgreSQL en Render, se conecta con la **Internal Database URL** |

#### 4.2 `build.sh` — qué corre en cada deploy

```bash
set -o errexit                              # build.sh:3 — falla el deploy ante cualquier error
pip install -r requirements.txt             # :5
python manage.py tailwind install           # :7  npm install en theme/static_src/
python manage.py tailwind build             # :8  compila theme/static/css/tailwind.css
python manage.py collectstatic --no-input   # :10 → staticfiles/ + manifest + .gz/.br
python manage.py migrate                    # :11
python manage.py createcachetable           # :12 crea la tabla django_cache
python scripts/seed_divisions.py            # :16 8 divisiones (Primera..Octava), idempotente
python scripts/create_initial_superuser.py  # :17 superusuario si no existe
python manage.py reparar_rankings           # :19 fusiona equipos duplicados + recalcula rankings
```

Observaciones:

- **No corre tests.** No hay CI ni gate de calidad antes del deploy.
- `reparar_rankings` no es un simple recálculo: fusiona equipos duplicados **borrando registros** (`torneos/management/commands/reparar_rankings.py:72`) y reasigna `Inscripcion`, `EquipoGrupo`, `PartidoGrupo`, `Partido` y `Torneo.ganador_del_torneo` al equipo canónico. Correrlo en cada deploy es una operación destructiva recurrente.
- `build.sh:21` deja escrito que `migrar_rankings_historicos` es puntual y **no** debe ir en el deploy.

#### 4.3 Gunicorn — tres configuraciones que no coinciden

| Fuente | Configuración |
| :--- | :--- |
| `Procfile:1` | `gunicorn padel_project.wsgi --config gunicorn_config.py --workers=2 --threads=4 --worker-class=gthread --timeout=120` |
| `gunicorn_config.py` | `timeout=120`, `workers=2`, `threads=4`, `worker_class='gthread'`, `accesslog='-'`, `errorlog='-'`, `loglevel='info'` |
| `render.yaml.disabled:11` + `deployment_guide.md:23` | `gunicorn padel_project.wsgi:application` — **sin** `--config` ni flags |

El start command documentado ignora `gunicorn_config.py`, así que en producción probablemente corren los **defaults** de Gunicorn (1 worker sync, timeout 30 s) en lugar de gthread 2×4 con timeout 120 s. El timeout largo está justificado en el código (`gunicorn_config.py:5`) por el procesamiento de imágenes y el envío de emails: conviene unificar.

#### 4.4 Variables a setear en Render

**Imprescindibles:** `SECRET_KEY`, `DATABASE_URL`, `DEBUG=False`, `PYTHON_VERSION`, `CUSTOM_DOMAIN` (o `RENDER_EXTERNAL_HOSTNAME`), `CLOUDINARY_URL`.

**Push (TP-11):** `VAPID_PRIVATE_KEY`, `VAPID_PUBLIC_KEY` y opcionalmente `VAPID_ADMIN_EMAIL`. Las claves se generan con `py_vapid` (comentario en `settings.py:297`). Si falta cualquiera de las dos, `accounts/push.py:16-17` desactiva el push en silencio — no hay error visible, simplemente nadie recibe notificaciones.

**Email:** `RESEND_API_KEY` **y** `BREVO_API_KEY` (ambos backends están en uso).

**Google OAuth2:** `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`.

**Superusuario:** `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_PASSWORD` — sin estas, `build.sh` crea un admin con contraseña conocida por cualquiera que lea el repo.

`deployment_guide.md` sólo documenta las primeras seis; el resto hay que deducirlo del código.

#### 4.5 Frontend build (Tailwind)

`django-tailwind` compila desde `theme/static_src/`:

- `theme/static_src/package.json` → `tailwindcss ^3.4.17`, script `build`: `tailwindcss -i ./src/styles.css -o ../static/css/tailwind.css --minify`.
- `theme/static_src/tailwind.config.js` → `darkMode: 'class'`, fuente `Inter`, `primary: '#10b981'`, con `content` apuntando a las 4 apps + `templates/`.
- `theme/package.json` (en la raíz de la app, **no** el que usa django-tailwind) declara `tailwindcss ^4.1.17`, `autoprefixer`, `postcss` y `cross-env`. Es una divergencia de versión mayor entre dos archivos con el mismo nombre.

Sólo Tailwind es local. Desde CDN externo se cargan (`theme/templates/base.html:60-71`): htmx 1.9.10 (unpkg), DaisyUI 4.7.2 (jsdelivr) y Google Fonts Inter. El atributo SRI de htmx está mal escrito — `xintegrity` en vez de `integrity` (`base.html:61`) — así que la verificación de integridad no se aplica.

#### 4.6 PWA y SEO en el URLconf

`padel_project/urls.py` sirve desde la raíz para que el *scope* del service worker sea `/`:

| Ruta | Contenido |
| :--- | :--- |
| `/sw.js` | `TemplateView` sobre `pwa/sw.js`, `content_type="application/javascript"` (`urls.py:23`) |
| `/manifest.webmanifest` | `TemplateView`, `content_type="application/manifest+json"` (`urls.py:24`) |
| `/robots.txt` | `TemplateView` texto plano (`urls.py:18`) |
| `/sitemap.xml` | 3 sitemaps: `StaticViewSitemap`, `TorneoSitemap`, `CitySitemap` (`urls.py:20`, `padel_project/sitemaps.py`) |
| `/googleed7ca9e7f31e28a7.html` | Verificación de Google Search Console (`urls.py:19`) |
| `/favicon.ico`, `/apple-touch-icon*.png` | `RedirectView` permanentes a `STATIC_URL` (`urls.py:21`, `:42-43`) |

---

### 5. Testing

#### 5.1 Números reales

| Métrica | Valor |
| :--- | :--- |
| Tests totales | **124** |
| Clases de test | 32 |
| Tiempo de ejecución | **430.276 s** (~7 min 10 s de wall clock) |
| Resultado | OK (0 fallos, 0 errores) |
| Base de datos | SQLite en memoria/temporal, creada y destruida por corrida |
| Framework | `django.test.TestCase` puro — sin pytest, sin factories, sin coverage |

Medido con `python manage.py test` sobre el repo: `Ran 213 tests in 607.566s / OK`.

#### 5.2 Mapa de tests

**`torneos/tests.py` — 77 tests, 19 clases**

| Clase | Tests | Qué cubre |
| :--- | :--: | :--- |
| `ShareButtonTorneoDetailTests` | 3 | TP-01: botón compartir, link `wa.me`, meta tags Open Graph dinámicos, URL absoluta |
| `GenerarBracketZonaIncompletaTests` | 2 | Bugfix: zonas con partidos pendientes no vuelcan equipos al cuadro (quedan placeholders `1A`/`2B`) |
| `PlacaCampeonesTests` | 3 | TP-01b: overlays de Cloudinary en la placa; `cloudinary_activo()` False en tests; `None` si el torneo no finalizó |
| `FichaVendedoraTests` | 2 | TP-03: `cupos_disponibles`, sede/ciudad/premio/reglamento y foto de cancha por defecto |
| `TorneosPorCiudadTests` | 2 | TP-14: página `/torneos/ciudad/<x>/` y su entrada en el sitemap |
| `TorneoVivoTests` | 1 | TP-13: scoreboard público en vivo responde 200 |
| `CircuitoTests` | 2 | TP-12: listado/detalle de circuitos y acumulación de puntos (15 pts por victoria de zona) |
| `AmericanoTests` | 4 | TP-09: join público sin login, 3 rondas con rotación completa de compañeros, suma de puntos, Mexicano ronda a ronda |
| `DescribirEstructuraTests` | 8 | TP-17.3: proyección de zonas, invariantes de **todas** las llaves FAP 6→48 (cada clasificado una vez, 2 entradas por partido, una sola final), byes de eliminación directa, coherencia proyección↔generación real |
| `TorneoAdminFormTests` | 9 | TP-17.1/.4/.5: alta en secciones, `foto_campeones` sólo al editar, prefijado desde la organización, validación de fechas y cupos, endpoint `preview-estructura` |
| `WalkoverAbandonoTests` | 5 | TP-18: W.O. (2-0 en sets, 0 games) y abandono (gana el que sigue, games del parcial cuentan) en zona y en bracket |
| `PlacaRedesTests` | 4 | Placas 9:16 para redes: genérica, anuncio, default por estado, campeones |
| `PushEventosTests` | 3 | TP-11: `_push_resultado` notifica a los 4 jugadores, `_push_programado`, y no notifica sin ganador (con `unittest.mock.patch`) |
| `ElegibilidadNotificacionesTests` | 3 | Filtros de compatibilidad para notificar torneos: división cercana, género, ciudad (normalizando tildes y mayúsculas), exclusión de dummies |
| `AgregarZonaTests` | 7 | Agregar zona a torneo en juego sin perder resultados; play-in de octavos con sólo 2 cruces; octavos solo para segundos; sin cruces fantasma; reset de llave obsoleta |
| `SeedConByesTests` | 1 | `_seed_con_byes`: distribución de byes sin enfrentar dos byes, para 7 combinaciones |
| `FormatoPersonalizadoTests` | 7 | Creador de formatos: parseo de `sizes`, validaciones, generación de zonas al iniciar, aislamiento por organización |
| `CrucesManualesTests` | 8 | Editor de cruces de fase final: JSON válido/repetido/incompleto, cruces con byes, generación real |
| `DashboardOrganizadorTests` | 3 | Panel de métricas: requiere login, métricas correctas, aislamiento por organización |

**`accounts/tests.py` — 37 tests, 10 clases**

| Clase | Tests | Qué cubre |
| :--- | :--: | :--- |
| `OrganizacionWhatsappTests` | 3 | TP-02: normalización de `whatsapp` a dígitos para `wa.me` |
| `PublicProfilePublicAccessTests` | 2 | TP-06: perfil público sin login (200, no 302) + botón compartir y OG tags |
| `PerfilStatsHistorialTests` | 3 | TP-19.1/.2: stats completas contando W.O., resultados recientes, render de perfil propio y público |
| `FichaLogrosCompletitudTests` | 6 | TP-19.3/.4: normalización de Instagram, validación de `juega_desde`, logros desbloqueados, medidor de completitud |
| `DedupCuentasTests` | 5 | TP-20: detección de duplicados con variantes/tildes/typos, merge real→real, rechazo de destino dummy, exclusión de fusionadas del ranking, vista admin |
| `MultiLoginCuentasFusionadasTests` | 6 | TP-20 etapa 2: login con mail viejo + pass canónica o pass vieja, rechazo de pass incorrecta, cadenas de fusión |
| `MergeColisionEquipoTests` | 1 | TP-20 fix: fusionar con compañero compartido no rompe `unique_active_team` y preserva el historial |
| `MergeDummyADummyTests` | 2 | Consolidar dos dummies; rechazar real→dummy |
| `HardeningSeguridadTests` | 3 | TP-21: organizador no puede fusionar reales, admin sí y queda `MergeAuditLog`, throttle de login |
| `PushNotificacionesTests` | 6 | TP-11: subscribe requiere login, alta/baja idempotente, payload inválido → 400, no-op sin VAPID, borrado de suscripción 410, render del botón |

**`core/tests.py` — 7 tests, 2 clases**

| Clase | Tests | Qué cubre |
| :--- | :--: | :--- |
| `LandingOrganizadoresTests` | 4 | TP-05: landing `/para-organizadores/`, CTA a WhatsApp (`wa.me/5492236886313`), contadores y testimonios, imagen de fondo del hero |
| `PWAInstalarTests` | 3 | `/sw.js` (content-type + `addEventListener`/`showNotification`), `/manifest.webmanifest` (`"standalone"`), tutorial de instalación Android/iPhone |

**`equipos/tests.py` — 3 tests, 1 clase**

| Clase | Tests | Qué cubre |
| :--- | :--: | :--- |
| `MatchmakingTests` | 3 | TP-10: listado público 200, publicar búsqueda (autocompleta división desde el jugador), aparición en el listado |

#### 5.3 Cómo se corren

```bash
python manage.py test                      # todo (213 tests, ~10 min)
python manage.py test torneos              # una app
python manage.py test torneos.tests.WalkoverAbandonoTests
python manage.py test torneos.tests.WalkoverAbandonoTests.test_grupo_walkover_convencion_tabla
python manage.py test --parallel           # no usado hoy; podría bajar bastante los 7 min
```

#### 5.4 Patrones y limitaciones

- **`TEST_STORAGES` duplicado 4 veces** (`torneos/tests.py:14-17`, `accounts/tests.py:9-12`, `core/tests.py:4-7`, `equipos/tests.py:8-11`): mismo dict copiado literalmente para forzar `StaticFilesStorage` plano, porque sin `collectstatic` no hay manifest de WhiteNoise y `{% static %}` explota. Candidato claro a extraer a un módulo compartido o a un `settings_test.py`.
- **Skip condicional** en `torneos/tests.py:168`: `@skipUnless(_CLOUDINARY_AVAILABLE)` para el test de overlays.
- **Ruido en la salida:** durante la corrida aparecen trazas de `django.db.utils.OperationalError: database table is locked` desde `_raw_delete` del `DatabaseCache` sobre SQLite. No hacen fallar el suite, pero evidencian contención en `django_cache` (el push envía en threads y varias clases hacen `cache.clear()`).
- **Sin cobertura de:** el bloque de settings de producción (Cloudinary, Resend, HSTS), `build.sh`, los management commands (`reparar_rankings` incluido) y el envío real de emails.
- **No hay** `coverage`, `pytest`, `factory_boy` ni CI. El único gate es correr los tests a mano.

---

### 6. Dependencias (`requirements.txt`)

> El archivo está guardado en **UTF-16 LE con BOM** (primeros bytes `ff fe`), no en UTF-8. `pip` lo tolera vía detección de BOM, pero cualquier herramienta que lo lea como texto plano (grep, diff, escáneres de dependencias) verá basura.

**Núcleo del framework**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `Django` | 5.2.8 | Framework |
| `asgiref` | 3.11.0 | Capa ASGI/sync-async de Django |
| `sqlparse` | 0.5.3 | Formateo de SQL (usado por el ORM/debug) |
| `tzdata` | 2025.2 | Zonas horarias (necesario en Windows para `America/Argentina/Buenos_Aires`) |

**Base de datos y deploy**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `psycopg2-binary` | 2.9.11 | Driver PostgreSQL |
| `dj-database-url` | 3.0.1 | Parsea `DATABASE_URL` → dict de `DATABASES` |
| `gunicorn` | 23.0.0 | Servidor WSGI de producción |
| `whitenoise` | 6.11.0 | Sirve estáticos comprimidos con manifest sin nginx |

**Media e imágenes**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `cloudinary` | 1.44.1 | SDK de Cloudinary (también genera los overlays de las placas) |
| `django-cloudinary-storage` | 0.3.0 | Backend `MediaCloudinaryStorage` |
| `pillow` | 11.3.0 | Requerido por `ImageField` de Django |

**Autenticación**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `social-auth-app-django` | 5.7.0 | Integración de social-auth con Django |
| `social-auth-core` | 4.8.5 | Backends OAuth2 (Google) |

**Frontend / formularios**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `django-tailwind` | 4.4.1 | Comandos `tailwind install` / `tailwind build` |
| `pytailwindcss` | 0.3.0 | Binario de Tailwind sin Node |
| `django-crispy-forms` | 2.5 | Renderizado de formularios |
| `crispy-tailwind` | 1.0.3 | Template pack Tailwind para crispy |
| `django-widget-tweaks` | 1.5.0 | Ajuste de widgets desde el template |
| `django-autocomplete-light` | 3.12.1 | Selects con autocompletado (`dal`, `dal_select2`) |

**Notificaciones y HTTP**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `pywebpush` | 2.3.0 | Envío Web Push con VAPID |
| `requests` | 2.32.5 | Llamadas a las APIs de Resend y Brevo |
| `certifi`, `idna`, `charset-normalizer`, `urllib3` | — | Dependencias transitivas de `requests` |

**Utilidades**

| Paquete | Versión | Propósito |
| :--- | :--- | :--- |
| `python-dateutil`, `arrow` | 2.9.0 / 1.4.0 | Manejo de fechas |
| `python-slugify`, `text-unidecode` | 8.0.4 / 1.3 | Slugs (alias de organizaciones, códigos) |
| `PyYAML` | 6.0.3 | Parseo YAML |
| `Jinja2`, `MarkupSafe` | 3.1.6 / 3.0.3 | Motor de templates (transitivo de cookiecutter) |
| `python-dotenv` | 1.2.1 | **Declarado pero nunca usado** — no hay `load_dotenv()` en el proyecto |

**Herramientas de desarrollo mezcladas con producción** (no hay `requirements-dev.txt`): `pylint` 3.3.8, `astroid` 3.3.11, `isort` 6.0.1, `mccabe` 0.7.0, `dill` 0.4.0, `tomlkit` 0.13.3, `platformdirs` 4.3.8, `cookiecutter` 2.6.0, `binaryornot` 0.4.4, `chardet` 5.2.0, `rich` 14.2.0, `Pygments` 2.19.2, `markdown-it-py` 4.0.0, `mdurl` 0.1.2, `click` 8.3.1, `colorama` 0.4.6, `packaging` 25.0, `six` 1.17.0. Se instalan en cada build de Render sin aportar nada al runtime.

---

### 7. Comandos habituales de desarrollo

```bash
# --- Puesta en marcha (local, SQLite) ---
pip install -r requirements.txt
python manage.py migrate
python manage.py createcachetable          # imprescindible: el caché es DatabaseCache
python scripts/seed_divisions.py           # 8 divisiones base
python manage.py createsuperuser
python manage.py runserver

# --- Frontend (Tailwind) ---
python manage.py tailwind install          # npm install en theme/static_src/
python manage.py tailwind build            # build minificado → theme/static/css/tailwind.css
python manage.py tailwind start            # watch en desarrollo

# --- Base de datos ---
python manage.py makemigrations
python manage.py migrate
python manage.py showmigrations
python manage.py shell

# --- Tests ---
python manage.py test                      # 213 tests, ~10 min
python manage.py test accounts             # una app
python manage.py test torneos.tests.AmericanoTests

# --- Estáticos ---
python manage.py collectstatic --no-input  # → staticfiles/ con manifest + .gz/.br

# --- Datos de prueba y mantenimiento ---
python manage.py seed_dev_data             # equipos/
python manage.py create_test_tournament    # equipos/
python manage.py simulate_group_results    # equipos/
python manage.py test_rankings_performance # equipos/
python manage.py crear_torneo_24           # torneos/
python manage.py simular_torneo_24         # torneos/
python manage.py reparar_rankings          # torneos/ — destructivo: fusiona equipos duplicados
python manage.py migrar_rankings_historicos # torneos/ — puntual, NO en cada deploy
```

---

### 8. Deuda e higiene detectada

Ordenado por severidad.

| # | Hallazgo | Ubicación |
| :-- | :--- | :--- |
| 1 | **Credencial de Postgres/Supabase en texto plano y commiteada** (usuario + contraseña + host). Debe rotarse la contraseña y purgarse el archivo del historial. | `loader.py:6` |
| 2 | **Contraseña de superusuario por defecto** (`emanuel2001`) que se aplica en **cada deploy** si no están las `DJANGO_SUPERUSER_*`. | `scripts/create_initial_superuser.py:17-19` + `build.sh:17` |
| 3 | Con `CLOUDINARY_URL` + `DEBUG=True` el proyecto **no arranca**: `MEDIA_URL` queda vacío y `static()` lanza `ImproperlyConfigured`. | `settings.py:195-234` + `urls.py:39` |
| 4 | El throttle de login confía en el primer valor de `X-Forwarded-For` → evitable con un header spoofeado. | `accounts/forms.py:170-172` |
| 5 | `whitenoise.runserver_nostatic` va después de `django.contrib.staticfiles`: la app no surte efecto. | `settings.py:91-93` |
| 6 | Tres configuraciones de Gunicorn contradictorias; el start command documentado ignora `gunicorn_config.py` y el `Procfile`. | `Procfile:1`, `gunicorn_config.py`, `render.yaml.disabled:11` |
| 7 | Dos proveedores de email en paralelo: `EMAIL_BACKEND` es Resend pero `torneos/emails.py` fuerza Brevo. | `settings.py:388` vs `torneos/emails.py:74,201` |
| 8 | `staticfiles/` (1003 archivos de build) commiteado y ausente de `.gitignore`. | raíz del repo |
| 9 | `requirements.txt` en UTF-16 LE con BOM; mezcla dependencias de desarrollo (pylint, cookiecutter, rich) con las de producción. | `requirements.txt` |
| 10 | `python-dotenv` declarado pero nunca usado; no existe `.env.example` que documente las 20+ variables. | `requirements.txt:39` |
| 11 | `render.yaml` deshabilitado → la infra no es reproducible desde el repo, y `deployment_guide.md` sólo documenta 6 de las ~20 variables (falta VAPID, Google, Resend, Brevo, `CUSTOM_DOMAIN`, superusuario). | `render.yaml.disabled`, `deployment_guide.md` |
| 12 | Sin CI ni gate de tests: `build.sh` despliega sin correr el suite. | `build.sh` |
| 13 | `reparar_rankings` (operación destructiva que borra equipos) corre en cada deploy. | `build.sh:19` |
| 14 | SRI de htmx inerte por atributo mal escrito (`xintegrity` en vez de `integrity`). | `theme/templates/base.html:61` |
| 15 | Dos `package.json` con versiones mayores divergentes de Tailwind (v4 en `theme/`, v3 en `theme/static_src/`). | `theme/package.json`, `theme/static_src/package.json` |
| 16 | `print()` de diagnóstico en `settings.py` que ensucian los logs de arranque en cada boot. | `settings.py:214,216,234,236,248` |
| 17 | `TEST_STORAGES` copiado literalmente en las 4 apps de tests. | `*/tests.py` (cabeceras) |
| 18 | Raíz del repo con ~30 scripts sueltos de debug (`debug_*.py`, `check_*.py`, `verify_*.py`, `test_*_teams.py`) y 9 dumps JSON de backup de producción. | raíz del repo |
| 19 | Número de WhatsApp del dueño hardcodeado en el context processor global. | `padel_project/context_processors.py:8` |
| 20 | Sin CSP, sin APM/Sentry, logging sólo a consola sin agregación. | `settings.py:349-380` |

---

## Anexo: entorno, tooling y convenciones

> Esta sección cubre lo que no entra en el modelo de datos ni en la lógica de torneos: cómo se levanta el proyecto, qué hay en la raíz del repo, qué convenciones no escritas existen y qué deuda de higiene arrastra.

### A.1 Punto de partida: no hay README

El repositorio **no tiene `README.md` ni `CLAUDE.md`**. Todo el conocimiento de setup vive en la cabeza del autor, en `deployment_guide.md` (que sólo cubre Render) y en la memoria de la herramienta. Esta sección es el reemplazo.

### A.2 Puesta en marcha local (Windows, que es el entorno real de desarrollo)

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt          # ojo: el archivo está en UTF-16 (ver A.4)

# Frontend (django-tailwind compila a theme/static/css/tailwind.css)
python manage.py tailwind install
python manage.py tailwind build

python manage.py migrate
python manage.py createcachetable        # OBLIGATORIO, ver abajo
python scripts/seed_divisions.py         # crea las 8 divisiones (Primera..Octava)
python manage.py createsuperuser
python manage.py runserver
```

**`createcachetable` no es opcional.** `CACHES` usa `DatabaseCache` sobre la tabla `django_cache` (`padel_project/settings.py:253-262`) y el context processor `notifications` hace `cache.get()` en **cada request autenticado**. Sin la tabla, toda página logueada devuelve 500.

Otros detalles del entorno local:

| Ítem | Comportamiento |
| :--- | :--- |
| Base de datos | SQLite (`db.sqlite3`) salvo que exista `DATABASE_URL`. El `db.sqlite3` versionado pesa 0 bytes: hay que migrar de cero. |
| Media | `FileSystemStorage` con `MEDIA_ROOT = BASE_DIR/'media'` (sin `CLOUDINARY_URL`). |
| Email | `console.EmailBackend` mientras `DEBUG=True`: los mails se imprimen en la terminal. |
| `NPM_BIN_PATH` | Hardcodeado a `C:\Program Files\nodejs\npm.cmd` en Windows (`settings.py:75-79`). En otra ruta de Node hay que tocar settings. |
| Búsqueda global | Degrada sin `unaccent` en SQLite (`core/utils.py:is_postgres()`); en local no se ejercita el camino Postgres. |

### A.3 Variables de entorno

**No hay `.env` ni `.env.example`, y aunque `python-dotenv` está en `requirements.txt`, no se importa en ningún archivo**: las variables se exportan a mano en la shell (local) o se cargan en el dashboard de Render (producción).

| Variable | Dónde se usa | Default / efecto si falta |
| :--- | :--- | :--- |
| `SECRET_KEY` | `settings.py:17` | `django-insecure-tu-secret-key-local` (inseguro) |
| `DEBUG` | `settings.py:20` | `'True'` → DEBUG activo |
| `RENDER` | `settings.py:22` | Si existe, **fuerza `DEBUG=False`** (fail-safe) |
| `RENDER_EXTERNAL_HOSTNAME` | `settings.py:27` | Se agrega a `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` |
| `CUSTOM_DOMAIN` | `settings.py:31` | Habilita dominio propio + www, y define `DEFAULT_FROM_EMAIL = noreply@<dominio>` |
| `DATABASE_URL` | `settings.py:151` | Sin ella → SQLite. Con ella → Postgres con `ssl_require=True`, `conn_max_age=600` |
| `CLOUDINARY_URL` | `settings.py:193` | Sin ella → media en filesystem. Formato `cloudinary://<key>:<secret>@<cloud>` |
| `CLOUDINARY_CLOUD_NAME` / `_API_KEY` / `_API_SECRET` | `settings.py:219-221` | Sólo fallback si el parseo de `CLOUDINARY_URL` falla |
| `RESEND_API_KEY` | `settings.py:389`, `accounts/resend_backend.py` | Sin ella, el backend loguea `!!! Missing RESEND_API_KEY` y devuelve 0 |
| `BREVO_API_KEY` | `settings.py:390` | Se lee pero **ningún backend activo la consume** (ver A.8) |
| `VAPID_PRIVATE_KEY` / `VAPID_PUBLIC_KEY` / `VAPID_ADMIN_EMAIL` | `settings.py:298-300` | Sin ellas no hay Web Push (TP-11) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | `settings.py:304-305` | Sin ellas el botón de Google OAuth2 falla |
| `DJANGO_SUPERUSER_USERNAME` / `_EMAIL` / `_PASSWORD` | `scripts/create_initial_superuser.py:17-19` | **Defaults hardcodeados** que se aplican en cada deploy |

### A.4 `requirements.txt`: dos trampas

1. **Está guardado en UTF-16 LE con BOM y saltos CRLF.** `pip` lo tolera (detecta el BOM), pero `grep`, `diff`, y cualquier editor ingenuo lo muestran como basura. Si se reescribe, hay que hacerlo en UTF-8.
2. **Arrastra dependencias que el proyecto no usa** y que se instalan en cada build de Render: `cookiecutter`, `binaryornot`, `arrow`, `Jinja2`, `PyYAML`, `text-unidecode`, `rich`, `tomlkit`, más las de linting (`pylint`, `astroid`, `isort`, `dill`, `mccabe`). En cambio **falta `playwright`**, que sí usa `capture_screens.py`.

Lo que sí importa del listado: `Django==5.2.8`, `gunicorn==23.0.0`, `whitenoise==6.11.0`, `dj-database-url`, `psycopg2-binary`, `cloudinary` + `django-cloudinary-storage`, `django-tailwind`, `django-crispy-forms` + `crispy-tailwind`, `django-autocomplete-light`, `django-widget-tweaks`, `social-auth-app-django`, `pywebpush`, `pillow`, `python-dateutil` (parseo de fechas en la búsqueda).

### A.5 Layout de la raíz del repositorio

La raíz mezcla código de producción con ~40 archivos de sesiones de debug. Para orientarse:

**Operativos (no tocar):** `manage.py`, `build.sh`, `Procfile`, `gunicorn_config.py`, `requirements.txt`, `.gitignore`, `templates/`, `scripts/`, `docs/`.

**Configuración inactiva:** `render.yaml.disabled` (blueprint de Render deshabilitado a propósito para no pagar el plan; el servicio se configura a mano desde el dashboard).

**Scripts sueltos de debug/verificación (~40 archivos):** `debug_*.py` (7), `verify_*.py` (5), `check_*.py` (4), `test_7_teams.py`, `test_12_teams.py`, `test_invitation_flow.py`, `simulate_15_teams.py`, `simulate_recalc.py`, `reproduce_issue.py`, `fix_winners.py`, `fix_json.py`, `create_user.py`, `detailed_divisions_debug.py`, `list_all_divisions.py`, más `tmp/test_divisions.py` y `tmp/verify_flex.py`.

Todos siguen la misma convención no escrita:

```python
sys.path.append(os.getcwd())            # o el dirname del parent
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()
```

Corren **contra la base de datos de desarrollo real**, borran por patrón (`Torneo.objects.filter(nombre="Torneo Test 7").delete()`) y varios tienen IDs de torneo hardcodeados. No son tests: son bisturíes de una sesión puntual.

> ⚠️ **`test_7_teams.py`, `test_12_teams.py` y `test_invitation_flow.py` matchean el patrón `test*.py` del descubridor de `manage.py test` cuando se corre desde la raíz** y se importan durante el discovery (ejecutando su `django.setup()`). Por eso conviene correr la suite acotada por app:
> ```bash
> python manage.py test accounts core equipos torneos
> ```

**Salida de debug versionada:** `migrations.txt`, `output.txt`, `schema.txt`, `simple_check.txt`, `test_output.txt`, `verify_output.txt`, `divisions_debug.txt` — varios en UTF-16 y con rutas absolutas de la máquina original (`C:\Users\egome\Desktop\python_project\...`).

**Assets fuera de lugar:** `padelicon.png` (124 KB en la raíz, fuera de `theme/static/img/`), `package-lock.json` vacío, `theme/templates/base.html.backup` (21 KB), `perfiles/` con 2 JPGs de perfiles reales (ver A.7).

### A.6 `scripts/` — qué corre en el deploy y qué no

| Script | ¿Corre en `build.sh`? | Qué hace |
| :--- | :--- | :--- |
| `seed_divisions.py` | Sí | Idempotente: crea Primera..Octava si faltan |
| `create_initial_superuser.py` | Sí | Crea el superusuario con **credenciales por defecto hardcodeadas** si no existe |
| `add_teams.py` | No | Crea 16 equipos e inscribe en **torneo id=8** (hardcodeado) |
| `assign_team_numbers.py` | No | Renumera `EquipoGrupo` del **torneo id=6** |
| `backfill_team_codes.py` | No | Ídem, torneo id=6 |
| `complete_inscriptions.py` | No | Completa inscripciones del torneo id=8 |
| `create_big_tournament.py` / `create_tournament_48.py` | No | Crean 48 equipos + torneo con zonas de 3 |
| `simulate_24_teams.py` | No | Simula un torneo de 24 de punta a punta |
| `datos_demo_informe.py` / `datos_demo_manual.py` | No | Elenco de vitrina para capturas (usuarios demo por rol, resultados, pagos, notificaciones). Sólo base local |
| `capturar_manual.py` | No | Captura todas las pantallas del manual por rol con Playwright → `docs/manual/img/<rol>/`. Requiere `runserver 8010` |
| `armar_reporte.py` / `armar_manual.py` | No | Ensamblan `docs/reporte/reporte-clientes.html` y `docs/manual/manual-usuario.html` desde sus `plantilla.html`, incrustando las capturas como WebP |
| `probar_planilla.py` | No | Genera el PDF de la planilla de horarios como lo haría el navegador y lo rasteriza para revisarlo |

Los one-off con IDs hardcodeados (`add_teams`, `assign_team_numbers`, `backfill_team_codes`, `complete_inscriptions`, `create_big_tournament`, `create_tournament_48`, `simulate_24_teams`): correrlos a ciegas contra una base con datos reales rompe cosas.

**Documentos generados** (`docs/`): `reporte/reporte-clientes.html` (informe de mejoras para clientes) y `manual/manual-usuario.html` (manual de usuario por rol: jugador / organizador / admin). Ambos autocontenidos (imágenes embebidas); las capturas fuente quedan en `docs/reporte/img/` y `docs/manual/img/<rol>/`. Para regenerarlos: `datos_demo_*` → `capturar_*` → `armar_*`.

### A.7 Datos: dump, restore y media legacy

- **9 fixtures `backup_*.json` versionados en la raíz** (~2 MB): `backup_local_db.json`, `backup_render.json` .. `backup_render6.json`, `backup_render_clean.json`, `backup_render_final.json`. No hay registro de cuál corresponde a qué momento.
- **`loader.py`** hace `call_command('loaddata', 'backup_render_final.json')` **pisando `DATABASE_URL` con una URL de Supabase con contraseña en claro (línea 6)**. Esa credencial hay que rotarla y sacarla del repo.
- **`fix_json.py`** repara dumps truncados (busca la última `}` y cierra el array): `backup_render4.json` → `backup_render_clean.json`. Es la evidencia de que los dumps se generaron con procesos que se cortaron.
- **`staticfiles/` está versionado** (1003 archivos, incluido `staticfiles.json`) porque `.gitignore` no lo excluye, aunque `build.sh` corre `collectstatic` en cada deploy. El manifiesto del repo queda desactualizado y ensucia todos los diffs.
- **`perfiles/`** contiene 2 JPGs de perfiles reales versionados: media legacy que quedó fuera de `MEDIA_ROOT` (`upload_to='perfiles/'` en `accounts/models.py:81`). `.gitignore` ignora `media` pero no `perfiles/`.

### A.8 Piezas transversales no cubiertas por las apps

#### Context processors (`padel_project/context_processors.py`)

Dos, ambos globales (`settings.py:136-137`):

- **`notifications(request)`** — sólo para usuarios autenticados. Cuenta invitaciones `PENDING` recibidas + partidos pendientes del equipo (llave `Partido` y zona `PartidoGrupo`, en torneos `AB`/`EJ`), y expone `notification_count`, `pending_invitations_count`, `upcoming_matches_count`, más los flags de banner `user_sin_foto` y `user_sin_equipo`. **Cachea el dict completo 60 s bajo la clave `notifications_count_<user_id>`**: un cambio de estado tarda hasta un minuto en reflejarse en el badge.
- **`contacto(request)`** — arma `organizador_whatsapp_url` para los CTA de captación. **El número del dueño está hardcodeado en el código**: `ORGANIZADOR_WHATSAPP = '5492236886313'` (línea 8).

#### Template tags (`torneos/templatetags/torneo_extras.py`)

Es la **única** librería de tags del proyecto (no hay `templatetags/` en `accounts`, `equipos` ni `core`), y es la que hace andar el bracket y las tablas de zonas:

| Tag / filtro | Uso |
| :--- | :--- |
| `get_team_code` / `get_team_info` / `get_team_display` | Devuelven el nombre de la pareja. Conservan el nombre "code" por compatibilidad histórica (antes devolvían `A1`, `B2`) e incluyen un **saneado legacy**: si el nombre contiene `@`, recortan la parte anterior a la arroba para no filtrar emails en la llave. `get_team_display` cae a `"Esperando resultados"` si no hay equipo. |
| `nombre_ronda_dinamico(ronda, total)` | Traduce el número de ronda a Final / Semifinal / Cuartos / Octavos / 16vos por distancia a la final. |
| `batch(lista, n)` | Parte una lista en sublistas de `n` (grillas). |
| `split(str, delim)` | Split con `strip()`. |
| `short_name(valor, max=20)` | Trunca con elipsis. |
| `{% setvar x = y %}` | Tag propio (`SetVarNode`) que asigna variables en el contexto; resuelve variables, y si falla interpreta `true`/`false` o el literal. |

#### Middleware

**No hay middleware propio.** El orden en `settings.py:110-121` tiene una particularidad a preservar: `GZipMiddleware` va **primero**, antes de `SecurityMiddleware` y de WhiteNoise; y `social_django.middleware.SocialAuthExceptionMiddleware` cierra la lista.

#### Caché

`DatabaseCache` sobre la tabla `django_cache`, `TIMEOUT=300`, `MAX_ENTRIES=1000` (`settings.py:253-262`). Se eligió DB y no LocMem porque Gunicorn corre 2 workers × 4 threads y LocMem sería por proceso. Consumidores: context processor de notificaciones (60 s), rankings por división, contadores de prueba social del home (1 h), throttling de login por IP.

#### Backends de email (`accounts/`)

| Archivo | Estado | Notas |
| :--- | :--- | :--- |
| `resend_backend.py` (`ResendBackend`) | **Activo en producción** | POST a `api.resend.com/emails` con `requests`, timeout 15 s. Extrae el HTML de `message.alternatives`. Loguea con `print()` el destinatario y la respuesta completa de la API. |
| `brevo_backend.py` (`BrevoBackend`) | Huérfano | Implementa la API v3 de Brevo. `BREVO_API_KEY` se lee en settings pero ningún setting lo referencia. |
| `email_backend.py` (`IPv4EmailBackend`) | Huérfano | SMTP con monkeypatch temporal de `socket.getaddrinfo` para forzar IPv4 sobre el host SMTP. Vestigio de la etapa Gmail. |

En `DEBUG` el backend es la consola (`settings.py:384-385`).

#### `torneos/social.py` — placa de campeones para Open Graph

Distinta de la placa 9:16 con `html2canvas`. Genera una URL de Cloudinary con **overlays de texto sobre la foto de campeones** que sube el organizador: canvas 1080×1080 `fill/center`, `brightness:-35`, "CAMPEONES" en `#10b981` arriba, la pareja campeona centrada, el nombre del torneo abajo y la marca "TodoPadel". Diseño defensivo: devuelve `None` si el torneo no está finalizado, si falta foto o ganador, o si el storage por defecto no es Cloudinary — los llamadores caen a la foto cruda o a la imagen OG genérica.

### A.9 Endpoints "escotilla" (operativos, peligrosos)

Dos vistas permiten disparar operaciones destructivas desde el navegador, **ambas por GET, sin CSRF ni confirmación**:

| Ruta | Vista | Guardia | Qué hace |
| :--- | :--- | :--- | :--- |
| `/trigger-migration/` | `core/views.py:146` | `request.user.is_superuser` (si no, 401 texto plano) | Ejecuta `call_command('migrar_rankings_historicos')` contra la base de producción y devuelve el resultado como HTML. |
| `/torneos/admin/crear-torneo-prueba/` | `torneos/views.py:2332` | `tipo_usuario == 'ADMIN'` | **Borra** todos los `Torneo` cuyo nombre empieza con `"Torneo 24 Equipos"` y **todos los usuarios con email que contenga `@ejemplo.com`**, y crea un torneo de prueba de 24 equipos. |

Existen porque el free tier de Render hace incómodo el shell. Deberían moverse a POST con confirmación, o quedar detrás de un flag de entorno.

**Quirk relacionado:** `torneos/urls.py` termina con `from django.shortcuts import redirect` **después** de `urlpatterns`, y la ruta base `/torneos/` es un lambda inline (`path('', lambda r: redirect('torneos:abierto_list'), name='base_redirect')`). Funciona sólo porque el lambda se evalúa en runtime, no al importar el módulo.

### A.10 Management commands: notas que faltan

Más allá del inventario de los 8 comandos de seeding/simulación/reparación:

- **`reparar_rankings`** es el único que corre en cada deploy (última línea útil de `build.sh`): fusiona parejas duplicadas por par `(jugador1, jugador2)` y recalcula rankings en BD.
- **`migrar_rankings_historicos`** es un command **no idiomático**: llama `django.setup()` en el import del módulo y decora `handle()` con `@patch('django.core.cache.cache.get')` / `cache.set` de `unittest.mock` para forzar el recálculo sin caché. `build.sh` lo aclara con un comentario: *"es un script puntual, NO debe correr en cada deploy"*.
- **`test_rankings_performance`** (app `equipos`) no es un test: instrumenta `RankingListView` con `RequestFactory`, limpia la caché y mide queries/tiempo con y sin caché.

### A.11 La migración `unaccent`

`core/migrations/0001_unaccent_extension.py` no tiene dependencias y ejecuta `UnaccentExtension()` (`CREATE EXTENSION unaccent`). Consecuencias:

- Es **no-op en SQLite** (Django saltea `CreateExtension` si el vendor no es postgresql), por eso corre sin ruido en local.
- En Postgres **requiere permisos para crear extensiones** en la base destino. Es la razón de que `django.contrib.postgres` esté en `INSTALLED_APPS`.
- La búsqueda global se adapta en runtime vía `core/utils.py:is_postgres()` (`connection.vendor == 'postgresql'`) y `get_smart_filter(field, valor, use_unaccent)`: con Postgres usa `__unaccent__icontains`, en SQLite cae a `icontains` común. **Los tests corren sobre SQLite, así que la rama unaccent nunca se ejercita en la suite.**

### A.12 Toolchain de Tailwind

Hay **dos `package.json` con versiones contradictorias**:

| Archivo | Contenido | Estado |
| :--- | :--- | :--- |
| `theme/static_src/package.json` | `tailwindcss ^3.4.17`, script `build` → `tailwindcss -i ./src/styles.css -o ../static/css/tailwind.css --minify` | **El real**: es el que usa `manage.py tailwind install/build` |
| `theme/package.json` | `tailwindcss ^4.1.17`, `autoprefixer`, `postcss`, `cross-env` | Residual, no usado. Confunde: sugiere Tailwind v4 |

`theme/static_src/tailwind.config.js`: `content` con globs relativos (`../../core/**/*.{html,py}`, `../../accounts/...`, `../../equipos/...`, `../../torneos/...`, `../../padel_project/**/*.py`, `../../theme/templates/**/*.html`, `../../templates/**/*.html`), `darkMode: 'class'`, fuente `Inter`, `primary: '#10b981'`. **Si se agrega una app nueva hay que sumarla al `content` o sus clases se purgan.** DaisyUI sigue llegando por CDN, fuera de esta compilación.

### A.13 Convenciones de git

| Convención | Detalle |
| :--- | :--- |
| **Rama de trabajo** | `main`. Render despliega desde `main`. |
| ⚠️ **`master` es una trampa** | `origin/HEAD -> origin/master`, pero `master` tiene 2 commits (`Initial commit`, `Restaurar código completo`) y está **521 commits detrás de `main`**. Un `git clone` limpio checkoutea un snapshot arqueológico. Corregir con `git remote set-head origin main` o repointar el default branch en GitHub. |
| **Ramas de feature** | `feat/<slug>` y `fix/<slug>`, con el ticket cuando existe: `feat/TP-01a-share-buttons`, `feat/formatos-fap`, `fix/vivo-mobile`. Quedaron 10 ramas locales ya mergeadas a `main` sin borrar. |
| **Commits** | Conventional commits **en castellano**, con scope. El scope suele ser el ticket del backlog o el área: `feat(TP-11): notificaciones push reales (Web Push + VAPID)`, `feat(formatos): cruces manuales para cualquier cantidad de parejas (byes)`, `fix(placas): abrir el selector de redes en mobile`. |
| **Hooks** | Ninguno propio: `.git/hooks/` sólo tiene los `.sample` de git. |
| **Remote** | `https://github.com/EmanuelGBolig/padel_project_web.git` |

### A.14 Calidad y automatización: lo que NO existe

Vale documentarlo explícitamente porque su ausencia es una decisión de facto:

- **Sin CI**: no hay `.github/workflows/` ni ningún otro pipeline. Nada corre los tests salvo a mano.
- **`build.sh` no corre tests** antes de migrar y publicar.
- **Sin linter ni formateador configurado**: `pylint` e `isort` están instalados pero no hay `pyproject.toml`, `setup.cfg`, `.pylintrc`, `.flake8` ni `.isort.cfg`. No hay `black`/`ruff`.
- **Sin `.editorconfig`** — relevante en un repo que mezcla archivos UTF-8 y UTF-16, LF y CRLF.
- **Sin `pytest.ini`/`tox.ini`**: los tests son `unittest` de Django, en un único `tests.py` por app (`torneos/tests.py` 1336 líneas, `accounts/tests.py` 547, `core/tests.py` 73, `equipos/tests.py` 49).
- **Sin `.pre-commit-config.yaml`** ni hooks propios.

### A.15 Documentación de usuario existente

| Archivo | Contenido | Estado |
| :--- | :--- | :--- |
| `docs/MANUAL.md` | Manual de usuario (público / jugador / organizador) | **Roto**: referencia `images/*.png` que no existen — `docs/` sólo contiene el `.md` |
| `manual_organizador.md` + `manual_organizador.pdf` | Manual del organizador, más completo y actual (organización, sponsors, torneos, resultados) | Vigente. Menciona la verificación por código de 6 dígitos, que hoy es vestigial |
| `manual_images/` | 8 screenshots mobile reales (`real_mobile_*.png`) | Insumo del PDF |
| `capture_screens.py` | Script Playwright que genera esos screenshots | **No reproducible**: apunta a `http://127.0.0.1:8000`, con credenciales hardcodeadas (`test@example.com` / `password123`) y `ARTIFACTS_DIR` a una carpeta local de otra herramienta (`C:\Users\egome\.gemini\antigravity\brain\<uuid>`). Además `playwright` no está en `requirements.txt` |
| `deployment_guide.md` | Guía manual de despliegue en Render free tier | Vigente pero incompleta: la tabla de env vars repite `DEBUG` y omite `CUSTOM_DOMAIN`, `VAPID_*`, `GOOGLE_CLIENT_*`, `RESEND_API_KEY` |
| `render.yaml.disabled` | Blueprint de Render | Deshabilitado a propósito (el Blueprint tiene costo); el servicio se configura a mano |

### A.16 Localización, logging y observabilidad

- **Localización**: `LANGUAGE_CODE = 'es-ar'`, `TIME_ZONE = 'America/Argentina/Buenos_Aires'`, `USE_TZ = True`, `USE_I18N = True` — pero **no hay catálogos `locale/` ni uso de `gettext`**. Todo el copy está escrito directo en castellano rioplatense en templates, formularios y `messages`. Convención: se escribe en español, sin `{% trans %}`.
- **Logging**: sólo consola (`root` en INFO, `django.request` en ERROR, formatter `verbose` con `{levelname} {asctime} {module} {message}`). Además hay `print()` en código de producción: `settings.py` imprime la configuración de Cloudinary/storage al arrancar, y `resend_backend.py` imprime destinatario y respuesta completa de la API.
- **Observabilidad**: sin Sentry, sin métricas, **sin endpoint de health check**. Los logs de Render son la única fuente. El free tier duerme el servicio, así que el primer request después de inactividad tarda decenas de segundos.

### A.17 Checklist de higiene pendiente

1. Rotar la contraseña de Supabase de `loader.py:6` y sacarla del repo (está en el historial de git).
2. Sacar la contraseña por defecto de `scripts/create_initial_superuser.py:19` y exigir `DJANGO_SUPERUSER_PASSWORD`.
3. Repointar el default branch del remote a `main` (`git remote set-head origin main` + settings de GitHub).
4. Reescribir `requirements.txt` en UTF-8 y podar las dependencias no usadas; agregar `playwright` si `capture_screens.py` se conserva.
5. Agregar `staticfiles/` y `perfiles/` a `.gitignore` y purgarlos del índice (`git rm -r --cached`).
6. Mover a `scripts/legacy/` (o borrar) los ~40 scripts de debug de la raíz y los `.txt` de salida; en particular renombrar los tres `test_*.py` de raíz para que no interfieran con el discovery.
7. Crear `README.md` con A.2 + A.3, y `.env.example` con la tabla de A.3 (o activar `python-dotenv`, que ya está instalado).
8. Convertir `/trigger-migration/` y `/torneos/admin/crear-torneo-prueba/` a POST con confirmación, o esconderlos detrás de un flag de entorno.
9. Borrar `theme/package.json` (Tailwind v4 fantasma) y `theme/templates/base.html.backup`.
10. Regenerar o borrar `docs/MANUAL.md` (sus imágenes no existen) y unificar con `manual_organizador.md`.
