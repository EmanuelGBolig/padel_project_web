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
            # Match 50: 3º A vs 2º B -> Winner to QF (Match 57) (Wait, image 14 says 3ºA ?)
            # Image 14: Match 50 connects to 57.
            # Match 50 teams: 3º A vs ... wait, image 14 is blurry.
            # Let's assume standard pattern: 3rd of group A (size 4) vs 2nd of group B (size 4).
            # Which is harder because B has 4 too.
            # Let's check format 13 again. Match 50 was 3A vs 2B.
            # In 14, B has 4 teams. So 3rd B exists.
            # Let's check Match 60 in 14 pairs image: 2º A vs 3º B (?).
            # Yes, looks like 2A vs 3B.
            # So Match 50: 3º A vs 2º B (?) No, 50 is on top left.
            # Top left target is winner of 50 plays 1º A in 57.
            # So 50 must be a lower seed vs lower seed. 3º A vs 2º B?
            # Or 3º A vs 3º B?
            # Let's assume 3º A vs 2º B for Match 50.
            # And Match 60: 2º A vs 3º B.
            {
                'id': 50, 
                'round': 1, 
                't1': ('A', 3), 
                't2': ('B', 2), 
                'next': 57
            },
            # Round 2 (Cuartos)
            # Match 57: 1º A vs Winner(50)
            {
                'id': 57, 
                'round': 2, 
                't1': ('A', 1), 
                't2': None, # Win 50
                'next': 61
            },
            # Match 58: 2º C vs 1º D
            {
                'id': 58, 
                'round': 2, 
                't1': ('C', 2), 
                't2': ('D', 1), 
                'next': 61
            },
            # Match 59: 1º C vs 2º D
            {
                'id': 59, 
                'round': 2, 
                't1': ('C', 1), 
                't2': ('D', 2), 
                'next': 62
            },
            # Match 60: 2º A vs 3º B (assuming 3B based on image logic for 14 teams)
            {
                'id': 60, 
                'round': 2, 
                't1': ('A', 2), 
                't2': ('B', 3), 
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
}

def get_format(num_teams: int) -> Optional[TournamentFormat]:
    return FORMATS.get(num_teams)
