# UZI-Skill (stock-deep-analyzer) — vendored

Source: https://github.com/wbh604/UZI-Skill (MIT, v3.3.2)

## What's here

| Path | Purpose |
| --- | --- |
| `.claude/commands/` | 14 slash commands (`/analyze-stock`, `/quick-scan`, `/dcf`, ...) |
| `.claude/skills/` | 4 SKILL.md modules: `deep-analysis`, `investor-panel`, `lhb-analyzer`, `trap-detector` |
| `.claude/agents/investor-panel.md` | Sub-agent role-played by Claude |
| `vendor/uzi-skill/` | Full upstream source incl. `scripts/`, `personas/`, `assets/`, `requirements.txt` |

## Why vendored instead of `/plugin install`

The upstream is a Claude Code plugin, but `/plugin marketplace add` / `/plugin install`
are not available in every Claude Code surface (e.g. web sessions). Surfacing the
commands and skills directly under `.claude/` makes them work in any environment that
auto-loads project `.claude/`.

## Python dependencies

The skill scripts call free data sources (akshare, yfinance, etc.). Install once:

```bash
pip install -r vendor/uzi-skill/requirements.txt
playwright install chromium   # only needed for HTML report screenshots
```

## Plugin root

Several command files reference `<plugin_root>` — substitute `vendor/uzi-skill/`
when running scripts manually. Example:

```bash
cd vendor/uzi-skill
python skills/deep-analysis/run.py --ticker 600519
```

## Hook (skipped)

Upstream ships a `SessionStart` hook (`hooks/session-start`) that depends on the
`${CLAUDE_PLUGIN_ROOT}` env var, which only exists when loaded as a real plugin.
It is not wired into `.claude/settings.json` here. To enable it locally, install
upstream as a plugin via `/plugin install stock-deep-analyzer@uzi-skill` in a
desktop Claude Code session.

## License

MIT — see `vendor/uzi-skill/LICENSE`.
