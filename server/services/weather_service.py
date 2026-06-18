"""services/weather_service.py — proxies to CivicAlert weather engine with 5-min TTL cache."""
import time, urllib.request, urllib.parse, json
from config.settings import CIVICALERT_URL

_cache: dict = {}
_TTL = 300


def get_weather_risk(area: str, lat=None, lng=None) -> dict:
    key = f'{area}:{lat}:{lng}'
    cached = _cache.get(key)
    if cached and (time.time() - cached['ts']) < _TTL:
        return {**cached['data'], 'cached': True}

    params = {}
    if lat is not None: params['lat'] = lat
    if lng is not None: params['lng'] = lng
    url = f'{CIVICALERT_URL}/api/weather/{urllib.parse.quote(str(area))}'
    if params:
        url += '?' + urllib.parse.urlencode(params)

    try:
        req = urllib.request.Request(url, headers={'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        _cache[key] = {'data': data, 'ts': time.time()}
        return {**data, 'cached': False}
    except Exception as e:
        print(f'[weather_service] CivicAlert unreachable for {area}: {e}')
        return {'area': area, 'risk_level': 'UNKNOWN', 'overall_risk': 0,
                'current_condition': 'Unavailable', 'curr_rain': 0, 'curr_temp': None,
                'storm_now': False, 'ai_bulletin': 'CivicAlert engine unavailable.',
                'error': True, 'cached': False}
