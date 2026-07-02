"""Formatos oficiales de torneo basados en las llaves de la Federación
Argentina de Pádel (FAP) — documento "Llaves todas" (6 a 48 parejas).

Cada llave define los cruces EXACTOS de la fase final (quién juega contra
quién y quién pasa directo), garantizando que parejas de la misma zona no
se re-crucen antes de lo que indica el cuadro oficial.

Convenciones FAP de numeración de partidos (cuadro de 64):
    33-48 = 16avos · 49-56 = octavos · 57-60 = cuartos · 61-62 = semis · 64 = final
Los números se conservan como `id`/`orden_partido` para que el cuadro se lea
igual que la planilla oficial.

Zonas: n // 3 zonas; las primeras (n % 3) tienen 4 parejas y el resto 3.
Clasifican 1º y 2º de cada zona, más los 3º que indique la llave (3ºA/3ºB).
"""
import math
from dataclasses import dataclass
from typing import List, Tuple, Union, Optional

LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


@dataclass
class TournamentFormat:
    teams: int
    groups: int
    teams_per_group: Union[int, List[int]]  # nº fijo o lista de tamaños por zona
    bracket_type: str  # 'semis', 'quarters', 'octavos', '16vos', 'custom'
    # Cruces legacy (brackets simétricos simples) — ya no se usa, se mantiene
    # por compatibilidad con la rama legacy de la generación.
    crossings: Optional[List[Tuple[Tuple[str, int], Tuple[str, int]]]] = None
    # Estructura explícita: [{'id', 'round', 't1', 't2', 'next'}, ...]
    # t1/t2: ('A', 1) = 1º de la Zona A, o None = ganador del partido que llega.
    bracket_structure: Optional[List[dict]] = None

    group_names: Optional[List[str]] = None


# --- Llaves oficiales FAP -----------------------------------------------------
# {parejas: [(id_partido, t1, t2, id_siguiente), ...]}
# t1/t2: '1A' = 1º de la Zona A; None = lo ocupa el ganador del partido previo.
# El partido con next=None es la final.
FAP_LLAVES = {
    6: [
        (61, '1A', '2B', 64), (62, '2A', '1B', 64),
        (64, None, None, None),
    ],
    7: [
        (58, '3A', '2B', 61),
        (61, '1A', None, 64), (62, '2A', '1B', 64),
        (64, None, None, None),
    ],
    8: [
        (58, '3A', '2B', 61), (59, '2A', '3B', 62),
        (61, '1A', None, 64), (62, None, '1B', 64),
        (64, None, None, None),
    ],
    9: [
        (58, '2B', '2C', 61), (59, '1C', '2A', 62),
        (61, '1A', None, 64), (62, None, '1B', 64),
        (64, None, None, None),
    ],
    10: [
        (58, '2B', '2C', 61), (59, '1C', '2A', 62), (60, '3A', '1B', 62),
        (61, '1A', None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    11: [
        (57, '1A', '3B', 61), (58, '2B', '2C', 61),
        (59, '1C', '2A', 62), (60, '3A', '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    12: [
        (57, '1A', '2B', 61), (58, '2C', '1D', 61),
        (59, '1C', '2D', 62), (60, '2A', '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    13: [
        (50, '3A', '2B', 57),
        (57, '1A', None, 61), (58, '2C', '1D', 61),
        (59, '1C', '2D', 62), (60, '2A', '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    14: [
        (50, '3A', '2B', 57), (55, '2A', '3B', 60),
        (57, '1A', None, 61), (58, '2C', '1D', 61),
        (59, '1C', '2D', 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    15: [
        (50, '2B', '2C', 57), (55, '2D', '2A', 60),
        (57, '1A', None, 61), (58, '1E', '1D', 61),
        (59, '1C', '2E', 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    16: [
        (50, '2B', '2C', 57), (54, '3A', '2E', 59), (55, '2D', '2A', 60),
        (57, '1A', None, 61), (58, '1E', '1D', 61),
        (59, '1C', None, 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    17: [
        (50, '2B', '2C', 57), (51, '1E', '3B', 58),
        (54, '3A', '2E', 59), (55, '2D', '2A', 60),
        (57, '1A', None, 61), (58, None, '1D', 61),
        (59, '1C', None, 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    18: [
        (50, '2C', '2F', 57), (51, '1E', '2B', 58),
        (54, '2A', '1F', 59), (55, '2E', '2D', 60),
        (57, '1A', None, 61), (58, None, '1D', 61),
        (59, '1C', None, 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    19: [
        (50, '2C', '2F', 57), (51, '1E', '2B', 58), (52, '3A', '1D', 58),
        (54, '2A', '1F', 59), (55, '2E', '2D', 60),
        (57, '1A', None, 61), (58, None, None, 61),
        (59, '1C', None, 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    20: [
        (50, '2C', '2F', 57), (51, '1E', '2B', 58), (52, '3A', '1D', 58),
        (53, '1C', '3B', 59), (54, '2A', '1F', 59), (55, '2E', '2D', 60),
        (57, '1A', None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    21: [
        (50, '2F', '2G', 57), (51, '1E', '2C', 58), (52, '2B', '1D', 58),
        (53, '1C', '2A', 59), (54, '2D', '1F', 59), (55, '1G', '2E', 60),
        (57, '1A', None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, '1B', 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    22: [
        (50, '2F', '2G', 57), (51, '1E', '2C', 58), (52, '2B', '1D', 58),
        (53, '1C', '2A', 59), (54, '2D', '1F', 59), (55, '1G', '2E', 60),
        (56, '3A', '1B', 60),
        (57, '1A', None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    23: [
        (49, '1A', '3B', 57), (50, '2F', '2G', 57),
        (51, '1E', '2C', 58), (52, '2B', '1D', 58),
        (53, '1C', '2A', 59), (54, '2D', '1F', 59),
        (55, '1G', '2E', 60), (56, '3A', '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    24: [
        (49, '1A', '2B', 57), (50, '2G', '1H', 57),
        (51, '1E', '2F', 58), (52, '2C', '1D', 58),
        (53, '1C', '2D', 59), (54, '2E', '1F', 59),
        (55, '1G', '2H', 60), (56, '2A', '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    25: [
        (34, '3A', '2B', 49),
        (49, '1A', None, 57), (50, '2G', '1H', 57),
        (51, '1E', '2F', 58), (52, '2C', '1D', 58),
        (53, '1C', '2D', 59), (54, '2E', '1F', 59),
        (55, '1G', '2H', 60), (56, '2A', '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    26: [
        (34, '3A', '2B', 49), (47, '2A', '3B', 56),
        (49, '1A', None, 57), (50, '2G', '1H', 57),
        (51, '1E', '2F', 58), (52, '2C', '1D', 58),
        (53, '1C', '2D', 59), (54, '2E', '1F', 59),
        (55, '1G', '2H', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    27: [
        (34, '2B', '2C', 49), (47, '2D', '2A', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', '2G', 58), (52, '2F', '1D', 58),
        (53, '1C', '2E', 59), (54, '2H', '1F', 59),
        (55, '1G', '2I', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    28: [
        (34, '2B', '2C', 49), (42, '3A', '2E', 53), (47, '2D', '2A', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', '2G', 58), (52, '2F', '1D', 58),
        (53, '1C', None, 59), (54, '2H', '1F', 59),
        (55, '1G', '2I', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    29: [
        (34, '2B', '2C', 49), (39, '2F', '3B', 52),
        (42, '3A', '2E', 53), (47, '2D', '2A', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', '2G', 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, '2H', '1F', 59),
        (55, '1G', '2I', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    30: [
        (34, '2C', '2F', 49), (39, '2G', '2B', 52),
        (42, '2A', '2H', 53), (47, '2E', '2D', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', '2J', 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, '2I', '1F', 59),
        (55, '1G', '1J', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    31: [
        (34, '2C', '2F', 49), (39, '2G', '2B', 52),
        (42, '2A', '2H', 53), (43, '2I', '3A', 54), (47, '2E', '2D', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', '2J', 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', '1J', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    32: [
        (34, '2C', '2F', 49), (38, '3B', '2J', 51), (39, '2G', '2B', 52),
        (42, '2A', '2H', 53), (43, '2I', '3A', 54), (47, '2E', '2D', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', '1J', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    33: [
        (34, '2F', '2G', 49), (38, '2B', '2K', 51), (39, '2J', '2C', 52),
        (42, '2D', '2I', 53), (43, '1K', '2A', 54), (47, '2H', '2E', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', '1J', 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    34: [
        (34, '2F', '2G', 49), (38, '2B', '2K', 51), (39, '2J', '2C', 52),
        (42, '2D', '2I', 53), (43, '1K', '2A', 54),
        (46, '3A', '1J', 55), (47, '2H', '2E', 56),
        (49, '1A', None, 57), (50, '1I', '1H', 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    35: [
        (34, '2F', '2G', 49), (35, '1I', '3B', 50),
        (38, '2B', '2K', 51), (39, '2J', '2C', 52),
        (42, '2D', '2I', 53), (43, '1K', '2A', 54),
        (46, '3A', '1J', 55), (47, '2H', '2E', 56),
        (49, '1A', None, 57), (50, None, '1H', 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    36: [
        (34, '2G', '2J', 49), (35, '1I', '2B', 50),
        (38, '2C', '1L', 51), (39, '2K', '2F', 52),
        (42, '2E', '2L', 53), (43, '1K', '2D', 54),
        (46, '2A', '1J', 55), (47, '2I', '2H', 56),
        (49, '1A', None, 57), (50, None, '1H', 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    37: [
        (34, '2G', '2J', 49), (35, '1I', '2B', 50), (36, '3A', '1H', 50),
        (38, '2C', '1L', 51), (39, '2K', '2F', 52),
        (42, '2E', '2L', 53), (43, '1K', '2D', 54),
        (46, '2A', '1J', 55), (47, '2I', '2H', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, '1G', None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    38: [
        (34, '2G', '2J', 49), (35, '1I', '2B', 50), (36, '3A', '1H', 50),
        (38, '2C', '1L', 51), (39, '2K', '2F', 52),
        (42, '2E', '2L', 53), (43, '1K', '2D', 54),
        (45, '1G', '3B', 55), (46, '2A', '1J', 55), (47, '2I', '2H', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    39: [
        (34, '2J', '2K', 49), (35, '1I', '2C', 50), (36, '2B', '1H', 50),
        (38, '2F', '1L', 51), (39, '1M', '2G', 52),
        (42, '2H', '2M', 53), (43, '1K', '2E', 54),
        (45, '1G', '2A', 55), (46, '2D', '1J', 55), (47, '2L', '2I', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, '1F', 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    40: [
        (34, '2J', '2K', 49), (35, '1I', '2C', 50), (36, '2B', '1H', 50),
        (38, '2F', '1L', 51), (39, '1M', '2G', 52),
        (42, '2H', '2M', 53), (43, '1K', '2E', 54), (44, '3A', '1F', 54),
        (45, '1G', '2A', 55), (46, '2D', '1J', 55), (47, '2L', '2I', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, '1E', None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    41: [
        (34, '2J', '2K', 49), (35, '1I', '2C', 50), (36, '2B', '1H', 50),
        (37, '1E', '3B', 51), (38, '2F', '1L', 51), (39, '1M', '2G', 52),
        (42, '2H', '2M', 53), (43, '1K', '2E', 54), (44, '3A', '1F', 54),
        (45, '1G', '2A', 55), (46, '2D', '1J', 55), (47, '2L', '2I', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    42: [
        (34, '2N', '2K', 49), (35, '1I', '2F', 50), (36, '2C', '1H', 50),
        (37, '1E', '2B', 51), (38, '2G', '1L', 51), (39, '1M', '2J', 52),
        (42, '2I', '1N', 53), (43, '1K', '2H', 54), (44, '2A', '1F', 54),
        (45, '1G', '2D', 55), (46, '2E', '1J', 55), (47, '2M', '2L', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, '1D', 58),
        (53, '1C', None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    43: [
        (34, '2N', '2K', 49), (35, '1I', '2F', 50), (36, '2C', '1H', 50),
        (37, '1E', '2B', 51), (38, '2G', '1L', 51),
        (39, '1M', '2J', 52), (40, '3A', '1D', 52),
        (42, '2I', '1N', 53), (43, '1K', '2H', 54), (44, '2A', '1F', 54),
        (45, '1G', '2D', 55), (46, '2E', '1J', 55), (47, '2M', '2L', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, None, 58),
        (53, '1C', None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    44: [
        (34, '2N', '2K', 49), (35, '1I', '2F', 50), (36, '2C', '1H', 50),
        (37, '1E', '2B', 51), (38, '2G', '1L', 51),
        (39, '1M', '2J', 52), (40, '3A', '1D', 52),
        (41, '1C', '3B', 53), (42, '2I', '1N', 53),
        (43, '1K', '2H', 54), (44, '2A', '1F', 54),
        (45, '1G', '2D', 55), (46, '2E', '1J', 55), (47, '2M', '2L', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, None, 58),
        (53, None, None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    45: [
        (34, '2N', '2O', 49), (35, '1I', '2G', 50), (36, '2F', '1H', 50),
        (37, '1E', '2C', 51), (38, '2J', '1L', 51),
        (39, '1M', '2K', 52), (40, '2B', '1D', 52),
        (41, '1C', '2A', 53), (42, '2L', '1N', 53),
        (43, '1K', '2I', 54), (44, '2D', '1F', 54),
        (45, '1G', '2E', 55), (46, '2H', '1J', 55), (47, '1O', '2M', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, None, 58),
        (53, None, None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, '1B', 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    46: [
        (34, '2N', '2O', 49), (35, '1I', '2G', 50), (36, '2F', '1H', 50),
        (37, '1E', '2C', 51), (38, '2J', '1L', 51),
        (39, '1M', '2K', 52), (40, '2B', '1D', 52),
        (41, '1C', '2A', 53), (42, '2L', '1N', 53),
        (43, '1K', '2I', 54), (44, '2D', '1F', 54),
        (45, '1G', '2E', 55), (46, '2H', '1J', 55),
        (47, '1O', '2M', 56), (48, '3A', '1B', 56),
        (49, '1A', None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, None, 58),
        (53, None, None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, None, 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    47: [
        (33, '1A', '3B', 49), (34, '2N', '2O', 49),
        (35, '1I', '2G', 50), (36, '2F', '1H', 50),
        (37, '1E', '2C', 51), (38, '2J', '1L', 51),
        (39, '1M', '2K', 52), (40, '2B', '1D', 52),
        (41, '1C', '2A', 53), (42, '2L', '1N', 53),
        (43, '1K', '2I', 54), (44, '2D', '1F', 54),
        (45, '1G', '2E', 55), (46, '2H', '1J', 55),
        (47, '1O', '2M', 56), (48, '3A', '1B', 56),
        (49, None, None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, None, 58),
        (53, None, None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, None, 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
    48: [
        (33, '1A', '2B', 49), (34, '2O', '1P', 49),
        (35, '1I', '2J', 50), (36, '2G', '1H', 50),
        (37, '1E', '2F', 51), (38, '2K', '1L', 51),
        (39, '1M', '2N', 52), (40, '2C', '1D', 52),
        (41, '1C', '2D', 53), (42, '2M', '1N', 53),
        (43, '1K', '2L', 54), (44, '2E', '1F', 54),
        (45, '1G', '2H', 55), (46, '2I', '1J', 55),
        (47, '1O', '2P', 56), (48, '2A', '1B', 56),
        (49, None, None, 57), (50, None, None, 57),
        (51, None, None, 58), (52, None, None, 58),
        (53, None, None, 59), (54, None, None, 59),
        (55, None, None, 60), (56, None, None, 60),
        (57, None, None, 61), (58, None, None, 61),
        (59, None, None, 62), (60, None, None, 62),
        (61, None, None, 64), (62, None, None, 64),
        (64, None, None, None),
    ],
}

_BRACKET_TYPE_POR_RONDAS = {2: 'semis', 3: 'quarters', 4: 'octavos', 5: '16vos'}


def _parse_seed(s):
    """'1A' -> ('A', 1); None -> None."""
    if s is None:
        return None
    return (s[1], int(s[0]))


def fap_sizes(n):
    """Tamaños de zona FAP: n // 3 zonas; las primeras n % 3 tienen 4 parejas."""
    zonas, extra = divmod(n, 3)
    return [4] * extra + [3] * (zonas - extra)


def _build_format(n, entries):
    """Construye un TournamentFormat desde la tabla compacta FAP_LLAVES."""
    by_id = {e[0]: e for e in entries}

    # Ronda = distancia a la final (la final es la ronda más alta).
    depth_cache = {}

    def depth(mid):
        if mid not in depth_cache:
            nxt = by_id[mid][3]
            depth_cache[mid] = 1 if nxt is None else 1 + depth(nxt)
        return depth_cache[mid]

    total_rondas = max(depth(e[0]) for e in entries)
    structure = [
        {
            'id': mid,
            'round': total_rondas - depth(mid) + 1,
            't1': _parse_seed(t1),
            't2': _parse_seed(t2),
            'next': nxt,
        }
        for (mid, t1, t2, nxt) in entries
    ]
    structure.sort(key=lambda m: (m['round'], m['id']))

    sizes = fap_sizes(n)
    return TournamentFormat(
        teams=n,
        groups=len(sizes),
        teams_per_group=sizes[0] if len(set(sizes)) == 1 else sizes,
        bracket_type=_BRACKET_TYPE_POR_RONDAS.get(total_rondas, 'custom'),
        bracket_structure=structure,
    )


# Registro de formatos: {cantidad de parejas: TournamentFormat}
FORMATS = {n: _build_format(n, entries) for n, entries in FAP_LLAVES.items()}


def get_format(num_teams: int) -> Optional[TournamentFormat]:
    return FORMATS.get(num_teams)


# --- Estructura de zonas (fuente de verdad única) --------------------------
# Nombre legible de la llave según el bracket_type de un TournamentFormat.
_BRACKET_LABELS = {
    'semis': 'semifinales',
    'quarters': 'cuartos',
    'octavos': 'octavos',
    '16vos': '16avos',
}

# Nombre de la ronda inicial de un cuadro de eliminación directa de tamaño N.
_RONDA_POR_TAMANO = {
    2: 'la final', 4: 'semifinales', 8: 'cuartos',
    16: 'octavos', 32: '16avos', 64: '32avos', 128: '64avos',
}


def _proxima_potencia_de_2(n: int) -> int:
    """2 ** ceil(log2(n)) — el tamaño de cuadro que envuelve a n equipos."""
    if n < 2:
        return 0
    return 2 ** math.ceil(math.log2(n))


def calcular_estructura_grupos(count, *, forzar_grupos_de_3=False, equipos_por_grupo=3):
    """Calcula la estructura de zonas para `count` equipos SIN tocar la DB.

    Fuente de verdad única reutilizada por la generación real
    (AdminTorneoManageView) y por la vista previa del alta (describir_estructura).
    Devuelve (num_grupos, sizes, nombres, custom_format).
    """
    custom_format = get_format(count)
    if custom_format:
        num_grupos = custom_format.groups
        teams_per_group_config = custom_format.teams_per_group
        if isinstance(teams_per_group_config, int):
            sizes = [teams_per_group_config] * num_grupos
        else:
            sizes = list(teams_per_group_config)
        nombres = [f"Zona {LETRAS[i]}" for i in range(num_grupos)]
        return num_grupos, sizes, nombres, custom_format

    if forzar_grupos_de_3:
        epg = 3
        num_grupos = count // 3
    else:
        epg = equipos_por_grupo or 3
        num_grupos = (count + epg - 1) // epg

    sizes = []
    resto = count
    for _ in range(num_grupos):
        s = min(epg, resto)
        sizes.append(s)
        resto -= s
    nombres = [f"Grupo {LETRAS[i]}" for i in range(num_grupos)]
    return num_grupos, sizes, nombres, None


def describir_estructura(num_equipos, tipo, *, forzar3=False, equipos_por_grupo=3):
    """Proyección legible de la estructura del torneo para la vista previa del alta.

    `tipo`: 'G' (fase de grupos) o 'E' (eliminación directa), igual que
    Torneo.TipoTorneo. NO decide la estructura real (eso se arma con los
    inscriptos reales en Gestionar); es una proyección "si se llenan los cupos".

    Devuelve un dict JSON-serializable:
        {ok, nivel('ok'|'warn'), titulo, flujo:[str], zonas:[[letra,tam]],
         byes:int, mensaje:str}
    """
    n = int(num_equipos or 0)

    # --- Eliminación directa ---
    if tipo == 'E':
        if n < 2:
            return {
                'ok': False, 'nivel': 'warn', 'titulo': 'Eliminación directa',
                'flujo': [], 'zonas': [], 'byes': 0,
                'mensaje': 'Necesitás al menos 2 parejas.',
            }
        size = _proxima_potencia_de_2(n)
        byes = size - n
        ronda = _RONDA_POR_TAMANO.get(size, f'un cuadro de {size}')
        flujo = [f'{n} parejas', f'cuadro de {size}', f'arranca en {ronda}']
        if byes > 0:
            mensaje = (
                f'{byes} pareja{"s" if byes > 1 else ""} con bye '
                f'(pasan libres a la 2da ronda) para completar el cuadro de {size}.'
            )
        else:
            mensaje = 'Cuadro exacto, sin byes.'
        return {
            'ok': True, 'nivel': 'ok', 'titulo': 'Eliminación directa',
            'flujo': flujo, 'zonas': [], 'byes': byes, 'mensaje': mensaje,
        }

    # --- Fase de grupos + eliminatoria ---
    titulo = 'Fase de grupos + eliminatoria'
    if n < 4:
        return {
            'ok': False, 'nivel': 'warn', 'titulo': titulo,
            'flujo': [f'{n} parejas', 'sin estructura de zonas'], 'zonas': [],
            'byes': 0,
            'mensaje': 'Para fase de zonas necesitás al menos 4 parejas. '
                       'Con menos, usá Eliminación directa.',
        }

    if forzar3 and n % 3 != 0:
        bajo = n - (n % 3)
        return {
            'ok': False, 'nivel': 'warn', 'titulo': titulo,
            'flujo': [f'{n} parejas', 'sin estructura de zonas'], 'zonas': [],
            'byes': 0,
            'mensaje': '“Forzar zonas de 3” está activo: el total tiene que ser '
                       f'divisible por 3. Probá {bajo} o {bajo + 3}.',
        }

    num_grupos, sizes, _nombres, custom_format = calcular_estructura_grupos(
        n, forzar_grupos_de_3=forzar3, equipos_por_grupo=equipos_por_grupo
    )
    zonas = [[LETRAS[i], s] for i, s in enumerate(sizes)]

    # Etiqueta de la llave
    if custom_format and custom_format.bracket_type in _BRACKET_LABELS:
        llave = _BRACKET_LABELS[custom_format.bracket_type]
    elif custom_format:
        llave = 'llaves a medida'
    else:
        clasificados = max(4, num_grupos * 2)
        llave = f'cuadro de {_proxima_potencia_de_2(clasificados)}'

    flujo = [f'{n} parejas', f'{num_grupos} zona{"s" if num_grupos != 1 else ""}', llave]

    if custom_format:
        mensaje = f'Cuadro oficial FAP: pasan los mejores de cada zona a la fase final ({llave}).'
        nivel = 'ok'
    else:
        # Agrupación genérica: fuera del rango de llaves oficiales (6–48),
        # el sistema arma las zonas y la llave igual.
        mensaje = (
            f'{num_grupos} zonas a medida. No es una de las llaves oficiales '
            '(6–48 parejas), pero el sistema arma las zonas y el cuadro igual.'
        )
        nivel = 'ok'

    return {
        'ok': True, 'nivel': nivel, 'titulo': titulo,
        'flujo': flujo, 'zonas': zonas, 'byes': 0, 'mensaje': mensaje,
    }
