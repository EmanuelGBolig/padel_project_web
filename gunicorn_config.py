# Gunicorn configuration file
# https://docs.gunicorn.org/en/stable/settings.html

# Timeout for worker processes (in seconds)
# Aumentado a 120 segundos para permitir procesamiento de imágenes
timeout = 120

# Worker class
worker_class = 'sync'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
