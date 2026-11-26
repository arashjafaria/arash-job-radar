"""Public Indeed/XING pages, shared Arash matching and permanent delivery claims.

Read-only unless --post. No login, challenge bypass or paid data provider.
"""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup, NavigableString

from config import BOT_TOKEN, CHAT_ID
from decisions import evaluate_details, record_decision
from delivery_policy import delivery_block_reason
from market_monitor import (SEARCH_TERMS, build_company, build_employment,
                            find_job_posting, parse_date, clean)
from notifications import notify_job_once, was_notified
from profile import MATCHER_REVISION
from supabase_store import get_job_record, save_job, update_job
from title_policy import excluded_title_reason

SOURCES = ('indeed', 'xing')


def search_urls(source, query):
    areas = [('München', 150), ('Nürnberg', 30), ('Deutschland', None)]
    for area, radius in areas:
        term = query + ' fully remote' if radius is None else query
        if source == 'indeed':
            params = {'q': term, 'l': area, 'fromage': 1, 'sort': 'date'}
            if radius:
                params['radius'] = radius
            yield 'https://de.indeed.com/jobs?' + urlencode(params)
        else:
            params = {'keywords': term, 'location': area, 'sort': 'date'}
            if radius:
                params['radius'] = radius
            yield 'https://www.xing.com/jobs/search?' + urlencode(params)


def job_identity(source, value):
    parsed = urlsplit(value)
    if parsed.hostname not in ({'de.indeed.com', 'www.indeed.com'} if source == 'indeed' else {'www.xing.com', 'xing.com'}):
        return None
    if source == 'indeed':
        if parsed.path not in {'/viewjob', '/rc/clk', '/pagead/clk', '/m/viewjob'}:
            return None
        params = parse_qs(parsed.query)
        jid = (params.get('jk') or params.get('vjk') or [''])[0]
        if not re.fullmatch(r'[a-zA-Z0-9]{8,32}', jid):
            return None
        return jid, 'https://de.indeed.com/viewjob?' + urlencode({'jk': jid})
    match = re.fullmatch(r'/jobs/[^/]+-(\d{6,})/?', parsed.path)
    if not match:
        return None
    return match[1], 'https://www.xing.com' + parsed.path.rstrip('/')


def fetch_html(session, url):
    response = session.get(url, timeout=25)
    response.raise_for_status()
    response.encoding = 'utf-8'
    soup = BeautifulSoup(response.text, 'html.parser')
    title = clean(soup.title.get_text() if soup.title else '').lower()
    if any(term in title for term in ('access denied', 'just a moment', 'captcha', 'additional verification required', 'verify you are human', 'zugriff verweigert')):
        raise ValueError('Access challenge; no bypass attempted')
    return soup


def collect_links(source, soup):
    jobs = {}
    base = 'https://de.indeed.com' if source == 'indeed' else 'https://www.xing.com'
    for link in soup.select('a[href]'):
        identity = job_identity(source, urljoin(base, link['href']))
        if not identity:
            continue
        jid, url = identity
        title = clean(link.get('aria-label') or link.get_text(' ', strip=True))
        # Ignore salary/footer links; an actual job anchor is required above.
        if jid not in jobs or (not jobs[jid]['title'] and title):
            jobs[jid] = {'source': source, 'job_id': jid, 'url': url, 'title': title}
    return list(jobs.values())


def sections(description_html):
    """Handle ordinary headings plus XING's plain-text Aufgaben/Profil labels."""
    soup = BeautifulSoup(description_html, 'html.parser')
    out = {key: [] for key in ('tasks', 'requirements', 'benefits', 'other')}
    current = 'other'
    headings = {
        'tasks': r'aufgaben|ihre aufgaben|deine aufgaben|responsibilities|your responsibilities|your role(?: key responsibilities.*)?|key responsibilities.*|your tasks',
        'requirements': r'profil|ihr profil|dein profil|qualifikationen?|anforderungen|requirements|qualifications|your profile(?: qualifications.*)?|your background.*|what you bring|das bringst du mit',
        'benefits': r'benefits|wir bieten|was wir bieten|what we offer|our benefits|über uns|about us',
    }
    for node in soup.descendants:
        if isinstance(node, NavigableString):
            if node.parent.name not in {'[document]', 'div', 'section'}:
                continue
            text = clean(node)
        elif node.name in {'h1', 'h2', 'h3', 'h4', 'h5', 'p', 'li', 'strong', 'b'}:
            if node.find_parent(['p', 'li']):
                continue
            text = clean(node.get_text(' ', strip=True))
        else:
            continue
        if not text:
            continue
        heading = next((key for key, pattern in headings.items() if re.fullmatch(pattern, text.rstrip(': '), re.I)), None)
        if heading:
            current = heading
        elif text not in out[current]:
            out[current].append(text)
    return out


def parse_details(soup, candidate):
    posting = None
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            posting = find_job_posting(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError):
            continue
        if posting:
            break
    if not posting:
        raise ValueError('No structured job description')
    raw = posting.get('description') or ''
    description = clean(BeautifulSoup(raw, 'html.parser').get_text(' ', strip=True))
    if len(description) < 100:
        raise ValueError('Incomplete job description')
    # Retain physical addresses even when TELECOMMUTE is present. Hybrid is not
    # Germany-wide remote, and the shared matcher needs the original city.
    locations = posting.get('jobLocation') or []
    if isinstance(locations, dict):
        locations = [locations]
    addresses = []
    for item in locations:
        address = item.get('address') or {}
        if not isinstance(address, dict):
            continue
        country = address.get('addressCountry', '')
        if isinstance(country, dict):
            country = country.get('name', '')
        if country and str(country).lower() not in {'de', 'deutschland', 'germany'}:
            raise ValueError('Vacancy outside Germany')
        addresses.append(', '.join(clean(x) for x in (address.get('addressLocality'), address.get('addressRegion'), country) if x))
    return {'title': clean(posting.get('title')) or candidate['title'],
            'company': build_company(posting), 'location': ' / '.join(addresses),
            'date_posted': clean(posting.get('datePosted')),
            'valid_through': clean(posting.get('validThrough')),
            'employment_type': build_employment(posting),
            'description': description, **sections(raw)}


def fetch_details(session, candidate):
    return parse_details(fetch_html(session, candidate['url']), candidate)


def assess(candidate, details, now=None):
    now = now or datetime.now(timezone.utc)
    posted = parse_date(details['date_posted'])
    expiry = parse_date(details.get('valid_through'))
    if posted is None or not timedelta(0) <= now - posted <= timedelta(hours=24):
        return 'reject', {'decision': 'reject', 'reason': 'outside_verified_24_hour_window'}, None
    if expiry is not None and expiry <= now:
        return 'reject', {'decision': 'reject', 'reason': 'expired'}, None
    return evaluate_details(candidate, details)


def process(session, candidate, post=False):
    if excluded_title_reason(candidate.get('title')):
        return {'job_id': candidate['job_id'], 'decision': 'reject', 'reason': 'excluded_title'}
    if post:
        record = get_job_record(candidate['source'], candidate['job_id'])
        if was_notified(record):
            return {'job_id': candidate['job_id'], 'decision': 'already_reserved'}
        if record and (record.get('status') or '').endswith('@' + MATCHER_REVISION):
            return {'job_id': candidate['job_id'], 'decision': 'already_assessed'}
    details = fetch_details(session, candidate)
    decision, evidence, score = assess(candidate, details)
    job = {**candidate, **details}
    result = {'job_id': job['job_id'], 'title': job['title'], 'company': job['company'],
              'location': job['location'], 'url': job['url'], 'date_posted': details['date_posted'],
              'decision': decision, 'reason': evidence['reason'], 'score': score,
              'description_read': True, 'sent': False}
    if not post:
        return result
    source, jid = job['source'], job['job_id']
    save_job(source, jid, title=job['title'], company=job['company'], location=job['location'],
             url=job['url'], posted_at=details['date_posted'], match_score=score,
             status=decision + '@' + MATCHER_REVISION)
    update_job(source, jid, status=decision + '@' + MATCHER_REVISION)
    evidence['stage'] = 'public_board_structured_review'
    record_decision(source, jid, decision, score, evidence)
    if decision in {'apply', 'manual'} and not delivery_block_reason(job):
        label = 'APPLY' if decision == 'apply' else 'MANUAL REVIEW'
        message = (f"{source.upper()} — {label}\n{job['title']}\n{job['company']}\n"
                   f"{job['location']}\nPosted: {details['date_posted']}\n"
                   f"Match: {score}%\n{evidence['reason']}\n{job['url']}")
        result['sent'] = bool(notify_job_once(job, message, send_telegram))
    return result


def send_telegram(message):
    # No retries: retain the permanent claim on a timeout or uncertain response.
    response = requests.post('https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
                             data={'chat_id': CHAT_ID, 'text': message}, timeout=25)
    return response.status_code == 200


def run(source, post=False, max_details=20, queries=None):
    queries = queries or SEARCH_TERMS[(int(time.time() // 3600) % 4)*3: (int(time.time() // 3600) % 4)*3+3]
    report = {'source': source, 'mode': 'production' if post else 'dry_run',
              'searches_ok': 0, 'search_errors': [], 'jobs': [], 'detail_errors': []}
    candidates = {}
    with requests.Session() as session:
        for query in queries:
            for url in search_urls(source, query):
                try:
                    soup = fetch_html(session, url)
                    jobs = collect_links(source, soup)
                    if not jobs and not re.search(r'keine.*(?:jobs|stellen)|no jobs|0 Jobs', soup.get_text(' ', strip=True), re.I):
                        raise ValueError('No vacancy links or explicit empty-result evidence')
                    report['searches_ok'] += 1
                    candidates.update({job['job_id']: job for job in jobs})
                except (requests.RequestException, ValueError) as exc:
                    report['search_errors'].append(type(exc).__name__)
                time.sleep(.3)
        checked = 0
        for candidate in candidates.values():
            # Known/excluded cards don't consume the description request budget.
            if excluded_title_reason(candidate.get('title')):
                continue
            if post:
                record = get_job_record(source, candidate['job_id'])
                if was_notified(record) or (record and (record.get('status') or '').endswith('@' + MATCHER_REVISION)):
                    continue
            if checked >= max_details:
                break
            checked += 1
            try:
                report['jobs'].append(process(session, candidate, post))
            except (requests.RequestException, ValueError) as exc:
                report['detail_errors'].append({'job_id': candidate['job_id'], 'error': type(exc).__name__})
            time.sleep(.4)
    report.update(candidates=len(candidates), details_attempted=checked,
                  descriptions_read=sum(j.get('description_read', False) for j in report['jobs']),
                  decisions=dict(Counter(j['decision'] for j in report['jobs'])),
                  sent=sum(j.get('sent', False) for j in report['jobs']))
    report['healthy'] = report['searches_ok'] > 0 and not report['search_errors']
    if checked and not report['descriptions_read']:
        report['healthy'] = False
    report['degraded'] = bool(report['detail_errors'])
    if not post and candidates and report['descriptions_read'] == 0:
        report['healthy'] = False
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=SOURCES, required=True)
    parser.add_argument('--post', action='store_true')
    parser.add_argument('--max-details', type=int, default=20)
    parser.add_argument('--output', default='board_audit.json')
    args = parser.parse_args()
    if args.max_details < 1:
        parser.error('Positive detail budget required')
    if args.post and (not BOT_TOKEN or not CHAT_ID):
        parser.error('Telegram configuration missing')
    report = run(args.source, args.post, args.max_details)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'jobs'}, indent=2))
    if not report['healthy']:
        raise SystemExit('Source access/parsing incomplete; inspect board audit')


if __name__ == '__main__':
    from scripts.trial_metrics import start
    start()
    main()
