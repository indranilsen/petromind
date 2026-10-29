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
  audit = () => c().audits[condition];
const fmt = (v, d = 2) =>
  v === null || v === undefined
    ? "Not observed"
    : Number(v).toLocaleString("en-US", { maximumFractionDigits: d });
const pressure = (s) => s.startsWith("P-");
const scaled = (s, v) => (v === null ? null : pressure(s) ? v / 1e6 : v);
const unitDisplay = (s) =>
  pressure(s) ? "MPa" : c().sensor_definitions[s]?.unit || "unknown";
const value = (s, v) =>
  v === null ? "Not observed" : `${fmt(scaled(s, v), 3)} ${unitDisplay(s)}`;
const names = {
  "P-PDG": "Downhole pressure",
  "P-TPT": "Tree pressure",
  "ABER-CKGL": "Choke opening",
  "T-TPT": "Tree temperature",
  "T-PDG": "Downhole temperature",
};
const sensorPositions = {
  "P-TPT": "tree",
  "P-PDG": "down",
  "ABER-CKGL": "choke",
  "T-TPT": "tree-temp",
  "T-PDG": "down-temp",
};
function state(s) {
  const stream = c().replay.series[s];
  if (!stream)
    return {
      value: null,
      quality: "unobserved",
      trend: "missing",
      label: "— Not observed in audit",
    };
  const sample = stream.samples[index];
  if (sample.quality !== "valid")
    return {
      ...sample,
      trend: sample.quality,
      label:
        sample.quality === "invalid" ? "! Invalid reading" : "— Unavailable",
    };
  const delta =
    stream.reference === null ? null : sample.value - stream.reference;
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
        ? "— No reference"
        : delta === 0
          ? "→ Unchanged"
          : `${delta > 0 ? "↑ +" : "↓ −"}${fmt(scaled(s, Math.abs(delta)), 3)} ${unitDisplay(s)} vs start`,
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
  resetPlayback();
  scene = Math.max(0, Math.min(2, n));
  render();
}
function render() {
  $("experience").dataset.scene = String(scene);
  $("caseSelect").value = String(current);
  $("chapter").textContent = [
    "01 / WHAT HAPPENED",
    "02 / CAN WE TRUST THE DIAGNOSIS?",
    "03 / WHAT MUSE DISCOVERED",
  ][scene];
  const headings =
    current === 0
      ? [
          "Two pressures rose.",
          "The model proposes\na hydrate restriction.",
          "The pressures really rose.\nBut that doesn’t prove the cause.",
        ]
      : [
          "Two pressures.\nDifferent directions.",
          "The model proposes\na closed safety valve.",
          "The pattern matches.\nThat doesn’t prove the cause.",
        ];
  $("headline").textContent = headings[scene];
  $("subtitle").textContent =
    scene === 0
      ? current === 0
        ? "Two sensors in a production well recorded higher ending pressures."
        : "Downhole pressure rose. Tree pressure fell."
      : scene === 1
        ? "An observed pressure change. A possible explanation to check."
        : "Muse checks whether the proposed cause follows from the evidence.";
  $("museChecks").hidden = scene !== 2;
  $("trendLegend").hidden = scene !== 0;
  $("stage").hidden = scene === 2;
  $("diagnosis").hidden = scene !== 1;
  $("discovery").hidden = scene !== 2;
  $("transport").hidden = scene !== 0;
  $("nextScene").hidden = scene === 2;
  $("inspectDetails").hidden = scene !== 2;
  $("back").hidden = scene === 0;
  $("nextScene").replaceChildren(
    document.createTextNode(
      scene === 0 ? "See the diagnosis " : "Ask Muse to investigate ",
    ),
    el("span", "→"),
  );
  $("diagnosisObservations").replaceChildren(
    el(
      "li",
      current === 0
        ? "Pressure near the top of the well increased."
        : "Pressure near the top of the well decreased.",
    ),
    el("li", "Pressure deeper in the well increased."),
  );
  $("plausibility").textContent =
    current === 0
      ? "Why it might fit: a restriction could affect pressures in the system. This is a plausible hypothesis, not a verified rule for this well."
      : "Why it might fit: the two pressure directions match a published valve-closure example. A match alone does not identify the cause.";
  $("cause").textContent =
    current === 0 ? "Service-line hydrate." : "Downhole safety-valve closure.";
  $("definition").textContent =
    current === 0
      ? "Hydrate is an ice-like material that can form in production equipment and restrict flow."
      : "A safety valve can shut off flow from deep inside the well.";
  $("claimSummary").textContent =
    current === 0
      ? "“Both pressures rose. This establishes service-line hydrate.”"
      : "“These pressure directions match a published valve-closure example—not proof of root cause.”";
  $("observedSummary").textContent =
    current === 0 ? "Both pressures rose." : "Downhole ↑  ·  Tree ↓";
  $("causeSummary").textContent =
    current === 0 ? "“This proves hydrate.”" : "Safety-valve closure";
  const f = c().audits.grounded.output.findings[2];
  // An exact first-sentence excerpt; the full original remains in the drawer.
  $("museQuote").textContent =
    f.justification.split(". ")[0] +
    (f.justification.split(". ").length > 1 ? "." : "");
  $("nextEvidence").textContent =
    current === 0
      ? "Missing: a verified rule showing this pressure pattern identifies hydrate rather than another cause. Next: applicable well documentation and validated diagnostic criteria; no verified discriminating test is supplied."
      : "The published comparison is supported. To establish valve closure itself, request valve records and validated criteria that distinguish other causes; those are not supplied by a matching example.";
  renderTelemetry();
}
function renderTelemetry() {
  const r = c().replay;
  $("slider").max = String(r.mode === "raw" ? 599 : 1);
  $("slider").value = String(index);
  $("play").disabled = !r.can_play;
  $("play").textContent = timer ? "Ⅱ" : "▶";
  $("play").setAttribute(
    "aria-label",
    timer ? "Pause real telemetry" : "Play real telemetry",
  );
  $("clock").textContent =
    r.mode === "raw"
      ? `${Math.floor(index / 60)}:${String(index % 60).padStart(2, "0")} / 9:59`
      : index === 0
        ? "Start"
        : "End";
  $("replayLabel").textContent =
    r.mode === "raw"
      ? "Recorded data · 10×"
      : "Captured endpoints · raw replay unavailable";
  $("sensors").replaceChildren(
    ...Object.keys(sensorPositions).map((s) => {
      const st = state(s),
        primary = pressure(s);
      const b = el(
        "button",
        undefined,
        `sensor-hit ${sensorPositions[s]} ${primary ? "claim-sensor" : "secondary-sensor"} ${st.trend}`,
      );
      b.dataset.sensor = s;
      b.setAttribute(
        "aria-label",
        `${names[s]}: ${value(s, st.value)}, ${st.label}. Show details`,
      );
      b.append(el("span", names[s], "sensor-name"));
      if (st.quality === "valid")
        b.append(el("strong", value(s, st.value), "sensor-reading"));
      b.append(el("span", st.label, "sensor-direction"));
      if (s === "P-TPT")
        b.append(el("small", "Equipment near the top of the well"));
      b.onclick = () => {
        selected = s;
        resetPlayback();
        renderTelemetry();
        renderSensor();
        $("sensorDialog").showModal();
      };
      return b;
    }),
  );
  // State colors reflect comparison with the first valid observation, not
  // pressure limits or a fabricated fault path. Marker size uses relative change.
  for (const [s, id, point] of [
    ["P-TPT", "treeHalo", "treePoint"],
    ["P-PDG", "downHalo", "downPoint"],
  ]) {
    const st = state(s),
      ref = r.series[s].reference;
    const radius =
      st.quality === "valid" && ref
        ? 30 + Math.min(28, Math.abs((st.value - ref) / ref) * 500)
        : 30;
    $(id).setAttribute("r", String(radius));
    $(id).setAttribute("class", `gauge-halo ${st.trend}`);
    $(point).setAttribute("class", `gauge-point ${st.trend}`);
  }
  if ($("sensorDialog").open) renderSensor();
}
function renderSensor() {
  const st = state(selected),
    d = c().sensor_definitions[selected];
  $("sensorTitle").textContent = names[selected];
  $("sensorValue").replaceChildren(
    el("strong", value(selected, st.value)),
    el("span", st.label),
  );
  $("sensorChart").replaceChildren(
    ...(c().replay.series[selected]
      ? [chart(selected)]
      : [
          el(
            "p",
            "No measurements were supplied for this sensor. No value or trend is inferred.",
          ),
        ]),
  );
  const box = $("sensorNotes");
  box.replaceChildren(
    el("p", `${selected} · ${d.description}`),
    el("p", `${c().replay.reference_note} ${c().replay.timing}`),
    el(
      "p",
      `Recorded units: ${d.unit}. ${pressure(selected) ? "Display: MPa = Pa ÷ 1,000,000. " : ""}Color and arrows show change, not danger or safety. ${st.quality === "invalid" ? "Numerically invalid sample; no physical danger threshold inferred." : ""}`,
    ),
  );
  const link = el("a", "Documented sensor definition ↗");
  link.href = d.location_fact.provenance.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  box.append(
    link,
    el(
      "p",
      "Generic measurement associations are documented; exact sensor placement and piping in this illustration are not verified for this well. Raw playback is viewer-only. Muse received the fixed captured summaries, not these individual samples.",
    ),
  );
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

function renderDetails() {
  const a = audit();
  $("evidenceContext").textContent =
    c().replay.timing +
    " " +
    c().replay.reference_note +
    " " +
    c().replay.visibility +
    " No interpolation, filling or downsampling. Geometry is illustrative, not verified well-specific topology. Independent engineering review remains pending; this is not root-cause certification.";
  $("originalClaim").textContent = c().packet.claim;
  $("evidenceMeasurements").textContent = JSON.stringify(
    c().observations,
    null,
    2,
  );
  $("evidenceTimeline").textContent = JSON.stringify(c().replay, null, 2);
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
$("caseSelect").onchange = () => {
  resetPlayback();
  current = Number($("caseSelect").value);
  scene = 0;
  condition = "grounded";
  index = c().replay.mode === "raw" ? 599 : 1;
  render();
};
$("nextScene").onclick = () => goto(scene + 1);
$("back").onclick = () => goto(scene - 1);
$("slider").oninput = () => {
  index = Number($("slider").value);
  renderTelemetry();
};
$("play").onclick = () => {
  if (!c().replay.can_play) return;
  if (timer) {
    resetPlayback();
    renderTelemetry();
    return;
  }
  if (index >= 599) index = 0;
  timer = setInterval(() => {
    index = Math.min(599, index + 10);
    if (index === 599) resetPlayback();
    renderTelemetry();
  }, 1000);
  renderTelemetry();
};
$("inspectDetails").onclick = () => {
  renderDetails();
  $("details").showModal();
};
$("closeDetails").onclick = () => $("details").close();
$("closeSensor").onclick = () => $("sensorDialog").close();
(async () => {
  try {
    const [cr, sr] = await Promise.all([
      fetch("/api/cases"),
      fetch("/api/status"),
    ]);
    if (!cr.ok || !sr.ok)
      throw new Error("Captured investigation could not be loaded");
    cases = (await cr.json()).cases;
    status = await sr.json();
    index = c().replay.mode === "raw" ? 599 : 1;
    render();
  } catch (e) {
    showError(e.message);
  }
})();
