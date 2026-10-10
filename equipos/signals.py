"""Sin receivers.

Acá vivía `invalidar_cache_rankings`, enganchado a post_save/post_delete de
Partido, PartidoGrupo y Torneo. Borraba tres claves de caché:

    rankings_jugadores_all
    rankings_div_{id}
    rankings_jugadores_div_{id}

Ninguna de las tres existe. La clave real que se escribe lleva el género en el
sufijo (`accounts/utils.py`):

    rankings_jugadores_div_{division_id}_gen_{ALL|MASCULINO|FEMENINO}

y ya la invalida bien `torneos/signals.py` (`invalidar_cache_rankings_division`).

O sea que el receiver no invalidaba nada, pero con DatabaseCache cada
`cache.delete` es un DELETE contra la base: eran `2 + 2 × divisiones` sentencias
inútiles por cada guardado. Medido con las 8 divisiones de producción, programar
el horario de un partido costaba 21 sentencias; sin esto, 1. En un torneo de 50
parejas, cargar los 72 horarios pasa de ~1.512 sentencias a 72.

Si alguna vez hace falta invalidar caché desde esta app, hacerlo con las claves
reales y verificando que alguien las escriba.
"""
