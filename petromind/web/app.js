"use strict";
const $ = (id) => document.getElementById(id),
  NS = "http://www.w3.org/2000/svg";
const el = (tag, text, cls) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
};
const svg = (tag, attrs, text) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {}))
    n.setAttribute(k, String(v));
  if (text !== undefined) n.textContent = text;
  return n;
};
const SCENES = [
  "See the well",
  "Replay the change",
  "The diagnosis",
  "Muse investigates",
  "The verdict",
];
const FAULTS = {
  9: "Hydrate blockage in the service line",
  2: "Unexpected closure of the downhole safety valve",
};
const symbols = {
  rising: "↑",
  falling: "↓",
  stable: "→",
  missing: "—",
  invalid: "!",
};
let contextSensor = false;
let cases = [],
  status = {},
  current = 0,
  scene = 0,
  index = 1,
  selected = "P-TPT",
  condition = "grounded",
  timer = null,
  liveBusy = false;
const liveResults = new Map();
const c = () => cases[current],
  audit = () => c().audits[condition],
  fmt = (v, d = 2) =>
    v === null || v === undefined
      ? "Not observed"
      : Number(v).toLocaleString("en-US", { maximumFractionDigits: d });
const pressure = (s) => s.startsWith("P-"),
  unit = (s) => c().sensor_definitions[s]?.unit || "unknown";
const unitDisplay = (s) => (pressure(s) ? "MPa" : unit(s)),
  scaled = (s, v) => (v === null ? null : pressure(s) ? v / 1e6 : v);
function value(s, v) {
  return v === null
    ? "Not observed"
    : `${fmt(scaled(s, v), 3)} ${unitDisplay(s)}`;
}
function state(s, i = index) {
  const stream = c().replay.series[s];
  if (!stream)
    return {
      value: null,
      quality: "not_in_audit",
      trend: "missing",
      label: "Not in audit",
    };
  const sample = stream.samples[i];
  if (sample.quality !== "valid")
    return {
      ...sample,
      trend: sample.quality,
      label:
        sample.quality === "invalid" ? "Invalid reading" : "Missing reading",
    };
  const ref = stream.reference,
    delta = ref === null ? null : sample.value - ref;
  return {
    ...sample,
    delta,
    trend:
      delta === null
        ? "missing"
        : delta === 0
          ? "stable"
          : delta > 0
            ? "rising"
            : "falling",
    label:
      delta === null
        ? "No valid reference"
        : delta === 0
          ? "Unchanged from first valid"
          : `${delta > 0 ? "Rising" : "Falling"} from first valid`,
  };
}
function resetPlayback() {
  if (timer) clearInterval(timer);
  timer = null;
}
function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}
function goto(n) {
  contextSensor = false;
  scene = Math.max(0, Math.min(4, n));
  render();
}
function render() {
  $("modeBadge").textContent = "Real captured audit · replay";
  $("caseSelect").value = String(current);
  $("progress").replaceChildren(
    ...SCENES.map((text, i) => {
      const b = el("button", undefined, i === scene ? "active" : "");
      b.append(el("b", String(i + 1).padStart(2, "0")), el("span", text));
      b.setAttribute("aria-current", i === scene ? "step" : "false");
      b.onclick = () => goto(i);
      return b;
    }),
  );
  const heads = [
    [
      "This is a production well.",
      "Pressure, temperature and equipment-state sensors record what happens.",
    ],
    [
      "Explore the recorded change.",
      "Rising or falling describes a measurement—not whether it is dangerous.",
    ],
    [
      "A plausible diagnosis is still a claim.",
      `The statistical model suggests: ${FAULTS[c().packet.baseline.prediction]}.`,
    ],
    [
      "Muse follows the claim to its evidence.",
      "Real captured findings and tool activity. Navigation explanations are editorial.",
    ],
    [
      current === 0
        ? "The pressure changes are real. The claimed root cause is not established."
        : "The pattern comparison is supported. Root cause is not established.",
      "Whole-window verdict: moving the playback cursor never changes the captured audit.",
    ],
  ];
  $("headline").className = "headline" + (scene === 4 ? " final" : "");
  $("headline").replaceChildren(
    el("h2", heads[scene][0]),
    el("p", heads[scene][1]),
  );
  $("replayBadge").textContent =
    c().replay.mode === "raw"
      ? "Real samples · viewer only"
      : "Actual endpoints · no raw series";
  $("timelineTitle").textContent =
    c().replay.mode === "raw"
      ? "Replay the original diagnostic window"
      : "Compare the captured endpoints";
  $("reference").textContent = c().replay.reference_note;
  $("slider").max = String(c().replay.mode === "raw" ? 599 : 1);
  $("slider").value = String(index);
  $("play").disabled = !c().replay.can_play;
  $("speed").disabled = !c().replay.can_play;
  $("play").textContent = timer ? "Ⅱ Pause" : "▶ Play";
  $("timing").textContent =
    c().replay.timing + " No interpolation or downsampling.";
  $("visibility").textContent =
    c().replay.visibility +
    (c().replay.mode === "endpoints"
      ? " Raw replay unavailable: " +
        c().replay.availability.replaceAll("_", " ") +
        ". Play is disabled."
      : "");
  const hints = [
    "Click a sensor for its meaning and source.",
    "Compare measured values. A trend is not a cause.",
    "Constructed evaluation claim—not an expert diagnosis.",
    "These are captured public findings, not private model reasoning.",
    "The audit is fixed; the slider only changes the viewer’s position.",
  ];
  $("sceneHint").textContent = hints[scene];
  $("nextScene").textContent = [
    "Replay what happened →",
    "See the diagnosis →",
    "Audit this diagnosis →",
    "See Muse’s verdict →",
    "Restart the story ↺",
  ][scene];
  $("verdictSection").hidden = scene !== 4;
  renderDiagram();
  renderContext();
  renderTime();
  renderVerdict();
  if (!$("details").hidden) renderDetails();
}
function renderDiagram() {
  $("familyRow").replaceChildren(
    ...["T-TPT", "T-PDG", "ESTADO-DHSV", "QGL"].map((s) => {
      const b = el(
        "button",
        `${c().sensor_definitions[s].name} · ${s} / not in audit`,
        "quiet",
      );
      b.onclick = () => {
        selected = s;
        contextSensor = true;
        renderContext();
        renderDiagram();
      };
      return b;
    }),
  );
  const layer = $("sensors");
  layer.replaceChildren();
  const mobile = matchMedia("(max-width:740px)").matches;
  $("well").classList.toggle("mobile", mobile);
  const charged = {
    "P-TPT": [28, 76, 392, 176],
    "P-PDG": [28, 232, 392, 319],
    "ABER-CKGL": [452, 6, 550, 152],
  };
  for (const [s, pos] of Object.entries(charged)) {
    const [x, y, px, py] = pos,
      w = 326,
      h = 102,
      st = state(s),
      d = c().sensor_definitions[s];
    const g = svg("g", {
      class: `sensor-hit ${st.trend}${selected === s ? " selected" : ""}`,
      role: "button",
      tabindex: 0,
      "aria-label": `${d.name}, ${s}, ${value(s, st.value)}, ${st.label}`,
    });
    const activate = () => {
      selected = s;
      contextSensor = true;
      renderContext();
      renderDiagram();
    };
    g.onclick = activate;
    g.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        activate();
      }
    };
    g.append(
      svg("title", {}, `${d.name}: ${d.description} ${s}. ${st.label}.`),
      svg("path", {
        d: `M${x + (x < 400 ? w : 0)} ${y + h * 0.5} L${px} ${py}`,
        class: "sensor-connector",
      }),
      svg("rect", { x, y, width: w, height: h, rx: 8, class: "sensor-card" }),
    );
    const dy = [24, 43, 73, 94];
    g.append(
      svg(
        "text",
        { x: x + 13, y: y + dy[0], class: "sensor-title" },
        s === "ABER-CKGL" ? "Gas-lift opening" : d.name,
      ),
      svg("text", { x: x + 13, y: y + dy[1], class: "sensor-id" }, s),
      svg(
        "text",
        { x: x + 13, y: y + dy[2], class: "sensor-value" },
        value(s, st.value),
      ),
      svg(
        "text",
        { x: x + 13, y: y + dy[3], class: "sensor-trend" },
        `${symbols[st.trend]} ${st.delta && st.quality === "valid" ? (st.delta > 0 ? "+" : "") + fmt(scaled(s, st.delta), 3) + " " + unitDisplay(s) + " from first valid" : st.label}`,
      ),
    );
    layer.append(g);
  }
}

function sensorContext() {
  const d = c().sensor_definitions[selected],
    st = state(selected),
    obs = c().observations[selected],
    box = $("context");
  box.append(
    el("div", "01 / UNDERSTAND THE SENSOR", "eyebrow"),
    el("h3", d.name),
    el("span", selected, "pill"),
    el("p", d.description),
  );
  if (pressure(selected))
    box.append(
      el(
        "p",
        "Pressure describes how strongly fluid pushes per unit area. A pressure change is an observation, not a diagnosis.",
      ),
    );
  if (obs) {
    const line = el("div", value(selected, st.value), "value-large");
    box.append(
      line,
      el(
        "p",
        `${symbols[st.trend]} ${st.label}. ${st.quality === "valid" ? "Valid recorded sample." : st.quality === "invalid" ? "Rejected by numeric quality guardrail; not a physical danger threshold." : "No measurement is available."}`,
      ),
    );
    if (st.value !== null)
      box.append(
        el("p", `Canonical recorded value: ${fmt(st.value, 4)} ${d.unit}.`),
      );
    if (st.delta !== undefined && st.delta !== null)
      box.append(
        el(
          "p",
          `Difference from first valid: ${st.delta > 0 ? "+" : ""}${value(selected, st.delta)}. This is not a normal-operation or safety threshold.`,
        ),
      );
    box.append(
      el(
        "p",
        `Captured window quality: ${obs.count}/${obs.total} valid; ${obs.quality_status}. ${obs.is_constant ? "Constant readings are not automatically missing." : ""}`,
      ),
    );
  } else
    box.append(
      el(
        "p",
        "Not observed in this audit. No value or physical state is inferred.",
        "gap",
      ),
    );
  box.append(
    el(
      "p",
      `Documented association: ${d.equipment.replaceAll("_", " ")}. Unit: ${d.unit}${pressure(selected) ? ". Display conversion: MPa = Pa ÷ 1,000,000" : ""}.`,
    ),
  );
  if (d.valve_encodings?.length)
    box.append(
      el(
        "p",
        "Documented ESTADO encoding: 0 closed, 1 open, 0.5 other. This is not an observed valve position or a hidden operational state label.",
      ),
    );
  const source = el("a", "Sensor-definition source ↗");
  source.href = d.location_fact.provenance.url;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  box.append(source, el("p", d.scope, "context-note"));
  const families = el("div", undefined, "family-buttons");
  for (const s of ["T-TPT", "ESTADO-DHSV", "QGL"]) {
    const b = el("button", c().sensor_definitions[s].name, "quiet");
    b.onclick = () => {
      selected = s;
      renderContext();
      renderDiagram();
    };
    families.append(b);
  }
  box.append(families);
}
function renderContext() {
  const box = $("context");
  box.replaceChildren();
  if (scene <= 1 || contextSensor) {
    sensorContext();
    if (contextSensor && scene > 1) {
      const back = el("button", "Return to investigation →", "quiet");
      back.onclick = () => {
        contextSensor = false;
        renderContext();
      };
      box.append(back);
    }
    return;
  }
  if (scene === 2) {
    box.append(
      el("div", "03 / THE MODEL’S DIAGNOSIS", "eyebrow"),
      el("h3", FAULTS[c().packet.baseline.prediction]),
      el(
        "p",
        current === 0
          ? "A hydrate blockage can obstruct the service line. The claim says two pressure rises prove that cause."
          : "A safety-valve closure is plausible. This claim only compares recorded pressure directions with a published example.",
      ),
    );
    const auditButton = el("button", "Audit this diagnosis →", "primary");
    auditButton.onclick = () => goto(3);
    box.append(auditButton);
    box.append(
      el("div", "THE CLAIM TO AUDIT", "eyebrow"),
      el("p", c().packet.claim, "quote"),
      el(
        "p",
        "Constructed evaluation claim using actual telemetry. The statistical score is uncalibrated and is not presented as a likelihood.",
        "context-note",
      ),
    );
    return;
  }
  if (scene === 3) {
    box.append(
      el("div", "04 / MUSE INVESTIGATES", "eyebrow"),
      el("h3", "Which premise makes the leap?"),
      el(
        "p",
        "Editorial guide: verify recorded changes → consult the document → examine the inference → identify the missing premise. This is not a fabricated tool chronology.",
      ),
    );
    const f = c().audits.grounded.output.findings[2];
    box.append(
      el("p", f.statement, "quote"),
      el("p", f.justification),
      el(
        "p",
        current === 0
          ? "Missing premise: " + f.missing_premise
          : "The source supports this limited comparison. Generalizability is needed only for a stronger diagnosis.",
        "gap",
      ),
    );
    box.append(el("div", "ACTUAL CAPTURED TOOL ORDER", "eyebrow"));
    for (const a of c().captured_activity.grounded) {
      const d = el("div", undefined, "tool-step");
      const label =
        a.tool === "lookup_knowledge"
          ? `Consult knowledge: ${a.topic}`
          : a.tool === "search_history"
            ? `Compare training history (${a.match_overlap.join(", ")} shared sensors)`
            : a.error
              ? "Submission rejected; repair requested"
              : "Submit captured audit";
      d.append(el("b", `${a.sequence}. ${label}`));
      box.append(d);
    }
    box.append(
      el(
        "p",
        "Muse started with three already charged sensor summaries. It did not request the raw samples or use this playback cursor.",
        "context-note",
      ),
    );
    return;
  }
  box.append(
    el("div", "05 / THE BOUNDARY OF THE EVIDENCE", "eyebrow"),
    el(
      "h3",
      current === 0
        ? "Measured changes. Unestablished cause."
        : "Supported comparison. Unestablished cause.",
    ),
    el(
      "p",
      current === 0
        ? "Muse accepts that both recorded pressures increased. It does not accept that those measurements establish service-line hydrate."
        : "Muse verifies that the two recorded directions match the published example. It does not upgrade a match into proof of valve closure.",
    ),
  );
  for (const a of c().reviewed_actions) {
    box.append(
      el("div", a.kind, "eyebrow"),
      el("p", a.target),
      el("p", a.status, "context-note"),
    );
  }
  box.append(
    el(
      "p",
      "Concrete requests are editorial review annotations, not new captured Muse output. No verified fault-discriminating test is supplied.",
      "context-note",
    ),
  );
}
function renderTime() {
  const r = c().replay;
  $("timing").textContent =
    r.timing +
    " No filling or resampling. " +
    (r.mode === "raw"
      ? `At ${$("speed").value}×, playback advances ${$("speed").value} measured samples per wall second; all 600 samples remain on the chart.`
      : "The two points are not a continuous trace.");
  $("slider").value = String(index);
  $("clock").textContent =
    r.mode === "raw"
      ? `${Math.floor(index / 60)}:${String(index % 60).padStart(2, "0")} / 9:59`
      : index === 0
        ? "First valid values"
        : "Last valid values";
  $("endLabel").textContent =
    r.mode === "raw" ? r.timestamps[index] : "2 captured endpoints";
  $("charts").replaceChildren(...["P-PDG", "P-TPT"].map((s) => chart(s)));
}
function chart(s) {
  const r = c().replay,
    stream = r.series[s],
    data = stream.samples.map((p) => scaled(s, p.value)),
    valid = data.filter((v) => v !== null),
    d = el("article", undefined, "chart-card");
  const head = el("div", undefined, "chart-heading");
  head.append(
    el("strong", `${c().sensor_definitions[s].name} · ${s}`),
    el("span", `${value(s, stream.samples[index].value)}`),
  );
  d.append(head);
  const v = svg("svg", {
    viewBox: "0 0 560 88",
    class: "chart-svg",
    role: "img",
    "aria-label": `${s} ${r.mode === "raw" ? "real samples, gaps preserved" : "two endpoints only, no continuous trace"}`,
  });
  if (!valid.length) {
    v.append(
      svg("text", { x: 20, y: 40, class: "chart-axis" }, "No valid readings"),
    );
    d.append(v);
    return d;
  }
  let lo = Math.min(...valid),
    hi = Math.max(...valid);
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const x = (i) => 48 + (i / (data.length - 1)) * 493,
    y = (p) => 57 - ((p - lo) / (hi - lo)) * 44;
  v.append(
    svg("text", { x: 0, y: 14, class: "chart-axis" }, `${fmt(hi, 2)}`),
    svg("text", { x: 0, y: 57, class: "chart-axis" }, `${fmt(lo, 2)}`),
    svg("text", { x: 3, y: 78, class: "chart-axis" }, unitDisplay(s)),
  );
  if (r.mode === "raw") {
    let path = "",
      connected = false;
    for (let i = 0; i < data.length; i++) {
      if (data[i] === null) {
        connected = false;
        continue;
      }
      path += (connected ? "L" : "M") + x(i) + " " + y(data[i]) + " ";
      connected = true;
    }
    v.append(svg("path", { d: path, class: "chart-line" }));
  } else
    data.forEach((p, i) => {
      if (p !== null)
        v.append(
          svg("circle", { cx: x(i), cy: y(p), r: 4, class: "chart-point" }),
        );
    });
  v.append(
    svg("line", {
      x1: x(index),
      x2: x(index),
      y1: 5,
      y2: 64,
      class: "chart-cursor",
    }),
  );
  if (data[index] !== null)
    v.append(
      svg("circle", {
        cx: x(index),
        cy: y(data[index]),
        r: 4,
        class: "chart-point",
      }),
    );
  v.append(
    svg(
      "text",
      { x: 48, y: 78, class: "chart-axis" },
      r.mode === "raw" ? "0:00" : "First valid",
    ),
    svg(
      "text",
      { x: 490, y: 78, class: "chart-axis" },
      r.mode === "raw" ? "9:59" : "Last valid",
    ),
  );
  d.append(v);
  return d;
}
function renderVerdict() {
  const a = c().audits.grounded.output;
  $("verdictTitle").textContent =
    current === 0
      ? "THE PRESSURE CHANGES ARE REAL. THE CLAIMED ROOT CAUSE IS NOT ESTABLISHED."
      : "THE DOCUMENTED COMPARISON IS SUPPORTED. ROOT CAUSE IS NOT ESTABLISHED.";
  const statements =
    current === 0
      ? [
          [
            "Observed",
            "Downhole and tree-pressure endpoints increased. These recorded changes are real.",
          ],
          [
            "Documented",
            "The source describes hydrate obstruction in the service line. It does not supply a necessary or specific pressure criterion.",
          ],
          [
            "Inferred",
            "The claim upgrades those increases to proof of a physical cause. That connecting premise is missing.",
          ],
          [
            "Needed",
            "Request the applicable tag map and validated differential procedure. No verified discriminating test is supplied.",
          ],
        ]
      : [
          [
            "Observed",
            "Downhole pressure increased and tree pressure decreased.",
          ],
          [
            "Documented",
            "Those two directions match the cited published fault-2 example.",
          ],
          [
            "Inferred",
            "A limited example match does not prove a safety-valve closure or exclude another cause.",
          ],
          [
            "Needed",
            "No more evidence is required for this narrow comparison. Valve logs and differential criteria would concern a stronger causal claim.",
          ],
        ];
  $("verdictColumns").replaceChildren(
    ...statements.map(([h, p]) => {
      const n = el("article");
      n.append(el("h3", h), el("p", p));
      return n;
    }),
  );
}
function renderDetails() {
  const a = audit();
  $("grounded").classList.toggle("selected", condition === "grounded");
  $("ungrounded").classList.toggle("selected", condition === "ungrounded");
  $("detailFindings").replaceChildren(
    ...a.output.findings.map((f, i) => {
      const n = el("article", undefined, "detail-finding");
      n.append(
        el("span", `${f.verdict} / ${f.basis}`, "tag"),
        el("h3", f.statement),
      );
      const list = el("ul");
      list.append(...f.premises.map((p) => el("li", p)));
      n.append(
        list,
        el("p", f.justification),
        el(
          "p",
          `Captured missing premise: ${f.missing_premise || "None stated"}`,
        ),
        el("p", `Captured next evidence: ${f.next_evidence}`),
        el("p", "Editorial scope note: " + a.notes[i].text, "review-note"),
      );
      return n;
    }),
  );
  const sources = $("sources");
  sources.replaceChildren();
  for (const [id, f] of Object.entries(a.sources)) {
    const n = el("article", undefined, "source-card");
    n.append(el("strong", id));
    if (f.matched_sensors) {
      n.append(
        el(
          "p",
          `Historical label ${f.training_event}; ${f.shared_sensors} shared sensors: ${f.matched_sensors.join(", ")}. Distance ${f.distance}, not a probability.`,
        ),
      );
      const p = el("progress");
      p.max = Object.keys(c().observations).length;
      p.value = f.shared_sensors;
      n.append(p);
    } else {
      n.append(
        el("p", `${f.subject} → ${f.relation} → ${f.object}`),
        el("p", `${f.scope} · ${f.locator}`),
      );
      const link = el("a", "Open recorded source ↗");
      link.href = f.provenance.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      n.append(link);
    }
    sources.append(n);
  }
  $("raw").textContent = JSON.stringify(
    {
      attribution: "Original captured real Muse output, unchanged",
      protocol_id: c().source_protocol_id,
      output: a.output,
      baseline: c().packet.baseline,
      chronology: c().captured_activity[condition],
    },
    null,
    2,
  );
  $("liveRun").disabled = !status.live_enabled || liveBusy;
  $("liveRun").textContent = liveBusy
    ? "Muse is auditing…"
    : status.live_enabled
      ? "Run live v2 · uses API · separate protocol"
      : "Live disabled · captured replay active";
  const saved = liveResults.get(c().id);
  $("liveRaw").hidden = !saved;
  if (saved) $("liveRaw").textContent = JSON.stringify(saved, null, 2);
}
$("caseSelect").onchange = () => {
  resetPlayback();
  contextSensor = false;
  current = Number($("caseSelect").value);
  index = c().replay.mode === "raw" ? 0 : 1;
  scene = 0;
  selected = "P-TPT";
  render();
};
$("nextScene").onclick = () => goto(scene === 4 ? 0 : scene + 1);
$("slider").oninput = () => {
  index = Number($("slider").value);
  renderDiagram();
  renderTime();
  if (scene <= 1 || contextSensor) renderContext();
};
$("speed").onchange = () => renderTime();
$("play").onclick = () => {
  if (!c().replay.can_play) return;
  if (timer) {
    resetPlayback();
    $("play").textContent = "▶ Play";
    return;
  }
  if (index >= 599) index = 0;
  timer = setInterval(() => {
    index = Math.min(599, index + Number($("speed").value));
    renderDiagram();
    renderTime();
    if (scene <= 1 || contextSensor) renderContext();
    if (index === 599) {
      resetPlayback();
      $("play").textContent = "▶ Play";
    }
  }, 1000);
  $("play").textContent = "Ⅱ Pause";
};
$("inspectDetails").onclick = () => {
  $("details").hidden = false;
  renderDetails();
  $("details").scrollIntoView({ behavior: "smooth", block: "start" });
};
$("closeDetails").onclick = () => ($("details").hidden = true);
$("grounded").onclick = () => {
  condition = "grounded";
  renderDetails();
};
$("ungrounded").onclick = () => {
  condition = "ungrounded";
  renderDetails();
};
$("downloadReview").onclick = async () => {
  const blob = new Blob(
    [JSON.stringify(await (await fetch("/api/review")).json(), null, 2)],
    { type: "application/json" },
  );
  const a = el("a");
  a.href = URL.createObjectURL(blob);
  a.download = "petromind-claim-review.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};
$("liveRun").onclick = async () => {
  if (liveBusy) return;
  liveBusy = true;
  renderDetails();
  const id = c().id;
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
      throw new Error(r.error || r.reason);
    liveResults.set(id, r);
    $("liveResult").textContent =
      "New live v2 result, independent review pending. Captured replay and verdict were not changed.";
  } catch (e) {
    showError(`Live failed: ${e.message}. No replay was substituted.`);
  } finally {
    liveBusy = false;
    renderDetails();
  }
};
window.addEventListener("resize", () => {
  if (cases.length) renderDiagram();
});
(async () => {
  try {
    const [cr, sr] = await Promise.all([
      fetch("/api/cases"),
      fetch("/api/status"),
    ]);
    if (!cr.ok || !sr.ok)
      throw new Error("Reviewed capture could not be loaded");
    cases = (await cr.json()).cases;
    status = await sr.json();
    index = c().replay.mode === "raw" ? 0 : 1;
    render();
  } catch (e) {
    showError(e.message);
  }
})();
