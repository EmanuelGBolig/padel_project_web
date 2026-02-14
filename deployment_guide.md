# Guía de Despliegue Manual en Render (Opción Gratuita)

Para evitar los costos del Blueprint, vamos a crear el servicio web y la base de datos manualmente usando el **Free Tier** de Render.

## 1. Crear la Base de Datos (PostgreSQL)

1.  En tu Dashboard de Render, haz clic en **New +** y selecciona **PostgreSQL**.
2.  Ponle un nombre (ej. `padel-db`).
3.  **Importante**: En "Instance Type", selecciona **Free**.
4.  Haz clic en **Create Database**.
5.  Espera a que se cree. Una vez lista, busca la sección **"Internal Database URL"** y cópiala. La necesitarás enseguida.

## 2. Crear el Servicio Web

1.  Haz clic en **New +** y selecciona **Web Service**.
2.  Conecta tu repositorio `padel_project_web`.
3.  Configura los siguientes campos:
    *   **Name**: `padel-project` (o lo que gustes).
    *   **Region**: La misma que tu base de datos (ej. Oregon).
    *   **Branch**: `main`.
    *   **Runtime**: `Python 3`.
    *   **Build Command**: `./build.sh`
    *   **Start Command**: `gunicorn padel_project.wsgi:application`
    *   **Instance Type**: Selecciona **Free**.

## 3. Configurar Variables de Entorno

Antes de darle a crear (o en la pestaña "Environment" si ya lo creaste), añade estas variables:

| Key | Value |
| :--- | :--- |
| `DATABASE_URL` | *(Pega aquí la "Internal Database URL" que copiaste en el paso 1)* |
| `SECRET_KEY` | *(Inventa una clave larga y segura, ej: `django-insecure-...`)* |
| `DEBUG` | `False` |
| `DEBUG` | `False` |
| `PYTHON_VERSION` | `3.11.9` (Recomendado para asegurar compatibilidad) |
| `CLOUDINARY_URL` | *(Copia `API Environment variable` del Dashboard de Cloudinary)* |
| `CLOUDINARY_CLOUD_NAME` | *(Opcional si usas URL, pero bueno tener)* |
| `CLOUDINARY_API_KEY` | *(Opcional si usas URL)* |
| `CLOUDINARY_API_SECRET` | *(Opcional si usas URL)* |

## 4. Finalizar

1.  Haz clic en **Create Web Service**.
2.  Render empezará a descargar tu código, instalar dependencias y ejecutar el script `build.sh`.
3.  Si todo va bien, verás un mensaje de "Live" y podrás acceder a tu web desde la URL que te da Render (ej. `https://padel-project.onrender.com`).

## 5. Crear Superusuario

Una vez desplegado, la base de datos estará vacía. Para entrar al admin:

1.  Ve a la pestaña **Shell** de tu Web Service en Render.
2.  Ejecuta: `python manage.py createsuperuser`
3.  Sigue las instrucciones para crear tu usuario admin.
