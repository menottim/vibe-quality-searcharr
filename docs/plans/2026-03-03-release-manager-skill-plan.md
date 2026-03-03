# Release Manager Skill — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a reusable Claude Code skill that orchestrates the full release lifecycle: version bump, doc updates, consistency audit, GitHub release, and verification.

**Architecture:** Single SKILL.md file in `~/.claude/skills/releasing/`. The skill is a rigid checklist with 6 phases, 3 confirmation gates, and auto-discovery from CLAUDE.md + memory. No external dependencies beyond `gh` CLI.

**Tech Stack:** Markdown skill file following superpowers plugin conventions.

---

### Task 1: Write RED baseline test scenarios

**Files:**
- Create: `~/.claude/skills/releasing/test-scenarios.md` (temporary, for baseline testing)

**Step 1: Write 3 pressure scenarios for baseline testing**

Scenario A — Simple release: "Bump to v1.2.0 and create the release"
Scenario B — Multi-repo release: "Release v1.2.0, update the wiki too"
Scenario C — Consistency pressure: "Quick release, the PRD and README versions don't matter right now"

**Step 2: Run baseline scenarios WITHOUT the skill**

Launch 3 Haiku subagents in parallel, each with one scenario and access to the Splintarr codebase. Document:
- Did they find all version sources?
- Did they update all docs?
- Did they check consistency?
- What did they skip or rationalize skipping?

**Step 3: Document baseline failures**

Record exact rationalizations and missed steps. These become the skill's red flags table.

---

### Task 2: Write the SKILL.md (GREEN phase)

**Files:**
- Create: `~/.claude/skills/releasing/SKILL.md`

**Step 1: Write YAML frontmatter**

```yaml
---
name: releasing
description: Use when cutting a release, shipping a version, bumping version numbers, or publishing to GitHub. Also use when asked to update all documentation for a release, or when version references across docs need synchronizing.
---
```

**Step 2: Write the Overview section**

Core principle in 1-2 sentences: what this skill does and why it exists. Reference the problem (27 stale refs found after 3 release attempts).

**Step 3: Write Phase 0 — Context Discovery**

How the skill auto-discovers:
- Version source (pyproject.toml, package.json, Cargo.toml, etc.)
- Release checklist from CLAUDE.md
- Doc files (README, RELEASE_NOTES, CHANGELOG, PRD, wiki repos)
- Git remotes and GitHub host

Fallback: ask user, save to memory.

**Step 4: Write Phase 1 — Pre-flight Check**

- Clean git status
- Read current version
- Ask for new version
- Generate changelog from `git log --oneline <last-tag>..HEAD`
- **GATE:** User confirms version + changelog

**Step 5: Write Phase 2 — Version Bump**

- Update version source file
- Update README version reference/link
- Write RELEASE_NOTES if file exists

**Step 6: Write Phase 3 — Documentation Updates**

- Scan all discovered doc files for version references
- If PRD exists, ask which features to mark as shipped
- If wiki repo exists, update Home + Release History
- Update auto-memory

**Step 7: Write Phase 4 — Consistency Audit**

Cross-check all docs for:
- Stale version references
- Feature list mismatches
- Status contradictions ("planned" for shipped features)

Present findings. Fix or ask for guidance.
**GATE:** User reviews audit results.

**Step 8: Write Phase 5 — Commit & Release**

- Stage, show diff summary
- Commit with standard message
- Push main
- Push wiki if separate
- **GATE:** User confirms release notes
- `gh release create`
- Set as latest

**Step 9: Write Phase 6 — Post-release Verification**

- `gh release view` confirms published
- Re-scan for stale refs

**Step 10: Write Error Handling table**

| Condition | Action |
|-----------|--------|
| Dirty git | Stop |
| Version source not found | Ask, save to memory |
| Wiki not found | Skip, note |
| gh not authed | Stop, instructions |
| Push fails | Stop, don't release |

**Step 11: Write Red Flags and Common Mistakes**

From baseline test rationalizations.

**Step 12: Write Quick Reference table**

One-line summary of each phase for scanning.

---

### Task 3: Run GREEN test — verify skill compliance

**Step 1: Run same 3 scenarios WITH the skill loaded**

Launch 3 Haiku subagents with the skill in their context. Verify:
- All version sources found
- All docs updated
- Consistency audit catches staleness
- Confirmation gates respected

**Step 2: Compare baseline vs skill results**

Document improvements. If any scenario still fails, identify the gap.

---

### Task 4: REFACTOR — close loopholes

**Step 1: Identify new rationalizations from GREEN testing**

Did agents skip phases? Rationalize away confirmation gates? Miss doc files?

**Step 2: Add explicit counters to SKILL.md**

Close each loophole with explicit instructions.

**Step 3: Re-test until all 3 scenarios pass**

---

### Task 5: Deploy

**Step 1: Copy to skills directory**

```bash
mkdir -p ~/.claude/skills/releasing
cp SKILL.md ~/.claude/skills/releasing/SKILL.md
```

**Step 2: Remove temporary test scenarios file**

**Step 3: Commit**

```bash
git add docs/plans/2026-03-03-release-manager-skill-plan.md
git commit -m "docs: add release-manager skill implementation plan"
```
