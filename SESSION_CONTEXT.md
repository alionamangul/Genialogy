# Family Tree — Session Context
_Last updated: 2026-04-12 (session 2)_

## Project Location
- **Source**: `/Users/alyona/Downloads/family-tree/`
- **Serving copy**: `/tmp/family-tree/` (must be kept in sync with `cp` after edits)
- **Server**: `python3 serve.py` on port 8080, started via `.claude/launch.json`
- **Main file**: `index.html` (all HTML/CSS/JS in one file)
- **Data**: `data.json` (GEDCOM-parsed family data)

## Current Task Status

### ✅ Completed
1. **Circular avatar nodes** — tree nodes render as circular photos with name/dates
2. **Focused tree view** (`renderFocusedTree`)  — on startup and when clicking a person in tree view, shows only relevant ancestors/descendants instead of all 296 nodes
3. **Default root**: Армен Шахназарян (`DEFAULT_ROOT_ID = '43938060'`) + Алёна Мангул
4. **Both family sides visible** — Алёна's ancestors (Мангул/Курудимов side) now show as primary (gold ring, full opacity), not dimmed. Fixed by calling `walkAncestors(alёnaId, primary)` in `getAncestorChain`
5. **No first-wife clutter** — Армен's first wife Анна and son Марк excluded via `visible.delete()` in `renderFocusedTree`
6. **Depth limit fix** — `addAncestors` now correctly stops at `maxUp` generations (was leaking extra nodes due to adding parents before checking depth)
7. **Couple-aware overlap resolution** — replaced individual-node overlap resolution with couple-based grouping (spouses treated as units, not separated)
8. **Viewport centering** — `zoomToFocusPerson` centers the couple (Армен+Алёна) at horizontal midpoint of viewport
9. **Depth-3 ancestors for Алёна's side** — `addAncestors(mainSpouseId, 0, 3)` (was 2) now shows parents of Василий Мангул (Архип+Марика) and Нины Романенко (Иван Романенко+Дарья), plus Дмитрий/Федора (above Константин) and Пантелей/Аксиния (above Нелли)
10. **placeUpVisited guard** — added `placeUpVisited = new Set()` in `placeUp` to prevent exponential recursion when shared ancestors are visited via multiple paths
11. **Extra-spouse cleanup** — after building `visible`, nodes at gen<0 with no visible children are removed (prevents e.g. second-marriage spouses of deep ancestors appearing as orphan nodes)

### ❌ Remaining Bug — Layout Misalignment
**The Problem**: Parents of each person are NOT appearing directly above them in the tree. Specifically, Людмила's parents (Шамир Иосиф Азарян + Евгения Оганесова) appear to the right of where Людмила is, instead of directly above her.

**Root Cause**: The minimum horizontal gap between non-couple groups is `NODE_W + H_GAP*2 = 140px`. When Авинер's parents (Григорий+Офелия) occupy the space at x=128-344, and Людмила's parents want to be at x=236-344 (centered above Людмила at x=290), there's a collision. The overlap resolver pushes Людмила's parents right to x=476-584, which is 190px right of where they should be.

**What's needed**: The couple (Авинер+Людмила) needs to be placed further apart horizontally so their respective parent families don't conflict. The minimum spacing between Авинер and Людмила should be ~248px (instead of the current SPOUSE_GAP=8px + NODE_W=100px = 108px).

Specifically, for two adjacent nodes each with their own parent couple, the node-to-node minimum is:
```
half_couple_w + H_GAP*2 + half_couple_w = 104 + 40 + 104 = 248px
```

**Proposed Fix Options**:
A. Compute `ancestorWidth(pid, depth)` — recursive function returning the minimum width needed for a person's ancestor subtree — and use it to determine spacing when placing couples in `placeDown`/`placeUp`
B. After `placeUp` places parents, check if they conflict with adjacent parents and push the CHILDREN apart (bottom-up width adjustment)
C. Simpler: Make the `SPOUSE_GAP` for ancestor-level couples very large (e.g., 150px) so the couple has room for both parent trees. This trades visual compactness for correctness.

## Key Constants (in index.html)
```javascript
const NODE_W = 100;
const NODE_H = 90;
const H_GAP = 20;
const SPOUSE_GAP = 8;
const V_GAP = 80;
const DEFAULT_ROOT_ID = '43938060'; // Армен Шахназарян
```

## Key Person IDs
| Person | ID |
|---|---|
| Армен Шахназарян | `43938060` |
| Алёна Мангул | `35454522` |
| Авинер Шахназарян (Армен's father) | `42972468` |
| Людмила Азарян (Армен's mother) | `84381481` |
| Игорь Курудимов (Алёна's father) | `94250166` |
| Светлана Мангул (Алёна's mother) | `7323016` |
| Григорий Шахназарян (Авинер's father) | `13356830` |
| Офелия Данилян (Авинер's mother) | `37845118` |
| Шамир (Иосиф) Азарян (Людмила's father) | `95547960` |
| Евгения Оганесова (Людмила's mother) | `60995756` |
| Константин Курудимов (Игорь's father) | `72367536` |
| Нелли Крот (Игорь's mother) | `34925832` |
| Василий Мангул (Светлана's father) | `78877471` |
| Нина Романенко (Светлана's mother) | `78092024` |
| Оганес Шахназарян (Григорий's father) | `58277898` |
| Варвара Шахназарян (Григорий's mother) | `93189758` |
| Вартан Даниелян (Офелии's father) | `41058944` |
| Астхик (Ася) Амбарцумян (Офелии's mother) | `53910212` |
| Шамир Азарян (Шамир Иосиф's father) | `28263536` |
| Мамикон Оганесов (Евгении's father) | `26223903` |
| Роза (Евгении's mother) | `39337534` |

## Key Functions in index.html

### `renderFocusedTree(personId, openPanel)`
- Builds `visible` set: `addAncestors(personId, 0, 3)` + children from main family + `addAncestors(mainSpouseId, 0, 2)`
- Excludes other spouses' families (Армен's first wife Анна)
- Layout steps: placeDown → placeUp → Step E (resolveRowOverlaps) → Step F (bottom-up re-centering + resolveRowOverlaps x2)
- Called from `init()` on startup and from `selectPerson()` when in tree view

### `resolveRowOverlaps()` (inside renderFocusedTree)
- Groups spouses as couple-units before resolving overlaps
- Gap between groups: `NODE_W + H_GAP * 2 = 140px`
- **This is the function that needs fixing** — couples are adjacent but parent misalignment persists

### `getAncestorChain(personId)` → Set
- Returns set of all "primary" nodes (focus person + all ancestors + spouse + spouse's ancestors + children)
- Calls `walkAncestors(spouseId, primary)` to include Алёна's side

### `zoomToFocusPerson(personId)`
- Centers couple in viewport
- Scale: `min(halfW/maxRadius, fitScaleV, 0.85)` clamped to 0.25 minimum
- Centers couple at `rect.width/2` horizontally, 65% down vertically

### `backToOverview()`
- Restores full 296-node tree and calls `fitToScreen()`

## Layout Algorithm (renderFocusedTree)
1. **Step A**: `placeDown(personId, x=0, gen=0)` — places focus person + descendants
2. **Step B**: Place siblings of focus person to the left
3. **Step C**: `placeUp(personId, 0)` + `placeUp(mainSpouseId, 0)` — places ancestors recursively, centered above children
4. **Step D**: Place any unplaced visible nodes at maxX
5. **Step E**: `resolveRowOverlaps()` — couple-aware overlap resolution
6. **Step F**: 2 passes of (re-center parents above children bottom-up + `resolveRowOverlaps()`)
7. **Normalize**: shift all positions so minX=50, minY=50

## Plan File
There is an existing plan at `/Users/alyona/.claude/plans/luminous-nibbling-eclipse.md` for adding menu sections + document support. That plan is SEPARATE from the current tree layout work.

## CSS Classes
```css
.tree-node.secondary { opacity: 0.16; filter: grayscale(1); transform: scale(0.42); }
.tree-node.primary-ancestor .node-photo { box-shadow: 0 0 0 3px var(--gold); }
```

## How to Continue
1. Start server: use preview tool with `family-tree` config (port 8080, serving from `/tmp/family-tree/`)
2. After editing `/Users/alyona/Downloads/family-tree/index.html`, always `cp` to `/tmp/family-tree/index.html`
3. The main remaining bug is the layout misalignment described above
4. Test by checking: are Шамир Иосиф + Евгения centered above Людмила (x≈290)?
