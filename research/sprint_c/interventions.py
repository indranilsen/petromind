"""Prompt-only interventions. No claim IDs, reference labels or private lists."""
from research.muse_integration.runner import INSTRUCTIONS as BASELINE

GROUNDING = '''\nEVIDENCE-TO-CLAIM GROUNDING PROCEDURE:
For each exact proposition, organize a compact evidence map using only what you received: measurement receipt(s), applicable documented fact(s), governing model assumption(s), their literal citation identifiers, source scope/applicability, and any missing premise. Express this map in the existing premises, citations and justification fields; do not add schema fields or request another tool. Supply concise public evidence statements, not private deliberation.
A measurement receipt establishes a reported value with its quality/uncertainty, not automatically its physical interpretation. A synthetic model premise is distinct from a measurement or external fact. For any conclusion that depends on that declared model, cite its governing model:<model id> receipt explicitly alongside the relevant measurements or derived graph evidence. A graph edge whose provenance names a model is not a replacement for explicitly citing that governing premise. The initial case-local model is already received; use its literal receipt ID.
For a documented comparison, cite the actual document and identify its applicability limits. A published example is not a universal law. For a calculation or physical conclusion, identify measurements and necessary governing assumptions together. Do not cite unreceived IDs, irrelevant sources, every available source indiscriminately, or a premise that does not establish the proposition. An evidence inventory does not determine the verdict; apply the original assessment task to the evidence map.'''

VERDICT = '''\nTHREE-WAY VERDICT DECISION PROCEDURE:
Evaluate the exact proposition at its stated scope using admissible evidence and applicable assumptions.
SUPPORTED: evidence establishes that proposition. Identify its sufficient evidentiary basis.
CONTRADICTED: evidence affirmatively conflicts with that proposition; identify an actual counter-observation, incompatible bound, or admissible counterexample for a universal assertion.
NOT_ESTABLISHED: neither support nor contradiction is adequately established, including unresolved calibration, unavailable evidence, or an inapplicable example.
Not proven does not mean disproven. Compatible does not mean established. A missing sensor does not prove an opposite reading. Unreliable calibration does not by itself establish that a physical conclusion is false. An example outside the required scope does not establish the current incident and does not alone prove the opposite incident. A failed proof obligation or missing necessary premise is not by itself affirmative contradictory physical evidence.
Avoid blanket abstention: retain SUPPORTED when admissible evidence establishes the claim, and CONTRADICTED when an actual conflict or counterexample exists under the stated scope. Do not weaken a valid conditional model inference into uncertainty merely because its assumptions are explicitly synthetic. Keep the exact proposition's quantifier, time window and scope; do not replace it with an easier claim.'''

VARIANTS = ('V0','V1','V2','V3')
PROMPTS = {'V0':BASELINE, 'V1':BASELINE+GROUNDING,
           'V2':BASELINE+VERDICT, 'V3':BASELINE+GROUNDING+VERDICT}
