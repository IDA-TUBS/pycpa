from pycpa import util
from pycpa import model
from pycpa import schedulers
from pycpa import analysis
from pycpa import nxamalthea as nxamp

from pycpa import options


def test():
    amp = nxamp.NxAmaltheaParser('../data/Waters_Challenge.xml', scale=0.7)

    G = amp.parse_runnables_and_labels_to_nx()
    G = amp.parse_tasks_and_cores_to_nx()
    #print(G.nodes(data=True))
    #print(G.edges(data=True))

    a = nxamp.NxConverter(G)
    s = a.get_cpa_sys()

    task_results = analysis.analyze_system(s)
    print("Result:")
    for r in sorted(s.resources, key=str):
        for t in sorted(r.tasks, key=str):
            print("%s: wcrt=%d" % (t.name, task_results[t].wcrt))
            print("    b_wcrt=%s" % (task_results[t].b_wcrt_str()))

def export_to_csv():
    amp = nxamp.NxAmaltheaParser('../data/Waters_Challenge.xml', scale=0.7)

    G = amp.parse_runnables_and_labels_to_nx()
    G = amp.parse_tasks_and_cores_to_nx()

    a = nxamp.NxConverter(G)

    a.write_to_csv('../data/Waters_Challenge.csv')

if __name__ == '__main__':
    test()
    export_to_csv()
