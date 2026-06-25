# Skill Creation Comparison Scorecard

Use this scorecard only for comparing the Skill asset created by GitHub Copilot `/create-skill` with the Skill asset created by `skill-creator`. This is not the A/C baseline scorecard.

Do not fill scores until both skills have been created and run on the same API contract input.

| Check Item | Scoring Standard | Copilot `/create-skill` Score / Evidence | `skill-creator` Score / Evidence | Notes |
|---|---|---|---|---|
| Runtime simplicity | 0=requires user to paste expert checklist; 1=some extra instructions needed; 2=user only invokes slash command and pastes contract |  |  |  |
| Skill structure | 0=monolithic or missing key files; 1=usable but hard to maintain; 2=concise `SKILL.md` with clear references/templates |  |  |  |
| Trigger clarity | 0=name/description unclear; 1=partially clear; 2=clear when and why to use the skill |  |  |  |
| Progressive disclosure | 0=loads all details into main file; 1=some references; 2=core workflow in `SKILL.md`, detailed methods in references |  |  |  |
| Requirement extraction | 0=misses many explicit rules; 1=partial IDs; 2=assigns IDs to all explicit rules |  |  |  |
| Contract gap discipline | 0=invents missing behavior; 1=some gaps marked; 2=systematically separates gaps and blocked tests |  |  |  |
| Boundary coverage | 0=few boundaries; 1=basic boundaries; 2=missing/null/empty/type/format/min/max/just-over/precision/time boundaries covered where relevant |  |  |  |
| Risk coverage | 0=mostly happy path; 1=some negative/security cases; 2=auth/authz/idempotency/retry/timeout/concurrency/security/privacy covered where relevant |  |  |  |
| Output usability | 0=unstructured; 1=partially tabular; 2=Chinese Markdown tables with TC IDs, priorities, evidence and traceability |  |  |  |
| Deduplication | 0=duplicated or noisy cases; 1=some overlap; 2=deduplicates semantically equivalent tests with notes |  |  |  |
| Installability | 0=cannot be installed/invoked; 1=manual fixes needed; 2=installs and invokes cleanly in the target environment |  |  |  |
| Baseline contamination control | 0=requires global instructions or shared state; 1=some contamination risk; 2=can be isolated from A group with new chat/workspace setup |  |  |  |

## Critical Misses

Record any critical miss even if the numeric score is high:

- Skill cannot be invoked.
- Skill requires global Copilot instructions or shared state that would pollute A group.
- Runtime input is no longer a normal user request.
- Skill invents API contract behavior instead of marking a gap.
- Skill output cannot be manually audited.
- Skill comparison reused the same chat context and may be contaminated.
