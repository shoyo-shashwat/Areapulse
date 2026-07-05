"""
database.py — Postgres/Neon backend for AreaPulse Portal
Drop-in replacement for the Firebase database module.
Exact same public API: init_db, get_issues, get_issue_by_id,
update_issue_status, get_all_ngos, escalate_issue, get_issues_for_gov,
SLA_HOURS, CROWD_ESCALATION_THRESHOLD.

Uses DATABASE_URL from .env (Neon Postgres).
Falls back to in-memory demo data if Postgres is unreachable.
"""

import os
import time
import json
import threading
from datetime import datetime

# ── Constants (same as existing app) ─────────────────────────
SLA_HOURS = {
    'sewage':      24,
    'electricity': 24,
    'traffic':     24,
    'noise':       24,
    'water':       48,
    'streetlight': 48,
    'garbage':     72,
    'other':       120,
    'pothole':     168,
    'tree':        168,
}
CROWD_ESCALATION_THRESHOLD = 25

# ── Postgres connection ───────────────────────────────────────
_DB_URL   = os.environ.get('DATABASE_URL', '')
_pg_conn  = None
_pg_lock  = threading.Lock()
_pg_ok    = False


def _get_conn():
    """Return a live psycopg2 connection, reconnecting if needed."""
    global _pg_conn, _pg_ok
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        return None

    with _pg_lock:
        # Test existing connection
        if _pg_conn:
            try:
                _pg_conn.cursor().execute('SELECT 1')
                return _pg_conn
            except Exception:
                try: _pg_conn.close()
                except Exception: pass
                _pg_conn = None

        if not _DB_URL:
            return None

        try:
            _pg_conn = psycopg2.connect(_DB_URL, connect_timeout=10)
            _pg_conn.autocommit = True
            _pg_ok = True
            return _pg_conn
        except Exception as e:
            print(f'[database] Postgres connect failed: {e}')
            _pg_ok = False
            return None


def _row_to_issue(row, cols):
    """Convert a DB row + column list to an issue dict."""
    d = dict(zip(cols, row))
    # Normalise field names to match what the portal expects
    if 'created_at' in d and 'timestamp' not in d:
        v = d['created_at']
        d['timestamp'] = v.timestamp() if hasattr(v, 'timestamp') else float(v or time.time())
    if 'updated_at' in d and 'updated_at' not in d:
        pass
    # Parse JSON fields
    for jf in ('metadata', 'extra', 'status_history'):
        if jf in d and isinstance(d[jf], str):
            try: d[jf] = json.loads(d[jf])
            except Exception: d[jf] = {}
    # Ensure numeric id
    if 'id' in d:
        try: d['id'] = int(d['id'])
        except Exception: pass
    return d


# ── Fallback demo data (used when Postgres unreachable) ───────
_DEMO = [
    {'id':1001,'area':'Rohini','tag':'pothole','severity':'high',
     'description':'Large pothole on Sector 7 main road','status':'open',
     'upvotes':28,'timestamp':time.time()-3600*5,'lat':28.7493,'lng':77.1000,
     'user_name':'priya','assigned_to':None,'image':None},
    {'id':1002,'area':'Karol Bagh','tag':'water','severity':'high',
     'description':'Water supply contaminated near metro exit','status':'acknowledged',
     'upvotes':41,'timestamp':time.time()-3600*30,'lat':28.6520,'lng':77.1904,
     'user_name':'arjun','assigned_to':'gov_water','image':None},
    {'id':1003,'area':'Lajpat Nagar','tag':'electricity','severity':'medium',
     'description':'Streetlights out for 3 days near Central Market','status':'in_progress',
     'upvotes':15,'timestamp':time.time()-3600*50,'lat':28.5700,'lng':77.2373,
     'user_name':'meera','assigned_to':'gov_electricity','image':None},
    {'id':1004,'area':'Chandni Chowk','tag':'garbage','severity':'medium',
     'description':'Overflowing bins near Fatehpuri mosque','status':'open',
     'upvotes':8,'timestamp':time.time()-3600*80,'lat':28.6507,'lng':77.2334,
     'user_name':'rohit','assigned_to':None,'image':None},
    {'id':1005,'area':'Dwarka','tag':'sewage','severity':'high',
     'description':'Sewage overflow on Sector 10 road','status':'open',
     'upvotes':33,'timestamp':time.time()-3600*20,'lat':28.5921,'lng':77.0460,
     'user_name':'kavita','assigned_to':None,'image':None},
    {'id':1006,'area':'Vasant Kunj','tag':'tree','severity':'high',
     'description':'Fallen tree blocking main road after storm','status':'escalated',
     'upvotes':52,'timestamp':time.time()-3600*10,'lat':28.5200,'lng':77.1569,
     'user_name':'sanjay','assigned_to':None,'image':None},
    {'id':1007,'area':'Saket','tag':'traffic','severity':'low',
     'description':'Signal at Select City Walk broken','status':'resolved',
     'upvotes':6,'timestamp':time.time()-3600*100,'lat':28.5245,'lng':77.2066,
     'user_name':'neha','assigned_to':'gov_traffic','image':None},
    {'id':1008,'area':'Pitampura','tag':'pothole','severity':'medium',
     'description':'Potholes near community centre','status':'open',
     'upvotes':12,'timestamp':time.time()-3600*60,'lat':28.7100,'lng':77.1279,
     'user_name':'deepak','assigned_to':None,'image':None},
]
_DEMO_NGOS = [
    {'id':1,'name':'Delhi Green Mission','focus':'Sanitation','tag':'garbage',
     'rating':4.6,'area':'Rohini','phone':'011-27551234',
     'email':'contact@delhigreen.org','lat':28.75,'lng':77.10,'issues_resolved':34},
    {'id':2,'name':'Jal Seva Trust','focus':'Water & Sewage','tag':'water',
     'rating':4.7,'area':'Hauz Khas','phone':'011-26960001',
     'email':'help@jalseva.org','lat':28.54,'lng':77.22,'issues_resolved':28},
    {'id':3,'name':'Road Safety India','focus':'Roads','tag':'pothole',
     'rating':4.4,'area':'Dwarka','phone':'011-28567890',
     'email':'info@roadsafetyindia.in','lat':28.59,'lng':77.05,'issues_resolved':19},
]


# ── Schema creation ───────────────────────────────────────────
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS issues (
    id            SERIAL PRIMARY KEY,
    area          TEXT,
    tag           TEXT,
    severity      TEXT DEFAULT 'medium',
    description   TEXT,
    status        TEXT DEFAULT 'open',
    upvotes       INTEGER DEFAULT 0,
    lat           DOUBLE PRECISION,
    lng           DOUBLE PRECISION,
    user_name     TEXT,
    assigned_to   TEXT,
    image_url     TEXT,
    photo         TEXT,
    contact       TEXT,
    escalated     BOOLEAN DEFAULT FALSE,
    status_history JSONB DEFAULT '[]',
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ngos (
    id             SERIAL PRIMARY KEY,
    name           TEXT NOT NULL,
    focus          TEXT,
    tag            TEXT,
    rating         REAL DEFAULT 4.0,
    area           TEXT,
    phone          TEXT,
    email          TEXT,
    lat            DOUBLE PRECISION,
    lng            DOUBLE PRECISION,
    issues_resolved INTEGER DEFAULT 0,
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS issues_status_idx ON issues(status);
CREATE INDEX IF NOT EXISTS issues_tag_idx    ON issues(tag);
CREATE INDEX IF NOT EXISTS issues_area_idx   ON issues(area);
CREATE INDEX IF NOT EXISTS issues_created_idx ON issues(created_at DESC);
"""


# Cache of actual column names and types discovered at runtime
_ISSUE_COLS  = None   # set of column names
_ISSUE_TYPES = {}     # col_name -> data_type
_ISSUES_TABLE = 'issues'


def _discover_schema(cur):
    """Read actual column names + types from the database."""
    global _ISSUE_COLS, _ISSUE_TYPES
    if _ISSUE_COLS is not None:
        return _ISSUE_COLS
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'issues'
        ORDER BY ordinal_position
    """)
    rows = cur.fetchall()
    _ISSUE_COLS  = {r[0] for r in rows}
    _ISSUE_TYPES = {r[0]: r[1] for r in rows}
    print(f'[database] issues columns: {sorted(_ISSUE_COLS)}')
    return _ISSUE_COLS


def _ts_expr(col):
    """Return SQL expression to get Unix epoch from a column regardless of its type."""
    dtype = _ISSUE_TYPES.get(col, '')
    # Already a numeric epoch (double precision, real, integer, bigint, numeric)
    if any(t in dtype for t in ('double','real','int','numeric','float')):
        return f'{col}::float'
    # Timestamp or timestamptz — use EXTRACT
    if 'timestamp' in dtype or 'date' in dtype:
        return f'EXTRACT(EPOCH FROM {col})'
    # Unknown — try casting to float, fall back to current time
    return f'COALESCE({col}::float, {time.time()})'


def _col(cols, *candidates):
    """Return first candidate column that exists, or None."""
    for c in candidates:
        if c in cols:
            return c
    return None


def init_db():
    """Create tables if they don't exist. Adapts to existing schema."""
    conn = _get_conn()
    if not conn:
        print('[database] Postgres unavailable — using demo data')
        return

    try:
        cur = conn.cursor()

        # Create tables only if they don't exist at all
        cur.execute("""
            CREATE TABLE IF NOT EXISTS issues (
                id            SERIAL PRIMARY KEY,
                area          TEXT,
                tag           TEXT,
                severity      TEXT DEFAULT 'medium',
                description   TEXT,
                status        TEXT DEFAULT 'open',
                upvotes       INTEGER DEFAULT 0,
                lat           DOUBLE PRECISION,
                lng           DOUBLE PRECISION,
                user_name     TEXT,
                assigned_to   TEXT,
                image_url     TEXT,
                contact       TEXT,
                escalated     BOOLEAN DEFAULT FALSE,
                status_history JSONB DEFAULT '[]',
                created_at    TIMESTAMPTZ DEFAULT NOW(),
                updated_at    TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ngos (
                id             SERIAL PRIMARY KEY,
                name           TEXT NOT NULL,
                focus          TEXT,
                tag            TEXT,
                rating         REAL DEFAULT 4.0,
                area           TEXT,
                phone          TEXT,
                email          TEXT,
                lat            DOUBLE PRECISION,
                lng            DOUBLE PRECISION,
                issues_resolved INTEGER DEFAULT 0,
                created_at     TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute('CREATE INDEX IF NOT EXISTS issues_status_idx ON issues(status)')
        cur.execute('CREATE INDEX IF NOT EXISTS issues_tag_idx    ON issues(tag)')
        cur.execute('CREATE INDEX IF NOT EXISTS issues_area_idx   ON issues(area)')

        # Discover actual schema
        cols = _discover_schema(cur)

        # Seed if empty
        cur.execute('SELECT COUNT(*) FROM issues')
        if cur.fetchone()[0] == 0:
            print('[database] Seeding demo issues…')
            ts_col  = _col(cols, 'created_at', 'timestamp', 'reported_at')
            upd_col = _col(cols, 'updated_at', 'modified_at')
            for iss in _DEMO:
                try:
                    insert_cols = ['area','tag','severity','description','status',
                                   'upvotes','lat','lng','user_name']
                    insert_vals = [iss['area'],iss['tag'],iss['severity'],
                                   iss['description'],iss['status'],iss['upvotes'],
                                   iss['lat'],iss['lng'],iss['user_name']]
                    if 'assigned_to' in cols:
                        insert_cols.append('assigned_to')
                        insert_vals.append(iss['assigned_to'])
                    if ts_col:
                        insert_cols.append(ts_col)
                        insert_vals.append('NOW()')  # placeholder
                    placeholders = ','.join(['%s']*len(insert_vals))
                    cur.execute(
                        f"INSERT INTO issues ({','.join(insert_cols)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING",
                        insert_vals
                    )
                except Exception as seed_err:
                    print(f'[database] seed row error: {seed_err}')

        # Seed NGOs if empty
        cur.execute('SELECT COUNT(*) FROM ngos')
        if cur.fetchone()[0] == 0:
            for ngo in _DEMO_NGOS:
                try:
                    cur.execute("""
                        INSERT INTO ngos (name,focus,tag,rating,area,phone,email,lat,lng,issues_resolved)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
                    """, (ngo['name'],ngo['focus'],ngo['tag'],ngo['rating'],
                          ngo['area'],ngo['phone'],ngo['email'],ngo['lat'],ngo['lng'],
                          ngo['issues_resolved']))
                except Exception: pass

        print('[database] Postgres ready ✓')
    except Exception as e:
        print(f'[database] init_db error: {e}')


# ── Public API ────────────────────────────────────────────────

def get_issues(tag=None, status=None, limit=300):
    conn = _get_conn()
    if not conn:
        r = list(_DEMO)
        if tag:    r = [i for i in r if i.get('tag') == tag]
        if status: r = [i for i in r if i.get('status') == status]
        return r[:limit]

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cols = _discover_schema(cur)

        # Build SELECT dynamically based on what columns actually exist
        sel = ['id', 'area', 'tag', 'severity', 'description', 'status']
        sel.append('upvotes'     if 'upvotes'     in cols else '0 AS upvotes')
        sel.append('lat'         if 'lat'         in cols else 'NULL::float AS lat')
        sel.append('lng'         if 'lng'         in cols else 'NULL::float AS lng')
        sel.append('user_name'   if 'user_name'   in cols else 'NULL AS user_name')
        sel.append('assigned_to' if 'assigned_to' in cols else 'NULL AS assigned_to')
        sel.append('contact'     if 'contact'     in cols else 'NULL AS contact')
        sel.append('escalated'   if 'escalated'   in cols else 'FALSE AS escalated')
        sel.append('status_history' if 'status_history' in cols else "'[]'::jsonb AS status_history")

        # Image — try common column names
        img_col = _col(cols, 'image_url', 'photo', 'image', 'photo_url', 'img')
        sel.append(f'{img_col} AS image' if img_col else 'NULL AS image')

        # Timestamp — detect type and use correct expression
        ts_col = _col(cols, 'created_at', 'timestamp', 'reported_at', 'filed_at')
        if ts_col:
            sel.append(f'{_ts_expr(ts_col)} AS timestamp')
        else:
            sel.append(f'{time.time()} AS timestamp')

        upd_col = _col(cols, 'updated_at', 'modified_at', 'last_updated')
        if upd_col:
            sel.append(f'{_ts_expr(upd_col)} AS updated_at')

        order_col = ts_col or 'id'
        wheres, vals = [], []
        if tag:    wheres.append('tag = %s');    vals.append(tag)
        if status: wheres.append('status = %s'); vals.append(status)
        where = ('WHERE ' + ' AND '.join(wheres)) if wheres else ''

        cur.execute(f"""
            SELECT {', '.join(sel)}
            FROM issues {where}
            ORDER BY {order_col} DESC
            LIMIT %s
        """, vals + [limit])

        result = []
        for row in cur.fetchall():
            d = dict(row)
            d['id'] = int(d['id'])
            d['timestamp'] = float(d.get('timestamp') or time.time())
            if isinstance(d.get('status_history'), str):
                try: d['status_history'] = json.loads(d['status_history'])
                except: d['status_history'] = []
            result.append(d)
        return result
    except Exception as e:
        print(f'[database] get_issues error: {e}')
        return list(_DEMO)


def get_issue_by_id(iid):
    conn = _get_conn()
    if not conn:
        for i in _DEMO:
            if int(i['id']) == int(iid): return i
        return None

    try:
        import psycopg2.extras
        # Reuse get_issues logic by fetching all and filtering — simpler, consistent
        all_issues = get_issues(limit=1000)
        for i in all_issues:
            if int(i.get('id',0)) == int(iid):
                return i
        return None
    except Exception as e:
        print(f'[database] get_issue_by_id error: {e}')
        return None


def update_issue_status(iid, status, updated_by='gov', note=''):
    conn = _get_conn()
    if not conn:
        for i in _DEMO:
            if int(i['id']) == int(iid):
                i['status'] = status
                return i
        return None

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cols = _discover_schema(cur)

        # Build UPDATE using only columns that exist
        sets = ['status = %s']
        vals = [status]

        upd_col = _col(cols, 'updated_at', 'modified_at', 'last_updated')
        if upd_col:
            sets.append(f'{upd_col} = NOW()')

        if 'escalated' in cols:
            sets.append("escalated = CASE WHEN %s = 'escalated' THEN TRUE ELSE escalated END")
            vals.append(status)

        if 'status_history' in cols:
            history_entry = json.dumps({
                'status': status, 'by': updated_by,
                'note': note, 'at': datetime.utcnow().isoformat()
            })
            sets.append("status_history = COALESCE(status_history,'[]'::jsonb) || %s::jsonb")
            vals.append(f'[{history_entry}]')

        vals.append(int(iid))
        cur.execute(f"""
            UPDATE issues SET {', '.join(sets)}
            WHERE id = %s RETURNING id, status
        """, vals)
        row = cur.fetchone()
        if row:
            return {'id': int(row['id']), 'status': row['status'], 'ok': True}
        return None
    except Exception as e:
        print(f'[database] update_issue_status error: {e}')
        return None


def escalate_issue(iid, reason='sla_breach'):
    return update_issue_status(iid, 'escalated', updated_by='system', note=reason)


def get_issues_for_gov(user, tags=None):
    issues = get_issues()
    if tags:
        issues = [i for i in issues if i.get('tag') in tags]
    return issues


def get_all_ngos():
    conn = _get_conn()
    if not conn:
        return list(_DEMO_NGOS)

    try:
        import psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute('SELECT * FROM ngos ORDER BY rating DESC')
        rows = cur.fetchall()
        return [dict(r) for r in rows] if rows else list(_DEMO_NGOS)
    except Exception as e:
        print(f'[database] get_all_ngos error: {e}')
        return list(_DEMO_NGOS)