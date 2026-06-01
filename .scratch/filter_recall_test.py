import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

os.environ['EPD_USE_GLOSSAR_FILTER'] = 'true'

from datasources.factory import create_data_source as create_datasource
from matching.epd_filter import EPDFilter

ds = create_datasource()
epds = ds.list_epds()
print(f"Total EPDs: {len(epds)}")

f = EPDFilter(epds)

cases = [
    ('STSuB 0/45',   'Nicht bituminöse Tragschicht'),
    ('FSS 0/32',     'Frostschutzschicht'),
    ('SMA 11 S',     'Deckschicht'),
    ('AC 16 B S',    'Binderschicht'),
    ('AC 22 T S',    'Bituminöse Tragschicht'),
    ('Splittmastixasphalt, laermreduzierend, feine Körnung', 'Deckschicht'),
    ('Schotter ungebunden, gebrochenes Korn 0-45', 'Nicht bituminöse Tragschicht'),
    ('Asphaltzwischenschicht mit polymermodifiziertem Bitumen Körnung 16mm', 'Binderschicht'),
    ('Gesteinskörnungsgemisch 0/32', 'Frostschutzschicht'),
]

print('\nFILTER RECALL:')
for mat, name in cases:
    filtered, _ = f.filter_for_single_material(epds, mat, schicht_name=name)
    print(f'  {len(filtered):4d} EPDs | {name:<35} | {mat[:55]}')
    for e in filtered[:3]:
        k = e.get('klassifizierung','')[:40]
        print(f'           -> {e.get("name","")[:55]}')
        print(f'              [{k}]')
