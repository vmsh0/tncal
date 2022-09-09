from flask import Flask, request, render_template, url_for, redirect, make_response, g
from flask_caching import Cache
from werkzeug.routing import BaseConverter
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
import json
import re

from typing import Dict, Tuple, List, Any

ACTIVITIES_URL = 'https://easyacademy.unitn.it/AgendaStudentiUnitn/combo.php?sw=ec_&aa=2022&page=attivita'
CALENDAR_URL = 'https://easyacademy.unitn.it/AgendaStudentiUnitn/export/ec_download_ical_list.php?include=attivita&anno=2022&attivita[]={}&date=08-09-2022'
UAL_TIMEOUT = 60*60*8  # 8 hours
ACTIVITY_TIMEOUT = 60*60  # 1 hour
VEVENT_REGEX = r"BEGIN:VEVENT.*?END:VEVENT"  # regex for lazy match

class ListConverter(BaseConverter):
  @staticmethod
  def _n(l: List):  # removes duplicates from a list
    return list(set(l))
  def to_python(self, v):
    return self._n(v.split(','))
  def to_url(self, vv):
    return ','.join(super(ListConverter, self).to_url(v) for v in self._n(vv))

activities: Dict[str, Tuple[str, str]] = {}

config = {
    'APP_NAME': 'UNITN\'s Shitty Calendar Webapp Work-Arounder'
}

app = Flask(__name__)
app.config.from_mapping(config)
app.url_map.converters['list'] = ListConverter
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})

@app.template_filter('l_with')
def _jinja_l_with(value: List, el: Any):
  return value + [el]

@app.template_filter('l_without')
def _jinja_l_without(value: List, el: Any):
  value = value[:]
  value.remove(el)
  return value

@app.get('/')
def index():
  return redirect(url_for('builder'))

@app.route('/builder', defaults={'acc': []}, methods=['GET', 'POST'])
@app.route('/builder/<list:acc>', methods=['GET', 'POST'])
def builder(acc: List[str]):
  s = request.form['suggest'] if request.method == 'POST' else ''
  query = None
  if s == '*': query = ''
  elif s != '': query = s
  context = {
      'activities': activities,
      'acc': acc,
      'suggest': s,
      'suggestions': suggest(query) if query is not None else None
  }
  return render_template('builder.html', **context)

@app.post('/ual')
@cache.cached(timeout=UAL_TIMEOUT)
def ual_cached():
  return ual()

@app.post('/ual/force')
def ual():
  r = requests.get(ACTIVITIES_URL)
  if not r.ok:
    return f"sc{t.status_code}", 500
  t = r.text  # quite inefficient, but raw urllib3 response doesn't allow seeking to skip the crap
              # we get as a prefix. todo: proxy class to skip the crap
  j = json.loads(t[t.find('['):t.rfind(';')])
  newactivities = {}  # use a new instance to avoid data races - god bless the GIL (not)
  for a in j:
    if a['pub_type'] != 'cal': continue
    newactivities[a['valore']] = a['nome_insegnamento'], a['docente']
  global activities
  activities = newactivities
  return 'ok'

@app.get('/suggest/', defaults={'query': ''})
@app.get('/suggest/<path:query>')
def suggest(query: str):
  query = query.lower()
  return {k: (i, p) for k, (i, p) in activities.items()
                                  if i.lower().find(query) != -1 or p.lower().find(query) != -1}

@app.get('/calendar/<list:acc>')
def calendar(acc: List[str]):
  from datetime import datetime
  activities_ = activities
  valid = map(lambda a: a in activities_, acc)
  if False in valid:
    return 'wüt', 406
  timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
  fname = f"{request.host}-{timestamp}.ics"
  r = make_response(render_template(
      'calendar.ics',
      vevents='\n'.join([get_activity(a) for a in acc if a is not None])
      ), 200)
  r.content_type = 'text/calendar'
  r.headers['Content-Disposition'] = f"attachment; filename={fname}"
  return r

@cache.memoize(timeout=ACTIVITY_TIMEOUT, response_filter=lambda r: r is not None)
def get_activity(activity: str):
  r = requests.get(CALENDAR_URL.format(activity))
  if not r.ok:
    return None
  return '\n'.join(re.findall(VEVENT_REGEX, r.text, re.MULTILINE | re.DOTALL))

ual()

