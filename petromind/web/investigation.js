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
  function focusedGraph(events, eventIndex, nodeId, limit = 10) {
    const full = graph(events),
      byId = new Map(full.nodes.map((n) => [n.id, n]));
    const current = events[eventIndex];
    const active =
      current?.kind === "completion"
        ? [...events].reverse().find((e) => e.assessment)
        : current;
    let anchor = byId.get(nodeId);
    if (!anchor && active?.assessment) {
      let i = active.assessment.findings.findIndex(
        (f) =>
          f.scope === "diagnostic_conclusion" &&
          f.verdict === "NOT_ESTABLISHED",
      );
      if (i < 0)
        i = active.assessment.findings.findIndex((f) => f.missing_premise);
      anchor = byId.get("finding:" + (i < 0 ? 0 : i));
    }
    const selected = new Set();
    const add = (id) => {
      if (byId.has(id) && selected.size < limit) selected.add(id);
    };
    if (anchor) {
      add(anchor.id);
      for (const e of full.edges)
        if (e.to === anchor.id || e.from === anchor.id) {
          add(e.from);
          add(e.to);
        }
      add("hypothesis"); // Context node; no invented connection to the finding.
    } else {
      const candidates = full.nodes.filter((n) =>
        n.eventKeys.includes(eventIndex),
      );
      candidates.sort(
        (a, b) =>
          (({ fact: 0, history: 0, request: 0, measurement: 1 })[a.kind] ?? 2) -
          ({ fact: 0, history: 0, request: 0, measurement: 1 }[b.kind] ?? 2),
      );
      for (const n of candidates) add(n.id);
    }
    for (const e of full.edges)
      if (!anchor && (selected.has(e.from) || selected.has(e.to))) {
        add(e.from);
        add(e.to);
      }
    return {
      nodes: full.nodes.filter((n) => selected.has(n.id)),
      edges: full.edges.filter(
        (e) => selected.has(e.from) && selected.has(e.to),
      ),
      total: full.nodes.length,
    };
  }
  function takeaway(result) {
    const f = result.findings || [],
      count = (scope, verdict) =>
        f.filter((x) => x.scope === scope && x.verdict === verdict).length;
    return [
      {
        kind: "measured",
        count: count("measured_observation", "SUPPORTED"),
        text: "measured observations supported",
      },
      {
        kind: "documented",
        count: count("documented_comparison", "SUPPORTED"),
        text: "documented comparisons supported",
      },
      {
        kind: "causal",
        count: count("diagnostic_conclusion", "NOT_ESTABLISHED"),
        text: "causal conclusions not established",
      },
      {
        kind: "contradicted",
        count: f.filter((x) => x.verdict === "CONTRADICTED").length,
        text: "claims contradicted by cited evidence",
      },
    ]
      .filter((x) => x.count)
      .map((x) => ({
        ...x,
        text:
          x.count === 1
            ? x.text
                .replace("observations", "observation")
                .replace("comparisons", "comparison")
                .replace("conclusions", "conclusion")
                .replace("claims", "claim")
            : x.text,
      }));
  }
  function completedResult(events) {
    // A submitted assessment alone is not a completed investigation.
    const end = events.findLastIndex((e) => e.kind === "completion");
    if (end < 0 || events[end].status !== "completed") return null;
    return (
      events
        .slice(0, end)
        .findLast((e) => e.tool === "submit_audit" && e.assessment)
        ?.assessment || null
    );
  }
  function conclusion(events) {
    const result = completedResult(events);
    if (!result) return null;
    const received = events.find((e) => e.kind === "evidence_received") || {};
    const findings = result.findings || [];
    const observations = { ...received.observations };
    for (const e of events)
      if (e.sensor && e.summary) observations[e.sensor] = e.summary;
    const measured = [];
    for (const [sensor, summary] of Object.entries(observations)) {
      const indices = findings.flatMap((f, i) =>
        f.verdict === "SUPPORTED" &&
        (f.scope === "measured_observation" ||
          (!f.scope && f.basis === "measurement")) &&
        (f.citations || []).includes("measurement:" + sensor)
          ? [i]
          : [],
      );
      const numbers = (result.numeric_observations || []).filter(
        (n) => n.sensor === sensor,
      );
      const matches = (metric) =>
        numbers.some(
          (n) =>
            n.metric === metric &&
            Number.isFinite(n.value) &&
            n.value === summary[metric],
        );
      if (
        indices.length &&
        summary.available &&
        Number.isFinite(summary.first) &&
        Number.isFinite(summary.last) &&
        (matches("delta") || (matches("first") && matches("last")))
      )
        measured.push({ sensor, summary, indices });
    }
    const causal = findings.filter((f) => f.scope === "diagnostic_conclusion");
    const priority = (f) =>
      f.scope === "diagnostic_conclusion" ||
      (!f.scope && f.basis === "hypothesis")
        ? 0
        : f.basis === "unsupported"
          ? 1
          : 2;
    const gaps = findings
      .filter((f) => f.missing_premise)
      .sort((a, b) => priority(a) - priority(b));
    const verified =
      causal.length > 0 &&
      causal.every((f) => f.verdict === "SUPPORTED" && !f.missing_premise);
    const contradicted = causal.some((f) => f.verdict === "CONTRADICTED");
    const unsupported =
      causal.some((f) =>
        ["NOT_ESTABLISHED", "PARTIALLY_SUPPORTED"].includes(f.verdict),
      ) ||
      findings.some(
        (f) =>
          !f.scope &&
          ["hypothesis", "unsupported"].includes(f.basis) &&
          f.missing_premise &&
          ["NOT_ESTABLISHED", "PARTIALLY_SUPPORTED"].includes(f.verdict),
      );
    const status =
      !causal.length && result.verdict === "CONTRADICTED"
        ? "claim_contradicted"
        : verified
          ? "supported"
          : contradicted
            ? "contradicted"
            : unsupported
              ? "unverified"
              : "not_recorded";
    const fault =
      faultNames[received.hypothesis] ||
      (received.hypothesis
        ? "fault category " + received.hypothesis
        : "proposed cause");
    const pressurePair = ["P-PDG", "P-TPT"].every((sensor) =>
      measured.some((m) => m.sensor === sensor),
    );
    const headline = pressurePair
      ? measured
          .filter((m) => ["P-PDG", "P-TPT"].includes(m.sensor))
          .every((m) => m.summary.last > m.summary.first)
        ? "Pressure increases confirmed."
        : "Pressure changes confirmed."
      : measured.length
        ? "Recorded measurements confirmed."
        : result.verdict === "CONTRADICTED"
          ? "The assessed claim is contradicted."
          : result.verdict === "SUPPORTED"
            ? "The assessed claim is supported within its stated scope."
            : "The full assessed claim is not established.";
    const cause =
      status === "claim_contradicted"
        ? "The assessed claim is contradicted; the physical cause is not settled."
        : status === "supported"
          ? "Muse recorded support for the causal claim."
          : status === "contradicted"
            ? "The causal claim is contradicted by the cited evidence."
            : status === "unverified"
              ? "Suspected " + fault.toLowerCase() + " not verified."
              : "No separate root-cause confirmation was recorded.";
    // Preserve recorded scope: an accepted source comparison is not a causal finding.
    const confirmed = findings.filter(
      (f) => f.verdict === "SUPPORTED" && f.scope !== "diagnostic_conclusion",
    );
    const uncertain = [...new Set(gaps.map((f) => f.missing_premise))];
    const next = [
      ...new Set(
        gaps
          .map((f) =>
            typeof f.next_evidence === "string"
              ? f.next_evidence
              : f.next_evidence?.kind !== "none"
                ? f.next_evidence?.purpose
                : "",
          )
          .filter(Boolean),
      ),
    ];
    return {
      headline,
      cause,
      status,
      fault,
      measured,
      confirmed,
      uncertain,
      next,
      caveat:
        status === "unverified" || status === "not_recorded"
          ? "Not verified does not mean ruled out. A pattern or source comparison alone does not identify its physical cause."
          : status === "contradicted"
            ? "A contradiction applies to the assessed claim; it does not by itself exclude every version of the suspected fault."
            : "This reports the accepted model finding, not independent verification of physical correctness.",
    };
  }
  function operatorConclusion(events) {
    const summary = conclusion(events);
    if (!summary) return null;
    const result = completedResult(events),
      received = events.find((e) => e.kind === "evidence_received") || {};
    const mechanism = events
      .flatMap((e) => e.facts || [])
      .find(
        (f) =>
          f.subject === `fault:${received.hypothesis}` &&
          f.relation === "described_as" &&
          f.object === "hydrate_obstruction",
      );
    const suspected =
      mechanism && /hydrate/i.test(summary.fault)
        ? summary.fault + " obstruction"
        : summary.fault;
    const statusLabel = {
      supported: "Root cause supported within the assessed claim’s scope",
      unverified: "Root cause not established",
      contradicted: "Specific causal claim contradicted",
      claim_contradicted: "Assessed claim contradicted; root cause not settled",
      not_recorded: "No separate root-cause assessment recorded",
    }[summary.status];
    const rootVerdict = {
      supported: "SUPPORTED WITHIN SCOPE",
      unverified: "NOT ESTABLISHED",
      contradicted: "CAUSAL CLAIM CONTRADICTED",
      claim_contradicted: "CLAIM CONTRADICTED",
      not_recorded: "NOT SEPARATELY ASSESSED",
    }[summary.status];
    // Do not interpret free-text gaps as physical rules. Keep each request tied
    // to its recorded finding and preserve negation, conditions and terminology.
    const requirementSources = [];
    const requests = [];
    result.findings.forEach((f, findingIndex) => {
      const premise =
        typeof f.missing_premise === "string" ? f.missing_premise.trim() : "";
      const n = f.next_evidence;
      const structured =
        n && typeof n === "object" && n.kind && n.kind !== "none";
      const purpose =
        structured && typeof n.purpose === "string" ? n.purpose.trim() : "";
      const legacy = typeof n === "string" ? n.trim() : "";
      if (purpose || legacy)
        requests.push({
          text: purpose || legacy,
          kind: structured ? n.kind : "legacy_request",
          target: structured ? n.target : "",
          findingIndex,
        });
      // A no-test record describes a limitation, not evidence to obtain.
      const evidencePurpose =
        n?.kind === "no_verified_discriminating_test" ? "" : purpose;
      if (evidencePurpose || premise)
        requirementSources.push({
          text: evidencePurpose || premise,
          source: evidencePurpose ? "recorded evidence request" : "recorded missing premise",
          findingIndex,
          premise,
          citations: [...(f.citations || [])],
        });
    });
    const requirements = requirementSources.map((r) => r.text);
    const noTest = result.findings.some((f) =>
      f.next_evidence?.kind === "no_verified_discriminating_test" ||
      (typeof f.next_evidence === "string" && /^No verified discriminating test (?:is |was )?(?:supplied|provided|identified|available)\b/i.test(f.next_evidence.trim())),
    );
    const comparisons = summary.confirmed.filter(
      (f) =>
        f.scope === "documented_comparison" ||
        (!f.scope && f.basis === "documented"),
    );
    const explanation =
      summary.status === "unverified"
        ? `${summary.measured.length ? "The measurement changes are supported. " : ""}${comparisons.length ? "Muse also supported a comparison with documented engineering context. " : ""}The evidence does not establish the suspected explanation as the cause. Not established does not mean disproven or ruled out.`
        : summary.status === "supported"
          ? "The accepted findings support the causal claim within its stated scope. Independent verification of physical correctness is still required."
          : summary.status === "contradicted" ||
              summary.status === "claim_contradicted"
            ? "The evidence contradicts the assessed claim. This does not automatically rule out every version of the suspected fault."
            : "The assessment supports only the findings shown below; it does not contain a separate root-cause assessment.";
    return {
      ...summary,
      suspected,
      statusLabel,
      rootVerdict,
      explanation,
      comparisons,
      nextPlan: {
        question: `What evidence is needed to assess ${suspected.toLowerCase()} as the cause?`,
        requirements,
        requirementSources,
        requests,
        limitation: noTest
          ? "The investigation did not identify a verified test that can conclusively distinguish these causes."
          : requests.length
            ? "The assessment requests additional evidence but does not supply a verified procedure for distinguishing these causes."
            : "No next-evidence recommendation or verified discriminating test was supplied.",
        noTest,
      },
    };
  }
  function findingEvidence(events, index) {
    const result = completedResult(events),
      f = result?.findings[index];
    if (!f) return { available: false, citations: [], unresolved: [] };
    const full = graph(events),
      ids = new Set(full.nodes.map((n) => n.id));
    const citations = (f.citations || []).filter((id) => ids.has(id));
    return {
      available: citations.length > 0 || ids.has("gap:" + index),
      citations,
      unresolved: (f.citations || []).filter((id) => !ids.has(id)),
      gap: ids.has("gap:" + index),
      finding: f,
    };
  }
  const api = {
    graph,
    completedResult,
    conclusion,
    operatorConclusion,
    findingEvidence,
    assessmentSections,
    focusedGraph,
    takeaway,
    faultNames,
    visible: (events, cursor) =>
      events.slice(0, Math.max(0, Math.min(cursor, events.length))),
    result: (events) =>
      [...events].reverse().find((e) => e.assessment)?.assessment || null,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PublicInvestigation = api;
})(typeof window !== "undefined" ? window : globalThis);
