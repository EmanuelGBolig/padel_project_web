"""Scoping por organización, compartido por todas las vistas de gestión.

Vive en su propio módulo (y no en `views.py`) porque `americano.py` también lo
necesita, y `views.py` importa `americano.py` al final: importarlo al revés
sería circular. Ese acoplamiento fue justamente lo que dejó a
`AmericanoManageView` sin scoping y abrió un IDOR entre clubes.
"""
from django.core.exceptions import ImproperlyConfigured


class OrgScopedQuerysetMixin:
    """Acota el queryset de la vista a la organización del usuario.

    `AdminRequiredMixin` deja pasar a los ORGANIZER, así que sin este filtro
    cualquier organizador puede operar sobre objetos de OTRO club con sólo
    cambiar el pk de la URL (IDOR).

    Definir `org_lookup` con el camino desde el modelo de la vista hasta la
    organización, p. ej. `'torneo__organizacion'`. Los ADMIN y el staff no se
    filtran.
    """
    org_lookup = None

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_staff or user.tipo_usuario == 'ADMIN':
            return qs
        if not self.org_lookup:
            raise ImproperlyConfigured(
                f"{self.__class__.__name__} usa OrgScopedQuerysetMixin sin definir org_lookup."
            )
        if not user.organizacion_id:
            return qs.none()
        return qs.filter(**{self.org_lookup: user.organizacion_id})


def objeto_de_mi_organizacion(user, obj, org_lookup):
    """Igual que OrgScopedQuerysetMixin pero para vistas que no tienen queryset
    (FormView que resuelve el objeto a mano). Devuelve True si puede operarlo."""
    if user.is_staff or user.tipo_usuario == 'ADMIN':
        return True
    if not user.organizacion_id:
        return False
    actual = obj
    for parte in org_lookup.split('__'):
        actual = getattr(actual, parte, None)
        if actual is None:
            return False
    return actual == user.organizacion_id or getattr(actual, 'pk', None) == user.organizacion_id
