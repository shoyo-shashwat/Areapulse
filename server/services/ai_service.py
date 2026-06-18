"""services/ai_service.py — all Groq AI calls. No Flask imports."""
import json, time
from config.settings import GROQ_API_KEY

MODEL = 'meta-llama/llama-4-scout-17b-16e-instruct'

try:
    from groq import Groq
    _client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
except ImportError:
    _client = None


def gov_briefing(issues):
    open_i   = [i for i in issues if i.get('status') != 'resolved']
    breached = [i for i in open_i if i.get('sla_state') == 'breached']
    by_area  = {}
    for i in open_i:
        a = i.get('area', 'Unknown')
        by_area[a] = by_area.get(a, 0) + 1
    top_area = max(by_area, key=by_area.get) if by_area else 'N/A'

    if not _client or not open_i:
        return (f'You have <strong>{len(open_i)} active issues</strong>. '
                f'<strong>{len(breached)} SLA-breached</strong>. '
                f'Hotspot: <strong>{top_area}</strong>. Set GROQ_API_KEY for full AI briefings.')
    try:
        resp = _client.chat.completions.create(model=MODEL, max_tokens=120, temperature=0.3,
            messages=[
                {'role':'system','content':'Write a 2-3 sentence gov briefing. Use <strong> for numbers. Max 60 words.'},
                {'role':'user','content':f'Open:{len(open_i)} Breached:{len(breached)} Top:{top_area}'},
            ])
        return (resp.choices[0].message.content or '').strip()
    except Exception:
        return (f'<strong>{len(open_i)} open issues</strong>. '
                f'<strong>{len(breached)} SLA-breached</strong>. '
                f'Hotspot: <strong>{top_area}</strong>.')


def ngo_recommend(issues, tags, area):
    matching = [i for i in issues if i.get('tag') in tags and i.get('status') != 'resolved']
    high     = [i for i in matching if i.get('severity') == 'high']
    if not _client or not matching:
        return (f'<strong>{len(matching)} matching issues</strong> in your focus area. '
                f'{len(high)} are high severity — prioritise these first.')
    issue_list = '\n'.join(
        f"#{i.get('id')} {i.get('area')} {i.get('tag')} {i.get('severity')} — {(i.get('description',''))[:50]}"
        for i in matching[:8]
    )
    try:
        resp = _client.chat.completions.create(model=MODEL, max_tokens=100, temperature=0.3,
            messages=[
                {'role':'system','content':f'NGO advisor for {", ".join(tags)} in {area}. Recommend 1-2 issues. Max 50 words.'},
                {'role':'user','content':issue_list},
            ])
        return (resp.choices[0].message.content or '').strip()
    except Exception:
        return f'{len(matching)} matching issues found in your focus area.'


def chat_stream(message, role, user_info, history=None, issues_snapshot=None):
    """Generator yielding SSE chunks."""
    if not _client:
        demo = (f'AI demo mode — no GROQ_API_KEY. '
                f'{len(issues_snapshot or [])} active issues available for analysis.')
        for word in demo.split():
            yield f'data: {json.dumps({"content": word + " "})}\n\n'
            time.sleep(0.04)
        yield 'data: [DONE]\n\n'
        return

    open_i   = [i for i in (issues_snapshot or []) if i.get('status') != 'resolved']
    breached = [f"#AP-{i['id']}" for i in open_i if i.get('sla_state') == 'breached'][:5]

    if role == 'gov':
        sys_p = (f"You are AreaPulse AI Copilot for {user_info.get('name','Officer')} "
                 f"({user_info.get('dept','')}).\n"
                 f"Open issues: {len(open_i)}. SLA breached: {', '.join(breached) or 'none'}.\n"
                 f"Give concise, actionable municipal advice. Max 150 words.")
    else:
        sys_p = (f"You are AreaPulse AI Advisor for {user_info.get('name','NGO')} "
                 f"({user_info.get('dept','')}).\n"
                 f"Focus: {', '.join(user_info.get('tags',[]))}. {len(open_i)} matching issues.\n"
                 f"Recommend resource deployment. Max 150 words.")

    msgs = [{'role':'system','content':sys_p}]
    for h in (history or [])[-8:]:
        if h.get('role') in ('user','assistant') and h.get('content'):
            msgs.append({'role':h['role'],'content':h['content']})
    msgs.append({'role':'user','content':message})

    try:
        stream = _client.chat.completions.create(
            model=MODEL, messages=msgs, max_tokens=600, temperature=0.3, stream=True)
        for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield f'data: {json.dumps({"content": delta})}\n\n'
        yield 'data: [DONE]\n\n'
    except Exception as e:
        yield f'data: {json.dumps({"content": f"Error: {type(e).__name__}"})}\n\n'
        yield 'data: [DONE]\n\n'
