# scripts/legacy — bisturíes de sesiones puntuales

Estos archivos estaban sueltos en la raíz del repo. **No son tests ni herramientas
de uso corriente**: son scripts de una sesión de debugging concreta, ya resuelta.

## ⚠️ Antes de correr cualquiera de estos

1. **Corren contra la base de datos de desarrollo real** (la que apunte
   `DJANGO_SETTINGS_MODULE`), no contra una base de test.
2. **Varios borran datos por patrón**, por ejemplo:
   ```python
   Torneo.objects.filter(nombre="Torneo Test 7").delete()
   ```
3. Varios tienen **IDs de torneo hardcodeados** de la sesión en que se escribieron.

Leelos enteros antes de ejecutarlos. Si necesitás datos de prueba, usá los
management commands, que sí están pensados para eso:

```bash
python manage.py seed_dev_data
python manage.py create_test_tournament
python manage.py crear_torneo_24
```

## Por qué se movieron acá

Tres de ellos (`test_7_teams.py`, `test_12_teams.py`, `test_invitation_flow.py`)
matcheaban el patrón `test*.py` del descubridor de `manage.py test` y se
importaban durante el discovery, ejecutando su `django.setup()`. Moverlos fuera
de la raíz evita ese efecto y deja la raíz del repo legible.
