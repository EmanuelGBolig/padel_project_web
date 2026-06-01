import math
from dataclasses import dataclass
from typing import List, Tuple, Union, Optional

LETRAS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

@dataclass
class TournamentFormat:
    teams: int
    groups: int
    teams_per_group: Union[int, List[int]]  # Can be a fixed number or a list of sizes per group
    bracket_type: str  # 'semis', 'quarters', 'octavos', '16vos', 'custom'
    # Legacy crossings (for simple symmetric brackets)
    crossings: Optional[List[Tuple[Tuple[str, int], Tuple[str, int]]]] = None
    # New explicit structure for complex/asymmetric brackets
    # List of dicts: {'id': int, 'round': int, 't1': Source, 't2': Source, 'next': int}
    # Source can be: ('A', 1) [Group A Pos 1] or None [Winner of previous match]
    bracket_structure: Optional[List[dict]] = None
    
    group_names: Optional[List[str]] = None

# Registry of formats
# Key: Number of teams
# Value: TournamentFormat instance
FORMATS = {
    6: TournamentFormat(
        teams=6,
        groups=2,
        teams_per_group=3,
        bracket_type='semis',
        crossings=[
            # Semifinal 1: 1º Zona A vs 2º Zona B
            (('A', 1), ('B', 2)),
            # Semifinal 2: 1º Zona B vs 2º Zona A
            (('B', 1), ('A', 2)),
        ]
    ),
    12: TournamentFormat(
        teams=12,
        groups=4,
        teams_per_group=3,
        bracket_type='quarters',
        crossings=[
            # Cuartos 1: 1º A vs 2º B
            (('A', 1), ('B', 2)),
            # Cuartos 2: 2º C vs 1º D
            (('C', 2), ('D', 1)),
            # Cuartos 3: 1º C vs 2º D
            (('C', 1), ('D', 2)),
            # Cuartos 4: 2º A vs 1º B
            (('A', 2), ('B', 1)),
        ]
    ),
    7: TournamentFormat(
        teams=7,
        groups=2,
        teams_per_group=[4, 3], # Zona A: 4, Zona B: 3
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Cuartos / Play-in)
            {
                'id': 1, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 2), 
                'next': 2
            },
            # Round 2 (Semifinales)
            {
                'id': 2, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Winner of Match 1
                'next': 4
            },
            {
                'id': 3, 
                'round': 2, 
                't1': ('A', 2), 
                't2': ('B', 1), 
                'next': 4
            },
            # Round 3 (Final)
            {
                'id': 4, 
                'round': 3, 
                't1': None, # Winner of Match 2
                't2': None, # Winner of Match 3
                'next': None
            }
        ]
    ),
    8: TournamentFormat(
        teams=8,
        groups=2,
        teams_per_group=4,
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Cuartos / Play-in)
            # Match 58: 3º A vs 2º B -> Winner to Semis (Match 61)
            {
                'id': 58, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 2), 
                'next': 61
            },
            # Match 59: 2º A vs 3º B -> Winner to Semis (Match 62)
            {
                'id': 59, 
                'round': 1, 
                't1': ('A', 2), 
                't2': ('B', 3), 
                'next': 62
            },
            # Round 2 (Semifinales)
            # Match 61: 1º A vs Winner(58) -> Winner to Final (Match 64)
            {
                'id': 61, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Winner of Match 58
                'next': 64
            },
            # Match 62: Winner(59) vs 1º B -> Winner to Final (Match 64)
            {
                'id': 62, 
                'round': 2, 
                't1': None, # Winner of Match 59
                't2': ('B', 1), 
                'next': 64
            },
            # Round 3 (Final)
            # Match 64: Winner(61) vs Winner(62)
            {
                'id': 64, 
                'round': 3, 
                't1': None, # Winner of Match 61
                't2': None, # Winner of Match 62
                'next': None
            }
        ]
    ),
    9: TournamentFormat(
        teams=9,
        groups=3,
        teams_per_group=3,
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Cuartos)
            # Match 58: 2º B vs 2º C -> Winner to Semis (Match 61)
            {
                'id': 58, 
                'round': 1, 
                't1': ('B', 2), 
                't2': ('C', 2), 
                'next': 61
            },
            # Match 59: 1º C vs 2º A -> Winner to Semis (Match 62)
            {
                'id': 59, 
                'round': 1, 
                't1': ('C', 1), 
                't2': ('A', 2), 
                'next': 62
            },
            # Round 2 (Semifinales)
            # Match 61: 1º A vs Winner(58) -> Winner to Final (Match 64)
            {
                'id': 61, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Winner of Match 58
                'next': 64
            },
            # Match 62: Winner(59) vs 1º B -> Winner to Final (Match 64)
            {
                'id': 62, 
                'round': 2, 
                't1': None, # Winner of Match 59
                't2': ('B', 1), 
                'next': 64
            },
            # Round 3 (Final)
            {
                'id': 64, 
                'round': 3, 
                't1': None, # Winner of Match 61
                't2': None, # Winner of Match 62
                'next': None
            }
        ]
    ),
    10: TournamentFormat(
        teams=10,
        groups=3,
        teams_per_group=[4, 3, 3], # Zona A: 4, Zona B: 3, Zona C: 3
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Cuartos)
            # Match 58: 2º B vs 2º C -> Winner to Semis (Match 61)
            {
                'id': 58, 
                'round': 1, 
                't1': ('B', 2), 
                't2': ('C', 2), 
                'next': 61
            },
            # Match 59: 1º C vs 2º A -> Winner to Semis (Match 62)
            {
                'id': 59, 
                'round': 1, 
                't1': ('C', 1), 
                't2': ('A', 2), 
                'next': 62
            },
            # Match 60: 3º A vs 1º B -> Winner to Semis (Match 62) ? Wait, image shows 3º A vs 1º B going to Match 62 side?
            # Let's re-verify image 10.
            # Match 60 is right side bottom. 3º A vs 1º B.
            # Match 62 connects Winner 59 (top right bracket) and Winner 60 (bottom right bracket).
            # Winner 62 goes to Final.
            # Match 61 connects 1º A (bye) and Winner 58.
            {
                'id': 60, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 1), 
                'next': 62
            },
            # Round 2 (Semifinales)
            # Match 61: 1º A vs Winner(58)
            {
                'id': 61, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Winner 58
                'next': 64
            },
            # Match 62: Winner(59) vs Winner(60)
            {
                'id': 62, 
                'round': 2, 
                't1': None, # Winner 59
                't2': None, # Winner 60
                'next': 64
            },
            # Round 3 (Final)
            {
                'id': 64, 
                'round': 3, 
                't1': None, 
                't2': None, 
                'next': None
            }
        ]
    ),
    11: TournamentFormat(
        teams=11,
        groups=3,
        teams_per_group=[4, 4, 3], # A:4, B:4, C:3
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Cuartos)
            # Match 57: 1º A vs 3º B -> Winner to Semis (Match 61)
            {
                'id': 57, 
                'round': 1, 
                't1': ('A', 1), 
                't2': ('B', 3), 
                'next': 61
            },
            # Match 58: 2º B vs 2º C -> Winner to Semis (Match 61)
            {
                'id': 58, 
                'round': 1, 
                't1': ('B', 2), 
                't2': ('C', 2), 
                'next': 61
            },
            # Match 59: 1º C vs 2º A -> Winner to Semis (Match 62)
            {
                'id': 59, 
                'round': 1, 
                't1': ('C', 1), 
                't2': ('A', 2), 
                'next': 62
            },
            # Match 60: 3º A vs 1º B -> Winner to Semis (Match 62)
            {
                'id': 60, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 1), 
                'next': 62
            },
            # Round 2 (Semifinales)
            # Match 61: Winner(57) vs Winner(58)
            {
                'id': 61, 
                'round': 2, 
                't1': None, # Win 57
                't2': None, # Win 58
                'next': 64
            },
            # Match 62: Winner(59) vs Winner(60)
            {
                'id': 62, 
                'round': 2, 
                't1': None, # Win 59
                't2': None, # Win 60
                'next': 64
            },
            # Round 3 (Final)
            {
                'id': 64, 
                'round': 3, 
                't1': None, 
                't2': None, 
                'next': None
            }
        ]
    ),
    13: TournamentFormat(
        teams=13,
        groups=4,
        teams_per_group=[4, 3, 3, 3], # A:4, B:3, C:3, D:3
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Play-in / Octavos parciales)
            # Match 50: 3º A vs 2º B -> Winner to QF (Match 57)
            {
                'id': 50, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 2), 
                'next': 57
            },
            # Round 2 (Cuartos)
            # Match 57: 1º A vs Winner(50) -> Winner to Semis (Match 61)
            {
                'id': 57, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Win 50
                'next': 61
            },
            # Match 58: 2º C vs 1º D -> Winner to Semis (Match 61)
            {
                'id': 58, 
                'round': 2, 
                't1': ('C', 2), 
                't2': ('D', 1), 
                'next': 61
            },
            # Match 59: 1º C vs 2º D -> Winner to Semis (Match 62)
            {
                'id': 59, 
                'round': 2, 
                't1': ('C', 1), 
                't2': ('D', 2), 
                'next': 62
            },
            # Match 60: 2º A vs 1º B -> Winner to Semis (Match 62)
            {
                'id': 60, 
                'round': 2, 
                't1': ('A', 2), 
                't2': ('B', 1), 
                'next': 62
            },
            # Round 3 (Semis)
            {
                'id': 61, 
                'round': 3, 
                't1': None, # Win 57
                't2': None, # Win 58
                'next': 64
            },
            {
                'id': 62, 
                'round': 3, 
                't1': None, # Win 59
                't2': None, # Win 60
                'next': 64
            },
            # Final
            {
                'id': 64, 
                'round': 4, 
                't1': None, 
                't2': None, 
                'next': None
            }
        ]
    ),
    14: TournamentFormat(
        teams=14,
        groups=4,
        teams_per_group=[4, 4, 3, 3], # A:4, B:4, C:3, D:3
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Play-in / Octavos parciales)
            {
                'id': 49, 
                'round': 1, 
                't1': ('A', 2), 
                't2': ('B', 3), 
                'next': 60
            },
            {
                'id': 50, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 2), 
                'next': 57
            },
            # Round 2 (Cuartos)
            {
                'id': 57, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Win 50
                'next': 61
            },
            {
                'id': 58, 
                'round': 2, 
                't1': ('C', 2), 
                't2': ('D', 1), 
                'next': 61
            },
            {
                'id': 59, 
                'round': 2, 
                't1': ('C', 1), 
                't2': ('D', 2), 
                'next': 62
            },
            {
                'id': 60, 
                'round': 2, 
                't1': None, # Win 49
                't2': ('B', 1), 
                'next': 62
            },
            # Round 3 (Semis)
            {
                'id': 61, 
                'round': 3, 
                't1': None, # Win 57
                't2': None, # Win 58
                'next': 64
            },
            {
                'id': 62, 
                'round': 3, 
                't1': None, # Win 59
                't2': None, # Win 60
                'next': 64
            },
            # Final
            {
                'id': 64, 
                'round': 4, 
                't1': None, 
                't2': None, 
                'next': None
            }
        ]
    ),
    15: TournamentFormat(
        teams=15,
        groups=5,
        teams_per_group=3,
        bracket_type='custom',
        bracket_structure=[
            # R1 (Previas)
            { 'id': 50, 'round': 1, 't1': ('B', 2), 't2': ('C', 2), 'next': 57 },
            { 'id': 55, 'round': 1, 't1': ('D', 2), 't2': ('A', 2), 'next': 60 },
            # R2 (Cuartos)
            { 'id': 57, 'round': 2, 't1': ('A', 1), 't2': None, 'next': 61 }, # Winner 50
            { 'id': 58, 'round': 2, 't1': ('E', 1), 't2': ('D', 1), 'next': 61 },
            { 'id': 59, 'round': 2, 't1': ('C', 1), 't2': ('E', 2), 'next': 62 },
            { 'id': 60, 'round': 2, 't1': None, 't2': ('B', 1), 'next': 62 }, # Winner 55
            # R3 (Semis)
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Final
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
    16: TournamentFormat(
        teams=16,
        groups=5,
        teams_per_group=[4, 3, 3, 3, 3], # A=4
        bracket_type='custom',
        bracket_structure=[
            # R1
            { 'id': 50, 'round': 1, 't1': ('B', 2), 't2': ('C', 2), 'next': 57 },
            { 'id': 54, 'round': 1, 't1': ('A', 3), 't2': ('E', 2), 'next': 59 },
            { 'id': 55, 'round': 1, 't1': ('D', 2), 't2': ('A', 2), 'next': 60 },
            # R2
            { 'id': 57, 'round': 2, 't1': ('A', 1), 't2': None, 'next': 61 },
            { 'id': 58, 'round': 2, 't1': ('E', 1), 't2': ('D', 1), 'next': 61 },
            { 'id': 59, 'round': 2, 't1': ('C', 1), 't2': None, 'next': 62 },
            { 'id': 60, 'round': 2, 't1': None, 't2': ('B', 1), 'next': 62 },
            # R3
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Final
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
    17: TournamentFormat(
        teams=17,
        groups=6,
        teams_per_group=[3, 3, 3, 3, 3, 2], # A-E=3, F=2
        bracket_type='custom',
        bracket_structure=[
            # R1
            { 'id': 50, 'round': 1, 't1': ('C', 2), 't2': ('F', 2), 'next': 57 },
            { 'id': 51, 'round': 1, 't1': ('E', 1), 't2': ('B', 2), 'next': 58 }, # 1E vs 2B -> plays 1D
            { 'id': 54, 'round': 1, 't1': ('A', 3), 't2': ('E', 2), 'next': 59 },
            { 'id': 55, 'round': 1, 't1': ('D', 2), 't2': ('A', 2), 'next': 60 },
            # R2
            { 'id': 57, 'round': 2, 't1': ('A', 1), 't2': None, 'next': 61 },
            { 'id': 58, 'round': 2, 't1': None, 't2': ('D', 1), 'next': 61 },
            { 'id': 59, 'round': 2, 't1': ('C', 1), 't2': None, 'next': 62 },
            { 'id': 60, 'round': 2, 't1': None, 't2': ('B', 1), 'next': 62 },
            # R3
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Final
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
    18: TournamentFormat(
        teams=18,
        groups=6,
        teams_per_group=3,
        bracket_type='custom',
        bracket_structure=[
            # R1
            { 'id': 50, 'round': 1, 't1': ('C', 2), 't2': ('F', 2), 'next': 57 },
            { 'id': 51, 'round': 1, 't1': ('E', 1), 't2': ('B', 2), 'next': 58 },
            { 'id': 54, 'round': 1, 't1': ('A', 2), 't2': ('F', 1), 'next': 59 },
            { 'id': 55, 'round': 1, 't1': ('E', 2), 't2': ('D', 2), 'next': 60 },
            # R2
            { 'id': 57, 'round': 2, 't1': ('A', 1), 't2': None, 'next': 61 },
            { 'id': 58, 'round': 2, 't1': None, 't2': ('D', 1), 'next': 61 },
            { 'id': 59, 'round': 2, 't1': ('C', 1), 't2': None, 'next': 62 },
            { 'id': 60, 'round': 2, 't1': None, 't2': ('B', 1), 'next': 62 },
            # R3
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Final
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
    19: TournamentFormat(
        teams=19,
        groups=6,
        teams_per_group=[4, 3, 3, 3, 3, 3], # A=4
        bracket_type='custom',
        bracket_structure=[
            # R1
            { 'id': 50, 'round': 1, 't1': ('C', 2), 't2': ('F', 2), 'next': 57 },
            { 'id': 51, 'round': 1, 't1': ('E', 1), 't2': ('B', 2), 'next': 58 },
            { 'id': 52, 'round': 1, 't1': ('A', 3), 't2': ('D', 1), 'next': 58 }, # 3A vs 1D -> Plays winner 51
            { 'id': 54, 'round': 1, 't1': ('A', 2), 't2': ('F', 1), 'next': 59 },
            { 'id': 55, 'round': 1, 't1': ('E', 2), 't2': ('D', 2), 'next': 60 },
            # R2
            { 'id': 57, 'round': 2, 't1': ('A', 1), 't2': None, 'next': 61 },
            { 'id': 58, 'round': 2, 't1': None, 't2': None, 'next': 61 }, # Win51 vs Win52
            { 'id': 59, 'round': 2, 't1': ('C', 1), 't2': None, 'next': 62 },
            { 'id': 60, 'round': 2, 't1': None, 't2': ('B', 1), 'next': 62 },
            # R3
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Final
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
    21: TournamentFormat(
        teams=21,
        groups=7,
        teams_per_group=3, # A-G=3
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Octavos)
            { 'id': 50, 'round': 1, 't1': ('F', 2), 't2': ('G', 2), 'next': 57 }, # 2ºF vs 2ºG -> plays 1A
            { 'id': 51, 'round': 1, 't1': ('E', 1), 't2': ('C', 2), 'next': 58 }, # 1ºE vs 2ºC
            { 'id': 52, 'round': 1, 't1': ('B', 2), 't2': ('D', 1), 'next': 58 }, # 2ºB vs 1ºD
            { 'id': 53, 'round': 1, 't1': ('C', 1), 't2': ('A', 2), 'next': 59 }, # 1ºC vs 2ºA
            { 'id': 54, 'round': 1, 't1': ('D', 2), 't2': ('F', 1), 'next': 59 }, # 2ºD vs 1ºF
            { 'id': 55, 'round': 1, 't1': ('G', 1), 't2': ('E', 2), 'next': 60 }, # 1ºG vs 2ºE -> plays 1B
            # Round 2 (Cuartos)
            { 'id': 57, 'round': 2, 't1': ('A', 1), 't2': None, 'next': 61 }, # 1ºA vs Win50
            { 'id': 58, 'round': 2, 't1': None, 't2': None, 'next': 61 }, # Win51 vs Win52
            { 'id': 59, 'round': 2, 't1': None, 't2': None, 'next': 62 }, # Win53 vs Win54
            { 'id': 60, 'round': 2, 't1': None, 't2': ('B', 1), 'next': 62 }, # Win55 vs 1ºB
            # Round 3 (Semis)
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Final
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
    24: TournamentFormat(
        teams=24,
        groups=8,
        teams_per_group=3, # All groups A-H has 3 teams
        bracket_type='custom',
        bracket_structure=[
            # Round 1 (Octavos)
            { 'id': 49, 'round': 1, 't1': ('A', 1), 't2': ('B', 2), 'next': 57 },
            { 'id': 50, 'round': 1, 't1': ('G', 2), 't2': ('H', 1), 'next': 57 },
            { 'id': 51, 'round': 1, 't1': ('E', 1), 't2': ('F', 2), 'next': 58 },
            { 'id': 52, 'round': 1, 't1': ('C', 2), 't2': ('D', 1), 'next': 58 },
            { 'id': 53, 'round': 1, 't1': ('C', 1), 't2': ('D', 2), 'next': 59 },
            { 'id': 54, 'round': 1, 't1': ('E', 2), 't2': ('F', 1), 'next': 59 },
            { 'id': 55, 'round': 1, 't1': ('G', 1), 't2': ('H', 2), 'next': 60 },
            { 'id': 56, 'round': 1, 't1': ('A', 2), 't2': ('B', 1), 'next': 60 },
            # Round 2 (Cuartos)
            { 'id': 57, 'round': 2, 't1': None, 't2': None, 'next': 61 },
            { 'id': 58, 'round': 2, 't1': None, 't2': None, 'next': 61 },
            { 'id': 59, 'round': 2, 't1': None, 't2': None, 'next': 62 },
            { 'id': 60, 'round': 2, 't1': None, 't2': None, 'next': 62 },
            # Round 3 (Semifinales)
            { 'id': 61, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            { 'id': 62, 'round': 3, 't1': None, 't2': None, 'next': 64 },
            # Round 4 (Final)
            { 'id': 64, 'round': 4, 't1': None, 't2': None, 'next': None }
        ]
    ),
}

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
        mensaje = f'Pasan los mejores de cada zona a la fase final ({llave}).'
        nivel = 'ok'
    else:
        # Agrupación genérica: el sistema igual la genera, pero no es uno de los
        # formatos optimizados (6–19, 21, 24).
        mensaje = (
            f'{num_grupos} zonas a medida. No es uno de los formatos optimizados, '
            'pero el sistema arma las zonas y la llave igual.'
        )
        nivel = 'ok'

    return {
        'ok': True, 'nivel': nivel, 'titulo': titulo,
        'flujo': flujo, 'zonas': zonas, 'byes': 0, 'mensaje': mensaje,
    }

