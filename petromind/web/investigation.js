/* Public-evidence projection only. No raw replay, private protocol or reasoning. */
(function (root) {
  "use strict";
  const faultNames = {
    1: "Abrupt flow increase",
    2: "Unexpected safety-valve closure",
    5: "Rapid productivity loss",
    7: "Scaling in the production choke",
    8: "Hydrate in the production line",
    9: "Service-line hydrate",
  };
  function graph(events) {
    const nodes = new Map(),
      edges = [];
    const add = (id, label, kind, data, layer, event, sensor) => {
      if (!id) return;
      if (!nodes.has(id))
        nodes.set(id, { id, label, kind, data, layer, sensor, eventKeys: [] });
      const n = nodes.get(id);
      if (!n.eventKeys.includes(event)) n.eventKeys.push(event);
      return id;
    };
    const link = (from, to, label, kind, event, provenance) => {
      if (nodes.has(from) && nodes.has(to))
        edges.push({ from, to, label, kind, event, provenance });
    };
    events.forEach((e, ei) => {
      if (e.kind === "evidence_received") {
        add(
          "hypothesis",
          faultNames[e.hypothesis] || `Fault ${e.hypothesis}`,
          "hypothesis",
          {
            prediction: e.hypothesis,
            scope: "Statistical prediction; not confirmed cause",
          },
          0,
          ei,
        );
        add(
          "claim",
          "Constructed claim under audit",
          "claim",
          {
            claim: e.claim,
            scope: "Constructed evaluation claim, not an expert diagnosis",
          },
          0,
          ei,
        );
        link(
          "hypothesis",
          "claim",
          "claim being audited",
          "record",
          ei,
          "received packet",
        );
        for (const [s, v] of Object.entries(e.observations || {}))
          add(
            "measurement:" + s,
            s,
            v.available ? "measurement" : "unavailable",
            {
              sensor: s,
              ...v,
              scope: "Original summary received by Muse; not the viewer replay",
            },
            1,
            ei,
            s,
          );
      }
      if (e.kind === "tool_request")
        add(
          "pending:" + e.sequence,
          e.topic ? `Lookup: ${e.topic}` : e.tool,
          "request",
          e,
          0,
          ei,
        );
      if (e.kind !== "tool_result") return;
      nodes.delete("pending:" + e.sequence);
      if (e.validation?.code)
        add(
          "validation:" + e.sequence,
          "Submission correction",
          "validation",
          e.validation,
          4,
          ei,
        );
      if (e.sensor && e.summary) {
        add(
          e.citation_id,
          e.sensor,
          "measurement",
          {
            sensor: e.sensor,
            ...e.summary,
            purpose: e.purpose,
            remaining_budget: e.remaining_budget,
            scope: e.scope,
          },
          1,
          ei,
          e.sensor,
        );
        link(
          e.source_id,
          e.citation_id,
          "motivated request · not fault proof",
          "citation",
          ei,
          e.source_id,
        );
      }
      for (const f of e.facts || []) {
        const id = f.citation_id || f.id;
        add(id, `${f.subject} → ${f.relation} → ${f.object}`, "fact", f, 3, ei);
        const subject = "entity:" + f.subject,
          object = "entity:" + f.object;
        add(
          subject,
          f.subject,
          f.subject.startsWith("fault:") ? "hypothesis" : "entity",
          {
            entity: f.subject,
            scope: f.scope,
            returned_in: id,
            fact: f,
            provenance: f.provenance,
          },
          2,
          ei,
        );
        add(
          object,
          f.object,
          f.relation === "affects" ? "equipment" : "entity",
          {
            entity: f.object,
            scope: f.scope,
            returned_in: id,
            provenance: f.provenance,
          },
          2,
          ei,
        );
        link(
          subject,
          object,
          f.relation,
          f.status === "documented" ? "documented" : "hypothesis",
          ei,
          f,
        );
        link(subject, id, "returned source fact", "record", ei, f);
        link(object, id, "described by", "record", ei, f);
        // Link a measurement only if the actual returned triple names that sensor.
        for (const s of [f.subject, f.object])
          link(
            "measurement:" + s,
            id,
            "sensor explicitly named in source",
            "documented",
            ei,
            f,
          );
        if (
          f.subject ===
          `fault:${events.find((x) => x.kind === "evidence_received")?.hypothesis}`
        )
          link(
            "hypothesis",
            subject,
            "same fault category · not confirmation",
            "record",
            ei,
            f,
          );
      }
      for (const m of e.matches || []) {
        add(
          m.citation_id,
          `Analogue · ${m.shared_sensors} shared`,
          "history",
          m,
          3,
          ei,
        );
        for (const s of m.matched_sensors || [])
          link(
            "measurement:" + s,
            m.citation_id,
            "shared measured characteristic",
            "empirical",
            ei,
            m.citation_id,
          );
      }
      if (e.assessment)
        e.assessment.findings.forEach((f, i) => {
          const id = "finding:" + i;
          add(id, f.statement, "finding", f, 4, ei);
          for (const cite of f.citations || [])
            link(
              cite,
              id,
              "Muse cites · citation is not entailment",
              "citation",
              ei,
              cite,
            );
          if (f.missing_premise) {
            add(
              "gap:" + i,
              f.missing_premise,
              "gap",
              {
                missing_premise: f.missing_premise,
                next_evidence: f.next_evidence,
                scope: "Public Muse finding, not verified physical truth",
              },
              4,
              ei,
            );
            link(
              id,
              "gap:" + i,
              "missing premise",
              "assessment",
              ei,
              "submitted public assessment",
            );
          }
        });
    });
    return { nodes: [...nodes.values()], edges };
  }
  function assessmentSections(result) {
    const sections = { measured: [], documented: [], causal: [], other: [] };
    for (const f of result.findings || []) {
      // Group for presentation only; never rewrite a recorded scope or verdict.
      const key =
        f.scope === "measured_observation"
          ? "measured"
          : f.scope === "documented_comparison"
            ? "documented"
            : f.scope === "diagnostic_conclusion"
              ? "causal"
              : !f.scope && f.basis === "measurement"
                ? "measured"
                : !f.scope && f.basis === "documented"
                  ? "documented"
                  : "other";
      sections[key].push(f);
    }
    return sections;
  }
  const api = {
    graph,
    assessmentSections,
    faultNames,
    visible: (events, cursor) =>
      events.slice(0, Math.max(0, Math.min(cursor, events.length))),
    result: (events) =>
      [...events].reverse().find((e) => e.assessment)?.assessment || null,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PublicInvestigation = api;
})(typeof window !== "undefined" ? window : globalThis);
