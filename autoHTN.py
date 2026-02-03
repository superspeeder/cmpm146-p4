import pyhop
import json


def check_enough(state, ID, item, num):
    if getattr(state, item)[ID] >= num: # This was pretty much done from your first initial comit
        return []
    if item in ('cobble', 'coal') and num >= 8 and getattr(state, 'stone_pickaxe')[ID] < 1: # Had to make some changes to accomodate pickaxe crafting (specifically the stone pickaxe)
        return [('check_enough', ID, 'stone_pickaxe', 1), ('produce', ID, item), ('check_enough', ID, item, num)]

    return [('produce', ID, item), ('check_enough', ID, item, num)]


pyhop.declare_methods('check_enough', check_enough)


def produce_enough(state, ID, item): # This is how we produce the different recipes for the items
    return [('produce_{}'.format(item), ID)]


pyhop.declare_methods('produce', produce_enough)

def _order_consumes(consumes: dict, dep_map: dict) -> list: # This orders the recipes based on dependencies
    items = list(consumes.keys())

    if len(items) <= 1:
        return items

    item_set = set(items) # This builds a dependency graph between consumed items
    graph = {x: set() for x in items}

    for x in items:
        for y in dep_map.get(x, set()):
            if y in item_set and y != x:
                graph[x].add(y)

    indeg = {x: 0 for x in items} # This is how the indegrees are computed for the topological sorting
    
    for x, ys in graph.items():
        for y in ys:
            indeg[y] += 1

    queue = [] # Empty queue for topological sorting
    for item in items:
        if indeg[item] == 0:
            queue.append(item)
            
    out = []

    while queue: #The topological sorting algorithm
        n = queue.pop()
        out.append(n)
        for y in graph[n]:
            indeg[y] -= 1
            if indeg[y] == 0:
                queue.append(y)

    if len(out) != len(items):
        return items
    return out

def m_get_wood(state, ID): # This is the HTN method for gathering wood using the best available axe, or punches if no axe is available.
    if getattr(state, 'iron_axe')[ID] >= 1:
        return [('op_iron_axe_for_wood', ID)]
    
    if getattr(state, 'stone_axe')[ID] >= 1:
        return [('op_stone_axe_for_wood', ID)]
    
    if getattr(state, 'wooden_axe')[ID] >= 1:
        return [('op_wooden_axe_for_wood', ID)]
    
    return [('op_punch_for_wood', ID)]


def m_get_cobble(state, ID): #This is the HTN method for mining cobble using the best available pickaxe, crafting a wooden pickaxe if needed.
    if getattr(state, 'iron_pickaxe')[ID] >= 1:
        return [('op_iron_pickaxe_for_cobble', ID)]
    
    if getattr(state, 'stone_pickaxe')[ID] >= 1:
        return [('op_stone_pickaxe_for_cobble', ID)]
    
    if getattr(state, 'wooden_pickaxe')[ID] >= 1:
        return [('op_wooden_pickaxe_for_cobble', ID)]
    
    return [('check_enough', ID, 'wooden_pickaxe', 1), ('op_wooden_pickaxe_for_cobble', ID)]


def m_get_coal(state, ID): #This is the HTN method for producing coal, it deterministically selects the best available pickaxe (iron > stone > wooden) to mine coal.
    if getattr(state, 'iron_pickaxe')[ID] >= 1:
        return [('op_iron_pickaxe_for_coal', ID)]
    
    if getattr(state, 'stone_pickaxe')[ID] >= 1:
        return [('op_stone_pickaxe_for_coal', ID)]
    
    if getattr(state, 'wooden_pickaxe')[ID] >= 1:
        return [('op_wooden_pickaxe_for_coal', ID)]
    
    return [('check_enough', ID, 'wooden_pickaxe', 1), ('op_wooden_pickaxe_for_coal', ID)]


def m_get_ore(state, ID): #This is the HTN method for getting ores, it deterministically selects the best available pickaxe (iron > stone > wooden) to mine the ores.
    if getattr(state, 'iron_pickaxe')[ID] >= 1:
        return [('op_iron_pickaxe_for_ore', ID)]
    
    if getattr(state, 'stone_pickaxe')[ID] >= 1:
        return [('op_stone_pickaxe_for_ore', ID)]
    
    return [('check_enough', ID, 'stone_pickaxe', 1), ('op_stone_pickaxe_for_ore', ID)]




def make_method(name, rule, tools=None, dep_map=None): #This turns the recipes into the HTN methods
    produces = rule.get("Produces", {})
    requires = rule.get("Requires", {})
    consumes = rule.get("Consumes", {})
    time_cost = rule.get("Time", 0)
    dep_map = dep_map or {}
    consumes_order = _order_consumes(consumes, dep_map)

    if 'iron_pickaxe' in produces and 'stick' in consumes and 'ingot' in consumes: # This is how we force safe consume ordering for pickaxe crafting.
        consumes_order = ['ingot', 'stick']

    tools = tools or set()
    def tier(tool_name: str) -> int: # These are the Tool tiers that are used to determine the simpler, lower-cost recipes first.
        if tool_name.startswith("wooden_"):
            return 1
        
        if tool_name.startswith("stone_"):
            return 2
        
        if tool_name.startswith("iron_"):
            return 3
        
        if tool_name in ("bench", "furnace"):
            return 0
        
        return 0

    required_tool_tier = 0
    for item in requires.keys():
        if item in tools:
            required_tool_tier = max(required_tool_tier, tier(item))

    def method(state, ID): # This is the HTN method that expands high-level crafting task into subtasks.
        subtasks = []

        for item, count in requires.items():
            subtasks.append(('check_enough', ID, item, count)) # This emsures that required tools are available.

        for item in consumes_order:
            subtasks.append(('check_enough', ID, item, consumes[item])) # This then ensures that all inputs are used in the correct order.

        subtasks.append(('op_' + name.replace(' ', '_'), ID)) # Finally, this adds the operator that performs the crafting action.
        return subtasks

    method.__name__ = "m_" + name.replace(' ', '_') # This sets metadata for the method to help with sorting and selection based on tool tierm time cost, and number of subtasks.
    method._meta = {
        "name": name,
        "time": time_cost,
        "tier": required_tool_tier,
        "n_subtasks": 1 + len(requires) + len(consumes),
        "produces": list(produces.keys()),
        "required_tools": [t for t in requires.keys() if t in (tools or set())],
    }
    return method


def declare_methods(data):
    # some recipes are faster than others for the same product even though they might require extra tools
    # sort the recipes so that faster recipes go first

    # your code here
    # hint: call make_method, then declare the method to pyhop using pyhop.declare_methods('foo', m1, m2, ..., mk)
    pyhop.declare_methods('check_enough', check_enough)
    pyhop.declare_methods('produce', produce_enough) # This is how the base tasks are declared.

    recipes = data["Recipes"] # This gets all the recipes from the data
    tools = set(data.get("Tools", [])) | {"bench", "furnace"} # As well as this
    dep_map = {}
    methods_by_product = {}

    for recipe_name, rule in recipes.items(): # This converts each recipe into a method and organizes them by product
        product = next(iter(rule.get("Produces", {})))  
        mth = make_method(recipe_name, rule, tools=tools, dep_map=dep_map)
        methods_by_product.setdefault(product, []).append(mth)

    for product, mlist in methods_by_product.items(): # This sorts the methods for each product based on tool tier, time cost, and number of subtasks
        mlist.sort(key=lambda m: (m._meta["tier"], m._meta["time"], m._meta["n_subtasks"]))
        pyhop.declare_methods("produce_" + product, *mlist)

    pyhop.declare_methods("produce_wood", m_get_wood)
    pyhop.declare_methods("produce_cobble", m_get_cobble)
    pyhop.declare_methods("produce_coal", m_get_coal)
    pyhop.declare_methods("produce_ore", m_get_ore)



def requirements_met(requirements, state, ID):
    return all(getattr(state, k)[ID] >= v for k, v in requirements.items())


def make_operator(rule): # This builds a primitive operator that applies a crafting recipe to the state.
    rule_name, rule_info = rule
    produces  = rule_info.get("Produces", {})
    requires  = rule_info.get("Requires", {})
    consumes  = rule_info.get("Consumes", {})
    time_cost = rule_info.get("Time", 0)

    def operator(state, ID): # This is the operator function that modifies the state based on the recipe. 
        if state.time[ID] < time_cost:
            return False

        if not requirements_met(requires, state, ID):
            return False

        if not requirements_met(consumes, state, ID):
            return False

        state.time[ID] -= time_cost

        for item, count in consumes.items():
            getattr(state, item)[ID] -= count

        for item, count in produces.items():
            getattr(state, item)[ID] += count

        return state

    operator.__name__ = "op_" + rule_name.replace(' ', '_')
    return operator



def declare_operators(data):
    # your code here
    # hint: call make_operator, then declare the operator to pyhop using pyhop.declare_operators(o1, o2, ..., ok)
    pyhop.declare_operators(*map(make_operator, data.get("Recipes", dict()).items()))


def add_heuristic(data, ID):
    # prune search branch if heuristic() returns True
    # do not change parameters to heuristic(), but can add more heuristic functions with the same parameters:
    # e.g. def heuristic2(...); pyhop.add_check(heuristic2)
    tool_set = set(data.get("Tools", [])) | {"bench", "furnace"}

    def heuristic(state, curr_task, tasks, plan, depth, calling_stack):
        # These stupid recursion make me want to blow my brains out
        if depth > 1200:
            return True

        if isinstance(curr_task, tuple) and isinstance(curr_task[0], str) and curr_task[0].startswith("produce_"):
            item = curr_task[0][len("produce_"):]
            if item in tool_set and getattr(state, item)[ID] >= 1:
                return True

            if item in tool_set:
                for st in calling_stack:
                    if isinstance(st, tuple) and st and st[0] == curr_task[0]:
                        return True

        return False

    pyhop.add_check(heuristic)

def define_ordering(data, ID):
    # if needed, use the function below to return a different ordering for the methods
    # note that this should always return the same methods, in a new order, and should not add/remove any new ones
    def reorder_methods(state, curr_task, tasks, plan, depth, calling_stack, methods):
        return methods
    pyhop.define_ordering(reorder_methods)


def set_up_state(data, ID):
    state = pyhop.State('state')
    setattr(state, 'time', {ID: data['Problem']['Time']})

    for item in data['Items']:
        setattr(state, item, {ID: 0})

    for item in data['Tools']:
        setattr(state, item, {ID: 0})

    for item, num in data['Problem']['Initial'].items():
        setattr(state, item, {ID: num})

    return state


def set_up_goals(data, ID):
    goals = []
    for item, num in data['Problem']['Goal'].items():
        goals.append(('check_enough', ID, item, num))

    return goals


if __name__ == '__main__':
    import sys

    rules_filename = 'crafting.json'
    if len(sys.argv) > 1:
        rules_filename = sys.argv[1]

    with open(rules_filename) as f:
        data = json.load(f)

    state = set_up_state(data, 'agent')
    goals = set_up_goals(data, 'agent')

    declare_operators(data)
    declare_methods(data)
    add_heuristic(data, 'agent')
    define_ordering(data, 'agent')

    # pyhop.print_operators()
    # pyhop.print_methods()

    # Hint: verbose output can take a long time even if the solution is correct;
    # try verbose=1 if it is taking too long
    pyhop.pyhop(state, goals, verbose=1)
# pyhop.pyhop(state, [('check_enough', 'agent', 'cart', 1),('check_enough', 'agent', 'rail', 20)], verbose=3)