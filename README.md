# SupportIQ — AI Customer Support Ticket Classifier

An AI-powered support triage app. Paste a customer's message and get back its
**category**, **priority** and **sentiment**, plus a **summary**, a **confidence
score** and a **ready-to-send reply** — in about four seconds.

Built with Django 6, Tailwind CSS 4, SQLite and open models via OpenRouter.

```
Ticket ──▶ Prompt ──▶ OpenRouter ──▶ JSON ──▶ Validate ──▶ Database ──▶ Dashboard
```

---

## What it does

| | |
| --- | --- |
| **Classifies** | Six categories: billing, bug, feature request, technical, account, general |
| **Prioritises** | Four levels, graded on business impact rather than how loudly the customer typed |
| **Reads tone** | Positive / neutral / negative, judged separately from severity |
| **Summarises** | One or two sentences of what the customer actually wants |
| **Drafts a reply** | Specific and polite, without inventing refunds or timelines |
| **Scores itself** | 0–100% confidence, so low-confidence tickets can go to a human |
| **Tracks history** | Search, filter, sort and paginate — scoped to your account only |
| **Charts it** | Category / priority / sentiment distribution and a 30-day volume trend |
| **Exports** | CSV and JSON, respecting whatever filters are active |

The public site (home, about, features, how-it-works, pricing, contact) is open to
everyone. Everything else lives behind a login.

---

## Quick start

**Requirements:** Python 3.12+ (developed and verified on 3.14.6). No Node needed —
Tailwind runs from a standalone binary.

```bash
git clone <your-repo-url>
cd CSA

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

**Configure.** Copy the example env file and fill it in:

```bash
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
```

Generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Get a free OpenRouter key at <https://openrouter.ai/keys> and put both into `.env`.

**Migrate and run:**

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000>.

### Working on the CSS

The compiled stylesheet (`static/css/output.css`) is gitignored, so **build it once
after cloning** or every page will render unstyled:

```bash
# Download the standalone binary once (Windows x64):
curl -L -o tailwindcss.exe https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-windows-x64.exe

# Build once:
./tailwindcss.exe -i static/css/input.css -o static/css/output.css --minify

# Or watch while developing:
./tailwindcss.exe -i static/css/input.css -o static/css/output.css --watch
```

> Tailwind v4 is configured **in CSS**, not in a `tailwind.config.js`. The palette,
> fonts and animations live in the `@theme` block at the top of `static/css/input.css`.

---

## Project layout

```
CSA/
├── support_classifier/     # settings, root urls
├── accounts/               # custom email-first user, auth, profile
├── pages/                  # public marketing site + contact form
├── tickets/                # ticket model, forms, views, export
├── dashboard/              # aggregate stats and charts
├── ai/                     # the AI layer — no Django imports
│   ├── services/
│   │   ├── ai_service.py   # orchestrator: prompt → call → parse → dict
│   │   ├── openrouter.py   # HTTP only: auth, retries, backoff
│   │   └── parser.py       # JSON extraction, repair, validation
│   ├── prompts/classifier.py
│   ├── utils/helpers.py
│   └── exceptions.py
├── templates/
├── static/
└── media/                  # user uploads (gitignored)
```

**`ai/` deliberately imports no Django.** It takes strings in and returns a dict out,
so the entire AI pipeline can be tested without a database:

```bash
python -m ai.services.ai_service
```

That classifies three built-in sample tickets and prints the parsed results. It is
the fastest way to tell whether a problem is in the AI layer or the web layer.

---

## The interesting part: surviving the model

The API call is easy. Making it *reliable* is not.

Free models are enthusiastic and imprecise. Asked to return only JSON, they will
happily return this:

````text
Sure! Here's the analysis:

```json
{
  "category": "Billing Issue",     // not one of the six allowed
  "priority": "P1",                // not one of the four allowed
  "sentiment": "frustrated",       // not one of the three allowed
  "confidence": "94%",             // a string, not a float
  "summary": "Customer double-charged...",
}                                  // trailing comma
```

Let me know if you need anything else!
````

`ai/services/parser.py` assumes exactly this and handles it:

- strips markdown fences and surrounding prose
- extracts the first **brace-balanced** object (a regex would break on a `}` inside a string value)
- repairs trailing commas, Python literals (`True`/`None`), and unquoted keys
- maps invented values back onto the real enums (`"P1"` → `high`, `"frustrated"` → `negative`)
- normalises confidence from `0.94`, `"94%"`, `94` or `"high"` to a float in 0–1
- falls back to a sensible default instead of raising, so one bad field never loses a whole classification

On top of that, `ai_service.classify_ticket()` makes three escalating attempts:
the primary model, then a stricter "JSON only" retry, then a **fallback model on a
different provider** — because free tiers rate-limit per provider, and a fallback on
the same provider fails at the same moment as the primary.

If all three fail, the ticket is still saved with a `FAILED` status and a retry
button. An AI outage never loses a customer's message and never produces a 500.

---

## Configuration

All settings come from `.env` (see `.env.example`):

| Variable | Purpose |
| --- | --- |
| `SECRET_KEY` | Django secret key — required |
| `DEBUG` | `True` in development, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames |
| `OPENROUTER_API_KEY` | Your key from <https://openrouter.ai/keys> |
| `OPENROUTER_MODEL` | Primary model slug |
| `OPENROUTER_FALLBACK_MODEL` | Used when the primary fails — keep it on a different provider |
| `OPENROUTER_TIMEOUT` | Per-request timeout in seconds (default 30) |
| `OPENROUTER_MAX_RETRIES` | Retries per model on 429/5xx (default 3) |
| `ANALYSIS_RATE_LIMIT_PER_HOUR` | Max analyses per user per hour (default 30) |

### A warning about free model slugs

**Free model availability changes constantly.** Models lose their free tier without
notice, and OpenRouter then returns `404` pointing at the paid slug. Others return
`429` when the upstream provider is saturated.

Verified working on **2026-07-15**:

| Model | Time | Notes |
| --- | --- | --- |
| `nvidia/nemotron-3-nano-30b-a3b:free` | ~3.5s | Current default — fastest |
| `openai/gpt-oss-20b:free` | ~8.7s | Current fallback, different provider |
| `nvidia/nemotron-3-super-120b-a12b:free` | ~4.2s | |
| `google/gemma-4-26b-a4b-it:free` | ~14.7s | |

If you get a persistent 404 or 429, pick a live one from
<https://openrouter.ai/models?max_price=0> and update `.env`.

---

## URL map

| URL | Auth |
| --- | --- |
| `/` `/about/` `/features/` `/how-it-works/` `/pricing/` `/contact/` | public |
| `/accounts/register/` `/accounts/login/` `/accounts/password-reset/` | public |
| `/accounts/profile/` `/accounts/logout/` | login |
| `/dashboard/` | login |
| `/tickets/` | login — history, search, filters, sorting |
| `/tickets/create/` | login |
| `/tickets/<pk>/` `/tickets/<pk>/result/` | login + owner |
| `/tickets/<pk>/reanalyze/` `/tickets/<pk>/delete/` `/tickets/<pk>/download/` | login + owner |
| `/tickets/export/csv/` `/tickets/export/json/` | login |
| `/admin/` | staff |

Requesting a ticket you don't own returns **404, not 403** — a 403 would confirm
that the ID exists.

---

## Notes on the design

**Custom user model from the first migration.** `accounts.User` drops `username` and
authenticates by email. This had to exist before the first `migrate` — swapping in a
custom user model afterwards means rebuilding the database.

**Every ticket has an owner.** `Ticket.user` is a foreign key, and every queryset in
`tickets/views.py` starts from a single `_owned(request)` helper. Scoping in one
place — rather than remembering it per view — is what stops one account reading
another's tickets. Exports go through the same helper.

**Synchronous AI calls.** A four-second call is covered by a spinner. Celery and Redis
would be the right answer at scale and are a large detour at this one; the AI layer is
already isolated behind `tickets/services.py`, so moving it to a task queue later means
changing one function.

**Dashboard aggregates in one query.** The six stat cards plus both averages come from a
single `.aggregate()` with filtered `Count`s, not seven separate `.count()` calls.

**Accessibility.** `prefers-reduced-motion` disables every animation including the hero
demo loop; charts have `role="img"` and labels; focus rings are visible for keyboard users.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Every page is unstyled | `static/css/output.css` is gitignored — run the Tailwind build |
| `404 ... unavailable for free` | That model lost its free tier — pick a new slug |
| `429 ... temporarily rate-limited` | Free tier saturated — wait, or switch provider |
| `decouple.UndefinedValueError: SECRET_KEY` | No `.env` — copy `.env.example` |
| Password reset email never arrives | Dev uses the console backend — the link prints in the `runserver` terminal |
| `DisallowedHost` in tests | Add `testserver` to `ALLOWED_HOSTS` |

---

## Security

- `.env` and `venv/` are gitignored. **Never commit `.env`** — it holds your API key.
- If a key is ever exposed, rotate it at <https://openrouter.ai/keys>.
- Before deploying: set `DEBUG=False`, set a real `ALLOWED_HOSTS`, run `collectstatic`,
  and move off SQLite if more than one worker will write concurrently.

---

## License

A learning project, not a commercial service. The pricing page is illustrative —
no payments are processed.
