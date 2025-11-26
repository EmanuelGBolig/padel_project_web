from django import template
from torneos.models import EquipoGrupo

register = template.Library()

@register.simple_tag
def get_team_code(equipo, torneo):
    """
    Devuelve el código del equipo en el torneo (Ej: "A1", "B2").
    Si no se encuentra o no tiene grupo asignado, devuelve el nombre del equipo.
    """
    if not equipo or not torneo:
        return ""
    
    # Buscar en qué grupo está el equipo dentro de este torneo
    try:
        equipo_grupo = EquipoGrupo.objects.filter(
            grupo__torneo=torneo, 
            equipo=equipo
        ).select_related('grupo').first()
        
        if equipo_grupo:
            # Extraer la letra del grupo (Asumiendo formato "Grupo A")
            nombre_grupo = equipo_grupo.grupo.nombre
            letra_grupo = nombre_grupo.replace("Grupo ", "").strip()
            
            # Obtener el número asignado
            numero = equipo_grupo.numero
            
            if letra_grupo and numero:
                return f"{letra_grupo}{numero}"
                
    except Exception:
        pass
        
    return equipo.nombre

@register.simple_tag
def get_team_info(equipo, torneo):
    """
    Devuelve un diccionario con el código y nombre del equipo.
    Retorna: {'code': 'A1', 'name': 'Gomez/Perez'}
    """
    if not equipo or not torneo:
        return {'code': '', 'name': ''}
    
    code = ''
    try:
        equipo_grupo = EquipoGrupo.objects.filter(
            grupo__torneo=torneo, 
            equipo=equipo
        ).select_related('grupo').first()
        
        if equipo_grupo:
            nombre_grupo = equipo_grupo.grupo.nombre
            letra_grupo = nombre_grupo.replace("Grupo ", "").strip()
            numero = equipo_grupo.numero
            
            if letra_grupo and numero:
                code = f"{letra_grupo}{numero}"
    except Exception:
        pass
    
    if not code:
        code = equipo.nombre
    
    return {'code': code, 'name': equipo.nombre}

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
    Devuelve el string formateado "CODIGO Nombre" (Ej: "A1 Perez/Gomez").
    """
    if not equipo or not torneo:
        return "TBD"
    
    code = get_team_code(equipo, torneo)
    # Si el codigo es igual al nombre (no tiene grupo), solo mostramos el nombre
    if code == equipo.nombre:
        return equipo.nombre
        
    return f"{code} {equipo.nombre}"
