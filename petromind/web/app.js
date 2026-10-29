"use strict";
const $ = (id) => document.getElementById(id);
const node = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
let cases = [],
  status = {},
  current = 0,
  condition = "grounded",
  selected = 0,
  tab = "Measurements",
  mode = "replay",
  opened = false;
const liveRows = new Map();
const nice = (x) => x.replaceAll("_", " ").toLowerCase();
const number = (v) =>
  v === null || v === undefined
    ? "Unavailable"
    : Number(v).toLocaleString("en-US", { maximumFractionDigits: 3 });
function activeCase() {
  return cases[current];
}
function activeAudit() {
  if (mode === "live" && liveRows.has(activeCase().id)) {
    const r = liveRows.get(activeCase().id);
    return {
      output: r.output,
      requests: r.requests,
      usage: r.usage,
      latency_seconds: r.latency_seconds,
      notes: [],
      sources: liveSources(r),
    };
  }
  return activeCase().audits[condition];
}
function liveSources(r) {
  const out = {};
  for (const a of r.audit || []) {
    const v = JSON.parse(a.result_json);
    for (const f of [...(v.facts || []), ...(v.matches || [])])
      out[f.citation_id] = f;
  }
  return out;
}
function showError(text) {
  $("error").textContent = text;
  $("error").hidden = false;
}
function renderCases() {
  const target = $("cases");
  target.replaceChildren();
  cases.forEach((c, i) => {
    const b = node(
      "button",
      undefined,
      "case-button" + (i === current ? " active" : ""),
    );
    b.append(
      node("small", `CASE 0${i + 1} / REAL 3W`),
      node("strong", i === 0 ? "The causal leap" : "The limited comparison"),
      node("span", i === 0 ? "Measured ≠ established" : "A match ≠ root cause"),
    );
    b.onclick = () => {
      current = i;
      selected = 0;
      opened = false;
      render();
    };
    target.append(b);
  });
}
function setMode(m) {
  mode = m;
  selected = 0;
  opened = false;
  condition = "grounded";
  render();
}
function render() {
  renderCases();
  const c = activeCase();
  $("caseNumber").textContent = `CASE 0${current + 1} / CLAIM INVESTIGATION`;
  $("caseTitle").textContent = c.title;
  $("claim").textContent = c.packet.claim;
  $("budgetValue").textContent = Object.keys(c.observations).length;
  const b = c.packet.baseline;
  const p = b.probabilities.find((x) => x.fault_type === b.prediction);
  $("baseline").replaceChildren(
    node("strong", `Statistical prediction: fault ${b.prediction}`),
    node(
      "span",
      ` · ${p ? (p.probability * 100).toFixed(2) + "% model score" : ""} · uncalibrated`,
    ),
  );
  $("modeBadge").textContent =
    mode === "replay" ? "CAPTURED REAL RUN · V1" : "LIVE MODE · NEW V2";
  $("replayMode").classList.toggle("active", mode === "replay");
  $("liveMode").classList.toggle("active", mode === "live");
  $("liveMode").disabled = !status.live_enabled;
  $("liveHelp").textContent = status.live_enabled
    ? "Live calls require an explicit click and use the frozen estimated-cost cap."
    : "Live calls are disabled. Replay requires no API key.";
  $("auditArea").hidden = !opened;
  $("inspect").textContent =
    mode === "replay" ? "Follow the evidence ↗" : "Inspect / run live v2 ↗";
  if (opened) renderAudit();
}
function renderAudit() {
  const c = activeCase();
  const a = activeAudit();
  const hasLive = mode === "live" && liveRows.has(c.id);
  $("grounded").classList.toggle("selected", condition === "grounded");
  $("ungrounded").classList.toggle("selected", condition === "ungrounded");
  $("grounded").disabled = mode === "live";
  $("ungrounded").disabled = mode === "live";
  $("liveRun").hidden = mode !== "live";
  $("liveNotice").hidden = mode !== "live";
  $("liveNotice").textContent = hasLive
    ? "New live v2 execution. Not part of the original pilot; independent review pending."
    : "Live v2 has not been paid-evaluated. Below is the original captured reference until you explicitly run live. No API call has been made by opening this view.";
  if (!a.output) {
    $("verdictTitle").textContent = "No successful live audit";
    $("findings").replaceChildren();
    return;
  }
  const r = a.output;
  selected = Math.min(selected, r.findings.length - 1);
  $("verdictTitle").textContent =
    current === 0
      ? "A measured trend. An unestablished cause."
      : "A documented comparison. A bounded conclusion.";
  $("verdictBadge").textContent = r.verdict.replaceAll("_", " ");
  $("verdictBadge").className =
    "verdict" + (r.verdict === "SUPPORTED" ? " supported" : "");
  $("runStats").textContent =
    `${hasLive ? "Live v2" : "Captured v1"} · ${a.requests} requests · $${a.usage.estimated_cost_usd.toFixed(4)} estimated · ${a.latency_seconds.toFixed(1)}s`;
  const list = $("findings");
  list.replaceChildren();
  r.findings.forEach((f, i) => {
    const b = node(
      "button",
      undefined,
      "finding" + (i === selected ? " active" : ""),
    );
    b.append(
      node("span", String(i + 1).padStart(2, "0"), "finding-index"),
      node("strong", f.statement),
      node(
        "small",
        `${nice(f.scope || f.basis)} / ${nice(f.verdict)}`,
        f.verdict === "SUPPORTED" ? "" : "warn",
      ),
    );
    b.onclick = () => {
      selected = i;
      renderAudit();
    };
    list.append(b);
  });
  const f = r.findings[selected];
  $("premises").replaceChildren(...f.premises.map((p) => node("li", p)));
  $("justification").textContent = f.justification;
  $("gapTitle").textContent =
    f.verdict === "SUPPORTED"
      ? "02 / KEEP THE CLAIM WITHIN ITS SCOPE"
      : "02 / LOCATE THE MISSING PREMISE";
  $("gap").textContent =
    f.verdict === "SUPPORTED" && f.missing_premise
      ? "Captured v1 proposed gap (reviewed below as a requirement for a stronger claim): " +
        f.missing_premise
      : f.missing_premise || "No missing premise at the stated claim scope.";
  $("next").textContent =
    typeof f.next_evidence === "string"
      ? f.next_evidence
      : `${nice(f.next_evidence.kind)}${f.next_evidence.target ? " / " + f.next_evidence.target : ""}${f.next_evidence.purpose ? " — " + f.next_evidence.purpose : ""}`;
  $("note").textContent =
    a.notes?.[selected]?.text ||
    "New live output. Mechanical source/value checks do not establish semantic or physical correctness. Independent review is required.";
  $("citations").replaceChildren(
    ...f.citations.map((id) => {
      const b = node("button", id, "citation");
      b.onclick = () => {
        tab = id.startsWith("measurement:")
          ? "Measurements"
          : id.startsWith("analogue:")
            ? "History"
            : "Knowledge";
        renderEvidence();
        $("evidence").scrollIntoView({ behavior: "smooth", block: "nearest" });
      };
      return b;
    }),
  );
  $("actions").replaceChildren(
    ...c.reviewed_actions.map((action) => {
      const d = node("article", undefined, "action-card");
      d.append(
        node("div", action.kind, "eyebrow"),
        node("h3", action.target),
        node("p", action.purpose),
        node("p", action.status, "action-status"),
      );
      return d;
    }),
  );
  $("raw").textContent = JSON.stringify(
    {
      attribution: hasLive
        ? "New live v2 output"
        : "Original captured real Muse output, unchanged",
      protocol_id: hasLive
        ? liveRows.get(c.id).protocol_id
        : c.source_protocol_id,
      output: r,
    },
    null,
    2,
  );
  renderEvidence();
}
function renderEvidence() {
  for (const t of ["Measurements", "Knowledge", "History"])
    $("tab" + t).classList.toggle("selected", t === tab);
  const e = $("evidence");
  e.replaceChildren();
  const c = activeCase();
  const a = activeAudit();
  if (tab === "Measurements") {
    e.append(
      node(
        "div",
        "Recorded endpoints and quality summaries from a 600-second diagnostic window. Endpoint comparison, not a reconstructed time series. No new sensor access.",
        "evidence-info",
      ),
    );
    for (const [sensor, s] of Object.entries(c.observations)) {
      const d = node("article", undefined, "sensor-card");
      const head = node("div", undefined, "sensor-name");
      head.append(
        node("span", sensor),
        node(
          "span",
          `${s.count}/${s.total} valid · ${s.quality_status}`,
          "quality" + (!s.available ? " missing" : ""),
        ),
      );
      d.append(head);
      if (s.available) {
        const ends = node("div", undefined, "endpoints");
        const first = node("div");
        first.append(
          node("small", "FIRST RECORDED"),
          node("strong", number(s.first)),
        );
        const last = node("div");
        last.append(
          node("small", "LAST RECORDED"),
          node("strong", number(s.last)),
        );
        ends.append(
          first,
          node(
            "span",
            s.delta === 0 ? "→" : s.delta > 0 ? "↗" : "↘",
            "endpoint-arrow",
          ),
          last,
        );
        d.append(
          ends,
          node(
            "div",
            `Δ ${s.delta > 0 ? "+" : ""}${number(s.delta)} ${sensor.startsWith("P-") ? "Pa" : "%"}`,
            "delta",
          ),
        );
      } else
        d.append(
          node(
            "p",
            "No observed value. Do not infer an opening or valve position.",
            "evidence-info",
          ),
        );
      d.append(
        node(
          "div",
          s.available
            ? "Recorded values establish this numerical observation, not its physical cause."
            : "Missing readings remain missing; legitimate zeros would remain valid.",
          "sensor-caption",
        ),
      );
      e.append(d);
    }
  } else if (tab === "Knowledge") {
    e.append(
      node(
        "div",
        "Facts actually retrieved in this run. Documented generic semantics and published examples are not verified per-well topology.",
        "evidence-info",
      ),
    );
    const facts = Object.values(a.sources).filter((f) => f.provenance);
    if (!facts.length)
      e.append(
        node(
          "p",
          "This ungrounded audit received no documentary context. Withholding documentary verification is reasonable.",
          "evidence-info",
        ),
      );
    for (const f of facts) {
      const d = node("article", undefined, "fact-card");
      const g = node("div", undefined, "fact-graph");
      g.append(
        node("span", f.subject, "fact-node"),
        node("span", f.relation.replace("example:", "example / "), "relation"),
        node("span", f.object, "fact-node"),
      );
      d.append(
        g,
        node("p", `${f.status} · ${nice(f.scope)}`),
        node("p", f.locator),
      );
      const url = f.provenance.url;
      if (
        url &&
        /^https:\/\/(arxiv\.org|github\.com|api\.github\.com)\//.test(url)
      ) {
        const link = node("a", "Open source ↗");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        d.append(link);
      }
      e.append(d);
    }
    e.append(
      node(
        "div",
        "Valve-code review: the registered Table 3 semantics are 0 closed, 1 open, 0.5 other. Neither captured audit queried them; no actual ESTADO-DHSV measurement is in these packets. This is review context, not captured Muse reasoning.",
        "evidence-info",
      ),
    );
  } else {
    e.append(
      node(
        "div",
        "Relative-median analogues from training wells only. Distances are not fault probabilities. Compare overlap before interpreting similarity.",
        "evidence-info",
      ),
    );
    const matches = Object.values(a.sources).filter((f) => f.matched_sensors);
    if (!matches.length)
      e.append(
        node(
          "p",
          "No historical evidence was returned to this condition.",
          "evidence-info",
        ),
      );
    for (const m of matches) {
      const d = node("article", undefined, "fact-card");
      d.append(
        node(
          "div",
          `${m.citation_id} / historical event ${m.training_event}`,
          "eyebrow",
        ),
        node(
          "h3",
          `${m.shared_sensors} of ${Object.keys(c.observations).length} observed sensors shared`,
        ),
      );
      const progress = node("progress");
      progress.max = Object.keys(c.observations).length;
      progress.value = m.shared_sensors;
      progress.setAttribute("aria-label", "Shared observed sensors");
      d.append(progress);
      for (const s of m.matched_sensors)
        d.append(node("span", s, "sensor-tag"));
      d.append(
        node(
          "p",
          `Distance ${m.distance}. Shared sensor names do not establish a shared physical cause.`,
        ),
      );
      e.append(d);
    }
  }
}
$("inspect").onclick = () => {
  opened = true;
  selected = condition === "grounded" ? 2 : current === 0 ? 3 : 2;
  render();
  $("auditArea").scrollIntoView({ behavior: "smooth", block: "start" });
};
$("grounded").onclick = () => {
  condition = "grounded";
  selected = 2;
  renderAudit();
};
$("ungrounded").onclick = () => {
  condition = "ungrounded";
  selected = current === 0 ? 3 : 2;
  renderAudit();
};
for (const t of ["Measurements", "Knowledge", "History"])
  $("tab" + t).onclick = () => {
    tab = t;
    renderEvidence();
  };
$("replayMode").onclick = () => setMode("replay");
$("liveMode").onclick = () => {
  if (status.live_enabled) setMode("live");
};
$("downloadReview").onclick = async () => {
  const r = await fetch("/api/review");
  const blob = new Blob([JSON.stringify(await r.json(), null, 2)], {
    type: "application/json",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "petromind-mechanical-claim-review.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("liveRun").onclick = async () => {
  const b = $("liveRun");
  b.disabled = true;
  b.textContent = "Muse is auditing…";
  const id = activeCase().id;
  try {
    const response = await fetch("/api/live", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-PetroMind-Token": status.token,
      },
      body: JSON.stringify({
        case_id: id,
        request_id: crypto.randomUUID().replaceAll("-", ""),
      }),
    });
    const r = await response.json();
    if (!response.ok || r.status !== "completed")
      throw new Error(r.error || r.reason || "Live run failed");
    liveRows.set(id, r);
    selected = 0;
    if (activeCase().id === id) renderAudit();
  } catch (error) {
    showError(
      `Live execution did not complete: ${error.message}. No replay has been substituted for this live result.`,
    );
  } finally {
    b.disabled = false;
    b.textContent = "Run live v2 · uses API";
  }
};
(async () => {
  try {
    const [c, s] = await Promise.all([
      fetch("/api/cases"),
      fetch("/api/status"),
    ]);
    if (!c.ok || !s.ok) throw new Error("Cannot load reviewed capture");
    cases = (await c.json()).cases;
    status = await s.json();
    render();
  } catch (e) {
    showError(e.message);
  }
})();
