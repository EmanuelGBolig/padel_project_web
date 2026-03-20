import re
from django.db.models import Q
from django.db import connection
from dateutil import parser
from django.utils import timezone

def normalize_query(query):
    """Elimina acentos y caracteres especiales básicos de una cadena."""
    if not query:
        return ""
    import unicodedata
    # Normalización NFKD descompone caracteres (ej: á -> a + ´)
    # Luego filtramos los caracteres que no son de combinación (Mn)
    return "".join(
        c for c in unicodedata.normalize('NFKD', query)
        if unicodedata.category(c) != 'Mn'
    ).lower()

def extract_dates(query):
    """
    Intenta extraer fechas de la consulta de búsqueda.
    Ejemplos: '19/03', '19 de marzo', '2026-03-19'
    """
    if not query:
        return []
    
    dates = []
    # Regex para fechas simples (dd/mm, dd-mm, dd/mm/aaaa, etc.)
    # Buscamos patrones como 19/03, 19-03, 19/03/2026
    date_patterns = [
        r'(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?',
    ]
    
    for pattern in date_patterns:
        matches = re.finditer(pattern, query)
        for match in matches:
            try:
                # Intentamos parsear con dateutil
                d_str = match.group(0)
                parsed_date = parser.parse(d_str, dayfirst=True)
                # Si no tiene año, asumimos el año actual
                if len(match.groups()) < 3 or not match.group(3):
                    parsed_date = parsed_date.replace(year=timezone.now().year)
                dates.append(parsed_date.date())
            except (ValueError, OverflowError):
                continue
    
    # También buscar meses por nombre (español básico)
    meses = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
        'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    for mes_name, mes_num in meses.items():
        if mes_name in query.lower():
            # Buscar un número cerca del mes (ej: '19 de marzo')
            day_match = re.search(r'(\d{1,2})\s+(?:de\s+)?' + mes_name, query.lower())
            if day_match:
                try:
                    day = int(day_match.group(1))
                    dates.append(timezone.now().replace(month=mes_num, day=day).date())
                except ValueError:
                    pass
            else:
                # Solo el mes: buscar todos los torneos de ese mes? 
                # Por ahora solo guardamos el primer día del mes como referencia
                pass

    return list(set(dates))

def get_smart_filter(field_name, value, use_unaccent=False):
    """
    Crea un objeto Q inteligente que usa unaccent si está disponible.
    """
    if use_unaccent:
        return Q(**{f"{field_name}__unaccent__icontains": value})
    return Q(**{f"{field_name}__icontains": value})

def is_postgres():
    """Verifica si la base de datos actual es PostgreSQL."""
    return connection.vendor == 'postgresql'
