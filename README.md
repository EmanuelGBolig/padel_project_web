# 🎾 TodoPadel

Plataforma web para **organizar y seguir torneos de pádel**. Los clubes crean el torneo, los
jugadores se inscriben en parejas, y la app arma las zonas, calcula las tablas de posiciones y genera
la llave de la fase final siguiendo los **cuadros oficiales de la Federación Argentina de Pádel**.

**En producción:** [todopadel.club](https://todopadel.club)

---

## Qué hace

| Para el jugador | Para el organizador |
|---|---|
| Se registra y arma su pareja invitando a un compañero | Crea torneos con cupos, división, categoría y fecha |
| Se inscribe a torneos de su división | Arma las zonas automáticamente al iniciar el torneo |
| Sigue los resultados y la llave en vivo | Carga resultados set por set (con W.O. y abandono) |
| Ve su historial, estadísticas y ranking | Genera la fase eliminatoria con la llave oficial FAP |
| Recibe notificaciones push de nuevos torneos | Programa horarios y canchas de cada partido |
| Comparte placas de resultados para redes | Diseña formatos propios y define los cruces a mano |
| Instala la app en el celular (PWA) | Ve métricas en el panel del organizador |

Además: circuitos (rankings multi-torneo), formato **Americano/Mexicano**, perfiles públicos
compartibles, buscador de compañero, y gestión de jugadores sin cuenta ("dummies") con fusión
posterior a cuentas reales.

---

## Stack

- **Backend:** Django 5.2.8 · Python 3.11
- **Base de datos:** PostgreSQL en producción, SQLite en local (se elige solo según `DATABASE_URL`)
- **Frontend:** Tailwind CSS vía `django-tailwind` + **DaisyUI 4.7.2** (tema `corporate` sobrescrito en oscuro)
- **Estáticos:** WhiteNoise con manifest + compresión · **Media:** Cloudinary en prod, filesystem en local
- **Auth:** login por email + Google OAuth2 (`social-auth-app-django`)
- **Push:** `pywebpush` con claves VAPID · **PWA:** manifest + service worker
- **Deploy:** Render (`build.sh` + `Procfile` con Gunicorn)

---

## Puesta en marcha (local)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createcachetable
python scripts/seed_divisions.py
python manage.py createsuperuser
python manage.py runserver
```

> ⚠️ `createcachetable` **no es opcional**: el caché del proyecto es `DatabaseCache`, y sin esa tabla
> varias vistas fallan.

Para compilar los estilos (en otra terminal):

```bash
python manage.py tailwind start
```

### Datos de prueba

```bash
python manage.py seed_dev_data
python manage.py create_test_tournament
```

---

## Tests

```bash
python manage.py test
```

124 tests, tarda unos **7 minutos**. Para iterar rápido, correr solo la app o la clase que tocaste:

```bash
python manage.py test torneos.tests.CrucesManualesTests
```

---

## Estructura del repo

```
padel_project/     Configuración Django (settings, urls, wsgi, sitemaps)
├── core/          Home, búsqueda global, landing de organizadores, PWA
├── accounts/      Usuarios, roles, divisiones, organizaciones, sponsors, push
├── equipos/       Parejas, invitaciones, ranking por jugador, busco-compañero
├── torneos/       Torneos, zonas, llaves, circuitos, americano  ← el núcleo
├── theme/         App de django-tailwind + base.html
├── templates/     Templates globales (PWA, password reset, robots)
├── scripts/       Scripts que corren en el deploy
└── docs/          Manuales de usuario
```

Los archivos de mayor peso: [`torneos/views.py`](torneos/views.py) (2.700 líneas, toda la gestión del
torneo), [`torneos/formats.py`](torneos/formats.py) (llaves oficiales FAP) y
[`accounts/utils.py`](accounts/utils.py) (estadísticas, ranking y fusión de cuentas).

---

## Roles de usuario

| Rol | Cómo se crea | Alcance |
|---|---|---|
| `PLAYER` | Registro público o Google | Su perfil, su pareja, inscripciones, rankings |
| `ORGANIZER` | Solo desde el admin de Django | Gestión completa **de su organización** |
| `ADMIN` | `createsuperuser` o admin | Todo, sin filtro de organización |

---

## Deploy

Render corre [`build.sh`](build.sh) en cada push a `main`: instala dependencias, compila Tailwind,
junta estáticos, migra, crea la tabla de caché y siembra divisiones.

Variables de entorno obligatorias en producción: `SECRET_KEY`, `DATABASE_URL`, `RENDER_EXTERNAL_HOSTNAME`.
Opcionales pero recomendadas: `CLOUDINARY_URL` (imágenes), `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY`
(notificaciones push), `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD`, `GOOGLE_OAUTH2_KEY` / `GOOGLE_OAUTH2_SECRET`.

El inventario completo de variables está en [`ARQUITECTURA.md`](ARQUITECTURA.md).

---

## Documentación

| Archivo | Para qué sirve |
|---|---|
| [`ARQUITECTURA.md`](ARQUITECTURA.md) | **Referencia técnica completa**: modelo de datos, cada vista, cada template, settings, convenciones |
| [`CLAUDE.md`](CLAUDE.md) | Instrucciones para trabajar con Claude Code en este repo |
| [`docs/MANUAL.md`](docs/MANUAL.md) | Manual de uso |
| [`manual_organizador.md`](manual_organizador.md) | Guía paso a paso para organizadores |
| [`deployment_guide.md`](deployment_guide.md) | Notas de deploy |
