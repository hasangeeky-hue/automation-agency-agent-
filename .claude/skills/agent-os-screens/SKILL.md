---
name: agent-os-screens
description: How to build any screen, board, desk, or agent surface in the Anthropos Agent OS so it matches the founder's wireframe and survives his gates. Use this skill whenever the work touches the Agent OS dashboard, a module screen (Media Buyer, SEO/AEO/GEO, Marketing/Content, Commerce, Leads & Outreach, Web & Data Core, Cockpit), an agent desk or roster card, a connector or wire status display, an approval queue, or any board that shows a number to the founder. Also use it when adding a verify_*/prover check, when writing anything that reports whether a wire is live, and when a change would put a metric, badge, chart, or status word in front of him, even if the request never says "screen" or "wireframe".
---

# Building screens in the Agent OS

The founder built an OS, looked at it, and said the data was not shown the way he needs to see it. He then drew a wireframe and wrote an agent philosophy. Everything here comes from that wireframe and from failures this codebase has actually shipped. Follow it so the next screen does not have to be rebuilt.

## The one idea underneath all of it

**A desk is a view. A lane has one owner.**

His wireframe shows 32 agent desks. The engine staffs 18 employees. That is not a shortfall, it is the design: splitting a lane across two agents means nobody owns the outcome and the lane's memory fragments in half. Several desks are views onto one worker.

The rule that follows: **when two desks share a worker, say so on both desks.** A desk that quietly borrows another's employee is how a founder comes to believe he has twice the staff he has. See `SHARED_DESKS` in `content_engine_agentos_leads.py` and `content_engine_agentos_commerce.py` for how existing modules disclose it.

## His shell is not negotiable

Every module renders inside `frame()` from `content_engine_os_kit.py`. Never flatten a module into a stack of cards, which is the single correction he has had to make more than once.

```
topbar  (cost, alerts)
sidebar (the 7 modules)          main   (the screens, stacked)
  subnav (this module's screens)
```

```python
import content_engine_os_kit as K

def marketing_section(ctx):
    body = _s9a(ctx) + _s9b(ctx) + _s9c(ctx)
    return "<div class='osx'>" + K.frame("3 · Marketing / Content",
                                         SUBNAV_MARKETING, body) + "</div>"
```

`K.MODULES` is the seven-module list. Read it; do not retype it. Subnav links are anchors because his own prototype navigates by anchor, so screens stack in one column rather than swapping panels.

The `.osx` wrapper matters: the OS declares its own `--ox-*` tokens there. A bare `var(--x, #fallback)` inside a shell that also defines `--x` silently resolves to the shell's value, not your fallback.

## Use the kit; do not hand-roll a component

`content_engine_os_kit.py` exports: `frame`, `crumb`, `screen`, `grid`, `bp`, `badge`, `stat`, `chart`, `dq`, `agent_card`, `connector_row`, `connector_table`, `source_chip`, `cmdchat`, `planned`, `check`.

Two carry rules you cannot re-implement casually:

- **`dq(rec, evidence)`** is his decision card. Called with no evidence it renders *"no evidence recorded, which is itself worth knowing"* rather than a bare recommendation. A recommendation with no evidence behind it is the thing he most distrusts.
- **`chart(title, rows)`** renders a `None` value as **"not measured"**. It never draws a zero-length bar for a missing number, because a zero-length bar reads as a measured zero.

If you need a component that does not exist, add it to the kit so every screen gets it, and extend `check()` by **deriving** the list of things to verify from the data structure rather than typing a second list beside the first.

## Four ways to lie, and how to not

These are the failure classes that have actually shipped here. They are worth more attention than any styling detail.

**1. False green.** A live badge over a thing that does not work. The reverse counts too: a control that implies a safety feature the engine does not have. Both were shipped. Example from this repo: a channel printed `READY TO POST` next to an HTTP 401, because the code read `available` (a credential exists) and not `verified` (the provider accepted it).

**2. False empty.** Reporting "no data" over data that exists. This is the worse direction, because it sends someone to fix a working pipeline and looks like diligence while doing it. It happened by reading `build_ctx()` when the screens actually read `search_bridge.enrich()`. Before you report a table as empty, confirm you are reading from the same place the screen reads from.

**3. Absence read as zero.** A missing cost is not a zero margin. An unmeasured week is not a zero bar. Untracked stock is not "none left". Carry `None` through and let the component say "not measured".

**4. Proof by receipt.** A container cannot prove facts about a host it cannot see. If something happens outside the process, it must be *told*, with a timestamp, and say so when it has not been told. The backup posture works this way: no receipt means "no proven backup", never "probably fine".

Related: **verification is by a read, never by a post.** A posting wire that can only be proven by posting can never be safely tested. LinkedIn is verified by `/v2/userinfo`, which changes nothing and costs nothing. When adding a wire to `VERIFIABLE`, find its free read first.

## Every number names where it came from

No metric renders without its source. `source_chip()` exists for this. "computed", "measured", "estimated" and "not measured" are four different words and the screen should use the right one. A total that contains an estimate is an estimate.

## The five permanent gates

**SPEND, PUBLISH, SEND, DEPLOY, CROSS-MODULE.** No code path, setting, or approval level opens them. Every one needs a named human, and the name is recorded.

When you build a screen where one of these could happen, state the gate on that screen. The founder should not have to remember which surfaces are dangerous.

Test a gate by **calling it**, not by reading it. Reading the source says the check is written; calling `apply_one(store, id, approved_by="")` and getting a refusal says the check runs. `live_test.py` lane 4 does both directions: no approver, and a named approver against a non-existent target.

Price proposals render pink specifically so they cannot be swept into a batch approve.

## Design tokens

Industry blueprint, not a SaaS gradient.

| Token | Value | Use |
|---|---|---|
| ground | `#f2f2f3` | page |
| ink | `#1d1f20` | text |
| accent | `#5980a6` | steel blue, the only accent |
| type | Barlow Condensed (headings), Barlow (body) | |
| corners | square | no border radius |
| cards | blueprint cards, 4 corner registration marks | |

11px is the floor for type. Status is icon **plus word**, never colour alone.

**No em-dashes anywhere, in code or UI.** This is his "written by AI" tell and `verify_agentos.py` fails the build over it. Use a comma, a colon, or a full stop.

## Build discipline

Three phases, in order:

1. **Code** the module.
2. **Gate it**: extend the relevant `verify_*.py`, then *render then look*. Serve the page, open it, read the DOM. Never claim a UI fix from reading source.
3. **Prove it where it runs**: add a section to `verify_deploy.py`. A check that passes locally and fails on the box has taught you nothing. One real case: a check opened `deploy/backup.sh`, which the Dockerfile deliberately does not copy.

A check must be able to fail. `assert not X or True` is not a test.

Assert against the **assembled** page, not your section in isolation. A correct section can still have stale markup appended after it.

## Traps this codebase has already fallen into

- **Two hand-written lists that must agree.** The most repeated bug here. Derive the second from the first, or have a check compare them. It has bitten on `ao_type`, `AUTO_CODES`, content types, badge classes, and wire names.
- **Guessing names.** Wire names, step names and model ids were all invented at some point and all shipped broken. Read them from `health()`, from the registry, from `K.MODULES`. Make `check()` fail the build on a name that does not resolve.
- **CSS class collisions.** `ox-sub` was a paragraph class and a subnav link class at once, so 9 expected links counted as 39. Gate against the collision, not just the count.
- **Overwriting a module that already exists.** Check the tree for the filename before writing. Two 900+ line modules were lost this way.
- **Text surgery on return expressions.** Splicing into a `return (...)` produces unbalanced parens across several files at once. Rewrite the whole function instead.

## Before you call a screen done

- It renders inside `frame()` with the sidebar and this module's subnav.
- Every number names its source; every gap says "not measured".
- Any shared desk discloses its worker.
- Any of the five gates that could fire here is stated on the screen.
- No dead buttons: every control reaches an endpoint that exists.
- No em-dash.
- A gate asserts all of the above against the assembled page, and it runs in `verify_deploy.py` where it is deployed.
