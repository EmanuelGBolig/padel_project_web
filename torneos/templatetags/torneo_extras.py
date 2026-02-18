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
    
    nombre = equipo.nombre
    
    # FIX: Si el nombre contiene emails (legacy data o error), limpiarlo para mostrar solo usuario
    if '@' in nombre:
        try:
            # Asumimos formato "email1@dom.com/email2@dom.com" o similar
            parts = nombre.split('/')
            clean_parts = []
            for p in parts:
                if '@' in p:
                    # Tomar solo la parte antes del @
                    clean_parts.append(p.split('@')[0])
                else:
                    clean_parts.append(p)
            nombre = '/'.join(clean_parts)
        except Exception:
            # Fallback si falla el parseo
            pass

    return {'code': nombre, 'name': nombre}

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
        
    nombre = equipo.nombre
    if '@' in nombre:
        try:
            parts = nombre.split('/')
            clean_parts = []
            for p in parts:
                if '@' in p:
                    clean_parts.append(p.split('@')[0])
                else:
                    clean_parts.append(p)
            nombre = '/'.join(clean_parts)
        except Exception:
            pass
            
    return nombre

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
    return value
@register.tag(name="setvar")
def do_setvar(parser, token):
    """
    Asigna un valor a una variable en el contexto del template.
    Uso: {% setvar variable_name = value %}
    """
    parts = token.split_contents()
    if len(parts) < 4:
        raise template.TemplateSyntaxError("'setvar' tag requires at least 3 arguments")
    
    # Soporta {% setvar var = value %}
    return SetVarNode(parts[1], parts[3])

class SetVarNode(template.Node):
    def __init__(self, var_name, var_value):
        self.var_name = var_name
        self.var_value = var_value

    def render(self, context):
        # Intentar resolver el valor (si es una variable o un literal)
        try:
            val = template.Variable(self.var_value).resolve(context)
        except template.VariableDoesNotExist:
            # Si no se puede resolver, tratar como string literal (si corresponde) o booleano
            if self.var_value.lower() == 'true':
                val = True
            elif self.var_value.lower() == 'false':
                val = False
            else:
                val = self.var_value
        
        context[self.var_name] = val
        return ""
