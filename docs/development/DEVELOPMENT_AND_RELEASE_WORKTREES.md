# MacSoft Agent Development And Release Workflow

## Source test workspace

`C:\hermes-packaging\server\MacSoft-Agent` is the only editable source workspace.

Run the complete source test product with:

```powershell
.\start-test.bat
```

This starts the current-Git Host and its owned services on ports 8766, 8643,
8642, and 8787, then starts the Server Desktop Vite test UI on 5174. Stop the
entire owned process tree with `stop-test.bat`.

The local `runtime`, `server\data`, credentials, databases, caches, venvs, and
node_modules are development state. They are never promoted to GitHub or copied
to a release payload. Authoritative defaults live in `runtime.example` and
`packaging\templates`.

## Packaging clone

`C:\hermes-packaging\server\MacSoft-Agent-Packaging` is a separate clean clone
of the GitHub repository. It is not an editable source workspace. Fetch the
accepted source commit and check it out exactly:

```powershell
git fetch origin
git checkout --detach <accepted-40-character-commit>
```

Build only when a release artifact is required:

```powershell
.\scripts\build-release.ps1 -ExpectedCommit <accepted-40-character-commit>
```

The release script refuses a dirty clone, a mismatched commit, the development
workspace name, or occupied product ports. It rebuilds Python and Node
dependencies from `uv.lock` and `package-lock.json`, creates Electron
`win-unpacked`, assembles a fresh audited staging payload, verifies its manifest,
and emits the final NSIS installer plus `release\build-report.json`.

If packaging or acceptance reveals a source defect, fix it in the source test
workspace, repeat testing, commit and push, then update the Packaging clone to
the new accepted commit. Do not patch the Packaging clone directly.
