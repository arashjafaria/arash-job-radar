"""Offline German place lookup; distances are calculated only by the builder."""
import gzip
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

# User exclusions, 2026-10-25. These do not change the 150 km definition.
EXCLUDED_ONSITE_CITIES = {'geislingen an der steige', 'geislingen', 'leonberg'}


def city_field(value):
    name = normalize(value.split(',')[0])
    name = re.sub(r'^\d{5}\s+', '', name)
    # LinkedIn metropolitan labels refer to the named city; no substring scan.
    name = re.sub(r'^greater\s+(.+?)\s+(?:area|metropolitan area|region)$', r'\1', name)
    name = re.sub(r'^(?:metropolregion|raum|grossraum)\s+', '', name)
    return re.sub(r'\s+\d+\s+km$', '', name)


def normalize(value):
    value = value.casefold().replace('ß', 'ss')
    for a, b in [('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue')]:
        value = value.replace(a, b)
    value = ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


@lru_cache(maxsize=1)
def data():
    with gzip.open(Path(__file__).parent / 'data/german_places.json.gz', 'rt', encoding='utf-8') as file:
        return json.load(file)


def onsite_location(location):
    """Return True/False/None: accepted, confirmed outside, or needs review."""
    lookup = data()
    low = normalize(location or '')
    if not low:
        return None, 'Location needs review: missing city'
    if low in {'germany', 'deutschland', 'de', 'bavaria germany', 'bayern deutschland', 'bavaria', 'bayern'}:
        return None, 'Location needs review: city not specified'
    if any(re.search(r'\b' + country + r'\b', low) for country in
           ('austria', 'oesterreich', 'switzerland', 'schweiz', 'france', 'italy', 'italien', 'netherlands')):
        return False, 'Onsite location outside Germany'
    pieces = re.split(r'\s*(?:/|;|\||\band\b|\bund\b)\s*', location or '', flags=re.I)
    outcomes = []
    user_excluded = False
    for piece in pieces:
        states, context = set(), normalize(','.join(piece.split(',')[1:]))
        for alias, code in sorted(lookup['states'].items(), key=lambda row: len(row[0]), reverse=True):
            pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
            if re.search(pattern, context):
                states.add(code)
                context = re.sub(pattern, ' ', context)
        # Match complete city fields; never match Erding inside Oberding.
        name = city_field(piece)
        if name in EXCLUDED_ONSITE_CITIES:
            user_excluded = True
            outcomes.append(False)
            continue
        rows = lookup['places'].get(name, [])
        if states:
            rows = [row for row in rows if row[0] in states]
        if not rows:
            outcomes.append(None)
            continue
        # The well-known city dominates identically named tiny settlements.
        ranked = sorted(rows, key=lambda row: row[2], reverse=True)
        if len(ranked) > 1 and ranked[0][2] >= 20000 and ranked[0][2] >= 10*max(1, ranked[1][2]):
            rows = ranked[:1]
        decisions = {row[1] for row in rows}
        outcomes.append(next(iter(decisions)) if len(decisions) == 1 else None)
    if True in outcomes:
        return True, 'Onsite/hybrid in saved Munich 150 km list or Nuremberg exception'
    if outcomes and all(value is False for value in outcomes):
        if user_excluded:
            return False, 'Onsite city explicitly excluded by user'
        return False, 'Known city outside Munich 150 km list and onsite exceptions'
    return None, 'Location needs review: unknown or ambiguous city'
