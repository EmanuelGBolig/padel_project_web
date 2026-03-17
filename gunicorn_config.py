# Gunicorn configuration file
# https://docs.gunicorn.org/en/stable/settings.html

# Timeout for worker processes (in seconds)
# 120 segundos para permitir procesamiento de imágenes y envío de emails
timeout = 120

# Workers and threads
workers = 2
threads = 4

# Worker class - gthread supports concurrent requests via threads
worker_class = 'gthread'

# Logging
accesslog = '-'
errorlog = '-'
loglevel = 'info'
