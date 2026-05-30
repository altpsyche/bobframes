# Repo bootstrap (one-time)

> Carved from CLI_PLAN §19. Run once, before [c01](commits/v01/c01_version.md). Version control from
> the start; the existing capture project becomes a sample-data consumer only. This `docs/plan/` set
> is the repo's first content (the carve is "step 0").

## Location
`c:\Users\vsiva\dev\bobframes\` (matches the existing `c:\Users\vsiva\dev\bobreview` pattern).

## Steps

```powershell
# 1. Init (the docs/plan/ tree already exists here from the carve)
cd c:\Users\vsiva\dev\bobframes
git init -b main

# 2. Copy current _analysis/ tree INTO bobframes/ (package named bobframes from the start — ADR-7)
robocopy "c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\_analysis" `
         "c:\Users\vsiva\dev\bobframes\bobframes" `
         /E /XD __pycache__ /XF *.pyc CLI_PLAN.md

# 2b. Sweep the old name in the copied source (this is the collapsed-c14 mechanical work, ADR-7):
#     - `from _analysis…` / `import _analysis…`            -> `bobframes…`
#     - `'-m', '_analysis.parsers.parse_init_state'`        -> `'bobframes.parsers.parse_init_state'`
#     - `prog='_analysis.reports.…'`                        -> `prog='bobframes.reports.…'`
#     - the replay path literal is handled by c12 (replay_script_path)
#     The package must import cleanly as `bobframes` before c01 begins.

# 3. Root scaffold files ALREADY created (pre-git, this session):
#    pyproject.toml (name='bobframes')  README.md  CHANGELOG.md  LICENSE  .gitignore  CLAUDE.md
#    docs/plan/ (this set)              .github/workflows/ (empty until c17)

# 4. First commit — includes the package tree AND docs/plan AND product stubs
git add .
git commit -m "Initial commit: extract _analysis pipeline + plan doc set
Source: c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\_analysis
At schema_version=3, stable_keys version=1 (post-extraction baseline)."

# 5. Remote (manual / gh CLI)
gh repo create mayhem-studios/bobframes --private --source=. --remote=origin --push
```

## `.gitignore`
```
# Python
__pycache__/
*.py[cod]
*$py.class
.Python
*.egg-info/
.eggs/
*.egg
build/
dist/
wheels/
pip-wheel-metadata/

# Virtual env
.venv/
venv/
env/

# Editor
.idea/
.vscode/
*.swp
.DS_Store

# Test artifacts
.pytest_cache/
.coverage
htmlcov/
.tox/

# Project-specific: never commit user data, manifests, or rendered output
**/_data/
**/_reports/
**/_stage/
**/_tmp/
**/index.html
**/*.parquet
**/*.rdc
**/*.zip.xml
**/_manifest.json
**/done.marker

# Exception: bundled synthetic test data
!bobframes/tests/data/synthetic/
!bobframes/tests/data/synthetic/**/*.parquet

# Bobframes config
.bobframes.toml

# Generated docs (docs/plan/ IS tracked — only built output is ignored)
docs/_build/

# OS
Thumbs.db
```

## Source-project cleanup (separate, after the repo ships v0.1)
```powershell
pipx install bobframes
bobframes check
bobframes ingest "c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026" --force
# verify identical output to the legacy embedded run, then:
Remove-Item -Recurse -Force "c:\Users\vsiva\Downloads\RDC mainline r110565 25-05-2026\_analysis"
```
The capture project becomes a pure data folder; no Python in it. The `CLI_PLAN.md` carved into this
repo's [archive](CLI_PLAN.archive.md) preserves the source — nothing is lost when `_analysis/` goes.

## Branch protection (suggested, via GH UI)
- `main` requires PR review (when team grows; OK to disable for solo).
- `main` requires CI green.
- Tags `v*` trigger publish; push only after CHANGELOG bumped.
