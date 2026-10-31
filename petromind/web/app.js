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
function newlyInspected(s) {
  return (
    execution === "live" &&
    visibleEvents().some(
      (e) => e.tool === "request_sensor" && e.sensor === s && e.summary,
    )
  );
}
function observationStatus(s) {
  return inventoryFor(s)?.observed_by_muse
    ? "Received captured summary"
    : newlyInspected(s)
      ? "Requested in this live audit"
      : "Viewer only · not observed by Muse";
}
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
  renderPlatform();
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
    b.dataset.value = st.value === null ? "" : String(st.value);
    b.dataset.quality = st.quality;
    b.dataset.trend = st.trend;
    b.dataset.index = String(index);
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
      !newlyInspected(s) &&
      streamFor(s)
    )
      b.append(el("small", "Viewer only", "viewer-tag"));
    if (newlyInspected(s))
      b.append(el("small", "Muse requested summary", "viewer-tag"));
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
      `Generic associations are documented; exact placement and piping are illustrative. ${inventoryFor(selected).observed_by_muse || newlyInspected(selected) ? "Raw samples are viewer-only. Muse received this sensor’s fixed summary, not these individual samples." : "This sensor was NOT observed by Muse. Any raw samples here are viewer-only and never added to the captured or live audit."}`,
    ),
  );
}
function renderInventory() {
  const r = c().replay;
  $("inventoryScope").textContent =
    r.mode === "raw"
      ? "27 documented channels. Presence and quality are checked in this incident’s verified window. Raw channels remain viewer-only. Inventory marks original summaries and any new explicitly requested live summary."
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
          el("p", `Muse: ${observationStatus(row.sensor)}`),
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
    "data-index": index,
    "data-sensor": s,
    "data-timestamp": r.timestamps?.[index] || "",
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
      ? "Run live · uses API · separate protocol"
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
$("allSensors").onclick = () => {
  resetPlayback();
  renderTelemetry();
  renderInventory();
  $("inventoryDialog").showModal();
};
$("closeInventory").onclick = () => $("inventoryDialog").close();
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

// One state/event model powers the operator and evidence views. No private reasoning.
let pageName =
  location.pathname === "/technology"
    ? "technology"
    : location.pathname === "/demo"
      ? "demo"
      : "home";
let workspaceView = "operator",
  execution = "captured",
  synthetic = false,
  focusSensor = null;
const investigations = new Map(),
  playbackPositions = new Map();
function investigation() {
  const key = `${c().id}:${execution}`;
  if (!investigations.has(key))
    investigations.set(key, {
      phase: 0,
      events: [],
      cursor: 0,
      row: null,
      error: null,
    });
  return investigations.get(key);
}
function visibleEvents() {
  const r = investigation();
  return execution === "captured" ? r.events.slice(0, r.cursor) : r.events;
}
function navigate(page, push = true) {
  pageName = page;
  if (push) history.pushState({}, "", page === "home" ? "/" : "/" + page);
  renderPlatform();
  window.scrollTo(0, 0);
}
function renderPlatform() {
  if (!cases.length) return;
  for (const name of ["home", "demo", "technology"])
    $(name + "Page").hidden = pageName !== name;
  document
    .querySelectorAll(".site-nav a")
    .forEach((a) =>
      a.setAttribute(
        "aria-current",
        a.getAttribute("href") === (pageName === "home" ? "/" : "/" + pageName)
          ? "page"
          : "false",
      ),
    );
  $("caseSelect").value = String(current);
  $("caseSelect").disabled = liveBusy;
  $("scenarioSelect").disabled = liveBusy;
  $("executionSelect").disabled = liveBusy;
  $("executionSelect").value = execution;
  $("executionSelect").options[1].disabled = !status.live_enabled;
  $("syntheticNotice").hidden = !synthetic;
  $("historicalWorkspace").hidden = synthetic;
  $("consoleView").hidden = workspaceView !== "operator";
  $("insidePanel").hidden = workspaceView !== "inside";
  $("operatorView").classList.toggle("active", workspaceView === "operator");
  $("insideView").classList.toggle("active", workspaceView === "inside");
  $("experience").dataset.scene = "0";
  $("dataBadge").textContent =
    c().replay.mode === "raw"
      ? "Verified real window · viewer only"
      : "Captured endpoints · raw replay unavailable";
  const r = investigation();
  $("diagnosisCard").hidden = r.phase !== 1;
  $("investigationHypothesis").hidden = r.phase !== 2;
  $("activeHypothesis").textContent =
    current === 0 ? "Service-line hydrate" : "Safety-valve closure";
  $("preDiagnosis").hidden = r.phase !== 0;
  $("cause").textContent =
    current === 0 ? "Service-line hydrate" : "Unexpected safety-valve closure";
  $("definition").textContent =
    current === 0
      ? "Ice-like material can form in production equipment and restrict flow."
      : "A valve deep in the well can shut off production flow.";
  $("diagnosisObservations").replaceChildren(
    el("li", "Downhole pressure increased."),
    el(
      "li",
      current === 0 ? "Tree pressure increased." : "Tree pressure decreased.",
    ),
  );
  $("plausibility").textContent =
    "This statistical prediction is a hypothesis. Its uncalibrated score is not a proven physical cause.";
  $("claimSummary").textContent = c().packet.claim;
  $("runBadge").textContent =
    execution === "captured"
      ? `Captured v1 · ${r.cursor}/${r.events.length} records revealed`
      : liveBusy
        ? `${status.capabilities?.new_sensor_queries ? "Live v3" : "Live v2"} · actual tool events arriving`
        : `${status.capabilities?.new_sensor_queries ? "Live v3" : "Live v2"} · explicit API execution`;
  $("runInstruction").textContent =
    execution === "captured"
      ? "This replays genuine captured activity, not a new API call. Advance records to inspect what happened."
      : status.live_enabled
        ? `Explicit action uses the Meta API. Fresh protocol limits: ${status.live_limits?.estimated_usd ?? 2} USD estimated, ${status.live_limits?.requests ?? 12} requests and ${status.live_limits?.output_tokens ?? 49152} output tokens globally; Python enforces remaining reservations.`
        : "Live is disabled. Prepare a fresh live protocol and restart with --enable-live; no API calls occur in replay.";
  $("capabilityText").textContent = status.capabilities?.new_sensor_queries
    ? "Live v3 adds request_sensor: at most two additional summaries, after lookup of their documented generic location. Initial and new sensors share five queries; missing queries count and cached repeats are free. No raw playback enters Muse. History remains the initial training-only snapshot; no exact well topology is available. Captured runs remain unchanged."
    : "Live evidence auditing exposes lookup_knowledge, search_history and submit_audit. Three inherited summaries count toward five queries. Extra sensors require a fresh active-sensor protocol and verified raw dataset. No exact well topology is available. History uses initial evidence only.";
  $("nextScene").disabled =
    liveBusy || (execution === "live" && !status.live_enabled && r.phase > 0);
  $("nextScene").textContent =
    r.phase === 0
      ? "Reveal statistical diagnosis →"
      : r.phase === 1
        ? execution === "live"
          ? "Investigate with Muse Spark · live API"
          : "Investigate with Muse · captured replay"
        : liveBusy
          ? "Muse is running…"
          : "Start a new investigation";
  $("back").hidden = r.phase === 0 || liveBusy;
  $("back").textContent = "Reset this view";
  $("activityPanel").hidden = r.phase < 2;
  $("nextRecord").hidden =
    execution !== "captured" || r.cursor >= r.events.length;
  $("graphAdvance").hidden =
    execution !== "captured" || r.cursor >= r.events.length;
  $("eventFeed").replaceChildren(
    ...visibleEvents().map((e) => {
      const li = el("li");
      li.append(el("strong", e.title || e.kind));
      if (e.sensor)
        li.append(
          el(
            "span",
            `${names[e.sensor] || e.sensor}: ${e.summary.available ? "summary available" : "no valid readings"} · ${e.cached ? "cached" : "charged"} · ${e.remaining_budget} queries left. Purpose: ${e.purpose}`,
          ),
        );
      if (e.topic) li.append(el("span", `Topic: ${e.topic}`));
      if (e.matches)
        li.append(
          el(
            "span",
            e.matches.length
              ? e.matches
                  .map(
                    (m) =>
                      `${m.shared_sensors} shared: ${m.matched_sensors.join(", ")}`,
                  )
                  .join(" · ")
              : "No historical matches returned.",
          ),
        );
      if (e.validation)
        li.append(
          el(
            "span",
            e.validation.code
              ? `Python validation: ${e.validation.code} / ${e.validation.field}`
              : "Python structural/numeric validation passed; physical correctness unverified.",
          ),
        );
      if (e.kind === "completion")
        li.append(el("span", `${e.status} · ${e.reason}`));
      return li;
    }),
  );
  const result =
    r.row?.output || visibleEvents().findLast((e) => e.assessment)?.assessment;
  const box = $("operatorResult");
  box.replaceChildren();
  if (r.error)
    box.append(
      el("h3", "Investigation stopped · no completed audit"),
      el(
        "p",
        {
          model_output_token_limit:
            "Muse reached its response limit before submitting. No conclusion is substituted.",
          sensor_budget_exhausted: "The five-sensor budget is exhausted.",
          live_precondition_failed:
            "Check the fresh protocol, exported key, verified dataset and remaining cost cap.",
        }[r.error] ||
          `Stopped: ${r.error}. No captured result was substituted.`,
      ),
    );
  if (result) {
    box.append(
      el(
        "div",
        `${execution === "live" ? "NEW LIVE" : "CAPTURED"} ASSESSMENT`,
        "eyebrow",
      ),
      el("h3", result.verdict.replaceAll("_", " ")),
    );
    const keyFinding =
      result.findings.find((f) =>
        ["NOT_ESTABLISHED", "PARTIALLY_SUPPORTED", "CONTRADICTED"].includes(
          f.verdict,
        ),
      ) || result.findings[result.findings.length - 1];
    if (keyFinding)
      box.append(
        el(
          "p",
          `${keyFinding.verdict}: ${keyFinding.statement}`,
          "key-finding",
        ),
      );
    if (keyFinding?.missing_premise)
      box.append(
        el("h4", "The missing link"),
        el("p", keyFinding.missing_premise),
      );
    if (keyFinding?.next_evidence) {
      const n = keyFinding.next_evidence;
      box.append(
        el("h4", "What to verify next"),
        el(
          "p",
          typeof n === "string"
            ? n
            : `${n.target ? n.target + ": " : ""}${n.purpose || "No additional evidence requested for this scope."}`,
        ),
      );
    }
    if (execution === "captured" && keyFinding?.next_evidence)
      box.append(
        el(
          "p",
          "Editorial scope: this is a captured recommendation, not a supplied procedure. No verified fault-discriminating test is available in this package.",
          "fine-print",
        ),
      );
    const events = visibleEvents(),
      received = events.find((e) => e.kind === "evidence_received");
    const requested = events.filter(
      (e) => e.tool === "request_sensor" && e.summary,
    );
    const facts = events.flatMap((e) => e.facts || []),
      matches = events.flatMap((e) => e.matches || []);
    const brief = el("dl", undefined, "operator-brief");
    brief.append(
      el("dt", "Classifier hypothesis"),
      el(
        "dd",
        current === 0
          ? "Service-line hydrate · statistical prediction, not proven cause"
          : "Unexpected safety-valve closure · statistical prediction, not proven cause",
      ),
      el("dt", "Evidence Muse inspected"),
      el(
        "dd",
        Object.keys(received?.observations || {})
          .map(
            (s) =>
              `${names[s] || s}${received.observations[s].available ? "" : " (unavailable)"}`,
          )
          .join(", "),
      ),
      el("dt", "Additional measurements"),
      el(
        "dd",
        requested.length
          ? requested
              .map(
                (e) =>
                  `${names[e.sensor] || e.sensor}${e.cached ? " (cached)" : " (charged)"}${e.summary.available ? "" : " · unavailable"}`,
              )
              .join(", ")
          : "None requested. Viewer playback did not add evidence.",
      ),
      el("dt", "Retrieved context"),
      el(
        "dd",
        `${facts.length} returned documented facts; ${matches.length} training analogues${matches.length ? " (overlap: " + matches.map((m) => m.shared_sensors).join(", ") + " sensors)" : ""}. Similarity does not prove cause.`,
      ),
    );
    const locators = [...new Set(facts.map((f) => f.locator).filter(Boolean))];
    if (locators.length)
      brief.append(
        el("dt", "Document sections actually returned"),
        el("dd", locators.join("; ")),
      );
    const supported = result.findings.filter((f) => f.verdict === "SUPPORTED");
    if (supported.length)
      brief.append(
        el("dt", "Supported at the stated scope"),
        el(
          "dd",
          supported
            .slice(0, 2)
            .map((f) => f.statement)
            .join(" "),
        ),
      );
    box.append(brief);
    for (const f of result.findings) {
      const d = el("details");
      d.append(
        el("summary", `${f.verdict}: ${f.statement}`),
        el("p", f.justification),
        el(
          "p",
          `Missing: ${f.missing_premise || "None stated for this scope"}`,
        ),
        el(
          "p",
          `Next evidence: ${typeof f.next_evidence === "string" ? f.next_evidence : JSON.stringify(f.next_evidence)}`,
        ),
        el("p", `Received citation IDs: ${f.citations.join(", ") || "None"}`),
      );
      box.append(d);
    }
    if (execution === "captured") {
      const follow = el("details");
      follow.append(
        el("summary", "Next-evidence requests · editorial source review"),
      );
      for (const action of c().reviewed_actions)
        follow.append(el("p", action.target), el("p", action.status));
      follow.append(
        el(
          "p",
          "These are editorial requests, not newly generated Muse findings or a verified discriminating test.",
        ),
      );
      box.append(follow);
    }
    box.append(
      el(
        "p",
        "Public Muse findings; Python validates numbers/structure, not physical entailment. Independent engineering review pending.",
        "fine-print",
      ),
    );
  }
  renderTelemetry();
  renderEvidenceGraph();
  if (focusSensor)
    document
      .querySelector(`[data-sensor="${focusSensor}"]`)
      ?.classList.add("evidence-focus");
}
function beginInvestigation() {
  const r = investigation();
  if (r.phase === 0) {
    r.phase = 1;
    renderPlatform();
    return;
  }
  if (r.phase === 2 && !liveBusy) {
    r.phase = 1;
    r.events = [];
    r.cursor = 0;
    r.row = null;
    r.error = null;
    renderPlatform();
    return;
  }
  if (execution === "captured") {
    r.phase = 2;
    r.events = c().investigation_events.grounded;
    r.cursor = 1;
    renderPlatform();
  } else startLive();
}
async function startLive() {
  if (liveBusy || !status.live_enabled || synthetic) return;
  resetPlayback();
  const r = investigation();
  const runCaseId = c().id;
  r.phase = 2;
  r.events = [];
  r.row = null;
  r.error = null;
  liveBusy = true;
  renderPlatform();
  try {
    const response = await fetch("/api/live/stream", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-PetroMind-Token": status.token,
      },
      body: JSON.stringify({
        case_id: runCaseId,
        request_id: crypto.randomUUID().replaceAll("-", ""),
      }),
    });
    if (!response.ok)
      throw new Error((await response.json()).error || "Live request rejected");
    const reader = response.body.getReader(),
      decoder = new TextDecoder();
    let buffer = "",
      terminal = false;
    const consume = (line) => {
      if (!line.trim()) return;
      const event = JSON.parse(line);
      r.events.push(event);
      if (event.kind === "completion") {
        terminal = true;
        r.row = event.row;
        if (event.status !== "completed") r.error = event.reason;
        else liveResults.set(runCaseId, event.row);
      }
      if (event.kind === "failure") {
        terminal = true;
        r.error = event.code;
      }
      renderPlatform();
    };
    while (true) {
      const { value: chunk, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(chunk, { stream: true });
      let end;
      while ((end = buffer.indexOf("\n")) >= 0) {
        consume(buffer.slice(0, end));
        buffer = buffer.slice(end + 1);
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) consume(buffer);
    if (!terminal)
      throw new Error(
        "Stream interrupted; no automatic retry. Inspect the saved request before rerunning.",
      );
  } catch (e) {
    r.error = e.message;
  } finally {
    liveBusy = false;
    renderPlatform();
  }
}
function advanceRecord() {
  const r = investigation();
  r.cursor = Math.min(r.events.length, r.cursor + 1);
  renderPlatform();
}
function inspectNode(node) {
  $("nodeTitle").textContent = node.label;
  $("nodeKind").textContent = node.kind;
  $("nodeData").textContent = JSON.stringify(node.data, null, 2);
  $("nodeLinks").replaceChildren();
  const url = node.data.provenance?.url;
  if (
    url &&
    (url.startsWith("https://arxiv.org/") ||
      url.startsWith("https://github.com/"))
  ) {
    const a = el("a", "Open actual source ↗");
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    $("nodeLinks").append(a);
  }
  if (node.sensor) {
    focusSensor = node.sensor;
    document
      .querySelector(`[data-sensor="${focusSensor}"]`)
      ?.classList.add("evidence-focus");
  }
  $("nodeDialog").showModal();
}
function renderEvidenceGraph() {
  const nodes = new Map(),
    edges = [];
  const add = (id, label, kind, data, layer, sensor) => {
    if (!nodes.has(id)) nodes.set(id, { id, label, kind, data, layer, sensor });
    return id;
  };
  const link = (from, to, label) => edges.push({ from, to, label });
  const events = visibleEvents();
  for (const e of events) {
    if (e.kind === "evidence_received") {
      add(
        "hypothesis",
        `Classifier: fault ${e.hypothesis}`,
        "Statistical hypothesis",
        { prediction: e.hypothesis, calibrated: false },
        0,
      );
      add(
        "claim",
        "Constructed claim to audit",
        "Constructed evaluation claim",
        { claim: e.claim },
        0,
      );
      link("hypothesis", "claim", "audited claim");
      for (const [s, summary] of Object.entries(e.observations)) {
        const id = "measurement:" + s;
        add(
          id,
          names[s] || s,
          summary.available
            ? "Measured summary"
            : "Unavailable measurement summary",
          {
            sensor: s,
            ...summary,
            scope: "Fixed summary supplied to Muse, not raw playback",
          },
          1,
          s,
        );
        link(id, "claim", "received evidence");
      }
    }
    if (e.kind === "tool_result") {
      const request = "request:" + e.sequence;
      add(
        request,
        `${e.sequence}. ${e.tool}`,
        e.validation?.code ? "Python validation" : "Actual tool response",
        e,
        1,
      );
      link("claim", request, "observable request");
      if (e.sensor && e.summary) {
        const id = e.citation_id;
        add(
          id,
          names[e.sensor] || e.sensor,
          "Additional charged summary",
          { sensor: e.sensor, ...e.summary, scope: e.scope },
          1,
          e.sensor,
        );
        link(request, id, e.cached ? "cached summary" : "charged measurement");
        if (nodes.has(e.source_id))
          link(e.source_id, request, "cited generic sensor location");
      }
      for (const f of e.facts || []) {
        const id = f.citation_id || f.id;
        add(
          id,
          `${f.subject} ${f.relation} ${f.object}`,
          `Documented relationship · ${f.scope}`,
          f,
          2,
        );
        link(request, id, "returned fact");
      }
      for (const m of e.matches || []) {
        const id = m.citation_id;
        add(
          id,
          `History: ${m.shared_sensors} shared sensors`,
          "Empirical correlation · not cause",
          m,
          2,
        );
        link(request, id, "returned analogue");
      }
      if (e.assessment) {
        e.assessment.findings.forEach((f, i) => {
          const id = "finding:" + i;
          add(id, f.statement, `Muse public assessment · ${f.verdict}`, f, 3);
          link(request, id, "submitted finding");
          for (const cite of f.citations)
            if (nodes.has(cite)) link(cite, id, "model cites");
          if (f.missing_premise) {
            const gap = "gap:" + i;
            add(
              gap,
              f.missing_premise,
              "Unresolved premise · model assessment",
              {
                missing_premise: f.missing_premise,
                next_evidence: f.next_evidence,
              },
              3,
            );
            link(id, gap, "missing premise");
          }
        });
      }
    }
  }
  const graph = $("evidenceGraph"),
    counts = [0, 0, 0, 0];
  for (const n of nodes.values()) {
    n.x = 15 + n.layer * 265;
    n.y = 20 + counts[n.layer]++ * 88;
  }
  graph.setAttribute(
    "viewBox",
    `0 0 1060 ${Math.max(330, Math.max(...counts) * 88 + 35)}`,
  );
  graph.replaceChildren();
  for (const edge of edges) {
    const a = nodes.get(edge.from),
      b = nodes.get(edge.to);
    if (!a || !b) continue;
    const p = svg("path", {
      d: `M${a.x + 215} ${a.y + 31} C${a.x + 245} ${a.y + 31},${b.x - 20} ${b.y + 31},${b.x} ${b.y + 31}`,
      class: "evidence-edge",
    });
    p.append(svg("title", {}, edge.label));
    graph.append(p);
  }
  for (const n of nodes.values()) {
    const g = svg("g", {
      class: `evidence-node layer-${n.layer}`,
      role: "button",
      tabindex: 0,
      "aria-label": n.label,
    });
    g.append(
      svg("rect", { x: n.x, y: n.y, width: 215, height: 64, rx: 9 }),
      svg(
        "text",
        { x: n.x + 12, y: n.y + 19, class: "node-kind" },
        n.kind.slice(0, 29),
      ),
    );
    const label = n.label.replaceAll("_", " ");
    g.append(
      svg("text", { x: n.x + 12, y: n.y + 38 }, label.slice(0, 29)),
      svg("text", { x: n.x + 12, y: n.y + 54 }, label.slice(29, 58)),
    );
    g.onclick = () => inspectNode(n);
    g.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        inspectNode(n);
      }
    };
    graph.append(g);
  }
  $("graphNodeList").replaceChildren(
    ...Array.from(nodes.values()).map((n) => {
      const b = el("button", n.label, "quiet");
      b.onclick = () => inspectNode(n);
      return b;
    }),
  );
  if (!nodes.size)
    graph.append(
      svg(
        "text",
        { x: 40, y: 80 },
        "Begin or replay an investigation to see actual received evidence.",
      ),
    );
}
const architectureData = [
  [
    "Telemetry",
    "Real replay / synthetic boundary",
    "Verified private mapping selects a real 600-sample window. All allowlisted viewer channels remain separate from Muse’s frozen packet. Synthetic scenario mode is deferred.",
  ],
  [
    "Statistical engine",
    "A hypothesis, not root-cause proof",
    "The preserved conventional classifier supplies the initial fault hypothesis and charged summaries. Its score is uncalibrated; the UI does not replace it with Muse’s verdict.",
  ],
  [
    "Muse Spark",
    "Substantive claim investigation",
    "The live Meta Responses client uses muse-spark-1.3 and actual tool calls: lookup_knowledge, search_history, submit_audit; optional v3 adds documented request_sensor. Muse decomposes public claims, cites received evidence and identifies gaps. No private reasoning is exported.",
  ],
  [
    "Knowledge / history",
    "Source-backed context",
    "Topic lookups return documented generic graph facts and scope. Historical matches are restricted prepared training incidents and disclose overlap. Neither establishes exact well topology or causal confirmation.",
  ],
  [
    "Python safeguards",
    "Deterministic enforcement",
    "DiagnosticSession enforces the shared five-sensor budget. This auditor inherits three summaries. Optional v3 charges up to two additional unique sensors; cached requests are free and missing queries count. It validates exact numbers/citations, bounds repairs and reserves API spend. A fresh protocol pins source/runtime/prompt/schema hashes.",
  ],
  [
    "Audit / replay",
    "Inspectable, reproducible evidence",
    "The same public event projection renders immutable captured runs and new live tool events. Hash-linked audit entries, actual source IDs, validation failures and completed public assessments remain inspectable. Physical judgments require independent engineering review.",
  ],
];
function buildArchitecture() {
  const show = (i) => {
    $("architectureDetail").replaceChildren(
      el("span", architectureData[i][1], "eyebrow"),
      el("h3", architectureData[i][0]),
      el("p", architectureData[i][2]),
    );
    $("architectureNodes")
      .querySelectorAll("button")
      .forEach((b, j) => b.classList.toggle("active", j === i));
  };
  $("architectureNodes").replaceChildren(
    ...architectureData.map((a, i) => {
      const b = el(
        "button",
        `${i + 1} · ${a[0]} ${i < 5 ? "→" : ""}`,
        "architecture-node",
      );
      b.onclick = () => show(i);
      return b;
    }),
  );
  show(2);
}
document.querySelectorAll(".page-link").forEach(
  (a) =>
    (a.onclick = (e) => {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      e.preventDefault();
      if (a.dataset.case !== undefined && !liveBusy) {
        playbackPositions.set(c().id, index);
        current = Number(a.dataset.case);
        synthetic = false;
        $("scenarioSelect").value = "historical";
        index =
          playbackPositions.get(c().id) ??
          (c().replay.mode === "raw" ? 599 : 1);
      }
      navigate(
        a.getAttribute("href") === "/"
          ? "home"
          : a.getAttribute("href").slice(1),
      );
    }),
);
window.onpopstate = () =>
  navigate(
    location.pathname === "/technology"
      ? "technology"
      : location.pathname === "/demo"
        ? "demo"
        : "home",
    false,
  );
$("caseSelect").onchange = () => {
  resetPlayback();
  playbackPositions.set(c().id, index);
  current = Number($("caseSelect").value);
  index =
    playbackPositions.get(c().id) ?? (c().replay.mode === "raw" ? 599 : 1);
  condition = "grounded";
  focusSensor = null;
  renderPlatform();
};
$("executionSelect").onchange = () => {
  execution = $("executionSelect").value;
  renderPlatform();
};
$("scenarioSelect").onchange = () => {
  synthetic = $("scenarioSelect").value === "synthetic";
  resetPlayback();
  renderPlatform();
};
$("returnHistorical").onclick = () => {
  synthetic = false;
  $("scenarioSelect").value = "historical";
  renderPlatform();
};
$("operatorView").onclick = () => {
  workspaceView = "operator";
  renderPlatform();
};
$("insideView").onclick = () => {
  workspaceView = "inside";
  renderPlatform();
};
$("nextScene").onclick = beginInvestigation;
$("nextRecord").onclick = advanceRecord;
$("graphAdvance").onclick = advanceRecord;
$("back").onclick = () => {
  if (liveBusy) return;
  const r = investigation();
  r.phase = 0;
  r.events = [];
  r.cursor = 0;
  r.row = null;
  r.error = null;
  renderPlatform();
};
$("liveRun").onclick = () => {
  if (!status.live_enabled || liveBusy) return;
  $("details").close();
  execution = "live";
  startLive();
};
$("closeNode").onclick = () => $("nodeDialog").close();
(async () => {
  try {
    const [cr, sr] = await Promise.all([
      fetch("/api/cases"),
      fetch("/api/status"),
    ]);
    if (!cr.ok || !sr.ok) throw Error("Reviewed capture could not be loaded");
    cases = (await cr.json()).cases;
    status = await sr.json();
    index = c().replay.mode === "raw" ? 599 : 1;
    const art = $("well").cloneNode(true);
    art.removeAttribute("id");
    art.setAttribute(
      "aria-label",
      "Illustrative production well; generic instrument locations",
    );
    for (const n of art.querySelectorAll("[id]")) {
      const id = n.id;
      n.id = "home-" + id;
      for (const attr of ["fill", "stroke"]) {
        art
          .querySelectorAll(`[${attr}="url(#${id})"]`)
          .forEach((x) => x.setAttribute(attr, `url(#home-${id})`));
      }
    }
    $("homeArt").append(art);
    buildArchitecture();
    renderPlatform();
  } catch (e) {
    showError(e.message);
  }
})();
