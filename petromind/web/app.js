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
const pressure = (s) => c().sensor_definitions[s]?.unit === "Pa";
const scaled = (s, v) => (v === null ? null : pressure(s) ? v / 1e6 : v);
const unitDisplay = (s) =>
  pressure(s)
    ? "MPa"
    : { degC: "°C", "m3/s": "m³/s", dimensionless: "code" }[
        c().sensor_definitions[s]?.unit
      ] ||
      c().sensor_definitions[s]?.unit ||
      "unknown";
const value = (s, v) =>
  v === null ? "Not observed" : `${fmt(scaled(s, v), 3)} ${unitDisplay(s)}`;
const names = {
  "P-PDG": "Downhole pressure",
  "P-TPT": "Tree pressure",
  "T-TPT": "Tree temperature",
  "T-PDG": "Downhole temperature",
  "ABER-CKGL": "Gas-lift choke",
  "ABER-CKP": "Production choke",
  QGL: "Gas-lift flow",
  "ESTADO-DHSV": "Safety-valve state",
  "ESTADO-SDV-P": "Shutdown-valve state",
  "P-ANULAR": "Annulus pressure",
  "P-MON-CKP": "Choke inlet pressure",
  "P-JUS-CKP": "Choke outlet pressure",
};
const groups = [
  { name: "Gas lift", cls: "gas-group", sensors: ["ABER-CKGL", "QGL"] },
  {
    name: "Production equipment",
    cls: "production-group",
    sensors: ["ABER-CKP", "P-MON-CKP", "P-JUS-CKP", "ESTADO-SDV-P"],
  },
  {
    name: "Other well instruments",
    cls: "well-group",
    sensors: ["T-TPT", "T-PDG", "ESTADO-DHSV", "P-ANULAR"],
  },
];
const sensorPositions = { "P-TPT": "tree", "P-PDG": "down" };
const streamFor = (s) => c().replay.series[s] || c().replay.viewer_series?.[s];
const inventoryFor = (s) =>
  c().replay.inventory.find((row) => row.sensor === s);
function state(s) {
  const stream = streamFor(s);
  if (!stream)
    return {
      value: null,
      quality: "unobserved",
      trend: "missing",
      label: "— Not observed in audit",
    };
  if (inventoryFor(s)?.present_in_incident === false)
    return {
      value: null,
      quality: "absent",
      trend: "missing",
      label: "— Not present in incident",
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
          "The statistical classifier\nsuggests service-line hydrate.",
          "Audit result:\ncause not established.",
        ]
      : [
          "Two pressures.\nDifferent directions.",
          "The statistical classifier\nsuggests safety-valve closure.",
          "Audit result:\ncomparison supported.",
        ];
  $("headline").textContent = headings[scene];
  $("subtitle").textContent =
    scene === 0
      ? current === 0
        ? "Two sensors in a production well recorded higher ending pressures."
        : "Downhole pressure rose. Tree pressure fell."
      : scene === 1
        ? "Its sensor-based prediction is a hypothesis. Muse Spark audits the claim below."
        : "A plausible diagnosis is not the same as a proven cause.";
  $("allSensors").hidden = scene !== 0;
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
  $("modelSuggestion").textContent =
    current === 0
      ? "Service-line hydrate — a possible flow restriction."
      : "Unexpected closure of the downhole safety valve.";
  $("measurementCheck").textContent =
    current === 0
      ? "Read the two recorded pressure increases, rather than treating the diagnosis as a fact."
      : "Read the deeper pressure increase and tree-pressure decrease.";
  $("sourceCheck").textContent =
    current === 0
      ? "Retrieved descriptions of hydrate obstruction. No necessary or specific joint-pressure rule was supplied."
      : "Retrieved a published example showing those two pressure directions, scoped to that example.";
  $("observedSummary").textContent =
    current === 0
      ? "Both recorded pressures rose."
      : "The two directions match the published example.";
  $("causeSummary").textContent =
    current === 0
      ? "“These rises prove hydrate.”"
      : "That the same physical cause occurred here.";
  $("whyItMatters").textContent =
    current === 0
      ? "Muse’s contribution: it accepts the readings but identifies the unsupported step from pressure change to a specific cause."
      : "Muse’s contribution: it accepts the narrow documented comparison without turning it into proof of valve closure.";
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
  const makeSensor = (s, primary = false) => {
    const st = state(s);
    const b = el(
      "button",
      undefined,
      `sensor-hit ${sensorPositions[s] || ""} ${primary ? "claim-sensor" : "secondary-sensor"} ${st.trend}`,
    );
    b.dataset.sensor = s;
    b.setAttribute(
      "aria-label",
      `${names[s]}: ${value(s, st.value)}, ${st.label}. Show details`,
    );
    b.append(
      el("span", names[s] || c().sensor_definitions[s].name, "sensor-name"),
    );
    if (
      !primary &&
      inventoryFor(s) &&
      !inventoryFor(s).observed_by_muse &&
      streamFor(s)
    )
      b.append(el("small", "Viewer only", "viewer-tag"));
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
  };
  $("sensors").replaceChildren(
    ...Object.keys(sensorPositions).map((s) => makeSensor(s, true)),
    ...groups.map((group) => {
      const box = el("section", undefined, "instrument-group " + group.cls);
      box.append(el("h3", group.name));
      for (const s of group.sensors) box.append(makeSensor(s));
      return box;
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
  if ($("inventoryDialog").open) renderInventory();
}
function renderSensor() {
  const st = state(selected),
    d = c().sensor_definitions[selected];
  $("sensorTitle").textContent = names[selected] || d.name;
  $("sensorValue").replaceChildren(
    el("strong", value(selected, st.value)),
    el("span", st.label),
  );
  $("sensorChart").replaceChildren(
    ...(streamFor(selected)
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
      `Generic associations are documented; exact placement and piping are illustrative. ${inventoryFor(selected).observed_by_muse ? "Raw samples are viewer-only. Muse received this sensor’s fixed summary, not these individual samples." : "This sensor was NOT observed by Muse. Any raw samples here are viewer-only and never added to the captured or live audit."}`,
    ),
  );
}
function renderInventory() {
  const r = c().replay;
  $("inventoryScope").textContent =
    r.mode === "raw"
      ? "27 documented channels. Presence and quality are checked in this incident’s verified window. Extra raw channels are viewer-only; Muse received only its three captured summaries."
      : "27 documented channels. Raw data is unavailable: column presence and availability are unknown unless established by captured measurements. Not observed by Muse does not mean missing from the incident.";
  $("inventoryGroups").replaceChildren(
    ...[
      "Pressure",
      "Temperature",
      "Valve / equipment state",
      "Flow / opening / other",
    ].map((group) => {
      const section = el("section", undefined, "inventory-section");
      const rows = r.inventory.filter((row) => row.group === group);
      section.append(el("h3", `${group} · ${rows.length}`));
      for (const row of rows) {
        const d = c().sensor_definitions[row.sensor],
          st = state(row.sensor),
          item = el("article", undefined, "inventory-row " + st.trend);
        const title = el("div", undefined, "inventory-name");
        title.append(el("strong", d.name), el("code", row.sensor));
        const presence =
          row.present_in_incident === null
            ? "Unknown without raw data"
            : row.present_in_incident
              ? "Present"
              : "Not present";
        item.append(
          title,
          el("p", `In incident: ${presence}`),
          el(
            "p",
            `Muse: ${row.observed_by_muse ? "received captured summary" : "not observed in audit"}`,
          ),
          el(
            "p",
            `Window availability: ${row.availability.replaceAll("_", " ")}`,
          ),
          el(
            "p",
            `Selected reading: ${st.quality === "valid" ? value(row.sensor, st.value) + " · " + st.label : st.label}`,
          ),
        );
        const inspect = el("button", "Inspect", "quiet");
        inspect.onclick = () => {
          selected = row.sensor;
          $("inventoryDialog").close();
          renderSensor();
          $("sensorDialog").showModal();
        };
        item.append(inspect);
        section.append(item);
      }
      return section;
    }),
  );
  const sections = Array.from($("inventoryGroups").children);
  $("inventoryNav").replaceChildren(
    ...sections.map((section, i) => {
      const button = el(
        "button",
        ["Pressure · 10", "Temperature · 4", "State · 9", "Flow / opening · 4"][
          i
        ],
        "quiet",
      );
      button.onclick = () => section.scrollIntoView({ block: "start" });
      return button;
    }),
  );
}
function chart(s) {
  const r = c().replay,
    stream = streamFor(s),
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
$("allSensors").onclick = () => {
  resetPlayback();
  renderTelemetry();
  renderInventory();
  $("inventoryDialog").showModal();
};
$("closeInventory").onclick = () => $("inventoryDialog").close();
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
