"""Build once from GeoNames DE.zip. No network access during job matching.

Download https://download.geonames.org/export/dump/DE.zip then run:
python -m scripts.build_city_lookup /path/DE.zip
"""
import argparse
import gzip
import hashlib
import json
import math
import unicodedata
import zipfile
from collections import defaultdict
from pathlib import Path

from location_lookup import normalize

STATES = {
    '01': ['Baden-Württemberg', 'Baden-Wuerttemberg'], '02': ['Bavaria', 'Bayern'],
    '03': ['Bremen'], '04': ['Hamburg'], '05': ['Hesse', 'Hessen'],
    '06': ['Lower Saxony', 'Niedersachsen'], '07': ['North Rhine-Westphalia', 'Nordrhein-Westfalen'],
    '08': ['Rhineland-Palatinate', 'Rheinland-Pfalz'], '09': ['Saarland'],
    '10': ['Schleswig-Holstein'], '11': ['Brandenburg'], '12': ['Mecklenburg-Vorpommern'],
    '13': ['Saxony', 'Sachsen'], '14': ['Saxony-Anhalt', 'Sachsen-Anhalt'],
    '15': ['Thuringia', 'Thueringen', 'Thüringen'], '16': ['Berlin']}


def distance(lat, lon):
    a, b = math.radians(lat-48.1351253), math.radians(lon-11.5819805)
    d = math.sin(a/2)**2 + math.cos(math.radians(lat))*math.cos(math.radians(48.1351253))*math.sin(b/2)**2
    return 6371*2*math.asin(math.sqrt(min(1, d)))


def build(path):
    places = defaultdict(dict)
    records = 0
    with zipfile.ZipFile(path) as archive:
        for line in archive.read('DE.txt').decode('utf-8').splitlines():
            c = line.split('\t')
            if c[8] != 'DE' or not (c[6] == 'P' and c[7] not in {'PPLH', 'PPLQ', 'PPLW'} or c[7] == 'ADM4'):
                continue
            records += 1
            near = distance(float(c[4]), float(c[5])) <= 150
            if c[0] == '2861650' or c[13] == '09564000':
                near = True
            names = {c[1], c[2]}
            for alias in c[3].split(','):
                if 2 <= len(alias) <= 120 and all(char in " -().'’" or
                    unicodedata.name(char, '').startswith('LATIN') for char in alias):
                    names.add(alias)
            if c[0] == '2867714':
                names.update({'Munich', 'München', 'Muenchen', 'Munchen'})
            if c[0] == '2861650':
                names.update({'Nuremberg', 'Nuernberg'})
            for name in names:
                key = normalize(name)
                if key:
                    # Same named municipality and settlement are often duplicated.
                    identity = (c[10], near)
                    places[key][identity] = max(int(c[14] or 0), places[key].get(identity, 0))
    result = {'metadata': {'source': 'https://download.geonames.org/export/dump/DE.zip',
        'license': 'https://creativecommons.org/licenses/by/4.0/',
        'attribution': 'GeoNames (geonames.org), CC BY 4.0; filtered and distances precomputed',
        'source_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        'center': [48.1351253, 11.5819805], 'radius_km': 150, 'distance': 'great-circle',
        'records': records}, 'states': {normalize(alias): code for code, names in STATES.items() for alias in names},
        'places': {name: [[state, near, pop] for (state, near), pop in sorted(rows.items())]
                   for name, rows in sorted(places.items())}}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/german_places.json.gz'))
    args = parser.parse_args()
    result = build(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(gzip.compress(json.dumps(result, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode(), mtime=0))
    print(json.dumps({'place_names': len(result['places']), 'accepted_names': sum(any(row[1] for row in rows) for rows in result['places'].values()),
                     'bytes': args.output.stat().st_size, **result['metadata']}, indent=2))


if __name__ == '__main__':
    main()
