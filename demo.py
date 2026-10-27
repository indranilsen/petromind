import argparse
from pathlib import Path
from graph_tools import Investigation, IncidentRetriever, well_id

p = argparse.ArgumentParser()
p.add_argument('--incident', required=True, type=Path)
p.add_argument('--dataset', required=True, type=Path)
p.add_argument('--budget', type=int, default=5)
a = p.parse_args()
inv = Investigation(a.incident, budget=a.budget)
print('Sensors:', len(inv.list_sensors()), '| budget:', inv.budget)
print('Graph lookup:', inv.get_equipment_neighbors('P-MON-CKP'))
for sensor in ['P-TPT', 'T-TPT']:
    print('Query:', inv.get_sensor_history(sensor))
retriever = IncidentRetriever(a.dataset, held_out_wells={well_id(a.incident)})
print('Training incidents indexed:', len(retriever.records))
print('Related training cases:', retriever.search(inv))
print('Remaining budget:', inv.budget - len(inv.queries))
print('Ground-truth label intentionally hidden until evaluation.')
