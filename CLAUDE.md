# CLAUDE.md — Instrucciones para trabajar en TodoPadel

## 🔴 Al iniciar cada sesión, hacé esto primero

1. **Leé este archivo completo.**
2. **Leé [`ARQUITECTURA.md`](ARQUITECTURA.md)** — al menos el índice y el "Mapa mental en 30 segundos".
   Antes de tocar un subsistema, leé su sección entera. No adivines cómo funciona algo que ya está
   documentado ahí.
3. Si vas a trabajar sobre torneos (el subsistema más complejo), leé además la sección
   **"Subsistema de torneos"** completa: la generación de la llave tiene mucha lógica no obvia
   (byes, play-in, placeholders, formatos FAP vs personalizados).

## 🔄 Mantener la documentación al día — OBLIGATORIO

**`ARQUITECTURA.md` es la fuente de verdad del proyecto y tiene que reflejar el código real.**

Cada vez que hagas un cambio que altere algo documentado, **actualizá `ARQUITECTURA.md` en el mismo
commit**, sin que el usuario tenga que pedírtelo. Concretamente:

| Si cambiás… | Actualizá en `ARQUITECTURA.md` |
|---|---|
| Un modelo, campo o migración | Sección **Modelo de datos** (tabla de campos + diagrama mermaid si cambian relaciones) |
| Una vista, URL o permiso | La tabla de vistas del subsistema correspondiente |
| La lógica de zonas o de la llave | Sección **Subsistema de torneos** |
| Roles, mixins o reglas de acceso | Sección **Subsistema de cuentas** |
| Un template o página nueva | El **inventario de templates** en la sección Frontend |
| `settings.py` o una variable de entorno | Sección **Infraestructura** (inventario de variables) |
| Un management command o script | **Anexo: entorno, tooling y convenciones** |

Reglas:
- Si agregás una **función nueva**, documentala. Si **borrás** algo, sacalo del documento.
- Actualizá también la fecha de "Última auditoría completa" del encabezado si hiciste una revisión amplia.
- Si el cambio es grande y también afecta cómo se instala o se usa el proyecto, actualizá `README.md`.
- **No dupliques** información entre archivos: `README.md` es la puerta de entrada (breve),
  `ARQUITECTURA.md` es el detalle exhaustivo, `CLAUDE.md` (este archivo) son las reglas de trabajo.

---

## Flujo de trabajo en este repo

1. Trabajar en una **rama de feature** (`feat/…`, `fix/…`), nunca commitear directo a `main`.
2. Antes de mergear, correr **siempre**:
   ```bash
   python manage.py makemigrations --check --dry-run
   python manage.py check
   python manage.py test
   ```
3. Mergear a `main` con `git merge --ff-only`.
4. **⚠️ NUNCA pushear sin confirmación explícita del usuario.** Cada push a `main` dispara un deploy
   en Render que va a producción con usuarios reales. Preguntá siempre antes.

### Commits

Formato `tipo(scope): descripción en español`, cuerpo explicando el *por qué*. Terminar con:

```
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

## Trampas conocidas (leer antes de perder una hora)

### Layout mobile: las reglas están en el CSS, no en los templates
La app se usa casi toda desde el celular. Las convenciones de botones, íconos y
paneles viven **una sola vez** en `theme/static_src/src/styles.css` (ver la sección
"Convenciones de UI en mobile" de `ARQUITECTURA.md`). Antes de agregar clases
sueltas a un template, fijate si la regla global ya lo cubre.

Tres errores que ya cometimos:
- Grilla con `md:grid-cols-2` **sin** `grid-cols-1`: en mobile no tiene columnas
  declaradas, se dimensiona al contenido y desborda la pantalla.
- `w-full` dentro de una fila flex: es el 100% del contenedor y, con algo al lado,
  se pasa. Va `flex-1 min-w-0`.
- Un `.collapse` de DaisyUI es un grid cuya columna se estira al contenido: hay
  que fijarla en `minmax(0, 1fr)` o corta lo que tenga a la derecha.

Después de tocar layout, verificá con:
```bash
python verificar_mobile.py
python auditoria_ui.py
```

### `runserver --noreload` no recarga los templates
Django usa el **cached loader** aunque `DEBUG=True`; lo que normalmente refresca
un template editado es el autoreloader, no el loader. Con `--noreload` (que es
como conviene levantarlo para verificar con Playwright) los cambios de template
**no se ven hasta reiniciar el server**. Ya perdimos un rato buscando por qué un
`print:hidden` "no aplicaba" cuando en el archivo estaba.

### Los comentarios `{# #}` de Django son de UNA línea
Escritos en varias, Django **no los interpreta** y los manda al HTML como texto
visible. Ya pasó en producción. Para varias líneas: `{% comment %}…{% endcomment %}`.
El test `core.tests.ComentariosDeTemplateTests` recorre los templates y falla si
vuelve a aparecer.

### CSS: DaisyUI usa **oklch**, no hsl
Las variables de tema son tripletes sin función envolvente (`--p: 72% 0.16 163`). Siempre:
```css
color: oklch(var(--p));                 /* ✅ */
background: oklch(var(--bc) / 0.2);     /* ✅ opacidad con slash adentro */
color: hsl(var(--p));                   /* ❌ rompe: es convención de DaisyUI 3 */
```
Copiar snippets de DaisyUI 3 de internet **rompe los colores en silencio**.

### El caché es `DatabaseCache`
Sin `python manage.py createcachetable` varias vistas fallan. Va en el setup y en `build.sh`.

### La suite de tests tarda ~7 minutos
221 tests. Mientras iterás, corré solo la clase que tocaste
(`python manage.py test torneos.tests.NombreDeLaClase`) y dejá la suite completa para antes de mergear.

### `requirements.txt` está en UTF-16 LE con BOM
`pip` lo lee bien, pero `grep`/`diff` lo muestran como basura. Si lo reescribís, **pasalo a UTF-8**.

### No escribir tests con heredoc
Los `\n` dentro de strings se convierten en saltos reales y rompen el archivo. Usá la herramienta
`Edit` para agregar tests, no `cat >> archivo << 'EOF'`.

### Hay ~40 scripts sueltos de debug en la raíz
`debug_*.py`, `verify_*.py`, `check_*.py`, `simulate_*.py`… **corren contra la base de datos real de
desarrollo y borran datos por patrón**. No los ejecutes salvo que sepas exactamente qué hacen.
Tres de ellos (`test_7_teams.py`, `test_12_teams.py`, `test_invitation_flow.py`) matchean el patrón
de descubrimiento de tests; si el discovery se comporta raro, acotá la corrida:
```bash
python manage.py test accounts core equipos torneos
```

### Datos sensibles versionados
Hay archivos `backup_*.json` con dumps de producción (usuarios reales, emails, teléfonos, hashes de
contraseña) commiteados en el repo. **No los uses ni los repliques**, y si vas a tocar el tema de
backups, avisá primero al usuario.

---

## Convenciones del proyecto

- **Idioma**: todo lo que ve el usuario va en **español rioplatense** ("vos", "cargá", "fijate").
  Los nombres de modelos, campos y funciones también están en español (`Torneo`, `equipos_por_grupo`,
  `generar_octavos_logica`). Mantené esa consistencia.
- **Permisos**: los mixins están duplicados entre apps y **no significan lo mismo**
  (`equipos.AdminRequiredMixin` excluye a `ORGANIZER`, `torneos.AdminRequiredMixin` lo incluye).
  Verificá cuál estás importando. Ver la tabla completa en `ARQUITECTURA.md`.
- **Scoping por organización**: se hace **dentro** de la vista, no en el mixin. Patrón:
  ```python
  if not user.is_staff and user.tipo_usuario == 'ORGANIZER':
      qs = qs.filter(organizacion=user.organizacion)
  ```
  Si agregás una vista de gestión, **no te olvides de este filtro** o exponés datos de otros clubes.
- **Migraciones**: siempre `makemigrations --check` antes de mergear. El deploy corre `migrate`
  automáticamente.

---

## Dónde está cada cosa

| Necesito tocar… | Voy a… |
|---|---|
| Generación de zonas o de la llave | `torneos/views.py` (`AdminTorneoManageView`) |
| Cuadros oficiales FAP | `torneos/formats.py` |
| Tabla de posiciones | `torneos/signals.py` (se recalcula por signal) |
| Avance de ganadores en el bracket | `torneos/models.py` → `Partido.save()` |
| Estadísticas, ranking, fusión de cuentas | `accounts/utils.py` |
| Navbar, tema, estilos globales | `theme/templates/base.html` |
| Home | `core/views.py` + `core/templates/core/home.html` |

---

## Contexto de producto

- Los usuarios son **jugadores amateur argentinos** y **organizadores de club**, en su mayoría poco
  técnicos, y **entran casi siempre desde el celular**. Priorizá mobile y lenguaje claro.
- Los organizadores usan la app **al borde de la cancha**, cargando resultados entre partidos: los
  flujos de carga tienen que ser rápidos y difíciles de equivocar.
- La app es una **PWA instalable** y manda **notificaciones push**; tenelo en cuenta al agregar features.
