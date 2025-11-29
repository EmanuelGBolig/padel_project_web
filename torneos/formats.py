from dataclasses import dataclass
from typing import List, Tuple, Union, Optional

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
}

def get_format(num_teams: int) -> Optional[TournamentFormat]:
    return FORMATS.get(num_teams)
