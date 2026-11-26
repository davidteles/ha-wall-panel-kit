# Your team's match on the panel

A slim strip on Home while your team plays: both logos, the kick-off time before the match, then the
score with the minute under it, "● Live" / "● Half time" / "Full time" and the competition. For a few
minutes after a goal, "⚽ GOAL <team>!" is the first line of the attention strip, and the strip says
"⚽ GOAL!" too. Outside the match the strip is gone, so it costs no room on a page that must fit.

![The match strip under the clock and the goal line first in the attention strip (sample home, made-up teams)](images/match.png)

It reads the [Team Tracker](https://github.com/vasqued2/ha-teamtracker) integration (Marketplace /
HACS), which gives one sensor per team with the state `PRE`, `IN`, `POST` or `NOT_FOUND` and the
ESPN details as attributes (`date`, `clock`, scores, names, logos). It works for any sport Team
Tracker covers; the wording ("Kick-off", "Half time") is football's.

## 1. Helpers

Settings → Devices & services → Helpers → Create helper:

| Helper | Type | Used for |
|---|---|---|
| `input_datetime.match_ended_at` | Date and time | when the last match ended (survives restarts) |
| `input_datetime.last_goal_at` | Date and time | optional — when the last goal went in |
| `input_text.last_goal_by` | Text | optional — which team scored it |

## 2. The blueprint that fills them

Import **Team Tracker match memory** from
[ha-blueprints](https://github.com/davidteles/ha-blueprints) (`blueprints/automation/sports/`) and pick
your Team Tracker sensor and the helpers above. It saves the final-whistle time (`IN` → `POST`) and,
for each goal during a live match, who scored and when. A goal that is taken back (the score goes
down) clears it. Restarts and the next match never count as a goal.

## 3. Two template helpers (the rules, in one place each)

Create helper → Template → **Binary sensor**. Replace `sensor.my_team` and the helper names.

**Match window** (`binary_sensor.match_window`): on from 30 minutes before kick-off, during the
match (half time included) and for one hour after the end.

```jinja
{% set s = states('sensor.my_team') %}
{% set k = state_attr('sensor.my_team', 'date') | as_datetime(none) %}
{% set ts = state_attr('input_datetime.match_ended_at', 'timestamp') %}
{% set e = ts | as_datetime(none) if ts is number else none %}
{% if s == 'IN' %}true
{% elif s == 'PRE' and k is not none %}{{ now() >= k - timedelta(minutes=30) }}
{% elif s == 'POST' and k is not none %}{% set end = e if e is not none and e > k else k + timedelta(minutes=115) %}{{ now() < end + timedelta(hours=1) }}
{% else %}false{% endif %}
```

The end time comes from the helper, never from `last_changed`, which resets when Home Assistant
restarts. If Home Assistant was down at the final whistle, it falls back to kick-off + 115 minutes.

**Goal alert** (`binary_sensor.goal_alert`, optional): on for 5 minutes after a goal, while live.

```jinja
{% set gts = state_attr('input_datetime.last_goal_at', 'timestamp') %}
{% set gby = states('input_text.last_goal_by') %}
{{ is_state('sensor.my_team', 'IN') and gts is number and gby not in ['', 'unknown', 'unavailable']
   and (now().timestamp() - gts) < 300 }}
```

Use the same window sensor anywhere else that should follow the match (a screensaver line, a
second card), so the rule lives in one place.

## Several competitions (don't use the "all" league)

Make one Team Tracker sensor **per competition** your team plays (for example `por.1`,
`uefa.champions`, `por.taca.portugal`: sport *soccer*, the league as the custom league path). Team
Tracker's "all" league reads the team's fixture list, not the live scoreboards: it never reports `IN`
or a score, and at kick-off it jumps to the next fixture, so the strip would vanish when the match
starts. Keep an "all" sensor only as a fallback for competitions ESPN has no feed for.

Then one template sensor (Helpers → Template → Sensor) picks which one to show: the live match, else
one that finished in the last 4 hours, else the nearest kick-off. List the competition sensors first:

```jinja
{%- set ids = ['sensor.my_team_league', 'sensor.my_team_champions', 'sensor.my_team_cup', 'sensor.my_team_all'] -%}
{%- set ns = namespace(live=none, post=none, post_k=none, pre=none, pre_k=none) -%}
{%- for e in ids -%}
{%- set s = states(e) -%}{%- set k = state_attr(e, 'date') | as_datetime(none) -%}
{%- if s == 'IN' and ns.live is none -%}{%- set ns.live = e -%}
{%- elif s == 'POST' and k is not none and now() < k + timedelta(hours=4) and (ns.post_k is none or k > ns.post_k) -%}{%- set ns.post = e -%}{%- set ns.post_k = k -%}
{%- elif s == 'PRE' and k is not none and (ns.pre_k is none or k < ns.pre_k) -%}{%- set ns.pre = e -%}{%- set ns.pre_k = k -%}
{%- endif -%}
{%- endfor -%}
{{ ns.live or ns.post or ns.pre or ids | last }}
```

Use it everywhere instead of a fixed sensor: in my_home.yaml as `source:` (instead of `sensor:`), and
in the two template helpers above as `{% set src = states('sensor.my_team_match_source') %}` with
`states(src)` / `state_attr(src, ...)`. Give the match memory blueprint all the competition sensors.

## 4. my_home.yaml

```yaml
match:
  sensor: sensor.my_team                 # or source: sensor.my_team_match_source (several competitions)
  window: binary_sensor.match_window
  goal_alert: binary_sensor.goal_alert   # optional, with goal_by
  goal_by: input_text.last_goal_by
```

Run `python tools/render.py` again. The strip sits under the clock and weather card and is 56 px
tall, the same as the other alert cards, so a page that fits today still fits during a match
(measure your own tablet if its Home page is already full).

## Remove it

Delete the `match:` block and render again; then delete the helpers and the blueprint automation.
