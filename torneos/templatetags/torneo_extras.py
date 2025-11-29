from django import template
from torneos.models import EquipoGrupo

register = template.Library()

@register.simple_tag
def get_team_code(equipo, torneo):
    """
    Devuelve el nombre del equipo.
    Anteriormente devolvía un código (Ej: "A1"), pero se cambió a nombre completo.
    """
    if not equipo:
        return ""
    return equipo.nombre

@register.simple_tag
def get_team_info(equipo, torneo):
    """
    Devuelve un diccionario con el nombre del equipo.
    Retorna: {'code': 'Gomez/Perez', 'name': 'Gomez/Perez'}
    Mantenemos la estructura de diccionario para compatibilidad con templates.
    """
    if not equipo:
        return {'code': '', 'name': ''}
    
    return {'code': equipo.nombre, 'name': equipo.nombre}

@register.filter
def split(value, delimiter=','):
    """
    Divide un string por el delimitador especificado.
    Uso: {{ "a,b,c"|split:"," }}
    """
    if not value:
        return []
    return [item.strip() for item in value.split(delimiter)]


@register.simple_tag
def get_team_display(equipo, torneo):
    """
    Devuelve el nombre del equipo.
    """
    if not equipo:
        return "Esperando resultados"
        
    return equipo.nombre

@register.filter
def batch(value, batch_size):
    """
    Divide una lista en sublistas de tamaño batch_size.
    """
    if not value:
        return []
    try:
        batch_size = int(batch_size)
        result = []
        for i in range(0, len(value), batch_size):
            result.append(value[i:i + batch_size])
        return result
    except (ValueError, TypeError):
        return value

@register.simple_tag
def nombre_ronda_dinamico(ronda_num, total_rondas):
    """
    Calcula el nombre de la ronda basado en la distancia a la final.
    total_rondas es el número máximo de rondas en el torneo.
    """
    try:
        ronda_num = int(ronda_num)
        total_rondas = int(total_rondas)
    except (ValueError, TypeError):
        return f"Ronda {ronda_num}"

    diff = total_rondas - ronda_num

    if diff == 0:
        return 'Final'
    elif diff == 1:
        return 'Semifinal'
    elif diff == 2:
        return 'Cuartos'
    elif diff == 3:
        return 'Octavos'
    elif diff == 4:
        return '16vos'
    else:
        return f"Ronda {ronda_num}"

@register.filter
def short_name(value, max_length=20):
    """
    Trunca el nombre si excede max_length.
    Ej: "Gomez/Perez" -> "Gomez/Perez" (si < 20)
    Ej: "Test8_12345_1/Test8_12345_1" -> "Test8_12345_1/Test..."
    """
    if len(str(value)) > max_length:
        return str(value)[:max_length] + "..."
    return str(value)
