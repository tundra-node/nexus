# Pre-Commit Checklist

## 1. Identify What Changed

Determine which services are affected by the edit:

| Change Type | Services to Rebuild |
|-------------|-------------------|
| Frontend HTML/CSS/JS | `abyssal-frontend` only |
| Abyssal backend Python | `abyssal-backend` only |
| Prism router Python | `prism-router` only |
| Prism browser Python | `prism-browser` only |
| Prism addressbook Python | `prism-addressbook` only |
| Prism frontend | `prism-frontend` only |
| Tunnel script | `abyssal-tunnel` only |
| Nginx config | `nginx` or `prism-nginx` only |
| Docker Compose | All dependent services |
| Test files | No rebuild needed |
| Docs only | No rebuild needed |

**NEVER do a full `docker compose up --build`. Only rebuild what changed.**

## 2. Rebuild Only Changed Services

```sh
# Frontend-only change (most common)
docker compose build abyssal-frontend
docker compose up -d abyssal-frontend

# Backend-only change
docker compose build abyssal-backend
docker compose up -d abyssal-backend

# Both frontend and backend changed
docker compose build abyssal-frontend abyssal-backend
docker compose up -d abyssal-frontend abyssal-backend
```

**IMPORTANT:** If you change the backend API response format, you MUST also rebuild the frontend if the JS expects the new format. The frontend and backend are separate containers — rebuilding one does not affect the other.

**Example:** Changed `/api/abyssal/wayback/urls` from returning a list to `{"urls": [...], "total": N}`. The frontend JS expects `urlsResp.urls` and `urlsResp.total`. If only the backend is rebuilt, the frontend still gets the old list format and shows "No URLs tracked yet." Must rebuild BOTH.

## 3. Run Tests

### Test File Syntax Check (no services needed)
```sh
python -m py_compile tests/abyssal/test_api.py
python -m py_compile tests/prism/test_api.py
```

### Abyssal API Tests (requires backend running)
```sh
cd ~/Developer/nexus
python -m pytest tests/abyssal/ -v
```

### Prism API Tests (requires Prism services running)
```sh
cd ~/Developer/nexus
python -m pytest tests/prism/ -v
```

## 4. Verify Deployed Files Match Source

After rebuilding, ALWAYS verify the containers have the latest code:

```sh
# Check frontend files in container
docker exec nexus-abyssal-frontend-1 sh -c "head -5 /usr/share/nginx/html/app.js"
docker exec nexus-abyssal-frontend-1 sh -c "grep 'class DirectoryPage' /usr/share/nginx/html/app.js"

# Check backend code is updated
docker exec nexus-abyssal-backend-1 python3 -c "
import sys; sys.path.insert(0, '/app')
# Import the module you changed and verify it has the new code
from abyssal.wayback.db import get_all_tracked_urls
import inspect
sig = inspect.signature(get_all_tracked_urls)
print('get_all_tracked_urls params:', list(sig.parameters.keys()))
"

# Check API response format matches what frontend expects
docker exec nexus-abyssal-backend-1 python3 -c "
import urllib.request, json
r = urllib.request.urlopen('http://localhost:8000/api/abyssal/wayback/urls?limit=1&offset=0')
d = json.loads(r.read())
print('Response keys:', list(d.keys()))
assert 'urls' in d, 'Missing urls key!'
assert 'total' in d, 'Missing total key!'
print('OK: response format matches frontend expectations')
"
```

## 5. Update Documentation

Check if any docs need updating:

- `README.md` — if architecture, setup, or requirements changed
- `AGENTS.md` — if API endpoints, stack, or conventions changed
- `PRECOMMIT.md` — if build/test process changed
- `prism/AGENTS.md` — if Prism-specific changes
- `prism/PROJECT_SUMMARY.md` — if features or architecture changed
- `prism/FILE_MANIFEST.md` — if new files added

## 6. Final Verification Checklist

- [ ] Only changed services rebuilt (not full compose)
- [ ] Test files compile (`py_compile`)
- [ ] Tests pass (or skip documented with reason)
- [ ] Deployed files match source (verified in container)
- [ ] API response format matches frontend expectations
- [ ] Documentation updated if needed
- [ ] Commit message describes what changed and why
