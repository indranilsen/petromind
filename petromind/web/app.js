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
  index = 0,
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
  const r = c().replay,
    w = r.workflow;
  $("slider").max = String(w.positions - 1);
  $("slider").value = String(index);
  $("play").disabled = !r.can_play;
  $("play").textContent = timer ? "Ⅱ" : "▶";
  $("play").setAttribute(
    "aria-label",
    timer ? "Pause real telemetry" : "Play real telemetry",
  );
  $("sampleCounter").textContent =
    r.mode !== "endpoints"
      ? `Sample ${index + 1} of ${w.positions}`
      : `Captured endpoint ${index + 1} of ${w.positions}`;
  $("clock").textContent = w.elapsed_seconds
    ? `${elapsedLabel(w.elapsed_seconds[index])} / ${elapsedLabel(w.elapsed_seconds.at(-1))}`
    : "Timestamps unavailable";
  $("replayLabel").textContent =
    r.mode !== "endpoints"
      ? "Recorded data · 10× playback"
      : "Captured endpoints · no continuous replay";
  const history = r.mode === "history",
    alerted = anomalyReached();
  const marker = $("checkpointMarker");
  marker.hidden = history && !alerted;
  marker.style.left = "";
  marker.style.right = history ? "auto" : "";
  if (history && alerted) {
    const first = w.monitor.trace
      .slice(0, index + 1)
      .findIndex((row) => row.new_alert);
    marker.style.left = `${(w.elapsed_seconds[first] / w.elapsed_seconds.at(-1)) * 100}%`;
  }
  $("checkpointCaption").textContent = history
    ? "Prefix-only deviation monitor · first 5 minutes form an observed reference, not verified normal operation."
    : "Demo investigation checkpoint at the end of the evidence · not a historical alarm";
  marker.classList.toggle("active", history ? alerted : checkpointReached());
  $("checkpointMarker").setAttribute(
    "aria-label",
    history
      ? "Anomaly alert computed from observed prefix; not a historical operational alarm or fault identification"
      : `${checkpointReached() ? "Reached" : "Upcoming"} demo investigation checkpoint · ${r.mode !== "endpoints" ? "last recorded sample" : "endpoint comparison complete"} · not a historical alarm`,
  );
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
    if ((history ? alerted : checkpointReached()) && primary)
      b.classList.add("checkpoint-focus");
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
    r.mode === "history"
      ? "27 documented channels in the recorded viewer clip. Only the original 600-sample summaries were given to Muse. Earlier and later readings are viewer-only."
      : r.mode !== "endpoints"
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
    "aria-label": `${s} ${r.mode !== "endpoints" ? "real samples, gaps preserved" : "two endpoints only, no continuous trace"}`,
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
  const elapsed = r.workflow.elapsed_seconds;
  const x = (i) =>
      48 +
      (elapsed ? elapsed[i] / elapsed.at(-1) : i / (data.length - 1)) * 493,
    y = (p) => 57 - ((p - lo) / (hi - lo)) * 44;
  v.append(
    svg("text", { x: 0, y: 14, class: "chart-axis" }, `${fmt(hi, 2)}`),
    svg("text", { x: 0, y: 57, class: "chart-axis" }, `${fmt(lo, 2)}`),
    svg("text", { x: 3, y: 78, class: "chart-axis" }, unitDisplay(s)),
  );
  if (r.mode !== "endpoints") {
    let path = "",
      connected = false;
    for (let i = 0; i < data.length; i++) {
      if (data[i] === null) {
        connected = false;
        continue;
      }
      if (i > 0 && elapsed[i] - elapsed[i - 1] > 1.5) connected = false;
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
      r.mode !== "endpoints" ? elapsedLabel(elapsed[0]) : "First valid",
    ),
    svg(
      "text",
      { x: 490, y: 78, class: "chart-axis" },
      r.mode !== "endpoints" ? elapsedLabel(elapsed.at(-1)) : "Last valid",
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
  resetPlayback();
  setReplayPosition(Number($("slider").value));
};
$("play").onclick = () => {
  if (!c().replay.can_play) return;
  if (timer) {
    resetPlayback();
    renderTelemetry();
    return;
  }
  if (index === c().replay.workflow.positions - 1) setReplayPosition(0);
  // Advance through existing samples only, selecting by actual elapsed timestamps.
  const elapsed = c().replay.workflow.elapsed_seconds;
  let playbackElapsed = elapsed[index];
  timer = setInterval(() => {
    playbackElapsed += 10;
    const target = playbackElapsed;
    let next = index;
    while (next + 1 < elapsed.length && elapsed[next + 1] <= target) next++;
    setReplayPosition(next);
    if (index === elapsed.length - 1) {
      resetPlayback();
      renderTelemetry();
    }
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
const investigations = new Map();
const workflowStates = new Map();
function elapsedLabel(seconds) {
  const whole = Math.floor(seconds);
  const suffix =
    seconds % 1 ? (seconds % 1).toFixed(3).slice(1).replace(/0+$/, "") : "";
  return `${String(Math.floor(whole / 60)).padStart(2, "0")}:${String(whole % 60).padStart(2, "0")}${suffix}`;
}
function monitoringPoint() {
  return c().replay.workflow.monitor?.trace[index] || null;
}
function anomalyReached() {
  return monitoringPoint()?.alerted === true;
}
function evidenceComplete() {
  return index >= c().replay.workflow.checkpoint.index;
}
function checkpointReached() {
  return (
    evidenceComplete() && (c().replay.mode !== "history" || anomalyReached())
  );
}
function transitionWorkflow(stage) {
  const previous = workflowStates.get(c().id) || {
    stage: "monitoring",
    transitions: ["monitoring"],
  };
  if (previous.stage !== stage) {
    previous.stage = stage;
    previous.transitions.push(stage);
    previous.transitions = previous.transitions.slice(-12);
  }
  workflowStates.set(c().id, previous);
}
function syncWorkflow() {
  if (!checkpointReached())
    transitionWorkflow(
      anomalyReached()
        ? monitoringPoint().new_alert
          ? "alert"
          : "accumulating"
        : "monitoring",
    );
  else {
    if ((workflowStates.get(c().id)?.stage || "monitoring") === "monitoring")
      transitionWorkflow(
        c().replay.mode === "history" ? "alert" : "checkpoint",
      );
    transitionWorkflow(
      investigation().phase === 2 ? "investigation" : "diagnosis",
    );
  }
  const state = workflowStates.get(c().id);
  $("historicalWorkspace").dataset.workflowStage = state.stage;
  $("historicalWorkspace").dataset.uiTransitions = JSON.stringify(
    state.transitions,
  );
  $("workflowStatus").textContent = {
    monitoring: "Monitoring · recorded measurements",
    alert: "Anomaly alert · sustained pressure deviation",
    accumulating: "Anomaly alert → Accumulating diagnostic evidence",
    diagnosis:
      c().replay.mode === "history"
        ? "Anomaly alert → Statistical fault diagnosis"
        : "Checkpoint reached → Statistical fault diagnosis",
    investigation:
      c().replay.mode === "history"
        ? "Anomaly alert → Statistical diagnosis → Muse investigation"
        : "Checkpoint reached → Statistical diagnosis → Muse investigation",
  }[state.stage];
}
function setReplayPosition(position) {
  const wasReady = checkpointReached(),
    wasAlerted = anomalyReached();
  index = Math.max(0, Math.min(c().replay.workflow.positions - 1, position));
  if (!checkpointReached()) {
    for (const id of ["details", "nodeDialog"]) if ($(id).open) $(id).close();
  }
  renderPlatform();
  if (
    ((!wasReady && checkpointReached()) || (!wasAlerted && anomalyReached())) &&
    pageName === "demo" &&
    workspaceView === "operator" &&
    !document.querySelector("dialog[open]")
  ) {
    requestAnimationFrame(() => {
      if (checkpointReached() || anomalyReached())
        $("checkpointAlert").scrollIntoView({
          block: window.matchMedia("(max-width: 740px)").matches
            ? "start"
            : "nearest",
        });
    });
  }
}

let capturedClock = null,
  capturedOwner = null,
  selectedEvidenceEvent = null;
const CAPTURE_DELAY_MS = 1400; // Presentation pacing, never claimed as original API timing.
function stopCapturedClock(pause = true) {
  if (capturedClock) clearTimeout(capturedClock);
  capturedClock = null;
  if (pause && capturedOwner) capturedOwner.playing = false;
  capturedOwner = null;
}
function syncCapturedClock() {
  const r = investigation();
  const active =
    execution === "captured" &&
    pageName === "demo" &&
    checkpointReached() &&
    !synthetic &&
    r.phase === 2 &&
    r.playing &&
    r.cursor < r.events.length;
  if (!active) {
    stopCapturedClock();
    return;
  }
  if (capturedClock && capturedOwner === r) return;
  stopCapturedClock(false);
  capturedOwner = r;
  capturedClock = setTimeout(() => {
    capturedClock = null;
    if (investigation() !== r || !checkpointReached() || pageName !== "demo") {
      r.playing = false;
      return;
    }
    r.cursor++;
    selectedEvidenceEvent = r.cursor - 1;
    const e = r.events[r.cursor - 1];
    if (e.sensor && e.summary) focusSensor = e.sensor;
    if (r.cursor === r.events.length) r.playing = false;
    renderPlatform();
    followInvestigation();
  }, CAPTURE_DELAY_MS);
}
function followInvestigation() {
  if (workspaceView !== "inside" || pageName !== "demo") return;
  requestAnimationFrame(() => {
    const finalPanel = $("insideAssessment");
    const target = finalPanel.children.length
      ? finalPanel
      : $("eventFeed").lastElementChild;
    target?.scrollIntoView({
      block: finalPanel.children.length ? "start" : "nearest",
      behavior:
        finalPanel.children.length ||
        matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
    });
  });
}
function eventTitle(e) {
  if (e.kind === "evidence_received")
    return "Inspecting the supplied sensor evidence";
  if (e.kind === "tool_request")
    return "Tool requested · waiting for its result";
  if (e.validation?.code) return "A submission required correction";
  if (e.kind === "completion")
    return e.status === "completed"
      ? "Investigation complete"
      : "Investigation stopped";
  return (
    {
      lookup_knowledge: "Retrieving documented engineering context",
      search_history: "Comparing historical training incidents",
      request_sensor: "Requesting an additional measurement",
      submit_audit: "Evaluating the suspected cause",
    }[e.tool] ||
    e.title ||
    e.kind
  );
}
function renderConversation() {
  const r = investigation(),
    events = visibleEvents();
  $("investigationLabel").textContent =
    execution === "captured"
      ? "Captured Muse activity · automatic presentation pacing, not original token timing. Headings are interface labels; findings below are recorded public output."
      : "Live Meta Muse · actual public events as received. No private reasoning or invented intermediate messages.";
  $("captureControls").hidden =
    execution !== "captured" || r.phase !== 2 || !checkpointReached();
  $("capturePause").textContent = r.playing ? "Pause replay" : "Resume replay";
  $("capturePause").disabled = r.cursor >= r.events.length;
  $("captureSkip").disabled = r.cursor >= r.events.length;
  $("investigationActivity").textContent =
    !checkpointReached() || r.phase !== 2
      ? ""
      : liveBusy
        ? "Live request running · awaiting the next actual event"
        : r.error
          ? "Stopped · no completed assessment substituted"
          : execution === "captured" && r.cursor < r.events.length
            ? r.playing
              ? "Replaying captured activity…"
              : "Replay paused"
            : "Public investigation records received";
  const feed = $("eventFeed"),
    owner = `${c().id}:${execution}`;
  if (feed.dataset.owner !== owner) {
    feed.replaceChildren();
    feed.dataset.owner = owner;
  }
  while (feed.children.length > events.length) feed.lastElementChild.remove();
  events.forEach((e, i) => {
    if (feed.children[i]) {
      feed.children[i].classList.toggle(
        "selected-event",
        selectedEvidenceEvent === i,
      );
      return;
    }
    const li = el(
      "li",
      undefined,
      "conversation-event is-new" +
        (selectedEvidenceEvent === i ? " selected-event" : ""),
    );
    li.dataset.eventIndex = i;
    li.dataset.kind = e.kind;
    if (e.tool) li.dataset.tool = e.tool;
    const button = el("button", eventTitle(e), "event-title");
    button.onclick = () => {
      selectedEvidenceEvent = i;
      renderPlatform();
    };
    li.append(button);
    li.append(
      el(
        "small",
        e.kind === "evidence_received"
          ? "Received input packet"
          : e.kind === "tool_request"
            ? "Actual live tool request"
            : e.kind === "completion"
              ? "Execution status"
              : "Actual public tool result",
        "event-origin",
      ),
    );
    if (e.observations)
      for (const [s, v] of Object.entries(e.observations)) {
        li.append(
          el(
            "p",
            `${names[s] || s} · ${s}: ${v.available ? `${value(s, v.first)} → ${value(s, v.last)}; Δ ${value(s, v.delta)}; ${v.count} valid readings` : `Unavailable (${v.total} samples; no valid measurement)`}`,
            "event-measurement",
          ),
        );
      }
    if (e.topic)
      li.append(
        el(
          "p",
          `Topic lookup: ${e.topic}. Returns predefined source-scoped facts, not general installed-well traversal.`,
        ),
      );
    for (const f of e.facts || []) {
      const fact = el(
        "button",
        `${f.subject} · ${f.relation.replaceAll("_", " ")} · ${f.object}`,
        "returned-fact",
      );
      fact.onclick = () => {
        selectedEvidenceEvent = i;
        renderPlatform();
        inspectNode({
          label: fact.textContent,
          kind: `${f.status} · ${f.scope}`,
          data: f,
        });
      };
      li.append(fact, el("small", `${f.status} · ${f.locator}`));
    }
    if (e.sensor && e.summary)
      li.append(
        el(
          "p",
          `${names[e.sensor] || e.sensor} · ${e.sensor}. Purpose: ${e.purpose}`,
        ),
        el(
          "p",
          e.summary.available
            ? `Median ${value(e.sensor, e.summary.median)}; Δ ${value(e.sensor, e.summary.delta)}`
            : "No valid readings returned",
        ),
        el(
          "small",
          `${e.cached ? "Cached" : "Charged"} · ${e.remaining_budget} sensor queries remaining`,
        ),
      );
    for (const m of e.matches || [])
      li.append(
        el(
          "p",
          `${m.citation_id}: ${m.shared_sensors} shared sensors (${m.matched_sensors.join(", ")}); distance ${m.distance}. Empirical similarity, not confirmation of cause.`,
        ),
      );
    if (e.matches?.length)
      li.append(
        el(
          "small",
          e.matches.some((m) => Object.hasOwn(m, "training_event"))
            ? "Original captured analogue metadata includes training-event categories, not hidden target labels. This historical record is preserved."
            : "Training-event labels are not returned in this live history projection.",
        ),
      );
    if (e.matches && !e.matches.length)
      li.append(el("p", "No historical match was returned."));
    if (e.validation?.code)
      li.append(
        el(
          "p",
          `Python validation: ${e.validation.code} · ${e.validation.field}. ${e.validation.instruction || e.validation.correction || ""}`,
        ),
      );
    if (e.assessment) {
      li.append(el("h3", e.assessment.verdict.replaceAll("_", " ")));
      for (const f of e.assessment.findings)
        li.append(el("p", `${f.verdict.replaceAll("_", " ")}: ${f.statement}`));
    }
    if (e.kind === "completion")
      li.append(el("p", `${e.status} · ${e.reason}`));
    feed.append(li);
  });
}
function renderPhysicalHypotheses(events) {
  const box = $("physicalHypotheses");
  box.replaceChildren();
  const facts = events.flatMap((e) => e.facts || []),
    assessment = PublicInvestigation.result(events);
  const mechanisms = facts.filter((f) => f.relation === "described_as");
  if (!mechanisms.length && !assessment) return;
  const details = el("details"),
    summary = el(
      "summary",
      "Physical explanation · sources and unresolved premises",
    );
  details.append(summary);
  details.append(
    el(
      "p",
      "Public source facts and submitted findings, not a reconstruction of Muse’s private reasoning. Generic equipment associations are not verified installed topology.",
    ),
  );
  for (const f of mechanisms) {
    details.append(
      el("h4", `Documented description: ${f.object.replaceAll("_", " ")}`),
      el("p", `Source: ${f.locator}. Scope: ${f.scope}.`),
    );
    const equipment = facts.find(
      (x) => x.subject === f.subject && x.relation === "affects",
    );
    if (equipment)
      details.append(
        el(
          "p",
          `Documented generic equipment association: ${equipment.object.replaceAll("_", " ")}.`,
        ),
      );
    const expectations = facts.filter((x) => x.relation.startsWith("example:"));
    details.append(
      el(
        "p",
        expectations.length
          ? "Returned example directions: " +
              expectations
                .map((x) => `${x.object} ${x.relation.slice(8)}`)
                .join("; ") +
              ". A published example is not a universal or discriminating fault rule."
          : "No verified fault-specific pressure expectation or discriminating test was returned. No differential-pressure model or installed flow path is inferred.",
      ),
    );
  }
  const observed = {
    ...events.find((e) => e.kind === "evidence_received")?.observations,
  };
  for (const e of events)
    if (e.sensor && e.summary) observed[e.sensor] = e.summary;
  details.append(el("h4", "Actual observations available to Muse"));
  const relevant = new Set([
    "P-PDG",
    "P-TPT",
    ...facts
      .filter((f) => f.relation.startsWith("example:"))
      .map((f) => f.object),
  ]);
  for (const sensor of relevant) {
    const reading = observed[sensor];
    details.append(
      el(
        "p",
        `${sensor}: ${!reading ? "Not observed by Muse; this example component cannot be evaluated." : !reading.available ? "No valid measurement was available." : `${value(sensor, reading.first)} → ${value(sensor, reading.last)}. Recorded endpoints, not proof of a mechanism.`}`,
      ),
    );
  }
  for (const f of assessment?.findings || []) {
    if (f.basis === "measurement") continue;
    details.append(
      el("h4", `Muse public finding · ${f.verdict.replaceAll("_", " ")}`),
      el("p", f.statement),
      el("p", `Premises: ${f.premises.join("; ")}`),
      el(
        "p",
        `Missing premise: ${f.missing_premise || "None stated within this finding’s narrow scope."}`,
      ),
      el(
        "p",
        `Next evidence: ${typeof f.next_evidence === "string" ? f.next_evidence : `${f.next_evidence.target}: ${f.next_evidence.purpose}`}`,
      ),
    );
  }
  box.append(details);
}

function investigation() {
  const key = `${c().id}:${execution}`;
  if (!investigations.has(key))
    investigations.set(key, {
      phase: 0,
      events: [],
      cursor: 0,
      row: null,
      error: null,
      playing: false,
    });
  return investigations.get(key);
}
function visibleEvents() {
  if (!checkpointReached()) return [];
  const r = investigation();
  return execution === "captured" ? r.events.slice(0, r.cursor) : r.events;
}
function navigate(page, push = true) {
  if (page !== "demo") resetPlayback();
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
    c().replay.mode === "history"
      ? "Recorded history · viewer only · retrospective clip selection"
      : c().replay.mode !== "endpoints"
        ? "Verified real window · viewer only"
        : "Captured endpoints · raw replay unavailable";
  const r = investigation(),
    ready = checkpointReached();
  syncWorkflow();
  const history = c().replay.mode === "history",
    point = monitoringPoint();
  $("checkpointAlert").hidden = history ? !anomalyReached() : !ready;
  $("alertEyebrow").textContent = history
    ? "▲ PREFIX-ONLY ANOMALY ALERT"
    : "▲ DEMO INVESTIGATION CHECKPOINT";
  $("checkpointTitle").textContent = history
    ? "Diagnostic alert triggered"
    : c().replay.mode !== "endpoints"
      ? "Diagnostic window complete"
      : "Captured comparison complete";
  $("checkpointExplanation").textContent = history
    ? "Both pressures deviated by at least 6 robust reference scales for 30 seconds. This heuristic detects change, not a fault or confirmed cause. The reference is not certified normal."
    : "Retrospective review of complete-window summaries. This is a demo checkpoint, not a historical alarm or early prediction.";
  const diagnosticCount = Math.max(
    0,
    Math.min(600, index - (c().replay.workflow.checkpoint.index - 599) + 1),
  );
  $("monitoringHeading").textContent = !history
    ? "Monitoring sensor measurements"
    : anomalyReached()
      ? "Accumulating diagnostic evidence"
      : point.state === "warmup"
        ? "Observing a reference prefix"
        : "Monitoring sensor measurements";
  $("monitoringExplanation").textContent = !history
    ? "Play or scrub the recorded measurements. The saved diagnosis becomes available only at the end-of-evidence checkpoint."
    : anomalyReached()
      ? `Alert recorded. Original diagnostic observations: ${diagnosticCount} of 600. The saved classifier and Muse summaries remain unavailable until this original window is complete; they are not recomputed at the alert.`
      : point.state === "warmup"
        ? "The first five recorded minutes form a measured reference. Earlier operation is not automatically normal or safe. No fault prediction is shown."
        : point.state === "reference_unavailable"
          ? "The reference lacks enough variable valid pressure measurements. A constant or zero signal is valid, but cannot supply this detector’s MAD scale. No alert is fabricated."
          : point.state === "measurement_unavailable"
            ? "A required pressure measurement is unavailable. Persistence resets; no reading is invented."
            : index === c().replay.workflow.positions - 1
              ? "No sustained two-pressure deviation alert was detected in this replay. No fault diagnosis was triggered."
              : "Monitoring recorded pressures against the earlier measured reference. Sustained deviation can trigger an anomaly alert; it does not identify the cause.";
  $("executionControl").hidden = !ready;
  $("capabilityDetails").hidden = !ready;
  $("runBadge").hidden = !ready;
  $("runInstruction").hidden = !ready;
  $("inspectDetails").hidden = !ready;
  $("executionNote").hidden = !ready;
  $("executionNote").textContent =
    execution === "captured"
      ? "Captured investigation · no new API call"
      : "Live Meta API · clicking Investigate spends against the prepared cap";
  $("insidePending").hidden = ready && r.phase === 2;
  $("insidePending").textContent = ready
    ? "The statistical diagnosis is available. Start the investigation from the Operator Console."
    : history
      ? "Monitor recorded changes, then complete the original diagnostic evidence. Muse investigation is available only after an alert and that evidence boundary."
      : "Review recorded measurements to the checkpoint. The diagnosis and investigation remain unavailable before that point.";
  $("graphLegend").hidden = !ready || r.phase !== 2;
  $("graphNodeList").hidden = !ready || r.phase !== 2;
  $("evidenceGraph").parentElement.hidden = !ready || r.phase !== 2;
  $("diagnosisCard").hidden = !ready || r.phase === 2;
  $("investigationHypothesis").hidden = !ready || r.phase !== 2;
  $("activeHypothesis").textContent =
    current === 0 ? "Service-line hydrate" : "Safety-valve closure";
  $("preDiagnosis").hidden = ready;
  const predicted = c().packet.baseline.prediction;
  const fault =
    PublicInvestigation.faultNames[predicted] || `Fault category ${predicted}`;
  $("cause").textContent = `Suspected failure: ${fault}`;
  const ranked = (c().packet.baseline.probabilities || [])
    .filter((p) => p.represented_in_fit)
    .sort((a, b) => b.probability - a.probability);
  $("classifierStatement").textContent =
    ranked.length && ranked[0].fault_type === predicted
      ? `The statistical classifier ranked ${fault.toLowerCase()} highest among its trained categories. Its score is not a calibrated likelihood.`
      : `The statistical classifier predicted ${fault.toLowerCase()}. This is a suspected category, not an established physical cause.`;
  $("classifierFeatures").textContent =
    `${c().classifier_context?.model || "Statistical evidence model"}: ${(c().classifier_context?.features || []).join(", ")}. No per-sensor feature importance is recorded.`;
  $("classifierInputs").textContent =
    c().classifier_context?.sensor_attribution ||
    "Exact classifier input attribution is not supplied by this capture.";
  $("definition").textContent =
    current === 0
      ? "Hydrate is ice-like material that can accumulate in production equipment and restrict flow."
      : "A valve deep in the well can shut off production flow.";
  $("diagnosisObservations").replaceChildren(
    ...["P-PDG", "P-TPT"].map((sensor) => {
      const summary = c().observations[sensor],
        li = el("li");
      li.append(
        el("strong", `${names[sensor]} · ${sensor}`),
        el(
          "span",
          summary?.available
            ? `${value(sensor, summary.first)} → ${value(sensor, summary.last)}`
            : "No valid recorded measurements",
        ),
        el(
          "small",
          summary?.available
            ? `Recorded endpoint change: ${value(sensor, summary.delta)} · ${summary.count} valid samples`
            : "Unavailable evidence, not a zero measurement",
        ),
      );
      return li;
    }),
  );
  $("plausibility").textContent =
    "This statistical prediction does not establish physical cause. Muse audits the stronger constructed claim below.";
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
  $("nextScene").hidden = !ready;
  $("nextScene").disabled =
    liveBusy || (execution === "live" && !status.live_enabled && r.phase !== 2);
  $("nextScene").textContent =
    r.phase === 2
      ? liveBusy
        ? "Muse investigation in progress"
        : "Review Muse investigation"
      : "Investigate with Muse Spark";
  $("back").hidden = !ready || liveBusy;
  $("back").textContent = "Restart replay";
  $("activityPanel").hidden = !ready || r.phase !== 2;
  renderConversation();
  const result =
    r.row?.output || visibleEvents().findLast((e) => e.assessment)?.assessment;
  const box = $("operatorResult");
  box.replaceChildren();
  if (ready && r.error)
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
  if (ready && result) {
    box.append(
      el(
        "div",
        `${execution === "live" ? "NEW LIVE" : "CAPTURED"} ASSESSMENT`,
        "eyebrow",
      ),
      el("h3", "Muse Spark assessment"),
      el(
        "p",
        {
          SUPPORTED: "Supported within the claim’s stated scope.",
          PARTIALLY_SUPPORTED:
            "Part of the claim is supported. The full claim is not established.",
          NOT_ESTABLISHED:
            "The supplied evidence does not establish the claim.",
          CONTRADICTED: "The supplied evidence contradicts the claim.",
        }[result.verdict] || result.verdict,
        "key-finding",
      ),
      el(
        "p",
        `Recorded verdict: ${result.verdict.replaceAll("_", " ")}`,
        "fine-print",
      ),
    );
    const keyFinding =
      result.findings.find((f) =>
        ["NOT_ESTABLISHED", "PARTIALLY_SUPPORTED", "CONTRADICTED"].includes(
          f.verdict,
        ),
      ) || result.findings[result.findings.length - 1];
    const scopeNote = el(
      "p",
      "Presentation guide: support for a measurement or example comparison is not proof of its physical cause. Recorded findings and verdicts below are unchanged.",
      "fine-print",
    );
    box.append(scopeNote);
    const sections = PublicInvestigation.assessmentSections(result);
    for (const [key, title, description] of [
      [
        "measured",
        "What the sensors establish",
        "Measured findings apply to the supplied summaries, not an inferred cause.",
      ],
      [
        "documented",
        "What the documentation establishes",
        "An example comparison applies only to the features actually checked. A production-line example is not proof of service-line hydrate.",
      ],
      [
        "causal",
        "What remains unknown about root cause",
        "A plausible explanation needs applicable discriminating evidence. Missing evidence is not a contradiction.",
      ],
      [
        "other",
        "Other recorded findings",
        "These older findings have no declared atomic scope; they have not been regraded.",
      ],
    ]) {
      if (key === "other" && !sections[key].length) continue;
      const section = el("section", undefined, "assessment-scope");
      section.dataset.scope = key;
      section.append(el("h4", title), el("p", description, "fine-print"));
      if (!sections[key].length)
        section.append(
          el(
            "p",
            "No separate finding was recorded for this scope.",
            "fine-print",
          ),
        );
      for (const f of sections[key]) {
        const item = el("div", undefined, "scoped-finding");
        item.append(
          el(
            "span",
            `Recorded verdict: ${f.verdict.replaceAll("_", " ")}`,
            "scope-verdict",
          ),
        );
        if (
          f.scope === "diagnostic_conclusion" &&
          f.verdict === "PARTIALLY_SUPPORTED"
        )
          item.append(
            el(
              "p",
              "Legacy recorded label — not regraded. Partial support for the composite claim must not be read as partial proof of this cause.",
              "scope-gap",
            ),
          );
        item.append(
          el("p", `Claim assessed: ${f.statement}`),
          el("p", f.justification),
        );
        if (f.missing_premise)
          item.append(
            el("p", `Missing premise: ${f.missing_premise}`, "scope-gap"),
          );
        section.append(item);
      }
      box.append(section);
    }
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
  $("insideAssessment").replaceChildren();
  if (ready && (result || r.error)) {
    const copy = box.cloneNode(true);
    copy.removeAttribute("id");
    $("insideAssessment").append(copy);
  }
  $("inspectDetails").hidden = !ready || !result;
  renderTelemetry();
  renderEvidenceGraph();
  syncCapturedClock();
  if (focusSensor && ready)
    document
      .querySelector(`[data-sensor="${focusSensor}"]`)
      ?.classList.add("evidence-focus");
}
function beginInvestigation() {
  if (!checkpointReached() || synthetic || liveBusy) return;
  const r = investigation();
  if (r.phase === 2) {
    workspaceView = "inside";
    renderPlatform();
    return;
  }
  if (execution === "captured") {
    r.phase = 2;
    r.events = c().investigation_events.grounded;
    resetPlayback();
    r.cursor = 1;
    r.playing = true;
    selectedEvidenceEvent = 0;
    workspaceView = "inside";
    $("graphPanel").open = !matchMedia("(max-width: 900px)").matches;
    renderPlatform();
    followInvestigation();
  } else startLive();
}
async function startLive() {
  if (
    liveBusy ||
    !status.live_enabled ||
    synthetic ||
    !checkpointReached() ||
    investigation().phase === 2
  )
    return;
  resetPlayback();
  const r = investigation();
  const runCaseId = c().id;
  r.phase = 2;
  r.events = [];
  r.row = null;
  r.error = null;
  liveBusy = true;
  workspaceView = "inside";
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
      if (event.tool === "request_sensor" && event.summary)
        focusSensor = event.sensor;
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
      selectedEvidenceEvent = r.events.length - 1;
      renderPlatform();
      followInvestigation();
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
  const events = visibleEvents(),
    projection = PublicInvestigation.graph(events),
    nodes = new Map(projection.nodes.map((n) => [n.id, n]));
  const graph = $("evidenceGraph"),
    counts = [0, 0, 0, 0, 0],
    active = selectedEvidenceEvent ?? events.length - 1;
  const topRows = Math.max(
    projection.nodes.filter((n) => n.layer === 0).length,
    projection.nodes.filter((n) => n.layer === 1).length,
  );
  for (const n of nodes.values()) {
    const column =
      n.layer < 2 ? n.layer : n.layer === 2 ? 0 : n.layer === 3 ? 1 : 2;
    const base = n.layer === 2 || n.layer === 3 ? topRows * 88 + 40 : 0;
    n.x = 12 + column * 205;
    n.y = 24 + base + counts[n.layer]++ * 88;
  }
  const hasAssessment = counts[4] > 0;
  graph.setAttribute(
    "viewBox",
    `0 0 ${hasAssessment ? 630 : 425} ${Math.max(340, ...Array.from(nodes.values(), (n) => n.y + 90))}`,
  );
  graph.replaceChildren();
  for (const edge of projection.edges) {
    const a = nodes.get(edge.from),
      b = nodes.get(edge.to);
    if (!a || !b) continue;
    const line = svg("path", {
      d: `M${a.x + 176} ${a.y + 30} C${a.x + 192} ${a.y + 30},${b.x - 22} ${b.y + 30},${b.x} ${b.y + 30}`,
      class: `evidence-edge relation-${edge.kind} ${edge.event === active ? "current-relation" : ""}`,
      "data-from": edge.from,
      "data-to": edge.to,
      "data-relation": edge.label,
    });
    line.append(
      svg(
        "title",
        {},
        `${edge.label} · provenance: ${typeof edge.provenance === "string" ? edge.provenance : edge.provenance?.locator || "actual returned record"}`,
      ),
    );
    graph.append(line);
  }
  for (const n of nodes.values()) {
    if (n.sensor) n.label = names[n.sensor] || n.label;
    const isActive = n.eventKeys.includes(active);
    const g = svg("g", {
      class: `evidence-node type-${n.kind} ${isActive ? "current-node" : ""}`,
      role: "button",
      tabindex: 0,
      "aria-label": n.label,
      "data-node-id": n.id,
      "data-event-keys": n.eventKeys.join(","),
    });
    g.append(
      svg("rect", { x: n.x, y: n.y, width: 176, height: 66, rx: 12 }),
      svg(
        "text",
        { x: n.x + 10, y: n.y + 17, class: "node-kind" },
        n.kind.toUpperCase(),
      ),
    );
    const words = n.label.replaceAll("_", " ").split(/\s+/),
      lines = [""];
    for (const word of words) {
      const last = lines.length - 1;
      if (lines[last] && lines[last].length + word.length + 1 > 24)
        lines.push(word);
      else lines[last] += (lines[last] ? " " : "") + word;
    }
    g.append(
      svg("text", { x: n.x + 10, y: n.y + 35 }, lines[0]),
      svg(
        "text",
        { x: n.x + 10, y: n.y + 52 },
        (lines[1] || "") + (lines.length > 2 ? "…" : ""),
      ),
      svg("title", {}, n.label),
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
  $("graphNodeList").replaceChildren();
  const list = el("details"),
    header = el("summary", `Inspect all ${nodes.size} received graph entities`);
  list.append(header);
  for (const n of nodes.values()) {
    const b = el("button", n.label, "quiet");
    b.onclick = () => inspectNode(n);
    list.append(b);
  }
  $("graphNodeList").append(list);
  renderPhysicalHypotheses(events);
  const signature = `${c().id}:${execution}:${active}:${nodes.size}`;
  if (graph.dataset.focusSignature !== signature && nodes.size) {
    graph.dataset.focusSignature = signature;
    const highlighted = Array.from(nodes.values()).filter((n) =>
      n.eventKeys.includes(active),
    );
    const top = highlighted.length
      ? Math.min(...highlighted.map((n) => n.y))
      : 0;
    requestAnimationFrame(() => {
      graph.parentElement.scrollTop = Math.max(
        0,
        (top * graph.clientWidth) / (hasAssessment ? 630 : 425) - 20,
      );
    });
  }
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
        const changed = current !== Number(a.dataset.case);
        current = Number(a.dataset.case);
        synthetic = false;
        $("scenarioSelect").value = "historical";
        if (changed) {
          index = 0;
          workspaceView = "operator";
        }
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
  current = Number($("caseSelect").value);
  index = 0;
  workspaceView = "operator";
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
$("capturePause").onclick = () => {
  const r = investigation();
  r.playing = !r.playing;
  renderPlatform();
};
$("captureRestart").onclick = () => {
  if (execution !== "captured" || !checkpointReached()) return;
  stopCapturedClock();
  const r = investigation();
  r.cursor = 1;
  r.playing = true;
  selectedEvidenceEvent = 0;
  renderPlatform();
};
$("captureSkip").onclick = () => {
  if (execution !== "captured" || !checkpointReached()) return;
  stopCapturedClock();
  const r = investigation();
  r.cursor = r.events.length;
  r.playing = false;
  selectedEvidenceEvent = r.cursor - 1;
  renderPlatform();
  followInvestigation();
};
$("back").onclick = () => {
  if (liveBusy) return;
  resetPlayback();
  workspaceView = "operator";
  setReplayPosition(0);
};
$("liveRun").onclick = () => {
  if (!status.live_enabled || liveBusy || !checkpointReached()) return;
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
    index = 0;
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
