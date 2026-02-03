from cProfile import label
import json
import pyhop
import autoHTN

def run_case(initial, goal, time_limit, label):
    with open("crafting.json") as f: # This loads the crafting.json file with the problems
        data = json.load(f)

    data["Problem"]["Initial"] = dict(initial)
    data["Problem"]["Goal"] = dict(goal)
    data["Problem"]["Time"] = time_limit

    ID = "agent" # This is the initializing of the agent ID for the problem and the goals
    state = autoHTN.set_up_state(data, ID)
    goals = autoHTN.set_up_goals(data, ID)

    pyhop.operators.clear() # This clears any previous operators, methods, checks, and custom method orders from pyhop (VERY IMPORTANT BECAUSE OTHERWISE IT CAUSES INFINITE LOOPS)
    pyhop.methods.clear()
    pyhop.checks.clear()
    pyhop.get_custom_method_order = None


    autoHTN.declare_operators(data) # This declares the operators, methods, heuristics, and ordering for the problem
    autoHTN.declare_methods(data)
    autoHTN.add_heuristic(data, ID)
    autoHTN.define_ordering(data, ID)

    #pyhop.print_methods() --  for debugging which methods get used and FINDING THE INFINITE LOOPS
    plan = pyhop.pyhop(state, goals, verbose=1)
    ok = (plan != False)
    status = "passed" if ok else "FAILED"
    length = 0 if plan is False else len(plan)
    
    print(f"Test {label} {status} with a plan length of {length}.")    
    return plan

tests = [ # From the PDF, the testing clauses
    ({"plank": 1}, {"plank": 1}, 0,   "a"),
    ({},          {"plank": 1}, 300, "b"),
    ({"plank": 3, "stick": 2}, {"wooden_pickaxe": 1}, 10,  "c"),
    ({},          {"iron_pickaxe": 1}, 100, "d"),
    ({},          {"cart": 1, "rail": 10}, 175, "e"),
    ({},          {"cart": 1, "rail": 20}, 250, "f"),
]


for initial, goal, t, label in tests:
    run_case(initial, goal, t, label)
