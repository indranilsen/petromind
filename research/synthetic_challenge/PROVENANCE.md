# Evidence provenance and scientific limits

Reviewed 2026-11-02 against the source material below. Source paraphrases are
supplied locally so the investigator can run without web access. URLs and locators
are preserved; paraphrases are not verbatim publication excerpts. The repository's
existing knowledge module was inspected only for sensor semantics and the existing
submission contract. No other session's interventions, branches or experiments
were inspected. Base commit: 516dab2004594cd6efdf0ec2f9ef3427b040321a.

| Proposition family | Evidence and locator | Status and boundary |
|---|---|---|
| Generic sensor locations and SI units | [Petrobras dataset.ini](https://github.com/petrobras/3W/blob/main/dataset/dataset.ini), PARQUET_FILE_PROPERTIES | Externally checked against current configuration. QBS is service-pump flow; this challenge's production meter is explicitly synthetic. Existing repository lists blob 4c4799e80e04a9cf8b10cb3f9a23f1c487797cc9; immutable blob retrieval was unavailable here, so that identifier is reported provenance, not a newly verified byte pin. |
| Example pressure directions | [Vaz Vargas et al., arXiv:2507.01048v1](https://arxiv.org/html/2507.01048v1), Figure 5 caption | Externally checked published production-line hydrate example. Only the measured subset can be compared; an unobserved PDG response is not supplied. No universal diagnostic implication follows. |
| Limits of real and simulated 3W data | Same paper, Sections 2.5–2.6 | Authors report unverified tag contextualization/original units and a valve-closure surrogate for simulated hydrate. These are source limitations, not permission to invent installed piping. |
| Several obstruction materials exist | [SLB Energy Glossary: blockage](https://glossary.slb.com/en/terms/b/blockage) | Externally checked generic definition; does not establish current deposit identity. |
| Hydrate risk is thermodynamic and contextual | [SLB Olga hydrate kinetics](https://www.slb.com/products-and-services/delivering-digital-at-scale/software/olga/olga-solids-management/olga-hydrate-kinetics), Overview / Applications | Externally checked broad risk context; local feasibility, occurrence and material identity remain separate propositions. |
| U–L–D–K–S connectivity and channel mapping | public/model.json and each case-local model | Explicit synthetic assumption, never a Petrobras installed-well claim. |
| Quadratic losses, linear inflow, compliant storage | M1 equations; private generator and numerical report | Bounded mathematical surrogate checked by algebra, dissipation, storage, units, interval arithmetic and time-step convergence. Coefficients are synthetic. No multiphase industrial calibration. |
| Temperature transient | Private passive first-order channel | Explicit synthetic cooling independent of hydraulic resistance; not a hydrate phase simulator. |
| Classifier diagnosis / similarity rank | Public case and history fixtures | Constructed plausible handoff and correlation; neither trained-model performance nor calibrated probability. |
| Material interpretation of resistance | Hypotheses in graph, declared M1 limits | Neither simulated chemistry nor physical deposit evidence exists. An effective parameter is not material identity. |
| Sensor quality and calibration withdrawal | Case-local synthetic metadata | Deliberate experimental conditions. A latent generating value is not admissible evidence when calibration is unverified. |

One lumped upstream node stores volume: inlet and outlet flow may differ during
transients. The two downstream losses share the same flow because their local
storage and branches are explicitly neglected. Never impose steady-state inflow
balance on the transient. Quadratic loss and positive flow imply positive
hydraulic dissipation; all generated pressures remain ordered and positive.
Temperature is not linked to hydrate phase; no heat/latent-heat conservation claim
is made. No gas lift, service-pump production proxy, installed valve-state mapping,
material deposit kinetics, leak model, phase envelope or wall-temperature field
has been invented.

These cases stress *evidence reasoning under declared premises*. Seven variants
are not seven independent field incidents. Numerical correctness does not certify
industrial validity, field safety, classifier accuracy or model efficacy. An
independent qualified production engineer has not certified the scenario. A
credible research result requires paired ablations and source-based semantic
review as well as mechanical scoring; negative results remain valid outcomes.
