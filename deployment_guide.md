# Guía de Despliegue en Render

He preparado tu proyecto para ser desplegado en Render. Aquí tienes los pasos que debes seguir:

## 1. Archivos Creados/Modificados

*   **`render.yaml`**: Este archivo define tu servicio web y la base de datos PostgreSQL. Render lo usará para configurar todo automáticamente (Blueprint).
*   **`build.sh`**: Este script se ejecuta durante el despliegue. Instala dependencias, compila Tailwind CSS, recolecta archivos estáticos y ejecuta migraciones.
*   **`padel_project/settings.py`**: Se ha actualizado para detectar automáticamente si está en Windows o Linux (Render) para la configuración de `npm`.

## 2. Pasos para Desplegar

1.  **Subir a GitHub**:
    Asegúrate de hacer commit y push de todos los cambios, incluyendo los nuevos archivos `render.yaml` y `build.sh`.
    ```bash
    git add .
    git commit -m "Preparar para deploy en Render"
    git push origin main
    ```

2.  **Crear Blueprint en Render**:
    *   Ve a tu dashboard de [Render](https://dashboard.render.com/).
    *   Haz clic en **New +** y selecciona **Blueprint**.
    *   Conecta tu repositorio de GitHub.
    *   Render detectará el archivo `render.yaml`.
    *   Dale un nombre al servicio (ej. `padel-project`).
    *   Haz clic en **Apply**.

3.  **Verificar el Despliegue**:
    Render comenzará a construir tu aplicación. Puedes ver el progreso en la pestaña "Logs".
    Si todo sale bien, tu aplicación estará en línea en unos minutos.

## Notas Importantes

*   **Base de Datos**: Se creará una base de datos PostgreSQL automáticamente. Los datos de tu SQLite local **NO** se subirán. Tendrás una base de datos vacía en producción.
*   **Superusuario**: Necesitarás crear un superusuario en la base de datos de producción para acceder al admin. Puedes hacerlo desde la "Shell" en el dashboard de Render:
    ```bash
    python manage.py createsuperuser
    ```
*   **Debug**: `DEBUG` está configurado en `False` para producción. Si tienes errores, revisa los logs en Render.
