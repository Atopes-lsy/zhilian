# MVP Report

Date: 2026-09-09

## Scope

Implemented first local demo for the approved MVP:

- MVP-01 Content Workspace
- MVP-02 Alchemy Generator with knowledge distillation and visible agent steps
- MVP-03 Learning Chat with Tutor / Mapper / Critic collaboration trace
- MVP-04 Demo Console

## Runtime

- API: `http://127.0.0.1:8000`
- Web: `http://127.0.0.1:5173/`
- LLM provider: mock
- Data: synthetic demo samples only

## Evidence

- `python -c "import sys, unittest; sys.path.insert(0, 'apps/api'); result = unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.discover('apps/api/tests', pattern='test_*.py')); raise SystemExit(0 if result.wasSuccessful() else 1)"` passed.
- `python apps/api/tests/smoke_api.py` passed.
- `npm run build` passed.
- Browser check completed one-click demo loading, asset generation, learning follow-up, source list and trace display.
- Browser check confirmed visible Distiller / Mapper / Tutor / Critic intermediate outputs.
- Browser check confirmed visible knowledge atoms: fact, concept, action, viewpoint, condition and risk.

## Known Limits

- The current model path is deterministic mock mode.
- Retrieval is lightweight local token scoring, not a vector database.
- Frontend visual QA has been checked on the current desktop browser; full mobile screenshot verification is still pending.
- Public deployment is not approved yet.

## Next Gate

G2 human MVP acceptance is pending after you try the local demo.
