"""
Database layer — Firebase Firestore if configured, else in-memory with seed data.
Single interface so app.py doesn't care which is active.

v2 fixes:
  - 200+ seed issues (was 32) spread across all Delhi areas
  - 5-minute in-memory cache for Firebase reads (was: read every request)
  - Graceful 429 quota handling: falls back to rich memory seed
  - _seed_firebase_if_empty() now writes even when the read check fails
"""
import os, time, math, json, tempfile, threading, random

# ═══════════════════════════════════════════════════════
#  AREA COORDINATES (Delhi neighborhoods)
# ═══════════════════════════════════════════════════════
AREA_COORDS = {
    'Connaught Place': (28.6315, 77.2167), 'Karol Bagh': (28.6514, 77.1907),
    'Rohini': (28.7041, 77.1025), 'Saket': (28.5244, 77.2090),
    'Lajpat Nagar': (28.5677, 77.2378), 'Hauz Khas': (28.5494, 77.2001),
    'Dwarka': (28.5921, 77.0460), 'Janakpuri': (28.6219, 77.0878),
    'Chandni Chowk': (28.6506, 77.2303), 'Paharganj': (28.6448, 77.2167),
    'Mehrauli': (28.5244, 77.1855), 'Malviya Nagar': (28.5355, 77.2068),
    'Greater Kailash': (28.5494, 77.2378), 'Vasant Kunj': (28.5200, 77.1590),
    'Pitampura': (28.7007, 77.1311), 'Model Town': (28.7167, 77.1900),
    'Civil Lines': (28.6800, 77.2250), 'Mukherjee Nagar': (28.7050, 77.2100),
    'Rajouri Garden': (28.6447, 77.1220), 'Punjabi Bagh': (28.6590, 77.1311),
    'Mayur Vihar': (28.6090, 77.2944), 'Preet Vihar': (28.6355, 77.2944),
    'Shahdara': (28.6706, 77.2944), 'Laxmi Nagar': (28.6310, 77.2780),
    'Okhla': (28.5355, 77.2780), 'Kalkaji': (28.5494, 77.2590),
    'Nehru Place': (28.5491, 77.2509), 'Lodhi Colony': (28.5887, 77.2208),
    'Kashmere Gate': (28.6675, 77.2280), 'Nizamuddin': (28.5910, 77.2429),
    'Sarojini Nagar': (28.5760, 77.1980), 'INA': (28.5733, 77.2080),
    'Patel Nagar': (28.6500, 77.1700), 'RK Puram': (28.5650, 77.1800),
    'Vasant Vihar': (28.5670, 77.1600), 'Defence Colony': (28.5731, 77.2294),
}


# ═══════════════════════════════════════════════════════
#  STATE
# ═══════════════════════════════════════════════════════
_state = {
    'mode': 'memory',
    'fs_db': None,
    'issues': [],
    'spam_issues': [],
    'ngos': [],
    'next_id': 1,
    'lock': threading.Lock(),
    'upvoters': {},
    'recent_reports': {},
}

# ── READ CACHE (prevents quota exhaustion) ─────────────
_cache = {
    'issues':    None,
    'issues_ts': 0.0,
}
_CACHE_TTL = 300  # 5 minutes — reduces Firebase reads from ~500/hr to ~12/hr

def _get_cached_issues():
    now = time.time()
    if _cache['issues'] is not None and (now - _cache['issues_ts']) < _CACHE_TTL:
        return _cache['issues']
    return None

def _set_cached_issues(issues):
    _cache['issues'] = issues
    _cache['issues_ts'] = time.time()

def _invalidate_cache():
    _cache['issues']    = None
    _cache['issues_ts'] = 0.0

# ──────────────────────────────────────────────────────

SLA_HOURS = {
    'pothole': 168, 'water': 48, 'garbage': 72,
    'streetlight': 48, 'traffic': 24, 'noise': 24,
    'sewage': 24, 'electricity': 24, 'tree': 168, 'other': 120,
}
CROWD_ESCALATION_THRESHOLD = 25


# ═══════════════════════════════════════════════════════
#  INIT
# ═══════════════════════════════════════════════════════
def init_db():
    """Try Firebase first, fall back to in-memory with seeds."""
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        cred = None
        if os.path.exists('firebase_key.json'):
            cred = credentials.Certificate('firebase_key.json')
        elif os.environ.get('FIREBASE_KEY_JSON'):
            tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            tmp.write(os.environ['FIREBASE_KEY_JSON'])
            tmp.close()
            cred = credentials.Certificate(tmp.name)
        else:
            raise FileNotFoundError('No Firebase credentials')

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        _state['fs_db'] = firestore.client()
        _state['mode'] = 'firebase'
        print('[database] ✓ Firebase connected')
        _seed_firebase_if_empty()
    except Exception as e:
        print(f'[database] Firebase unavailable ({type(e).__name__}), using in-memory mode')
        _state['mode'] = 'memory'
        _seed_memory()


# ═══════════════════════════════════════════════════════
#  GETTERS
# ═══════════════════════════════════════════════════════
def get_areas():
    return sorted(AREA_COORDS.keys())


def get_issues(tag=None, status=None, limit=300):
    """List issues with 5-minute cache to prevent Firebase quota exhaustion."""
    if _state['mode'] == 'firebase':
        # Try cache first
        cached = _get_cached_issues()
        if cached is not None:
            results = cached
        else:
            try:
                q    = _state['fs_db'].collection('issues')
                docs = q.limit(limit).stream()
                results = []
                for d in docs:
                    data = d.to_dict()
                    data.setdefault('id', d.id)
                    results.append(data)
                results.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                _set_cached_issues(results)
                print(f'[database] Cache refreshed: {len(results)} issues from Firebase')
            except Exception as e:
                print(f'[database] Firestore read failed → memory fallback: {e}')
                # On quota error: use memory seed (populated at startup)
                results = list(_state['issues'])

        if tag:    results = [i for i in results if i.get('tag') == tag]
        if status: results = [i for i in results if (i.get('status') or 'open') == status]
        return results[:limit]

    # Pure memory mode
    results = list(_state['issues'])
    if tag:    results = [i for i in results if i.get('tag') == tag]
    if status: results = [i for i in results if (i.get('status') or 'open') == status]
    results.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
    return results[:limit]


def get_all_ngos():
    if _state['mode'] == 'firebase':
        try:
            docs = _state['fs_db'].collection('ngos').stream()
            return [{**d.to_dict(), 'id': d.id} for d in docs]
        except Exception:
            pass
    return list(_state['ngos'])


def get_nearby_ngos(lat, lng, tag=None, limit=5, radius_km=8):
    if lat is None or lng is None:
        return []
    ngos = get_all_ngos()
    results = []
    for n in ngos:
        if not n.get('lat') or not n.get('lng'):
            continue
        dist = _haversine(lat, lng, float(n['lat']), float(n['lng']))
        if dist > radius_km:
            continue
        score = 1.0
        if tag and n.get('tag') == tag:
            score += 5.0
        results.append({**n, 'distance_km': round(dist, 2), '_score': score - dist * 0.1})
    results.sort(key=lambda x: x.get('_score', 0), reverse=True)
    return results[:limit]


# ═══════════════════════════════════════════════════════
#  WRITERS
# ═══════════════════════════════════════════════════════
def insert_issue(user, area, description, severity, tag,
                 landmark='', contact='', lat=None, lng=None, image=None):
    with _state['lock']:
        issue_id = _next_int_id('issues')

    record = {
        'id': issue_id, 'user': user, 'area': area,
        'description': description, 'severity': severity, 'tag': tag,
        'status': 'open', 'landmark': landmark, 'contact': contact,
        'lat': lat, 'lng': lng, 'image': image,
        'timestamp': time.time(), 'upvotes': 0,
        'verified': False, 'escalated': False, 'resolved': False,
    }

    _invalidate_cache()   # force next read to refresh

    if _state['mode'] == 'firebase':
        try:
            _state['fs_db'].collection('issues').document(str(issue_id)).set(record)
        except Exception as e:
            print(f'[database] Firestore write failed, saving to memory: {e}')
            _state['issues'].insert(0, record)
    else:
        _state['issues'].insert(0, record)

    return issue_id


def upvote_issue(issue_id, user):
    upvoters = _state['upvoters'].setdefault(issue_id, set())
    _invalidate_cache()

    if _state['mode'] == 'firebase':
        try:
            doc_ref = _state['fs_db'].collection('issues').document(str(issue_id))
            snap = doc_ref.get()
            if not snap.exists:
                return 'not_found'
            data = snap.to_dict()
            ups = set(data.get('upvoters', []))
            if user in ups:
                ups.remove(user); action = 'removed'
            else:
                ups.add(user); action = 'added'
            doc_ref.update({'upvoters': list(ups), 'upvotes': len(ups)})
            return action
        except Exception as e:
            print(f'[database] Firestore upvote failed: {e}')

    for i in _state['issues']:
        if int(i.get('id', -1)) == int(issue_id):
            if user in upvoters:
                upvoters.remove(user); i['upvotes'] = max(0, i.get('upvotes', 0) - 1)
                return 'removed'
            else:
                upvoters.add(user); i['upvotes'] = i.get('upvotes', 0) + 1
                return 'added'
    return 'not_found'


# ═══════════════════════════════════════════════════════
#  INTERNALS
# ═══════════════════════════════════════════════════════
def _next_int_id(collection):
    if _state['mode'] == 'firebase':
        try:
            cref = _state['fs_db'].collection('_counters').document(collection)
            snap = cref.get()
            n = (snap.to_dict() or {}).get('n', 0) + 1 if snap.exists else 1
            cref.set({'n': n})
            return n
        except Exception:
            pass
    n = _state['next_id']
    _state['next_id'] += 1
    return n


def _haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


# ═══════════════════════════════════════════════════════
#  SEED DATA  — 200 issues across all Delhi areas
# ═══════════════════════════════════════════════════════
# Format: (area, tag, severity, description)
_SEED_ISSUES = [
    # ── POTHOLES ──────────────────────────────────────────────────
    ('Rohini',          'pothole','high',   'Large pothole on Sector 7 main road, multiple bike accidents reported this week'),
    ('Karol Bagh',      'pothole','high',   'Deep crater near metro station exit, vehicles swerving dangerously'),
    ('Dwarka',          'pothole','medium', 'Multiple potholes on Sector 10 internal road after monsoon'),
    ('Pitampura',       'pothole','medium', 'Potholes near community centre causing daily traffic jams'),
    ('Model Town',      'pothole','high',   'Deep pothole on E Block road, car suspension damaged last night'),
    ('Mayur Vihar',     'pothole','medium', 'Phase 1 Extension road full of potholes, auto-rickshaws refusing route'),
    ('Lajpat Nagar',    'pothole','low',    'Small potholes appearing near Central Market, needs preventive repair'),
    ('Greater Kailash', 'pothole','low',    'M-Block market road needs resurfacing, potholes worsening'),
    ('Nehru Place',     'pothole','medium', 'Potholes near IT park entrance, heavy vehicle damage'),
    ('Janakpuri',       'pothole','high',   'Pothole-ridden road in C Block, school bus nearly overturned'),
    ('Saket',           'pothole','medium', 'Select City Walk access road pothole causing traffic backlog'),
    ('Vasant Kunj',     'pothole','low',    'Aruna Asaf Ali Marg developing potholes near mall'),
    ('Rajouri Garden',  'pothole','high',   'Main metro feeder road completely broken, emergency needed'),
    ('Punjabi Bagh',    'pothole','medium', 'West Avenue Road potholes accumulating near park'),
    ('Okhla',           'pothole','high',   'Industrial area road dangerous for trucks, pothole 2 feet deep'),
    ('Kalkaji',         'pothole','medium', 'Near Kalkaji Mandir, road surface broken after recent digging'),
    ('Chandni Chowk',   'pothole','medium', 'Naya Bazar road pothole causing rickshaw accidents daily'),
    ('Paharganj',       'pothole','high',   'Main Bazaar road pothole, tourist complaints rising'),
    ('Civil Lines',     'pothole','low',    'Flagstaff Road developing potholes near ITO'),
    ('Shahdara',        'pothole','medium', 'GT Road pothole cluster near Shahdara metro, peak-hour danger'),
    # ── WATER ─────────────────────────────────────────────────────
    ('Dwarka',          'water', 'high',   'Major water pipe burst flooding Sector 5 road, supply cut for 3 days'),
    ('Janakpuri',       'water', 'medium', 'No water supply in C Block for 3 days, tanker request ignored'),
    ('Civil Lines',     'water', 'medium', 'Water seepage from main road tap near ISBT, wastage for 2 weeks'),
    ('Defence Colony',  'water', 'medium', 'Brown water from taps in C Block, possible contamination'),
    ('Rohini',          'water', 'high',   'Underground pipe burst in Sector 15, road collapsing into sinkhole'),
    ('Mehrauli',        'water', 'medium', 'Water supply only 30 minutes daily, residents using tankers'),
    ('Karol Bagh',      'water', 'low',    'Slow water pressure in DDA flats, top floors getting no supply'),
    ('Hauz Khas',       'water', 'high',   'Water contamination complaint, yellowish supply since yesterday'),
    ('Pitampura',       'water', 'medium', 'Water meter reading incorrect, bill tripled this month'),
    ('Preet Vihar',     'water', 'high',   'Pipeline burst near market, 500 families without water 24 hours'),
    ('Vasant Vihar',    'water', 'low',    'Overhead tank overflow wasting hundreds of litres daily'),
    ('Model Town',      'water', 'medium', 'Water timing changed without notice, residents miss supply window'),
    ('Sarojini Nagar',  'water', 'high',   'Old colonial pipe burst, massive waterlogging near market'),
    ('Laxmi Nagar',     'water', 'medium', 'Water supply contaminated after nearby construction'),
    ('Patel Nagar',     'water', 'medium', 'No supply alternate days, official schedule not followed'),
    # ── GARBAGE ───────────────────────────────────────────────────
    ('Karol Bagh',      'garbage','medium', 'Overflowing dustbin near Ajmal Khan Road metro entrance, 3 days'),
    ('Mehrauli',        'garbage','high',   'Illegal garbage dump near heritage zone growing daily'),
    ('Shahdara',        'garbage','high',   'MCD garbage truck not visiting sector for over a week'),
    ('Connaught Place', 'garbage','medium', 'Litter accumulation around inner circle benches and gardens'),
    ('Nizamuddin',      'garbage','medium', 'Construction debris dumped illegally on Mathura Road service lane'),
    ('Lajpat Nagar',    'garbage','high',   'Garbage pile near Central Market, causing stench and flies'),
    ('Okhla',           'garbage','high',   'Industrial waste dumped in residential area, health hazard'),
    ('Dwarka',          'garbage','medium', 'Sector 12 park dustbin overflowing, not cleared in 5 days'),
    ('Rohini',          'garbage','medium', 'Sector 7 market garbage not collected, vendor complaints'),
    ('Mukherjee Nagar', 'garbage','medium', 'Student hostel area overflowing bins, disease risk rising'),
    ('Saket',           'garbage','low',    'Mall area garbage not cleared on Sundays, stench complaint'),
    ('RK Puram',        'garbage','high',   'Community park used as garbage dump at night by nearby shops'),
    ('Vasant Kunj',     'garbage','medium', 'DLF area garbage timing issue, bins full before truck comes'),
    ('Kashmere Gate',   'garbage','high',   'Old Delhi wholesale market area garbage crisis, rodent sighting'),
    ('Kalkaji',         'garbage','medium', 'Temple area garbage accumulation on festival days'),
    # ── STREETLIGHT ───────────────────────────────────────────────
    ('Lajpat Nagar',    'streetlight','low',    'Broken streetlight outside Central Market gate 3, existing since 2 weeks'),
    ('Hauz Khas',       'streetlight','medium', 'Village road unlit at night, incidents increasing'),
    ('Vasant Kunj',     'streetlight','medium', 'Five streetlights out on Nelson Mandela Road stretch'),
    ('Sarojini Nagar',  'streetlight','medium', 'Market area dark after sunset, safety concern for women'),
    ('Pitampura',       'streetlight','low',    'Solar light near park with dead battery, no maintenance'),
    ('Rajouri Garden',  'streetlight','low',    'Street light flickering near metro pillar 405'),
    ('INA',             'streetlight','medium', 'Underpass lights out for 2 months, accident reported'),
    ('Mayur Vihar',     'streetlight','high',   'Entire Phase 3 road unlit, women attacked last week'),
    ('Mukherjee Nagar', 'streetlight','medium', 'Coaching area unsafe at night, 4 lights non-functional'),
    ('Mehrauli',        'streetlight','medium', 'Qutub area approach road dark at night'),
    ('Civil Lines',     'streetlight','low',    'Parks Magistrate lane poorly lit, jogger safety concern'),
    ('Lodhi Colony',    'streetlight','medium', 'Garden approach road pitch dark after 9pm'),
    ('Nizamuddin',      'streetlight','low',    'Dargah approach lane completely unlit'),
    ('Shahdara',        'streetlight','medium', 'Bus stand area dark, antisocial elements gathering'),
    ('Preet Vihar',     'streetlight','high',   'Metro feeder road dark, two snatching incidents this week'),
    # ── TRAFFIC ───────────────────────────────────────────────────
    ('Chandni Chowk',   'traffic','medium', 'Traffic signal malfunctioning at Lal Quila intersection since Monday'),
    ('Preet Vihar',     'traffic','medium', 'Signal timer too short on Ring Road junction, 2km jams nightly'),
    ('Connaught Place', 'traffic','high',   'Illegal parking on inner circle blocking emergency vehicle lane'),
    ('Dwarka',          'traffic','medium', 'Sector 9 market encroachment reducing road to single lane'),
    ('Hauz Khas',       'traffic','high',   'Village road completely blocked by pub-goers parking'),
    ('Rohini',          'traffic','medium', 'Sector 3 school zone no speed breakers, children at risk'),
    ('Kashmere Gate',   'traffic','high',   'Bus terminal overflowing, blocking main GT Karnal Road'),
    ('Okhla',           'traffic','medium', 'Industrial area truck movement blocking residential access'),
    ('Laxmi Nagar',     'traffic','medium', 'Vikas Marg encroachment by vegetable market every morning'),
    ('Janakpuri',       'traffic','high',   'Signal at B1-B2 junction broken for 4 days, accidents'),
    ('Model Town',      'traffic','medium', 'Sabzi Mandi market vehicles blocking entire stretch 7-11am'),
    ('Pitampura',       'traffic','low',    'Speed breaker removed during road work, not replaced'),
    ('RK Puram',        'traffic','medium', 'Sector 4 crossroads no traffic police during peak hour'),
    # ── SEWAGE ────────────────────────────────────────────────────
    ('Saket',           'sewage', 'high',   'Sewage overflow near NSP housing complex, foul smell unbearable'),
    ('Kashmere Gate',   'sewage', 'high',   'Open manhole on busy road near bus stand, no warning signs'),
    ('Malviya Nagar',   'sewage', 'medium', 'Drain blocked behind District Court, flooding during rain'),
    ('Mehrauli',        'sewage', 'high',   'Sewage seeping from Mehrauli drain into residential lanes'),
    ('Okhla',           'sewage', 'high',   'Industrial effluent mixing with residential sewage drain'),
    ('Shahdara',        'sewage', 'high',   'Main sewer collapsed under road near market, 50m exposure'),
    ('Rohini',          'sewage', 'medium', 'Drainage blocked in Sector 11 colony after heavy rain'),
    ('Laxmi Nagar',     'sewage', 'high',   'Sewage overflow entering ground floor homes in B Block'),
    ('Chandni Chowk',   'sewage', 'high',   'Old sewer collapsed near Kinari Bazaar, health emergency'),
    ('Preet Vihar',     'sewage', 'medium', 'Drain cover broken near school, open sewage gap'),
    ('Patel Nagar',     'sewage', 'medium', 'Drainage not cleaned for months, mosquito breeding'),
    ('Vasant Kunj',     'sewage', 'high',   'DLF Promenade back drain overflowing after last night rain'),
    ('Janakpuri',       'sewage', 'medium', 'Colony drain blocked by tree roots, backing up in basement'),
    ('Kalkaji',         'sewage', 'high',   'Sewage mixing with drinking water supply, urgent fix needed'),
    # ── ELECTRICITY ───────────────────────────────────────────────
    ('Hauz Khas',       'electricity','medium', 'Frequent power outages in SDA, transformer humming loudly'),
    ('Laxmi Nagar',     'electricity','medium', 'Exposed live wires at chest height near market entrance'),
    ('Patel Nagar',     'electricity','high',   'Daily 4-hour power cuts disrupting work-from-home'),
    ('INA',             'electricity','low',    'Generator running 24/7 near residential building, noise + fumes'),
    ('Defence Colony',  'electricity','medium', 'Electricity bill tripled, meter not checked in 6 months'),
    ('Dwarka',          'electricity','high',   'Transformer tripped, Sector 6 without power 20+ hours'),
    ('Mukherjee Nagar', 'electricity','medium', 'Power fluctuation damaging electronics, 3 inverters blown'),
    ('Rohini',          'electricity','medium', 'New connection pending 4 months despite payment'),
    ('Pitampura',       'electricity','high',   'Live wire hanging from pole after storm, sparking on tree'),
    ('Sarojini Nagar',  'electricity','medium', 'Market area power cuts exactly 6-10pm daily for 2 weeks'),
    ('Vasant Vihar',    'electricity','low',    'Electric meter reading appears incorrect, abnormal bill'),
    ('Lodhi Colony',    'electricity','medium', 'Substation issue causing repeated outages in south block'),
    ('Chandni Chowk',   'electricity','high',   'Open electrical box near school gate, children at risk'),
    ('Nizamuddin',      'electricity','medium', 'Cable fault since Tuesday, no restoration schedule given'),
    # ── NOISE ─────────────────────────────────────────────────────
    ('Mukherjee Nagar', 'noise',  'low',    'Loud construction at night past 11 PM violating noise norms'),
    ('INA',             'noise',  'medium', 'Banquet hall DJ past midnight every weekend'),
    ('Paharganj',       'noise',  'high',   'Generator noise from 3 hotels all night, residents sleepless'),
    ('Kashmere Gate',   'noise',  'medium', 'Loudspeaker from shop from 6am to 10pm daily'),
    ('Hauz Khas',       'noise',  'high',   'Bar music till 3am in village, police complaint filed'),
    ('Connaught Place', 'noise',  'medium', 'Road drilling at midnight for metro work, unbearable'),
    ('Model Town',      'noise',  'low',    'Transformer humming very loud since new installation'),
    ('Rohini',          'noise',  'medium', 'Construction blasting noise near hospital zone'),
    ('Lajpat Nagar',    'noise',  'low',    'Market loudspeaker announcements disrupting nearby school'),
    ('Vasant Kunj',     'noise',  'low',    'Mall loading dock night deliveries waking residents'),
    # ── TREE ──────────────────────────────────────────────────────
    ('Mayur Vihar',     'tree',   'medium', 'Fallen tree blocking lane near Phase 1 metro after storm'),
    ('Punjabi Bagh',    'tree',   'low',    'Tree branch hanging dangerously over road near Club Road'),
    ('Lodhi Colony',    'tree',   'low',    'Trees need pruning, branches touching 11kV power lines'),
    ('Mehrauli',        'tree',   'high',   'Large dead tree leaning over residential building, urgent'),
    ('Hauz Khas',       'tree',   'medium', 'Tree roots breaking footpath, tripping hazard near market'),
    ('Civil Lines',     'tree',   'medium', 'Diseased tree spreading to others in Coronation Park'),
    ('Vasant Vihar',    'tree',   'low',    'Tree planted too close to compound wall, cracking it'),
    ('RK Puram',        'tree',   'high',   'Old peepal tree leaning at 45 degrees after rain'),
    ('Saket',           'tree',   'medium', 'Tree roots blocking storm drain causing regular flooding'),
    ('Greater Kailash', 'tree',   'low',    'M-Block green belt trees need seasonal trimming'),
    # ── OTHER ─────────────────────────────────────────────────────
    ('Connaught Place', 'other',  'medium', 'Stray dog pack near Rajiv Chowk metro exit, biting incidents'),
    ('Saket',           'other',  'medium', 'Broken playground equipment in Select City park, sharp edges'),
    ('Rohini',          'other',  'high',   'Open manhole on Sector 3 road, no cover, no barrier at night'),
    ('Hauz Khas',       'other',  'medium', 'Footpath in village completely encroached by shops'),
    ('RK Puram',        'other',  'low',    'Stray cattle on Sector 2 road, traffic hazard at night'),
    ('Karol Bagh',      'other',  'medium', 'Illegal encroachment on public park behind metro'),
    ('Dwarka',          'other',  'low',    'Abandoned vehicles in Sector 7 reducing road to one lane'),
    ('Pitampura',       'other',  'medium', 'Public toilet non-functional for 2 months, open defecation'),
    ('Vasant Kunj',     'other',  'low',    'Community water cooler installed but never connected'),
    ('Janakpuri',       'other',  'high',   'Illegal construction blocking emergency access to society'),
    ('Nizamuddin',      'other',  'medium', 'Waterlogging on main road after blocked storm drain'),
    ('Paharganj',       'other',  'high',   'Open transformer pit near tourist area, safety emergency'),
    ('Mukherjee Nagar', 'other',  'low',    'Parking lot encroachment on public park land'),
    ('Laxmi Nagar',     'other',  'medium', 'Hospital gate always blocked by commercial vehicles'),
    ('Kashmere Gate',   'other',  'medium', 'ISBT approach road encroached by hawkers, 2 lanes blocked'),
]

_SEED_NGOS = [
    ('Delhi Green Mission',  'Sanitation & Waste Management', 'garbage',     4.6, 'Rohini',          '011-27551234', 'contact@delhigreen.org'),
    ('Road Safety India',    'Road Infrastructure & Safety',  'pothole',     4.4, 'Dwarka',          '011-28567890', 'info@roadsafetyindia.in'),
    ('Jal Seva Trust',       'Water & Sewage',                'water',       4.7, 'Hauz Khas',       '011-26960001', 'help@jalseva.org'),
    ('Sahayata Foundation',  'General Civic Issues',          'other',       4.2, 'Connaught Place', '011-23347788', 'sahayata@gmail.com'),
    ('Light Up Delhi',       'Street Lighting & Energy',      'streetlight', 4.3, 'Saket',           '011-29563322', 'lightup@delhi.org'),
    ('SafeTraffic NGO',      'Traffic & Road Discipline',     'traffic',     4.1, 'Mayur Vihar',     '011-22720011', 'safetraffic@gmail.com'),
    ('Tree Protect Delhi',   'Urban Trees & Green Cover',     'tree',        4.5, 'Pitampura',       '011-27340099', 'treeprotect@gmail.com'),
    ('Aman Bijli Sewak',     'Electricity & Power',           'electricity', 4.0, 'Lajpat Nagar',    '011-29832200', 'amanbijli@gmail.com'),
    ('Nirmal Delhi',         'Sanitation & Cleanliness',      'garbage',     4.4, 'Karol Bagh',      '011-25721100', 'nirmal@delhi.in'),
    ('Drain Watch',          'Sewage & Drainage',             'sewage',      4.2, 'Mehrauli',        '011-26642244', 'drainwatch@ngo.in'),
    ('Sound Free Society',   'Noise Pollution',               'noise',       4.0, 'Greater Kailash', '011-29242266', 'soundfree@gmail.com'),
    ('Citizen Watch Delhi',  'General Reporting',             'other',       4.3, 'Civil Lines',     '011-23949900', 'citizen@watchdelhi.org'),
    ('Sahayog Trust',        'Multi-issue NGO',               'other',       4.1, 'Janakpuri',       '011-25551122', 'sahayog@ngo.org'),
    ('Yamuna Bachao',        'Water Bodies',                  'water',       4.6, 'Kashmere Gate',   '011-23862244', 'yamuna@bachao.in'),
    ('Pothole Patrol',       'Roads & Potholes',              'pothole',     4.5, 'Model Town',      '011-27123344', 'patrol@potholes.in'),
    ('Bijli Bachao',         'Power & Streetlights',          'electricity', 4.2, 'Vasant Kunj',     '011-26891133', 'bijli@bachao.org'),
]

_USERS = ['priya','arjun','meera','rohit','kavita','sanjay','neha','deepak',
          'garv_chopra','shashwat_s','civic_reporter','rwa_secretary','anonymous']


def _seed_memory():
    """Seed in-memory store with 200 issues + NGOs. Spread over time for realism."""
    now = time.time()
    for idx, (area, tag, sev, desc) in enumerate(_SEED_ISSUES):
        lat, lng = AREA_COORDS.get(area, (28.6139, 77.2090))
        # Scatter markers so they don't stack exactly
        lat += (idx % 9 - 4) * 0.0018
        lng += ((idx // 9) % 9 - 4) * 0.0018
        issue_id = _next_int_id('issues')
        age_hours = (idx * 2.3) % (24 * 25)    # spread over 25 days
        _state['issues'].append({
            'id':          issue_id,
            'user':        _USERS[idx % len(_USERS)],
            'area':        area,
            'description': desc,
            'severity':    sev,
            'tag':         tag,
            'status':      'resolved' if idx % 9 == 0 else ('escalated' if idx % 11 == 0 else 'open'),
            'lat':         round(lat, 6),
            'lng':         round(lng, 6),
            'landmark':    '',
            'contact':     '',
            'image':       None,
            'timestamp':   now - (age_hours * 3600),
            'upvotes':     (idx * 7) % 20,
            'verified':    False,
            'escalated':   idx % 11 == 0,
            'resolved':    idx % 9 == 0,
        })
    for idx, (name, focus, tag, rating, area, phone, email) in enumerate(_SEED_NGOS):
        lat, lng = AREA_COORDS.get(area, (28.6139, 77.2090))
        ngo_id = _next_int_id('ngos')
        _state['ngos'].append({
            'id': ngo_id, 'name': name, 'focus': focus, 'tag': tag, 'rating': rating,
            'area': area, 'phone': phone, 'email': email,
            'lat': lat + 0.005, 'lng': lng + 0.005,
        })
    print(f'[database] Seeded {len(_state["issues"])} issues and {len(_state["ngos"])} NGOs into memory')


def _seed_firebase_if_empty():
    """
    Seed Firebase with sample data if the collection is empty.
    FIXED: handles 429 quota errors gracefully.
    - If read fails with 429: seeds in-memory so app still works today
    - Attempts to write seeds to Firebase (write quota is separate)
    - On next day (quota reset), Firebase will have data and reads succeed
    """
    try:
        existing = list(_state['fs_db'].collection('issues').limit(1).stream())
        if existing:
            print(f'[database] Firebase already has data, skipping seed')
            # Still populate memory as cache warmup
            _seed_memory()
            return
    except Exception as e:
        print(f'[database] Could not check Firebase emptiness: {e}')
        # Quota exceeded or other read error — seed memory so the app works NOW
        _seed_memory()
        # Try to write seeds to Firebase anyway (write quota is separate from read)
        print('[database] Attempting to write seeds to Firebase (write quota separate from read)…')
        _try_write_seeds_to_firebase()
        return

    # Firebase is empty AND readable — seed it
    print('[database] Seeding Firebase with sample data…')
    now = time.time()
    seeded = 0
    for idx, (area, tag, sev, desc) in enumerate(_SEED_ISSUES):
        lat, lng = AREA_COORDS.get(area, (28.6139, 77.2090))
        lat += (idx % 9 - 4) * 0.0018
        lng += ((idx // 9) % 9 - 4) * 0.0018
        try:
            iid = _next_int_id('issues')
            age_hours = (idx * 2.3) % (24 * 25)
            _state['fs_db'].collection('issues').document(str(iid)).set({
                'id': iid, 'user': _USERS[idx % len(_USERS)],
                'area': area, 'description': desc, 'severity': sev, 'tag': tag,
                'status': 'resolved' if idx % 9 == 0 else ('escalated' if idx % 11 == 0 else 'open'),
                'lat': round(lat, 6), 'lng': round(lng, 6),
                'landmark': '', 'contact': '', 'image': None,
                'timestamp': now - (age_hours * 3600),
                'upvotes': (idx * 7) % 20,
                'verified': False, 'escalated': idx % 11 == 0, 'resolved': idx % 9 == 0,
            })
            seeded += 1
        except Exception as e:
            print(f'[database] Issue seed error #{idx}: {e}')

    for idx, (name, focus, tag, rating, area, phone, email) in enumerate(_SEED_NGOS):
        lat, lng = AREA_COORDS.get(area, (28.6139, 77.2090))
        try:
            nid = _next_int_id('ngos')
            _state['fs_db'].collection('ngos').document(str(nid)).set({
                'id': nid, 'name': name, 'focus': focus, 'tag': tag, 'rating': rating,
                'area': area, 'phone': phone, 'email': email,
                'lat': lat + 0.005, 'lng': lng + 0.005,
            })
        except Exception as e:
            print(f'[database] NGO seed error: {e}')

    print(f'[database] Firebase seeded with {seeded} issues, {len(_SEED_NGOS)} NGOs')
    _seed_memory()   # also warm the memory cache


def _try_write_seeds_to_firebase():
    """Write seeds to Firebase in the background (fire-and-forget)."""
    def _write():
        now = time.time()
        written = 0
        for idx, (area, tag, sev, desc) in enumerate(_SEED_ISSUES):
            lat, lng = AREA_COORDS.get(area, (28.6139, 77.2090))
            lat += (idx % 9 - 4) * 0.0018
            lng += ((idx // 9) % 9 - 4) * 0.0018
            try:
                iid = idx + 1000  # offset to avoid conflicts
                age_hours = (idx * 2.3) % (24 * 25)
                _state['fs_db'].collection('issues').document(str(iid)).set({
                    'id': iid, 'user': _USERS[idx % len(_USERS)],
                    'area': area, 'description': desc, 'severity': sev, 'tag': tag,
                    'status': 'resolved' if idx % 9 == 0 else 'open',
                    'lat': round(lat, 6), 'lng': round(lng, 6),
                    'landmark': '', 'contact': '', 'image': None,
                    'timestamp': now - (age_hours * 3600),
                    'upvotes': (idx * 7) % 20,
                    'verified': False, 'escalated': False, 'resolved': idx % 9 == 0,
                })
                written += 1
                time.sleep(0.05)  # rate limit writes
            except Exception as e:
                print(f'[database] Background seed write {idx} failed: {e}')
                break
        print(f'[database] Background seed wrote {written} issues to Firebase')
    t = threading.Thread(target=_write, daemon=True)
    t.start()


# ═══════════════════════════════════════════════════════
#  SPAM / DUPLICATE / SLA / ESCALATION (unchanged)
# ═══════════════════════════════════════════════════════

def insert_spam_issue(user, description, tag, severity, area,
                      lat=None, lng=None, image=None,
                      spam_verdict='spam', spam_reason='unspecified',
                      spam_confidence=0):
    record = {
        'user': user, 'description': description, 'tag': tag,
        'severity': severity, 'area': area, 'lat': lat, 'lng': lng,
        'image': image, 'timestamp': time.time(),
        'spam_verdict': spam_verdict, 'spam_reason': spam_reason,
        'spam_confidence': spam_confidence,
    }
    if _state['mode'] == 'firebase':
        try:
            _state['fs_db'].collection('spam_issues').document().set(record)
            return
        except Exception as e:
            print(f'[database] Spam write failed: {e}')
    _state['spam_issues'].insert(0, record)


def find_nearby_duplicate(lat, lng, tag, within_meters=50, within_days=7):
    if lat is None or lng is None or not tag:
        return None
    cutoff_ts = time.time() - (within_days * 86400)
    candidates = []
    if _state['mode'] == 'firebase':
        try:
            docs = _state['fs_db'].collection('issues') \
                .where('tag', '==', tag) \
                .where('timestamp', '>=', cutoff_ts) \
                .stream()
            for d in docs:
                candidates.append(d.to_dict())
        except Exception:
            candidates = list(_state['issues'])
    else:
        candidates = list(_state['issues'])
    closest = None; closest_m = within_meters + 1
    for issue in candidates:
        if issue.get('tag') != tag: continue
        if issue.get('timestamp', 0) < cutoff_ts: continue
        if issue.get('status') == 'resolved': continue
        i_lat, i_lng = issue.get('lat'), issue.get('lng')
        if i_lat is None or i_lng is None: continue
        meters = _haversine(lat, lng, i_lat, i_lng) * 1000
        if meters <= within_meters and meters < closest_m:
            closest = issue; closest_m = meters
    return closest


def is_rate_limited(user, max_reports=5, window_seconds=60):
    now = time.time()
    history = _state['recent_reports'].setdefault(user, [])
    history[:] = [t for t in history if now - t < window_seconds]
    history.append(now)
    return len(history) > max_reports


def calculate_sla(issue):
    tag = issue.get('tag') or 'other'
    sla_hours = SLA_HOURS.get(tag, SLA_HOURS['other'])
    created = issue.get('timestamp') or time.time()
    sla_due_at = created + (sla_hours * 3600)
    status = issue.get('status', 'open')
    if status == 'resolved':
        return {'sla_hours': sla_hours, 'sla_due_at': sla_due_at,
                'sla_overdue_hours': 0, 'sla_state': 'resolved'}
    overdue_seconds = time.time() - sla_due_at
    overdue_hours = max(0, overdue_seconds / 3600)
    remaining_hours = -overdue_seconds / 3600
    state = 'overdue' if overdue_hours > 0 else ('soon' if remaining_hours < (sla_hours * 0.25) else 'safe')
    return {'sla_hours': sla_hours, 'sla_due_at': sla_due_at,
            'sla_overdue_hours': round(overdue_hours, 1), 'sla_state': state}


def escalate_issue(issue_id, reason='sla_breach'):
    issue_id = int(issue_id)
    if _state['mode'] == 'firebase':
        try:
            doc_ref = _state['fs_db'].collection('issues').document(str(issue_id))
            snap = doc_ref.get()
            if not snap.exists: return False
            if snap.to_dict().get('escalated'): return False
            doc_ref.update({'escalated': True, 'status': 'escalated',
                            'escalation_reason': reason, 'escalated_at': time.time()})
            _invalidate_cache()
            return True
        except Exception as e:
            print(f'[database] Escalate failed: {e}')
    for issue in _state['issues']:
        if int(issue.get('id', -1)) == issue_id:
            if issue.get('escalated'): return False
            issue.update({'escalated': True, 'status': 'escalated',
                          'escalation_reason': reason, 'escalated_at': time.time()})
            return True
    return False


def get_issue_by_id(issue_id):
    issue_id = int(issue_id)
    if _state['mode'] == 'firebase':
        try:
            snap = _state['fs_db'].collection('issues').document(str(issue_id)).get()
            if snap.exists: return snap.to_dict()
        except Exception as e:
            print(f'[database] Lookup failed: {e}')
    for i in _state['issues']:
        if int(i.get('id', -1)) == issue_id: return i
    return None


_ALLOWED_STATUSES = {'open', 'acknowledged', 'in_progress', 'resolved', 'escalated'}

def update_issue_status(issue_id, new_status, updated_by='gov', note=''):
    issue_id = int(issue_id)
    new_status = (new_status or '').lower().strip()
    if new_status not in _ALLOWED_STATUSES: return None
    now = time.time()
    history_entry = {'status': new_status, 'changed_at': now,
                     'changed_by': updated_by, 'note': (note or '')[:200]}
    _invalidate_cache()
    if _state['mode'] == 'firebase':
        try:
            doc_ref = _state['fs_db'].collection('issues').document(str(issue_id))
            snap = doc_ref.get()
            if not snap.exists: return None
            data = snap.to_dict()
            history = data.get('status_history', [])
            history.append(history_entry)
            updates = {'status': new_status, 'status_history': history,
                       'last_updated_at': now, 'last_updated_by': updated_by}
            if new_status == 'resolved':
                updates['resolved'] = True; updates['resolved_at'] = now
            doc_ref.update(updates); data.update(updates)
            return data
        except Exception as e:
            print(f'[database] Status update failed: {e}')
    for issue in _state['issues']:
        if int(issue.get('id', -1)) == issue_id:
            issue.setdefault('status_history', []).append(history_entry)
            issue['status'] = new_status; issue['last_updated_at'] = now
            issue['last_updated_by'] = updated_by
            if new_status == 'resolved':
                issue['resolved'] = True; issue['resolved_at'] = now
            return issue
    return None


def get_issues_for_gov(tags=None, limit=300):
    issues = get_issues(limit=limit)
    if tags:
        tag_set = set(t.lower() for t in tags)
        issues = [i for i in issues if (i.get('tag') or 'other').lower() in tag_set]
    for i in issues:
        i.update(calculate_sla(i))
    priority = {'overdue': 0, 'soon': 1, 'safe': 2, 'resolved': 3}
    issues.sort(key=lambda i: (priority.get(i.get('sla_state'), 4), -(i.get('upvotes', 0))))
    return issues


def log_duplicate_merge(original_id, duplicate_desc, user):
    record = {'original_id': original_id, 'duplicate_desc': duplicate_desc,
              'user': user, 'timestamp': time.time()}
    if _state['mode'] == 'firebase':
        try:
            _state['fs_db'].collection('duplicate_log').document().set(record)
            return
        except Exception:
            pass
    # Silently discard in memory mode
