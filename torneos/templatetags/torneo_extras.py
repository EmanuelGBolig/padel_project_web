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
        return "TBD"
        
    return equipo.nombre
