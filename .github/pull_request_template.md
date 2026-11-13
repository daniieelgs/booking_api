## What and why
<!-- One paragraph. -->

Closes #<!-- issue number. One PR = one issue. Use "Refs #n" if it only partially addresses it. -->

## How it was tested
<!-- Paste the real output of what you ran (python -m pytest tests/ ...). Say if the services tier was skipped and why. -->

## Deployment impact
- [ ] Restart needed (web / worker / beat)
- [ ] Migration / schema change
- [ ] Image rebuild (Dockerfile / requirements)
- [ ] New or changed env variables
- [ ] `VERSION` bumped in `globals.py` (old -> new): 
- [ ] None

## Checklist
- [ ] Branch is `feature/*`, `fix/*` or `hotfix/*` and targets `develop` (hotfix: `master`)
- [ ] Regression test included (fixes) / tests added (features)
- [ ] No secrets, `.env`, dumps or `private/`/`public/` files
- [ ] Docs updated if behaviour or operations changed
