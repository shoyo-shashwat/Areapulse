"""config/db_stub.py — stub DB used when running without the parent Areapulse database module."""
import time

SLA_HOURS = {
    'sewage': 24, 'electricity': 24, 'traffic': 24, 'noise': 24,
    'water': 48,  'streetlight': 48, 'garbage': 72, 'other': 120,
    'pothole': 168, 'tree': 168,
}
CROWD_ESCALATION_THRESHOLD = 25

_STUB = [
    {'id':1001,'area':'Rohini',        'tag':'pothole',     'severity':'high',   'description':'Large pothole on Sector 7 main road',        'status':'open',       'upvotes':28,'timestamp':time.time()-3600*5, 'lat':28.7493,'lng':77.1000,'user_name':'priya',  'assigned_to':None,          'image':None},
    {'id':1002,'area':'Karol Bagh',    'tag':'water',       'severity':'high',   'description':'Water supply contaminated near metro exit',    'status':'acknowledged','upvotes':41,'timestamp':time.time()-3600*30,'lat':28.6520,'lng':77.1904,'user_name':'arjun',  'assigned_to':'gov_water',   'image':None},
    {'id':1003,'area':'Lajpat Nagar',  'tag':'electricity', 'severity':'medium', 'description':'Streetlights out for 3 days near Central Mkt', 'status':'in_progress','upvotes':15,'timestamp':time.time()-3600*50,'lat':28.5700,'lng':77.2373,'user_name':'sneha',  'assigned_to':'gov_electricity','image':None},
    {'id':1004,'area':'Dwarka',        'tag':'sewage',      'severity':'high',   'description':'Sewer overflow near Sector 10 market',         'status':'escalated',  'upvotes':33,'timestamp':time.time()-3600*28,'lat':28.5921,'lng':77.0460,'user_name':'rahul',  'assigned_to':None,          'image':None},
    {'id':1005,'area':'Chandni Chowk', 'tag':'garbage',     'severity':'medium', 'description':'Uncollected waste for 4 days',                 'status':'open',       'upvotes':19,'timestamp':time.time()-3600*96,'lat':28.6507,'lng':77.2334,'user_name':'meera',  'assigned_to':None,          'image':None},
    {'id':1006,'area':'Rohini',        'tag':'water',       'severity':'high',   'description':'Burst pipe near market',                       'status':'open',       'upvotes':22,'timestamp':time.time()-3600*8, 'lat':28.7500,'lng':77.1100,'user_name':'amit',   'assigned_to':None,          'image':None},
    {'id':1007,'area':'Saket',         'tag':'streetlight', 'severity':'low',    'description':'3 lights out on main road',                    'status':'open',       'upvotes':7, 'timestamp':time.time()-3600*72,'lat':28.5244,'lng':77.2090,'user_name':'priti',  'assigned_to':None,          'image':None},
    {'id':1008,'area':'Hauz Khas',     'tag':'tree',        'severity':'medium', 'description':'Fallen tree blocking footpath',                'status':'acknowledged','upvotes':11,'timestamp':time.time()-3600*12,'lat':28.5494,'lng':77.2001,'user_name':'rohit',  'assigned_to':None,          'image':None},
    {'id':1009,'area':'Connaught Place','tag':'traffic',    'severity':'high',   'description':'Broken signal at junction',                    'status':'open',       'upvotes':45,'timestamp':time.time()-3600*3, 'lat':28.6315,'lng':77.2167,'user_name':'kavita', 'assigned_to':'gov_traffic', 'image':None},
    {'id':1010,'area':'Mehrauli',      'tag':'pothole',     'severity':'high',   'description':'Multiple potholes on arterial road',           'status':'open',       'upvotes':31,'timestamp':time.time()-3600*18,'lat':28.5245,'lng':77.1855,'user_name':'suresh', 'assigned_to':None,          'image':None},
]

_NGOS = [
    {'id':1,'name':'Delhi Green Mission',  'focus':'Sanitation','tags':['garbage','sewage'],          'area':'Rohini',         'phone':'011-23456789','email':'info@dghm.in',   'lat':28.73,'lng':77.12,'issues_resolved':34,'rating':4.6},
    {'id':2,'name':'Jal Seva Trust',       'focus':'Water',     'tags':['water','sewage'],            'area':'Hauz Khas',      'phone':'011-34567890','email':'info@jst.in',    'lat':28.55,'lng':77.20,'issues_resolved':28,'rating':4.7},
    {'id':3,'name':'Sahayata Foundation',  'focus':'Civic',     'tags':['other','pothole','tree'],    'area':'Connaught Place', 'phone':'011-45678901','email':'info@sahayata.in','lat':28.63,'lng':77.22,'issues_resolved':15,'rating':4.2},
    {'id':4,'name':'Light Up Delhi',       'focus':'Lighting',  'tags':['streetlight','electricity'],'area':'Saket',          'phone':'011-56789012','email':'info@lud.in',    'lat':28.53,'lng':77.21,'issues_resolved':22,'rating':4.3},
]


def init_db():
    print('[db_stub] Running on stub data — set DATABASE_URL for Postgres')


def get_issues(tag=None, status=None, limit=300):
    r = list(_STUB)
    if tag:    r = [i for i in r if i.get('tag') == tag]
    if status: r = [i for i in r if i.get('status') == status]
    return r[:limit]


def get_issue_by_id(issue_id):
    for i in _STUB:
        if int(i['id']) == int(issue_id):
            return dict(i)
    return None


def update_issue_status(issue_id, new_status, updated_by='', note=''):
    for i in _STUB:
        if int(i['id']) == int(issue_id):
            i['status'] = new_status
            return dict(i)
    return None


def get_all_ngos():
    return list(_NGOS)


def escalate_issue(issue_id, reason='sla_breach'):
    for i in _STUB:
        if int(i['id']) == int(issue_id):
            i['status'] = 'escalated'
            i['escalated'] = True
            return True
    return False


def get_issues_for_gov(user, tags=None):
    r = get_issues()
    if tags:
        r = [i for i in r if i.get('tag') in tags]
    return r
