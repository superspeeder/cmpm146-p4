# Heuristic README
#### This project uses custom heuristic that guide the PyHOP HTN planner to heopl prevent infinite recursions and to better the search behavior. The heuristics were created in add_heuristic, and they are designed to prune the branches of the tree that aare most likely to lead to dead plans.
#### To prevent the planner from continuously looping:
```
if depth > 1200:
  return True
```
#### The pickaxes, axes, the bench, and the furnace only need to be crafted once. If the planner tries to produce a tool that already exists in the current state, we prune that branch:
```
if item in tool_set and getattr(state, item)[ID] >= 1:
    return True
```
#### The tool production can create cycles (for example: trying to produce a tool that indirectly requires producing the same tool again).This is detected by checking whether the same produce_<tool> task appears again in the calling stack and prune if it does:
```
for st in calling_stack:
    if isinstance(st, tuple) and st and st[0] == curr_task[0]:
        return True
```
#### This is to prevent infinite loops during tool-building chains and keeps the planner focused on productive branches.