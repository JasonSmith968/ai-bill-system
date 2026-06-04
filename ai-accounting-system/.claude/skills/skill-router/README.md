# skill-router

> You've got 183 skills installed but can't remember which one handles what?  
> Just use this one. It'll pick exactly what you need.

`skill-router` activates once per session, scans every skill you have installed, builds a lightweight index, then silently routes your requests to the right one — without you lifting a finger.

No announcements. No overhead on simple questions. The bar for triggering a skill is deliberately high: it only fires when a skill would *actually* change the quality of the response.

---

## Install

```bash
mkdir -p ~/.claude/skills/skill-router
curl -o ~/.claude/skills/skill-router/SKILL.md \
  https://raw.githubusercontent.com/pcx-wave/skill-router/main/SKILL.md
```

## Usage

**Suggest mode** (default — proposes, asks before loading):
```
/skill-router on
```
```
Skill Router active [suggest] — 42 skills indexed (GEO/SEO, Testing, Deployment, Git, Security).
```
When a skill matches your request, you'll see:
```
Suggested skills for this request:
  1. geo-audit — matches "GEO audit" + domain name
  2. geo-technical — also relevant for site-level analysis

Use skill 1, 2, or answer directly? (1/2/no)
```

**Auto mode** (silent routing with attribution):
```
/skill-router on --auto
```
Routes automatically and appends `*(via skill-name)*` to routed responses. Nothing else.

**Check what's indexed:**
```
/skill-router status
```

**See which skills you actually use:**
```
/skill-router stats
```
```
Skill Usage Stats
-----------------
Skill               | Total | Session | Last Used
--------------------+-------+---------+----------
geo-audit           |    12 |       2 | 2026-05-15
vibe                |     8 |       0 | 2026-05-10
geo-schema          |     0 |       0 | never
```
Cumulative counts are persisted to `~/.claude/skill-usage.json` across sessions — handy for spotting skills you've never actually used and cleaning them out.

**Turn it off:**
```
/skill-router off
```

---

## How it works

When you send a substantive request, the router checks the index before responding:

- Simple question or short message? → answered directly, no skill loaded
- Substantive task with a clear keyword match? → suggests or auto-routes depending on mode
- Weak or ambiguous match? → answered directly, no skill mentioned, no noise

One skill per request, max.

---

## Limits

- The skill index is session-only — routing state resets on new sessions
- Usage stats are persisted to `~/.claude/skill-usage.json` (written on each invocation)
- In very long sessions, context compression can silently reset the routing state — just re-run `/skill-router on` if you notice it stopped
- Requires skills installed at `~/.claude/skills/`

---

## License

MIT
