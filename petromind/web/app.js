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
let tooltipSerial = 0,
  graphZoom = 1;
function sensorLabel(sensor) {
  return names[sensor] || c()?.sensor_definitions?.[sensor]?.name || sensor;
}
function canonicalPlain(text) {
  let output = String(text || "");
  for (const sensor of Object.keys(c()?.sensor_definitions || {}).sort(
    (a, b) => b.length - a.length,
  )) {
    const label = sensorLabel(sensor);
    if (label !== sensor) output = output.replaceAll(sensor, label);
  }
  return output;
}
function namedText(text) {
  const fragment = document.createDocumentFragment(),
    source = String(text || "");
  const sensors = Object.keys(c()?.sensor_definitions || {})
    .filter((s) => sensorLabel(s) !== s)
    .sort((a, b) => b.length - a.length);
  if (!sensors.length) {
    fragment.append(source);
    return fragment;
  }
  const escaped = sensors.map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  for (const part of source.split(
    new RegExp("(" + escaped.join("|") + ")", "g"),
  )) {
    if (!sensors.includes(part)) {
      fragment.append(part);
      continue;
    }
    const term = el("span", sensorLabel(part), "sensor-term");
    term.tabIndex = 0;
    term.setAttribute("role", "button");
    term.setAttribute(
      "aria-label",
      `${sensorLabel(part)}. Technical identifier: ${part}. Activate to inspect.`,
    );
    term.title = part;
    term.dataset.sensorId = part;
    const tip = el("span", part, "sensor-tooltip");
    tip.id = "sensor-tip-" + ++tooltipSerial;
    tip.setAttribute("role", "tooltip");
    term.setAttribute("aria-describedby", tip.id);
    term.append(tip);
    term.onfocus = () => term.classList.remove("tooltip-dismissed");
    term.onmouseenter = () => term.classList.remove("tooltip-dismissed");
    term.onclick = () => { term.classList.toggle("tooltip-open"); term.classList.toggle("tooltip-dismissed",!term.classList.contains("tooltip-open")); };
    term.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        term.classList.toggle("tooltip-open");
      }
      if (e.key === "Escape") { term.classList.remove("tooltip-open"); term.classList.add("tooltip-dismissed"); }
    };
    fragment.append(term);
  }
  return fragment;
}
function narrative(tag, text, cls) {
  const n = el(tag, undefined, cls);
  n.append(namedText(text));
  return n;
}
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
    execution !== "captured" &&
    visibleEvents().some(
      (e) => e.tool === "request_sensor" && e.sensor === s && e.summary,
    )
  );
}
function observationStatus(s) {
  return inventoryFor(s)?.observed_by_muse
    ? "Received captured summary"
    : newlyInspected(s)
      ? `Requested in this ${execution === "saved" ? "saved" : "live"} audit`
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
  // Reserve counter widths so changing digits cannot resize the drag track.
  $("sampleCounter").style.minWidth = `${11 + 2 * String(w.positions).length}ch`;
  $("clock").style.minWidth = w.elapsed_seconds
    ? `${3 + 2 * Math.max(8, elapsedLabel(w.elapsed_seconds.at(-1)).length)}ch`
    : "";
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
    ? "Recorded pressure changes · the first 5 minutes provide a measured reference, not a certified safe range."
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
    b.title = s;
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
function renderPressureOverview() {
  const box = $("pressureOverview");
  box.replaceChildren();
  for (const sensor of ["P-PDG", "P-TPT"]) {
    const stream = streamFor(sensor);
    if (!stream) continue;
    const card = el("article", undefined, "pressure-preview");
    card.append(
      el("strong", names[sensor]),
      el("span", `${sensor} · ${value(sensor, stream.samples[index].value)}`),
    );
    const plot = svg("svg", {
      viewBox: "0 0 320 70",
      role: "img",
      "aria-label": `${names[sensor]} through current recorded position; gaps preserved`,
      "data-index": index,
    });
    const samples = stream.samples.slice(0, index + 1);
    const valid = samples
      .filter((p) => p.quality === "valid" && p.value !== null)
      .map((p) => scaled(sensor, p.value));
    if (valid.length) {
      const lo = Math.min(...valid),
        hi = Math.max(...valid),
        range = hi - lo || 1;
      let d = "",
        connected = false;
      samples.forEach((p, i) => {
        if (p.quality !== "valid" || p.value === null) {
          connected = false;
          return;
        }
        if (
          i &&
          c().replay.workflow.elapsed_seconds &&
          c().replay.workflow.elapsed_seconds[i] -
            c().replay.workflow.elapsed_seconds[i - 1] >
            1.5
        )
          connected = false;
        const x =
            8 + (304 * i) / Math.max(1, c().replay.workflow.positions - 1),
          y = 52 - (38 * (scaled(sensor, p.value) - lo)) / range;
        // Endpoint captures remain unconnected points, never fabricated traces.
        if (c().replay.mode === "endpoints" || !connected)
          plot.append(
            svg("circle", { cx: x, cy: y, r: 2.5, class: "chart-point" }),
          );
        if (c().replay.mode !== "endpoints")
          d += `${connected ? "L" : "M"}${x} ${y} `;
        connected = true;
      });
      if (d) plot.append(svg("path", { d, class: "chart-line" }));
    } else
      plot.append(
        svg(
          "text",
          { x: 8, y: 35, class: "chart-axis" },
          "No valid readings at this position",
        ),
      );
    card.append(
      plot,
      el(
        "small",
        c().replay.mode === "endpoints"
          ? "Recorded endpoints only · no continuous trace"
          : "Recorded values to current time · local vertical scale",
      ),
    );
    box.append(card);
  }
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
  const selectedEvents = visibleEvents();
  const selectedOutput = PublicInvestigation.result(selectedEvents);
  const a =
    execution === "captured"
      ? audit()
      : {
          output: selectedOutput || { findings: [] },
          sources: Object.fromEntries(
            selectedEvents
              .flatMap((e) => [...(e.facts || []), ...(e.matches || [])])
              .map((f) => [f.citation_id, f]),
          ),
          notes: (selectedOutput?.findings || []).map(() => ({
            text: "Recorded public finding; independent engineering review remains pending.",
          })),
        };
  $("grounded").disabled = execution !== "captured";
  $("ungrounded").disabled = execution !== "captured";
  $("evidenceContext").textContent =
    c().replay.timing +
    " " +
    c().replay.reference_note +
    " " +
    c().replay.visibility +
    " No interpolation, filling or downsampling. Geometry is illustrative, not verified well-specific topology. Independent engineering review remains pending; this is not root-cause certification.";
  $("originalClaim").textContent = c().packet.claim;
  $("evidenceMeasurements").textContent = JSON.stringify(
    execution === "captured"
      ? c().observations
      : Object.assign(
          {},
          c().observations,
          ...selectedEvents
            .filter((e) => e.sensor && e.summary)
            .map((e) => ({ [e.sensor]: e.summary })),
        ),
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
        el(
          "p",
          `Recorded next evidence: ${typeof f.next_evidence === "string" ? f.next_evidence : JSON.stringify(f.next_evidence)}`,
        ),
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
          `${f.training_event !== undefined ? "Original historical label " + f.training_event + "; " : ""}${f.shared_sensors} shared sensors: ${f.matched_sensors.join(", ")}. Distance ${f.distance}, not a probability.`,
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
      attribution:
        execution === "captured"
          ? "Original captured real Muse output, unchanged"
          : execution === "saved"
            ? "Verified saved v5 public output, unchanged"
            : "New live public output",
      parent_capture_protocol_id: c().source_protocol_id,
      output: a.output,
      baseline: c().packet.baseline,
      chronology:
        execution === "captured"
          ? c().captured_activity[condition]
          : selectedEvents,
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
  focusSensor = null,
  showAllEvidence = false,
  selectedFinding = null;
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
function journeyState() {
  const r = investigation(),
    events = visibleEvents();
  const done = r.phase === 2 && !!PublicInvestigation.completedResult(events);
  if (done) return 4;
  if (checkpointReached()) return r.phase === 2 ? 3 : 2;
  return anomalyReached() ? 1 : 0;
}
function renderJourney() {
  const stage = journeyState(),
    r = investigation(),
    ready = checkpointReached();
  const firstAlert = c().replay.workflow.monitor?.trace.findIndex(
    (p) => p.new_alert,
  );
  const noAlertEnd =
    c().replay.mode === "history" &&
    firstAlert < 0 &&
    index >= c().replay.workflow.checkpoint.index;
  const target = !ready
    ? firstAlert >= 0 && index < firstAlert
      ? firstAlert
      : c().replay.workflow.checkpoint.index
    : null;
  $("journeyMode").textContent =
    execution === "live"
      ? "Live Muse mode · paid when started"
      : execution === "saved"
        ? "Saved Muse replay · no new API call"
        : "Captured Muse replay · no new API call";
  [...$("journeySteps").children].forEach((step, i) => {
    step.classList.toggle("is-current", i === stage);
    step.classList.toggle("is-complete", i < stage);
    if (i === stage) step.setAttribute("aria-current", "step");
    else step.removeAttribute("aria-current");
  });
  $("journeyHint").textContent = noAlertEnd
    ? "No sustained alert was detected in this recorded clip. A classifier or Muse investigation has not been triggered. You can inspect the measurements without inventing a diagnosis."
    : [
        "A production well moves fluids from underground to surface equipment. Watch its recorded pressures, then inspect the change.",
        "The monitor found sustained pressure deviation. Complete the recorded evidence window to reveal the saved classifier prediction.",
        "The classifier proposes a failure. Review its evidence and the claim Muse will investigate.",
        r.error
          ? "The investigation stopped. Inspect the failure, or explicitly select a recorded replay from the console."
          : "Follow actual tool activity and returned evidence. The assessment appears only when it is received.",
        "Review what the recorded findings establish, what they leave unknown, and the evidence needed next.",
      ][stage];
  const button = $("journeyAction");
  button.hidden = liveBusy;
  button.textContent = noAlertEnd
    ? "Inspect recorded measurements →"
    : !ready
      ? target === firstAlert
        ? "Jump to recorded alert →"
        : "Continue to classifier →"
      : stage === 2
        ? "Review classifier & continue →"
        : stage === 4
          ? "Read the findings →"
          : workspaceView === "inside"
            ? "Return to console"
            : "Follow Muse investigation →";
  button.onclick = () => {
    if (liveBusy) return;
    if (noAlertEnd) {
      workspaceView = "operator";
      renderPlatform();
      $("pressureOverview").scrollIntoView({
        block: "center",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
      return;
    }
    if (!ready) {
      resetPlayback();
      setReplayPosition(target, true);
      return;
    }
    if (stage === 2) {
      workspaceView = "operator";
      renderPlatform();
      $("classifierHandoff").scrollIntoView({
        block: "start",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
    } else {
      workspaceView =
        workspaceView === "inside" && stage !== 4 ? "operator" : "inside";
      renderPlatform();
      (stage === 4
        ? $("insideAssessment")
        : workspaceView === "inside"
          ? $("insidePanel")
          : $("consoleView")
      ).scrollIntoView({
        block: "start",
        behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
      });
    }
  };
  $("journeySeekNote").style.visibility = ready ? "hidden" : "visible";
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
  renderJourney();
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
function setReplayPosition(position, scrollToAlert = false) {
  const wasReady = checkpointReached(),
    wasAlerted = anomalyReached();
  index = Math.max(0, Math.min(c().replay.workflow.positions - 1, position));
  if (!checkpointReached()) {
    for (const id of ["details", "nodeDialog"]) if ($(id).open) $(id).close();
  }
  renderPlatform();
  if (
    scrollToAlert &&
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
    execution !== "live" &&
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
    selectedFinding = null;
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
    "Muse checks the proposed explanation against measurements and engineering context.";
  const modeDisclosure =
    execution === "live"
      ? "A fresh Muse investigation using the enabled model and tools."
      : "This demonstration replays a previously completed Muse investigation using its original recorded evidence and findings. No new AI request will be made.";
  $("insideModeBadge").textContent =
    execution === "live" ? "Live investigation" : "Investigation replay";
  $("insideModeBadge").setAttribute("aria-label", modeDisclosure);
  $("insideModeText").textContent =
    modeDisclosure +
    (execution !== "live"
      ? " Event order is preserved; playback pacing is presentation timing, not original model timing."
      : " Progress shows received tool activity.");
  $("captureControls").hidden = r.phase !== 2 || !checkpointReached();
  for (const id of ["capturePause", "captureRestart", "captureSkip"])
    $(id).hidden = execution === "live";
  $("capturePause").textContent = r.playing ? "Pause investigation" : "Continue investigation";
  $("capturePause").disabled = r.cursor >= r.events.length;
  $("captureSkip").disabled = r.cursor >= r.events.length;
  $("investigationActivity").textContent =
    !checkpointReached() || r.phase !== 2
      ? ""
      : liveBusy
        ? "Muse is investigating · waiting for evidence"
        : r.error
          ? "Stopped · no completed assessment substituted"
          : execution !== "live" && r.cursor < r.events.length
            ? r.playing
              ? "Investigation in progress…"
              : "Replay paused"
            : "Investigation complete";
  $("investigationBrief").hidden = !checkpointReached() || r.phase !== 2;
  const received = events.find((e) => e.kind === "evidence_received");
  $("investigationQuestion").replaceChildren(
    namedText(
      received?.claim ||
        "Waiting for the measurements and question under review.",
    ),
  );
  const observations = new Set(Object.keys(received?.observations || {}));
  for (const e of events) if (e.sensor && e.summary) observations.add(e.sensor);
  const facts = events.flatMap((e) => e.facts || []),
    matches = events.flatMap((e) => e.matches || []);
  $("investigationEvidence").textContent =
    `${observations.size} sensor summaries · ${facts.length} source facts · ${matches.length} historical comparisons`;
  const feed = $("eventFeed"),
    owner = `${c().id}:${execution}:${!!PublicInvestigation.completedResult(events)}`;
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
      selectedFinding = null;
      renderPlatform();
    };
    li.append(button);
    li.append(
      el(
        "small",
        e.kind === "evidence_received"
          ? "Measurements and claim received"
          : e.kind === "tool_request"
            ? execution !== "live"
              ? "Evidence requested"
              : "Evidence requested"
            : e.kind === "completion"
              ? "Execution status"
              : "Evidence retrieved",
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
          `Engineering context: ${canonicalPlain(e.topic)}. Documentation describes general topics, not a verified layout of this well.`,
        ),
      );
    for (const f of e.facts || []) {
      const fact = el(
        "button",
        canonicalPlain(
          `${f.subject} · ${f.relation.replaceAll("_", " ")} · ${f.object}`,
        ),
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
    if (e.assessment && !PublicInvestigation.completedResult(events)) {
      li.append(
        el("p", "Assessment submitted; awaiting execution completion."),
      );
    } else if (e.assessment) {
      li.append(
        el("h3", "Assessment received"),
        el(
          "p",
          "Read the investigation finding above. Exact findings are available in the technical audit.",
        ),
      );
      const detail = el("details");
      detail.append(el("summary", "Assessment details"));
      for (const f of e.assessment.findings)
        detail.append(
          el("p", `${f.verdict.replaceAll("_", " ")}: ${f.statement}`),
        );
      li.append(detail);
    }
    if (e.kind === "completion") {
      const d = el("details");
      d.append(
        el("summary", "Execution details"),
        el("p", `${e.status} · ${e.reason}`),
      );
      li.append(d);
    }
    feed.append(li);
  });
}
function renderPhysicalHypotheses(events) {
  const box = $("physicalHypotheses");
  box.replaceChildren();
  const facts = events.flatMap((e) => e.facts || []),
    summary = PublicInvestigation.operatorConclusion(events);
  if (!facts.length && !summary) return;
  box.append(
    el("h4", "How the evidence connects"),
    el(
      "p",
      "Logical evidence diagram — not a piping diagram or a physical causal model.",
      "fine-print",
    ),
  );
  const diagram = el("div", undefined, "physical-evidence-diagram");
  function card(title, label, kind) {
    const c = el("section", undefined, "physical-card " + kind);
    c.append(el("small", label), el("h5", title));
    diagram.append(c);
    return c;
  }
  const observed = card(
    "Observed measurement changes",
    summary ? "SUPPORTED MEASUREMENTS" : "MEASUREMENTS RECEIVED",
    "measured",
  );
  if (summary?.measured.length)
    for (const m of summary.measured)
      observed.append(
        narrative(
          "p",
          `${m.sensor}: ${value(m.sensor, m.summary.first)} → ${value(m.sensor, m.summary.last)}`,
        ),
      );
  else
    observed.append(
      el(
        "p",
        "Read the supplied measurements in the evidence timeline; no new direction or causal inference is added here.",
      ),
    );
  const documented = card(
    "Documented comparison",
    "ENGINEERING CONTEXT",
    "documented",
  );
  if (summary?.comparisons.length)
    documented.append(narrative("p", summary.comparisons[0].statement));
  else {
    const example = facts.find((f) =>
      String(f.relation).startsWith("example:"),
    );
    documented.append(
      example
        ? narrative(
            "p",
            `${example.subject}: ${example.object} — ${example.relation.replaceAll("_", " ")}`,
          )
        : el(
            "p",
            "No supported example comparison was identified in this assessment.",
          ),
    );
  }
  documented.append(
    el(
      "small",
      "A source example or general association is not proof of this well’s cause.",
    ),
  );
  const causal = card(
    "Evidence needed for causation",
    summary?.rootVerdict || "ASSESSMENT PENDING",
    "gap",
  );
  if (summary?.nextPlan.requirements.length)
    for (const requirement of summary.nextPlan.requirements.slice(0, 2))
      causal.append(narrative("p", requirement));
  else
    causal.append(
      el(
        "p",
        summary?.statusLabel ||
          "Causal status is shown only after the assessment completes.",
      ),
    );
  box.append(diagram);
  const sources = el("details");
  sources.append(el("summary", "Engineering source facts and exact scope"));
  for (const fact of facts)
    sources.append(
      narrative("p", `${fact.subject} · ${fact.relation} · ${fact.object}`),
      el("small", `${fact.locator || ""} · ${fact.scope || ""}`),
    );
  box.append(sources);
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
  return execution !== "live" ? r.events.slice(0, r.cursor) : r.events;
}
function navigate(page, push = true) {
  if (page !== "demo") resetPlayback();
  pageName = page;
  if (push) history.pushState({}, "", page === "home" ? "/" : "/" + page);
  renderPlatform();
  window.scrollTo(0, 0);
}
function renderClassifierCandidates(ranked) {
  // Display-only ranking of the supplied scores; never refit or recalibrate them.
  const usable = ranked.filter(
    (p) => Number.isFinite(p.probability) && p.probability >= 0,
  );
  $("classifierRanking").hidden =
    usable.length < 2 || usable[0].probability <= 0;
  const maximum = usable[0]?.probability || 1;
  $("classifierCandidates").replaceChildren(
    ...usable.slice(0, 3).map((candidate, i) => {
      const row = el("li");
      const label =
        PublicInvestigation.faultNames[candidate.fault_type] ||
        `Fault category ${candidate.fault_type}`;
      row.dataset.fault = candidate.fault_type;
      row.dataset.score = candidate.probability;
      row.append(
        el("span", String(i + 1).padStart(2, "0"), "candidate-rank"),
        el("span", label, "candidate-name"),
      );
      const bar = el("span", undefined, "candidate-track"),
        fill = el("span");
      bar.setAttribute("aria-hidden", "true");
      fill.style.width = `${(100 * candidate.probability) / maximum}%`;
      bar.append(fill);
      row.append(bar);
      return row;
    }),
  );
}
function renderPlatform() {
  if (!cases.length) return;
  if (execution === "saved" && !c().saved_investigation) execution = "captured";
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
  const liveOption = $("executionSelect").querySelector('[value="live"]');
  liveOption.disabled = !status.live_enabled;
  liveOption.textContent = status.live_enabled
    ? "Run live investigation"
    : "Run live investigation · not enabled";
  $("savedExecution").disabled = !c().saved_investigation;
  $("savedExecution").hidden = !c().saved_investigation;
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
    ? "MEASUREMENT ALERT"
    : "MEASUREMENT REVIEW";
  $("checkpointTitle").textContent = history
    ? "Diagnostic alert triggered"
    : c().replay.mode !== "endpoints"
      ? "Diagnostic window complete"
      : "Captured comparison complete";
  $("checkpointExplanation").textContent = history
    ? "Both monitored pressures moved unusually far from their earlier measured reference. Something changed; this alert does not identify the failure cause."
    : "The recorded pressure comparison is ready for investigation. This review checkpoint is not a recorded operational alarm.";
  $("alertRuleDetails").textContent = history
    ? "The recorded detector flagged both pressures after deviations of at least 6 robust reference scales persisted for 30 seconds. The measured reference is not certified normal; this is a demonstration heuristic, not a validated industrial alarm."
    : "This demonstration uses completion of the captured measurement window as its review checkpoint, not a historical operational alarm or early prediction.";
  const diagnosticCount = Math.max(
    0,
    Math.min(600, index - (c().replay.workflow.checkpoint.index - 599) + 1),
  );
  $("monitoringHeading").textContent = !history
    ? "Monitoring sensor measurements"
    : anomalyReached()
      ? "Accumulating diagnostic evidence"
      : point.state === "warmup"
        ? "Building a measurement reference"
        : "Monitoring sensor measurements";
  $("monitoringExplanation").textContent = !history
    ? "Play or scrub the recorded measurements. The saved diagnosis becomes available only at the end-of-evidence checkpoint."
    : anomalyReached()
      ? `Alert recorded. Collecting the diagnosis evidence: ${diagnosticCount} of 600 recorded observations. The saved diagnosis stays hidden until its complete measurement window is available.`
      : point.state === "warmup"
        ? "The first five recorded minutes form a measured reference. Earlier operation is not automatically normal or safe. No fault prediction is shown."
        : point.state === "reference_unavailable"
          ? "The reference lacks enough variable valid pressure measurements. A constant or zero signal is valid, but cannot supply this detector’s MAD scale. No alert is fabricated."
          : point.state === "measurement_unavailable"
            ? "A required pressure measurement is unavailable. Persistence resets; no reading is invented."
            : index === c().replay.workflow.positions - 1
              ? "No sustained two-pressure deviation alert was detected in this replay. No fault diagnosis was triggered."
              : "Monitoring recorded pressures against the earlier measured reference. Sustained deviation can trigger an anomaly alert; it does not identify the cause.";
  $("investigationNext").hidden = !ready || r.phase === 2;
  $("investigationLaunch").hidden = !ready;
  $("handoffDetails").hidden = !ready;
  $("executionControl").hidden = !ready;
  $("capabilityDetails").hidden = !ready;
  $("runBadge").hidden = !ready;
  $("runInstruction").hidden = !ready;
  $("inspectDetails").hidden = !ready;
  $("executionNote").hidden = !ready;
  $("executionNote").textContent =
    execution !== "live"
      ? execution === "saved"
        ? "Verified saved v5 replay · no new API call"
        : "Original captured investigation · no new API call"
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
    PublicInvestigation.faultNames[c().packet.baseline.prediction] ||
    "Recorded classifier hypothesis";
  $("preDiagnosis").hidden = ready;
  const predicted = c().packet.baseline.prediction;
  const fault =
    PublicInvestigation.faultNames[predicted] || `Fault category ${predicted}`;
  $("cause").replaceChildren(
    el("span", "Suspected failure:", "cause-label"),
    el("strong", fault, "cause-name"),
  );
  const ranked = (c().packet.baseline.probabilities || [])
    .filter((p) => p.represented_in_fit)
    .sort((a, b) => b.probability - a.probability);
  $("classifierStatement").textContent =
    ranked.length && ranked[0].fault_type === predicted
      ? "The statistical classifier compared this measurement pattern with patterns learned from training data and ranked this failure highest. It is a ranked statistical hypothesis, not proof or a calibrated probability."
      : "The statistical classifier compared measured features with patterns learned from training data. This prediction is a statistical hypothesis, not proof or a calibrated probability.";
  renderClassifierCandidates(ranked);
  $("classifierFeatures").textContent =
    `${c().classifier_context?.model || "Statistical evidence model"}: ${(c().classifier_context?.features || []).join(", ")}. No per-sensor feature importance is recorded.`;
  $("classifierInputs").textContent =
    c().classifier_context?.sensor_attribution ||
    "Exact classifier input attribution is not supplied by this capture.";
  $("definition").textContent = [8, 9].includes(predicted)
    ? "Hydrate is ice-like material that can accumulate in production equipment and restrict flow."
    : "A valve deep in the well can shut off production flow.";
  $("diagnosisObservations").replaceChildren(
    ...["P-PDG", "P-TPT"].map((sensor) => {
      const summary = c().observations[sensor],
        li = el("li");
      li.dataset.direction = !summary?.available
        ? "missing"
        : summary.delta > 0
          ? "up"
          : summary.delta < 0
            ? "down"
            : "stable";
      li.append(
        el("strong", names[sensor]),
        el(
          "b",
          !summary?.available
            ? "— Unavailable"
            : summary.delta > 0
              ? "↑ Increased"
              : summary.delta < 0
                ? "↓ Decreased"
                : "→ No endpoint change",
          "measurement-direction",
        ),
        el(
          "span",
          summary?.available
            ? `${value(sensor, summary.first)} → ${value(sensor, summary.last)}`
            : "No valid recorded measurements",
        ),
        el(
          "small",
          summary?.available
            ? `Change from first to last valid reading: ${value(sensor, summary.delta)}`
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
    execution !== "live"
      ? `${execution === "saved" ? "Saved v5" : "Captured v1"} · ${r.cursor}/${r.events.length} records revealed`
      : liveBusy
        ? `${status.capabilities?.new_sensor_queries ? "Live v3" : "Live v2"} · actual tool events arriving`
        : `${status.capabilities?.new_sensor_queries ? "Live v3" : "Live v2"} · explicit API execution`;
  $("runInstruction").textContent =
    execution !== "live"
      ? execution === "saved"
        ? "Replay: This demonstration replays a previously completed Muse investigation using its original recorded evidence and findings. No new AI request will be made. Playback advances automatically."
        : "Replay: This demonstration replays a previously completed Muse investigation using its original recorded evidence and findings. No new AI request will be made. Playback advances automatically."
      : status.live_enabled
        ? `Live: runs a fresh Muse investigation with the enabled model and tools. Clicking Investigate uses the paid API within the prepared $${status.live_limits?.estimated_usd ?? 2} estimated cap.`
        : "Live is disabled. Prepare a fresh live protocol and restart with --enable-live; no API calls occur in replay.";
  $("capabilityText").textContent = status.capabilities?.new_sensor_queries
    ? "Live v3 adds request_sensor: at most two additional summaries, after lookup of their documented generic location. Initial and new sensors share five queries; missing queries count and cached repeats are free. No raw playback enters Muse. History remains the initial training-only snapshot; no exact well topology is available. Captured runs remain unchanged."
    : "Live evidence auditing exposes lookup_knowledge, search_history and submit_audit. Three inherited summaries count toward five queries. Extra sensors require a fresh active-sensor protocol and verified raw dataset. No exact well topology is available. History uses initial evidence only.";
  if (status.live_enabled)
    $("capabilityText").textContent +=
      ` Prepared global limits: $${status.live_limits?.estimated_usd ?? 2} estimated, ${status.live_limits?.requests ?? 12} requests, ${status.live_limits?.output_tokens ?? 49152} output tokens. Python enforces remaining reservations.`;
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
  const events = visibleEvents(),
    result = PublicInvestigation.completedResult(events);
  const finished = !!result;
  const previouslyFinished = $("insidePanel").dataset.completed === "true";
  $("insidePanel").dataset.completed = String(finished);
  $("completionEvidenceTitle").hidden = !finished;
  if (finished && !previouslyFinished) $("completionEvidence").open = false;
  if (!finished) $("completionEvidence").open = true;
  const box = $("operatorResult");
  box.replaceChildren();
  const completion = events.findLast((e) => e.kind === "completion");
  const stopped =
    r.error ||
    (!result && completion && (completion.reason || completion.status));
  if (ready && stopped)
    box.append(
      el("h3", "Investigation stopped · no completed audit"),
      el(
        "p",
        stopped === "model_output_token_limit"
          ? "Muse reached its response limit before completing the assessment. No conclusion is substituted."
          : "The investigation did not complete. No diagnosis or recorded replay was substituted.",
      ),
      el("p", `Recorded execution status: ${stopped}`, "fine-print"),
    );
  $("insideAssessment").replaceChildren();
  if (ready && result) {
    renderFinalFinding($("insideAssessment"), result, events);
    const summary = PublicInvestigation.operatorConclusion(events);
    const compact = el("section", undefined, "operator-investigation-summary");
    compact.append(
      el("p", "Investigation complete", "eyebrow"),
      el("h3", summary.statusLabel),
      el("p", summary.headline),
      el("p", `Classifier suspected: ${summary.suspected}.`),
    );
    const review = el("button", "Open investigation finding →", "primary");
    review.dataset.openFinding = "true";
    compact.append(review);
    box.append(compact);
  } else if (ready && stopped) {
    box.append(el("p","Root-cause assessment incomplete","root-cause-status"));
    const review=el("button","Review incomplete investigation →","quiet");review.dataset.openFinding="true";box.append(review);
    const incomplete=box.cloneNode(true);incomplete.removeAttribute("id");$("insideAssessment").append(incomplete);
  } else if (ready && r.phase === 2)
    box.append(
      el("h3", "Muse investigation in progress"),
      el("p", "Follow the evidence and findings in Inside Muse."),
    );
  $("classifierHandoff").hidden = ready && r.phase === 2;
  const modeHome = r.phase === 2 ? $("handoffDetails").querySelector(".handoff-detail-body") : $("investigationLaunch");
  if(r.phase===2) modeHome.append($("executionControl"),$("runInstruction"));
  else { modeHome.insertBefore($("executionControl"),$("nextScene")); modeHome.insertBefore($("runInstruction"),$("nextScene")); }

  for (const root of [box, $("insideAssessment")])
    root.onclick = (event) => {
      const finding = event.target.closest("[data-finding-index]");
      if (finding) {
        showFindingEvidence(Number(finding.dataset.findingIndex));
        return;
      }
      if (event.target.closest("[data-open-finding]")) {
        workspaceView = "inside";
        renderPlatform();
        followInvestigation();
        return;
      }
      if (event.target.closest("[data-inspect-evidence]")) {
        workspaceView = "inside";
        $("completionEvidence").open = true;
        $("graphPanel").open = true;
        renderPlatform();
        $("completionEvidence").scrollIntoView({ block: "start" });
      }
    };
  $("inspectDetails").hidden = !ready || !result;
  renderTelemetry();
  renderPressureOverview();
  renderEvidenceGraph();
  syncCapturedClock();
  if (focusSensor && ready)
    document
      .querySelector(`[data-sensor="${focusSensor}"]`)
      ?.classList.add("evidence-focus");
}
function renderFinalFinding(box, result, events) {
  const summary = PublicInvestigation.operatorConclusion(events);
  const mode =
    execution === "live"
      ? "NEW LIVE"
      : execution === "saved"
        ? "SAVED v5"
        : "ORIGINAL CAPTURED";
  const hero = el("section", undefined, "final-conclusion");
  hero.dataset.causeStatus = summary.status;
  hero.append(
    el("p", "Investigation finding", "eyebrow"),
    el("h3", summary.headline),
    el(
      "p",
      `Suspected root cause: ${summary.suspected} — ${summary.rootVerdict}.`,
      "conclusion-cause",
    ),
    el("strong", summary.statusLabel, "root-cause-status"),
  );
  hero.append(el("p", summary.explanation, "conclusion-boundary"));
  box.append(hero);
  const comparison = el("div", undefined, "result-comparison");
  const classifier = el("section"),
    muse = el("section");
  classifier.append(
    el("h4", "Statistical classifier"),
    el("strong", summary.fault),
    el("p", "Preliminary statistical hypothesis — not proof of cause."),
  );
  muse.append(
    el("h4", "Muse investigation"),
    el("strong", summary.statusLabel),
    el("p", "The findings below report what the received evidence supports."),
  );
  comparison.append(classifier, muse);
  box.append(comparison);
  const parts = el("div", undefined, "result-summary");
  function part(title, key) {
    const section = el("section");
    section.dataset.resultPart = key;
    section.append(el("h4", title));
    parts.append(section);
    return section;
  }
  const confirmed = part("What we confirmed", "confirmed");
  if (summary.measured.length) {
    for (const m of summary.measured)
      confirmed.append(
        narrative(
          "p",
          `${m.sensor}: ${value(m.sensor, m.summary.first)} → ${value(m.sensor, m.summary.last)} (change ${value(m.sensor, m.summary.delta)}).`,
          "confirmed-measurement",
        ),
      );
  }
  const other = summary.confirmed.filter(
    (f) =>
      !(
        f.scope === "measured_observation" ||
        (!f.scope && f.basis === "measurement")
      ),
  );
  for (const f of other.slice(0, 1))
    confirmed.append(narrative("p", f.statement));
  if (!summary.measured.length && !other.length)
    confirmed.append(
      el(
        "p",
        summary.confirmed[0]?.statement ||
          "No supported observation was separately recorded.",
      ),
    );
  const uncertain = part("What remains uncertain", "uncertain");
  if (summary.uncertain.length) {
    uncertain.append(
      el(
        "p",
        summary.status === "unverified"
          ? `The supplied evidence does not establish ${summary.fault.toLowerCase()} as the cause of these readings. The missing link is evidence connecting the observed pattern to this specific cause.`
          : "The recorded evidence leaves limits on what this finding establishes. A matching example does not independently identify the cause.",
      ),
    );
    const gaps = el("details");
    gaps.append(el("summary", "Read the recorded evidence gap"));
    for (const gap of summary.uncertain) gaps.append(narrative("p", gap));
    uncertain.append(gaps);
  }
  if (!summary.uncertain.length)
    uncertain.append(
      el(
        "p",
        summary.status === "supported"
          ? "No missing premise was recorded for that scoped causal finding. Independent physical verification is still not supplied."
          : "No separate causal gap was recorded. Read the claim's exact scope before drawing a root-cause conclusion.",
      ),
    );
  box.append(parts);
  const next = el("section", undefined, "operator-next-steps");
  next.dataset.resultPart = "next";
  next.append(
    el("p", "Next evidence", "eyebrow"),
    el("h4", "What should be verified next?"),
    el("strong", summary.nextPlan.question, "unresolved-question"),
  );
  const requirements = el("ul");
  for (const requirement of summary.nextPlan.requirementSources) {
    const item = narrative("li", requirement.text);
    item.append(el("small", `Finding ${requirement.findingIndex + 1} · ${requirement.source}`, "fine-print"));
    if (requirement.premise && requirement.premise !== requirement.text) {
      const origin = el("details");
      origin.append(el("summary", "Original missing premise"), narrative("p", requirement.premise));
      item.append(origin);
    }
    requirements.append(item);
  }
  if (!requirements.children.length)
    requirements.append(
      el(
        "li",
        "No separate evidence requirement was specified for this claim.",
      ),
    );
  next.append(
    el("h5", "Evidence needed"),
    requirements,
    el("p", summary.nextPlan.limitation, "test-limitation"),
  );
  const requests = el("details");
  requests.append(el("summary", "Assessment’s evidence requests and scope"));
  for (const request of summary.nextPlan.requests)
    requests.append(narrative("p", request.text));
  if (!summary.nextPlan.requests.length)
    requests.append(el("p", "No additional recommendation was supplied."));
  requests.append(
    el(
      "p",
      "These are evidence requirements, not newly identified tests, sensor readings or field procedures.",
    ),
  );
  next.append(requests);
  box.append(next);
  const inspect = el("button", "Inspect supporting evidence →", "primary");
  inspect.dataset.inspectEvidence = "true";
  box.append(inspect);
  const receipt = el("details", undefined, "full-receipt");
  receipt.append(
    el("summary", "Technical audit · exact findings, verdicts and citations"),
    el(
      "p",
      `Execution: ${mode}. Exact verdict: ${result.verdict.replaceAll("_", " ")}`,
    ),
    el(
      "p",
      `Contract: ${result.contract_version || "Not specified"}. This presentation does not regrade or modify it.`,
    ),
  );
  const groups = PublicInvestigation.assessmentSections(result);
  for (const [key, title] of [
    ["measured", "Recorded sensor findings"],
    ["documented", "Recorded source comparisons"],
    ["causal", "Recorded causal claims"],
    ["other", "Other original findings (no declared scope)"],
  ]) {
    if (!groups[key].length) continue;
    const group = el("section", undefined, "assessment-scope");
    group.dataset.scope = key;
    group.append(el("h4", title));
    for (const f of groups[key]) {
      const item = el("article", undefined, "scoped-finding");
      item.dataset.verdict = f.verdict;
      item.append(
        el("h4", `Recorded verdict: ${f.verdict.replaceAll("_", " ")}`),
        el("p", `Claim assessed: ${f.statement}`),
      );
      for (const premise of f.premises || []) item.append(el("p", premise));
      item.append(
        el("p", f.justification || ""),
        el("p", `Citations: ${(f.citations || []).join(", ") || "None"}`),
        el("p", `Missing premise: ${f.missing_premise || "None recorded"}`),
        el(
          "p",
          `Next evidence: ${typeof f.next_evidence === "string" ? f.next_evidence : JSON.stringify(f.next_evidence || null)}`,
        ),
      );
      if (
        f.scope === "diagnostic_conclusion" &&
        f.verdict === "PARTIALLY_SUPPORTED"
      )
        item.append(
          el(
            "p",
            "Legacy recorded label — not regraded. This is not partial proof of cause.",
            "scope-gap",
          ),
        );
      const index = result.findings.indexOf(f),
        resolution = PublicInvestigation.findingEvidence(events, index);
      if (resolution.available) {
        const button = el(
          "button",
          resolution.citations.length
            ? "Show this evidence"
            : "Inspect the missing evidence",
          "quiet",
        );
        button.dataset.findingIndex = index;
        item.append(button);
        if (!resolution.citations.length)
          item.append(
            el(
              "p",
              "No received source citation supports this finding; inspect its stated evidence gap.",
              "fine-print",
            ),
          );
      } else
        item.append(
          el(
            "p",
            "No visual source or measurement can be resolved for this finding.",
            "fine-print",
          ),
        );
      group.append(item);
    }
    receipt.append(group);
  }
  receipt.append(el("details", undefined, "raw-assessment"));
  const raw = receipt.lastElementChild;
  raw.append(
    el("summary", "Full accepted public output (unchanged JSON)"),
    el("pre", JSON.stringify(result, null, 2)),
  );
  box.append(
    receipt,
    el(
      "p",
      "Recorded model findings; source integrity and numeric checks do not certify physical correctness. Independent engineering review pending.",
      "fine-print",
    ),
  );
}
function showFindingEvidence(index) {
  const resolution = PublicInvestigation.findingEvidence(
    visibleEvents(),
    index,
  );
  if (!resolution.available) return;
  workspaceView = "inside";
  selectedFinding = "finding:" + index;
  showAllEvidence = false;
  const entries = visibleEvents();
  selectedEvidenceEvent = entries.findLastIndex((e) => e.assessment);
  $("completionEvidence").open = true;
  $("graphPanel").open = true;
  renderPlatform();
  $("completionEvidence").open = true;
  $("graphPanel").open = true;
  renderEvidenceGraph();
  requestAnimationFrame(() => {
    $("graphPanel").scrollIntoView({ block: "start", behavior: "instant" });
    const node = Array.from(
      $("evidenceGraph").querySelectorAll("[data-node-id]"),
    ).find((n) => n.dataset.nodeId === selectedFinding);
    node?.focus({ preventScroll: true });
  });
}
function beginInvestigation() {
  if (!checkpointReached() || synthetic || liveBusy) return;
  const r = investigation();
  if (r.phase === 2) {
    workspaceView = "inside";
    renderPlatform();
    return;
  }
  if (execution !== "live") {
    r.phase = 2;
    r.events =
      execution === "saved"
        ? c().saved_investigation.events
        : c().investigation_events.grounded;
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
      selectedFinding = null;
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
  const received = visibleEvents();
  const events = PublicInvestigation.completedResult(received)
      ? received
      : received.map((e) =>
          e.assessment ? { ...e, assessment: undefined } : e,
        ),
    full = PublicInvestigation.graph(events),
    projection = showAllEvidence
      ? full
      : PublicInvestigation.focusedGraph(
          events,
          selectedEvidenceEvent ?? events.length - 1,
          selectedFinding,
        ),
    nodes = new Map(projection.nodes.map((n) => [n.id, n]));
  const context = $("findingEvidenceContext");
  context.replaceChildren();
  context.hidden = !selectedFinding;
  if (selectedFinding) {
    const index = Number(selectedFinding.split(":")[1]),
      selected = PublicInvestigation.findingEvidence(events, index);
    if (selected.finding)
      context.append(
        el("strong", "Evidence for the selected finding"),
        narrative("p", selected.finding.statement),
        el(
          "p",
          selected.citations.length
            ? `${selected.citations.length} cited evidence item(s) are connected to this finding. Highlighted links show citations, not proof of cause.`
            : "This finding records missing evidence. No received source citation establishes it.",
        ),
      );
  }
  const graph = $("evidenceGraph"),
    active = selectedEvidenceEvent ?? events.length - 1;
  const mobile =
    matchMedia("(max-width: 740px)").matches ||
    (showAllEvidence && graph.parentElement.clientWidth < 1196);
  const columns = mobile ? 1 : showAllEvidence ? 5 : 3,
    available = graph.parentElement.clientWidth || 600,
    nodeWidth =
      showAllEvidence && !mobile
        ? 220
        : Math.floor((available - 24 - (columns - 1) * 18) / columns);
  const heights = Array(columns).fill(24);
  for (const n of nodes.values()) {
    n.technicalLabel = n.technicalLabel || n.label;
    n.label = canonicalPlain(n.label);
    if (n.sensor) n.label = sensorLabel(n.sensor);
    const words = n.label.replaceAll("_", " ").split(/\s+/),
      lines = [""];
    for (const word of words) {
      const i = lines.length - 1;
      if (
        lines[i] &&
        lines[i].length + word.length + 1 >
          Math.max(18, Math.floor((nodeWidth - 20) / 6.5))
      )
        lines.push(word);
      else lines[i] += (lines[i] ? " " : "") + word;
    }
    n.lines = lines;
    n.height = Math.max(78, 34 + lines.length * 16);
    const column = mobile
      ? 0
      : showAllEvidence
        ? ({ finding: 3, gap: 4, fact: 2, history: 2, equipment: 1, entity: 1 }[
            n.kind
          ] ?? 0)
        : ({ finding: 1, gap: 2 }[n.kind] ?? 0);
    n.x = 12 + column * (nodeWidth + 18);
    n.y = heights[column];
    heights[column] += n.height + 24;
  }
  const graphWidth = 24 + columns * nodeWidth + (columns - 1) * 18;
  graph.setAttribute(
    "viewBox",
    `0 0 ${graphWidth} ${Math.max(220, ...heights)}`,
  );
  graph.style.width = `${graphWidth}px`;
  graph.style.height = `${Math.max(220, ...heights)}px`;
  $("graphToggle").textContent = showAllEvidence
    ? "Focus current evidence"
    : `Show all evidence (${full.nodes.length})`;
  $("graphFocusNote").textContent = showAllEvidence
    ? "All evidence received so far. Edges are recorded relationships, never inferred causation."
    : `${nodes.size} of ${full.nodes.length} received entities · focused on the current event or selected finding. Unconnected context is deliberately unconnected.`;
  graph.replaceChildren();
  for (const edge of projection.edges) {
    const a = nodes.get(edge.from),
      b = nodes.get(edge.to);
    if (!a || !b) continue;
    const line = svg("path", {
      d: `M${a.x + nodeWidth} ${a.y + 30} C${a.x + nodeWidth + 16} ${a.y + 30},${b.x - 22} ${b.y + 30},${b.x} ${b.y + 30}`,
      class: `evidence-edge relation-${edge.kind} ${edge.event === active ? "current-relation" : ""} ${selectedFinding && (edge.from === selectedFinding || edge.to === selectedFinding) ? "finding-reference" : ""}`,
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
    n.technicalLabel = n.technicalLabel || n.label;
    n.label = canonicalPlain(n.label);
    if (n.sensor) n.label = sensorLabel(n.sensor);
    const isActive = n.eventKeys.includes(active);
    const g = svg("g", {
      class: `evidence-node type-${n.kind} verdict-${n.data?.verdict || "none"} ${isActive ? "current-node" : ""} ${n.id === selectedFinding ? "selected-finding" : ""}`,
      role: "button",
      tabindex: 0,
      "aria-label":
        n.label + (n.sensor ? `. Technical identifier: ${n.sensor}` : ""),
      "data-node-id": n.id,
      "data-event-keys": n.eventKeys.join(","),
    });
    g.append(
      svg("rect", {
        x: n.x,
        y: n.y,
        width: nodeWidth,
        height: n.height,
        rx: 12,
      }),
      svg(
        "text",
        { x: n.x + 10, y: n.y + 17, class: "node-kind" },
        n.kind === "finding"
          ? (n.data.verdict || "FINDING").replaceAll("_", " ")
          : n.kind.toUpperCase(),
      ),
    );
    n.lines.forEach((line, i) =>
      g.append(svg("text", { x: n.x + 10, y: n.y + 38 + i * 16 }, line)),
    );
    g.append(svg("title", {}, n.sensor || n.technicalLabel || n.label));
    g.onfocus = () => {
      $("graphIdentifier").textContent = n.sensor
        ? `${sensorLabel(n.sensor)} · identifier ${n.sensor}`
        : "Select a node to inspect its source details.";
    };
    g.onclick = () => {
      if (n.kind === "finding") selectedFinding = n.id;
      inspectNode(n);
    };
    g.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        inspectNode(n);
      }
    };
    graph.append(g);
  }
  $("graphNodeList").replaceChildren();
  const expand = el(
    "button",
    showAllEvidence
      ? "Return to focused evidence"
      : `Expand full evidence graph (${full.nodes.length} entities)`,
    "quiet",
  );
  expand.dataset.expandGraph = "true";
  expand.onclick = () => {
    showAllEvidence = !showAllEvidence;
    graphZoom = 1;
    renderEvidenceGraph();
  };
  $("graphNodeList").append(expand);
  const list = el("details");
  list.append(el("summary", "Technical entity index"));
  for (const n of full.nodes) {
    const button = el("button", canonicalPlain(n.label), "quiet");
    button.onclick = () => inspectNode(n);
    list.append(button);
  }
  $("graphNodeList").append(list);
  const toolbar = $("graphControls");
  toolbar.replaceChildren();
  for (const [label, change] of [
    ["Zoom out", -0.25],
    ["Zoom in", 0.25],
    ["Reset view", 0],
  ]) {
    const button = el("button", label, "quiet");
    button.onclick = () => {
      graphZoom = change ? Math.max(0.75, Math.min(2, graphZoom + change)) : 1;
      renderEvidenceGraph();
    };
    toolbar.append(button);
  }
  toolbar.append(
    el(
      "span",
      `${Math.round(graphZoom * 100)}% · scroll or drag the background to explore`,
      "fine-print",
    ),
  );
  graph.style.width = `${graphWidth * graphZoom}px`;
  graph.style.height = `${Math.max(220, ...heights) * graphZoom}px`;
  const viewport = graph.parentElement;
  if (!viewport.dataset.panBound) {
    viewport.dataset.panBound = "true";
    let pan = null;
    viewport.onpointerdown = (e) => {
      if (e.target.closest(".evidence-node")) return;
      pan = {
        x: e.clientX,
        y: e.clientY,
        left: viewport.scrollLeft,
        top: viewport.scrollTop,
      };
      viewport.setPointerCapture(e.pointerId);
    };
    viewport.onpointermove = (e) => {
      if (pan) {
        viewport.scrollLeft = pan.left + pan.x - e.clientX;
        viewport.scrollTop = pan.top + pan.y - e.clientY;
      }
    };
    viewport.onpointerup = () => (pan = null);
    viewport.onpointercancel = () => (pan = null);
  }
  renderPhysicalHypotheses(events);
  const signature = `${c().id}:${execution}:${active}:${nodes.size}`;
  if (graph.dataset.focusSignature !== signature && nodes.size) {
    graph.dataset.focusSignature = signature;
    graph.parentElement.scrollLeft = 0;
    const highlighted = Array.from(nodes.values()).filter((n) =>
      n.eventKeys.includes(active),
    );
    const top = highlighted.length
      ? Math.min(...highlighted.map((n) => n.y))
      : 0;
    requestAnimationFrame(() => {
      graph.parentElement.scrollTop = Math.max(0, top - 20);
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
    "The live Meta Responses client uses muse-spark-1.3 and actual tool calls: lookup_knowledge, search_history, submit_audit; supported active modes add documented request_sensor. Muse decomposes public claims, cites received evidence and identifies gaps. No private reasoning is exported.",
  ],
  [
    "Knowledge / history",
    "Source-backed context",
    "Topic lookups return documented generic graph facts and scope. Historical matches are restricted prepared training incidents and disclose overlap. Neither establishes exact well topology or causal confirmation.",
  ],
  [
    "Python safeguards",
    "Deterministic enforcement",
    "DiagnosticSession enforces the shared five-sensor budget. This auditor inherits three summaries. Supported active modes charge up to two additional unique sensors; cached requests are free and missing queries count. It validates exact numbers/citations, bounds repairs and reserves API spend. A fresh protocol pins source/runtime/prompt/schema hashes.",
  ],
  [
    "Audit / replay",
    "Inspectable, reproducible evidence",
    "The same public event projection renders immutable captured runs and new live tool events. Hash-linked audit entries, actual source IDs, validation failures and completed public assessments remain inspectable. Physical judgments require independent engineering review.",
  ],
];
const techComponentIO = [
  {
    input: "Recorded 3W channels",
    output: "Timestamped viewer replay + restricted summaries",
    api: "Verified replay adapter",
    boundary: "Viewer-only channels are not added to Muse's evidence packet.",
    responsibility:
      "Replay pressure, temperature, flow and equipment-state measurements without inventing samples.",
  },
  {
    input: "Past/current measurements; original diagnostic window",
    output: "Anomaly alert → suspected fault",
    api: "Prefix monitor · statistical feature model",
    boundary:
      "The alert is not fault identification. Diagnosis waits for its complete original evidence window.",
    responsibility:
      "Detect measured deviation, then compute median, variability and change features for the statistical hypothesis.",
  },
  {
    input: "Candidate fault + supplied sensor summaries",
    output: "Scoped findings, citations and missing premises",
    api: "lookup_knowledge · search_history · request_sensor* · submit_audit",
    boundary:
      "Additional summaries are optional in supported active modes. No hidden labels or unqueried viewer telemetry.",
    responsibility:
      "Investigate whether the physical explanation follows from the supplied measurements and documented context.",
  },
  {
    input: "Public topic or already observed sensor evidence",
    output: "Documented facts or training-only analogues",
    api: "lookup_knowledge · search_history",
    boundary:
      "Predefined source-scoped facts, not installed-well multi-hop traversal. Analogues use the initial observed evidence; new queries do not rerank them.",
    responsibility:
      "Return provenance-tagged sensor, equipment and fault descriptions, with actual sensor overlap for historical matches.",
  },
  {
    input: "Sensor requests and proposed public assessments",
    output: "Validated structure or actionable rejection",
    api: "DiagnosticSession · v5 atomic validation",
    boundary:
      "Five unique sensors in total; cache hits are free, missing requests count. Numeric and citation checks do not certify physical interpretation.",
    responsibility:
      "Enforce the shared budget, evidence isolation, citation integrity, bounded repairs and verdict aggregation.",
  },
  {
    input: "Actual public requests, returned evidence and assessment",
    output: "Hash-linked audit + clearly labeled replay",
    api: "Public event projection · saved-run verification",
    boundary:
      "No private reasoning, invented tool activity or silent fallback. Hash integrity is not vendor authenticity or physical certification.",
    responsibility:
      "Preserve the recorded investigation and let an operator inspect what is observed, inferred and still unknown.",
  },
];
function techIcon(kind) {
  const icon = svg("svg", {
    viewBox: "0 0 40 40",
    width: 40,
    height: 40,
    "aria-hidden": "true",
    class: "tech-icon",
  });
  const paths = {
    telemetry: "M3 22h5l4-12 6 23 5-18 5 7h10",
    monitor: "M5 6h30v23H5z M13 35h14 M20 29v6 M9 20h5l4-7 6 11 4-5h4",
    classifier: "M8 31V17h5v14 M18 31V9h5v22 M28 31V21h5v10",
    muse: "M20 3 36 20 20 37 4 20z M12 20h16 M20 12v16",
    assessment: "M10 5h22v30H10z M5 11h10 M5 20h10 M5 29h10 M20 19l4 4 7-9",
    operator: "M20 19a7 7 0 1 0 0-14 7 7 0 0 0 0 14 M7 35v-5c0-10 26-10 26 0v5",
    knowledge:
      "M8 8h8v8H8z M27 5h8v8h-8z M25 27h8v8h-8z M12 16l17 11 M16 12l11-3",
    guard: "M20 3 34 9v11c0 8-14 17-14 17S6 28 6 20V9z M13 19l5 5 10-12",
    audit: "M9 5h22v30H9z M14 12h12 M14 20h12 M14 28h8",
  };
  icon.append(
    svg("path", {
      d: paths[kind] || paths.muse,
      fill: "none",
      stroke: "currentColor",
      "stroke-width": 1.7,
      "stroke-linecap": "round",
      "stroke-linejoin": "round",
    }),
  );
  return icon;
}
function techArrow(label, dashed = false) {
  const edge = el(
    "div",
    undefined,
    "tech-arrow" + (dashed ? " is-dashed" : ""),
  );
  edge.append(
    el("small", label),
    svg("svg", { viewBox: "0 0 90 12", "aria-hidden": "true" }),
  );
  edge.lastChild.append(
    svg("path", {
      d: "M2 6H85 M79 2l6 4-6 4",
      fill: "none",
      stroke: "currentColor",
      "stroke-width": 1.5,
    }),
  );
  return edge;
}
function buildArchitecture() {
  const stages = [
    [
      "telemetry",
      "Well telemetry",
      "27 documented channels",
      "Real recorded measurements",
      0,
    ],
    [
      "monitor",
      "Anomaly detection",
      "Past + current only",
      "An alert, not a fault",
      1,
    ],
    [
      "classifier",
      "Statistical classifier",
      "Original diagnostic window",
      "A suspected failure",
      1,
    ],
    [
      "muse",
      "Meta Muse Spark",
      "Measurements + source context",
      "Investigates the explanation",
      2,
    ],
    [
      "assessment",
      "Evidence assessment",
      "Atomic, scoped findings",
      "Supported / unestablished",
      4,
    ],
    [
      "operator",
      "Operator conclusion",
      "Auditable evidence + gaps",
      "Human decision support",
      5,
    ],
  ];
  const show = (i) => {
    const info = techComponentIO[i];
    for (const b of document.querySelectorAll(
      "#technologyPage [data-component]",
    )) {
      const active = Number(b.dataset.component) === i;
      b.classList.toggle("active", active);
      b.setAttribute("aria-pressed", String(active));
    }
    const activeStages = stages
      .map((s, j) => (s[4] === i ? j : -1))
      .filter((j) => j >= 0);
    document
      .querySelectorAll(".tech-stage")
      .forEach((b, j) =>
        b.classList.toggle(
          "tech-adjacent",
          activeStages.some((k) => Math.abs(k - j) === 1) &&
            !activeStages.includes(j),
        ),
      );
    const panel = $("architectureDetail");
    panel.replaceChildren();
    const heading = el("div", undefined, "tech-inspector-heading");
    heading.append(
      el("span", String(i + 1).padStart(2, "0"), "tech-detail-number"),
      el("h3", architectureData[i][0]),
      el("span", architectureData[i][1], "tech-inspector-tag"),
    );
    panel.append(heading, el("p", info.responsibility));
    const grid = el("div", undefined, "tech-io-grid");
    for (const [title, text] of [
      ["INPUT", info.input],
      ["OUTPUT", info.output],
      ["INTERFACE", info.api],
      ["BOUNDARY", info.boundary],
    ]) {
      const box = el("div");
      box.append(el("small", title), el("p", text));
      grid.append(box);
    }
    panel.append(grid);
    const more = el("details");
    more.append(
      el("summary", "Implementation scope"),
      el("p", architectureData[i][2]),
    );
    panel.append(more);
  };
  $("techPipeline").replaceChildren(
    ...stages.map((s, i) => {
      const b = el(
        "button",
        undefined,
        "tech-stage" + (s[0] === "muse" ? " tech-muse-stage" : ""),
      );
      b.type = "button";
      b.dataset.component = s[4];
      b.setAttribute("aria-controls", "architectureDetail");
      b.append(
        el("span", `0${i + 1}`, "tech-stage-number"),
        techIcon(s[0]),
        el("strong", s[1]),
        el("span", s[2], "tech-stage-input"),
        el("small", s[3]),
      );
      b.onclick = () => show(s[4]);
      return b;
    }),
  );
  $("techResources").replaceChildren(
    ...[
      [3, "knowledge", "Knowledge & history"],
      [4, "guard", "Python safeguards"],
      [5, "audit", "Audit & replay"],
    ].map(([i, icon, label]) => {
      const b = el("button", undefined, "tech-resource");
      b.type = "button";
      b.dataset.component = i;
      b.append(techIcon(icon), el("span", label));
      b.onclick = () => show(i);
      return b;
    }),
  );
  $("architectureNodes").replaceChildren(
    ...architectureData.map((a, i) => {
      const b = el("button", a[0], "architecture-node tech-component");
      b.type = "button";
      b.dataset.component = i;
      b.setAttribute("aria-controls", "architectureDetail");
      b.onclick = () => show(i);
      b.onkeydown = (e) => {
        let next = i;
        if (e.key === "ArrowRight") next = (i + 1) % 6;
        else if (e.key === "ArrowLeft") next = (i + 5) % 6;
        else if (e.key === "Home") next = 0;
        else if (e.key === "End") next = 5;
        else return;
        e.preventDefault();
        show(next);
        $("architectureNodes").children[next].focus();
      };
      return b;
    }),
  );
  show(2);
  buildTechWorkflow();
  buildTechKnowledge();
  buildTechSignals();
  buildTechScores();
}
function buildTechWorkflow() {
  const steps = [
    [
      "Candidate fault",
      "A statistical hypothesis arrives with the already charged summaries.",
      "Classifier output",
      "Hypothesis + supplied measurements",
      "No physical cause has been established.",
    ],
    [
      "Inspect measurements",
      "Read actual values and quality metadata; separate observations from interpretations.",
      "Supplied summaries",
      "Observed changes + quality",
      "A correctly cited number does not prove its physical explanation.",
    ],
    [
      "Retrieve engineering context",
      "Look up public sensor, equipment and fault topics with provenance.",
      "lookup_knowledge",
      "Documented facts + explicit scope",
      "Generic locations and published examples are not verified per-well topology or universal fault rules.",
    ],
    [
      "Compare historical evidence",
      "Compare the initially observed sensors with the prepared training-only snapshot.",
      "search_history",
      "Analogues + shared-sensor overlap",
      "Different overlap counts are not equivalent corroboration. Similarity is not causal proof.",
    ],
    [
      "Request a measurement",
      "In supported active live modes, request a source-motivated additional summary when useful.",
      "request_sensor · optional",
      "One additional sensor summary",
      "Shared five-sensor limit. A new missing reading costs a query; cache hits are free. Not every investigation needs another sensor.",
    ],
    [
      "Evaluate individual claims",
      "Separate supported observations, documented comparisons and causal conclusions.",
      "Muse public assessment",
      "Atomic findings + missing premises",
      "A compatible example does not uniquely identify a fault. No verified fault-discriminating test is supplied here.",
    ],
    [
      "Return an auditable assessment",
      "Submit the findings and their evidence for Python's deterministic checks.",
      "submit_audit",
      "Structured verdict + citations + next evidence",
      "Validation checks structure, numbers and citations; independent physical interpretation remains a human review task.",
    ],
  ];
  const show = (i) => {
    const s = steps[i];
    document.querySelectorAll(".tech-work-step").forEach((b, j) => {
      b.setAttribute("aria-selected", String(i === j));
      b.tabIndex = i === j ? 0 : -1;
    });
    const panel = $("techWorkflowDetail");
    panel.setAttribute("aria-labelledby", `tech-work-${i}`);
    panel.replaceChildren(
      el("span", `CAPABILITY ${i + 1} / 7`, "tech-index"),
      el("h3", s[0]),
      el("p", s[1]),
    );
    const capsule = el("div", undefined, "tech-tool-capsule");
    capsule.append(
      el("small", "ACTUAL INTERFACE / RESPONSIBILITY"),
      el("code", s[2]),
    );
    panel.append(capsule);
    const transfer = el("div", undefined, "tech-transfer");
    transfer.append(
      el("span", "SUPPLIED EVIDENCE"),
      techArrow("inspect / return"),
      el("span", s[3]),
    );
    panel.append(transfer);
    if (i === 4) {
      const budget = el("div", undefined, "tech-budget");
      budget.setAttribute(
        "aria-label",
        "Five unique sensors maximum, including inherited evidence",
      );
      for (let j = 0; j < 5; j++)
        budget.append(
          el("span", String(j + 1), j < 3 ? "inherited" : "remaining"),
        );
      panel.append(
        budget,
        el(
          "small",
          "Current demo: 3 inherited queries; at most 2 new unique queries.",
        ),
      );
    }
    panel.append(el("p", s[4], "tech-work-boundary"));
  };
  $("techWorkflow").setAttribute("role", "tablist");
  $("techWorkflow").setAttribute("aria-orientation", "vertical");
  $("techWorkflow").replaceChildren(
    ...steps.map((s, i) => {
      const li = el("li"),
        b = el("button", undefined, "tech-work-step");
      b.type = "button";
      b.id = `tech-work-${i}`;
      b.setAttribute("role", "tab");
      b.setAttribute("aria-controls", "techWorkflowDetail");
      b.append(
        el("span", String(i + 1).padStart(2, "0")),
        el("strong", s[0]),
        el("small", i === 4 ? "OPTIONAL" : ""),
      );
      b.onclick = () => show(i);
      b.onkeydown = (e) => {
        let next = i;
        if (["ArrowDown", "ArrowRight"].includes(e.key)) next = (i + 1) % 7;
        else if (["ArrowUp", "ArrowLeft"].includes(e.key)) next = (i + 6) % 7;
        else if (e.key === "Home") next = 0;
        else if (e.key === "End") next = 6;
        else return;
        e.preventDefault();
        show(next);
        document.getElementById(`tech-work-${next}`).focus();
      };
      li.append(b);
      return li;
    }),
  );
  $("techWorkflowDetail").setAttribute("role", "tabpanel");
  show(2);
}
function buildTechKnowledge() {
  const definition = cases[0].sensor_definitions;
  const inspect = (title, fact, explanation) => {
    const panel = $("techSourceDetail");
    panel.replaceChildren(
      el("span", "PROVENANCE / SCOPE", "tech-index"),
      el("h3", title),
      el("p", explanation),
    );
    if (fact) {
      panel.append(
        el(
          "code",
          fact.caption_summary ||
            `${fact.subject} → ${fact.relation} → ${fact.object}`,
        ),
        el("p", fact.scope.replaceAll("_", " "), "tech-caption"),
        el("p", fact.locator, "tech-caption"),
      );
      const a = el("a", "Open documented source ↗");
      a.href = fact.provenance.immutable_url || fact.provenance.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      panel.append(a);
    }
  };
  const node = (title, type, handler) => {
    const b = el("button", undefined, "tech-knowledge-node tech-node-" + type);
    b.type = "button";
    b.append(el("small", type.toUpperCase()), el("strong", title));
    b.onclick = () => {
      document
        .querySelectorAll(".tech-knowledge-node")
        .forEach((x) => x.classList.toggle("active", x === b));
      handler();
    };
    return b;
  };
  const locations = () => {
    $("techLocations").setAttribute("aria-pressed", "true");
    $("techClaims").setAttribute("aria-pressed", "false");
    const graph = $("techEvidenceDiagram");
    graph.className = "tech-evidence-diagram tech-location-graph";
    graph.replaceChildren();
    for (const [sensor, title, equipment] of [
      ["P-PDG", "Downhole pressure", "Downhole gauge"],
      ["P-TPT", "Tree pressure", "Subsea tree transducer"],
    ]) {
      const fact = definition[sensor].location_fact;
      const handler = () =>
        inspect(
          sensor,
          fact,
          `Documented ${definition[sensor].quantity_relation.replaceAll("_", " ")} association; pressure is recorded in ${definition[sensor].unit}. This is not an exact installed-well location.`,
        );
      graph.append(
        node(sensor + " · " + title, "sensor", handler),
        techArrow("pressure at"),
        node(equipment, "equipment", handler),
      );
    }
    const doc = node("dataset.ini · version 2.0.0", "source", () =>
      inspect(
        "Generic sensor definitions",
        definition["P-PDG"].location_fact,
        "The same public configuration documents both generic associations. Geometry here illustrates records, not well piping.",
      ),
    );
    doc.classList.add("tech-source-node");
    graph.append(doc);
    $("techGraphScope").textContent =
      "Solid arrows reproduce documented pressure_at associations. The source node supplies their provenance. Diagram positions are illustrative, never installed-well topology.";
    inspect(
      "P-PDG",
      definition["P-PDG"].location_fact,
      "Pressure at a downhole gauge is a documented generic association, not verified placement for this particular well.",
    );
  };
  const claims = () => {
    $("techLocations").setAttribute("aria-pressed", "false");
    $("techClaims").setAttribute("aria-pressed", "true");
    const graph = $("techEvidenceDiagram");
    graph.className = "tech-evidence-diagram tech-claim-graph";
    graph.replaceChildren();
    const illustration = (title, text) => () =>
      inspect(
        title,
        null,
        text +
          " This is an explanatory illustration, not a new tool response or saved model finding.",
      );
    const example = {
      caption_summary: "Figure 5: P-PDG increase · P-TPT increase",
      scope: "published_example_not_fault_rule",
      locator: "Figure 5 caption",
      provenance: { url: "https://arxiv.org/html/2507.01048v1" },
    };
    graph.append(
      node(
        "Two measured pressure increases",
        "observation",
        illustration(
          "Observed directions",
          "The original first captured incident summaries have positive endpoint changes in P-PDG and P-TPT. This does not mean a monotonic rise.",
        ),
      ),
      techArrow("compare", true),
      node("Published fault-8 example", "source", () =>
        inspect(
          "Published comparison",
          example,
          "Figure 5 also includes a downstream pressure decrease. A two-direction comparison does not establish that the whole signature was observed, or that fault 9 caused this incident.",
        ),
      ),
      node(
        "Limited comparison",
        "finding",
        illustration(
          "Comparison scope",
          "A comparison may be supported without proving the example generalizes to this well.",
        ),
      ),
      techArrow("does not prove", true),
      node(
        "Fault 9 as the cause?",
        "hypothesis",
        illustration(
          "Causal scope",
          "The supplied registry has no verified fault-discriminating causal rule that turns this pressure pattern into proof of service-line hydrate.",
        ),
      ),
      node(
        "Missing discriminating premise",
        "gap",
        illustration(
          "Missing premise",
          "Applicable documentation or a validated discriminating test would be needed. No such verified test is supplied here.",
        ),
      ),
    );
    $("techGraphScope").textContent =
      "Explanatory propositions and dotted assessment links, not captured calls or physical propagation paths. Only the published source comparison is documented; no causal edge to fault 9 is asserted.";
    inspect(
      "Comparison is not causation",
      example,
      "A published fault-8 production-line hydrate example shares two pressure directions. That narrow comparison cannot prove or disprove fault-9 service-line hydrate.",
    );
  };
  $("techLocations").onclick = locations;
  $("techClaims").onclick = claims;
  locations();
}
function buildTechSignals() {
  const replay = cases[0].replay,
    candidates = ["P-PDG", "P-TPT", "T-TPT", "QGL", "ABER-CKGL"];
  const available = candidates
    .map((s) => [s, replay.series[s] || replay.viewer_series?.[s]])
    .filter(([, v]) => v)
    .slice(0, 4);
  const drawing = svg("svg", {
    viewBox: `0 0 420 ${available.length * 32 + 15}`,
    role: "img",
    "aria-label":
      "Actual available captured measurements, per-channel normalized dots; no interpolation",
  });
  available.forEach(([s, stream], row) => {
    const values = stream.samples
        .filter((v) => v.quality === "valid")
        .map((v) => v.value),
      lo = Math.min(...values),
      hi = Math.max(...values),
      n = stream.samples.length;
    drawing.append(
      svg("text", { x: 0, y: row * 32 + 22, class: "tech-signal-label" }, s),
    );
    const selected = [
      ...new Set(
        Array.from({ length: Math.min(20, n) }, (_, i) =>
          Math.round((i * (n - 1)) / Math.max(1, Math.min(20, n) - 1)),
        ),
      ),
    ];
    for (const i of selected) {
      const sample = stream.samples[i];
      if (sample.quality !== "valid") continue;
      const x = 85 + (320 * i) / Math.max(1, n - 1),
        y =
          row * 32 +
          26 -
          (hi === lo ? 8 : (16 * (sample.value - lo)) / (hi - lo));
      drawing.append(
        svg("circle", {
          cx: x,
          cy: y,
          r: 2.8,
          class: "tech-signal-dot",
          "data-tech-sensor": s,
          "data-sample-index": i,
          "data-recorded-value": sample.value,
        }),
      );
    }
  });
  $("techSignalPreview").replaceChildren(drawing);
  $("techSignalScope").textContent =
    replay.mode === "endpoints"
      ? "Actual captured endpoints only; timestamps unavailable and endpoints need not be simultaneous across channels. Dots use independent channel scales. No continuous trace is invented."
      : "Viewer-only preview: up to 20 actual recorded samples per channel, on independent min–max scales. Dots only, no interpolation. This does not add agent evidence.";
  const missing = cases[1]?.observations["ABER-CKGL"];
  $("techMissingScope").textContent =
    missing && !missing.available
      ? `Recorded second-case example: ABER-CKGL has ${missing.invalid_count}/${missing.total} unusable readings. No observed valve opening is inferred.`
      : "Unavailable measurements are kept unavailable; this notation is explanatory.";
}
function buildTechScores() {
  const rows = Array.from(document.querySelectorAll("#frozenResults tbody tr"));
  $("techScoreChart").replaceChildren(
    ...rows.map((row, i) => {
      const [name, count, accuracy] = Array.from(row.cells).map((c) =>
          c.textContent.trim(),
        ),
        [correct, total] = count.split("/").map(Number);
      const b = el(
        "button",
        undefined,
        "tech-score-row " + (i < 2 ? "tech-stat-score" : "tech-muse-score"),
      );
      b.type = "button";
      b.dataset.correct = correct;
      b.dataset.total = total;
      b.dataset.accuracy = accuracy;
      b.setAttribute(
        "aria-label",
        `${name}: ${correct} of ${total} correct, ${accuracy} accuracy. Scale 0 to 100 percent.`,
      );
      const label = el("span", undefined, "tech-score-name");
      label.append(
        el("strong", name),
        el("small", `${correct} / ${total} correct`),
      );
      const chart = svg("svg", {
        viewBox: "0 0 100 10",
        "aria-hidden": "true",
        preserveAspectRatio: "none",
      });
      chart.append(
        svg("rect", {
          x: 0,
          y: 1,
          width: 100,
          height: 8,
          rx: 1,
          class: "tech-bar-track",
        }),
        svg("rect", {
          x: 0,
          y: 1,
          width: (100 * correct) / total,
          height: 8,
          rx: 1,
          class: "tech-bar-value",
        }),
      );
      b.append(label, chart, el("strong", accuracy, "tech-score-value"));
      b.onclick = () => {
        document
          .querySelectorAll(".tech-score-row")
          .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        $("techScoreDetail").textContent =
          `${name}: ${correct}/${total} correct (${accuracy}). Frozen classification benchmark; not claim-auditor accuracy.`;
      };
      return b;
    }),
  );
  $("techScoreChart").firstElementChild.click();
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
  $("handoffDetails").open = false;
  $("capabilityDetails").open = false;
  current = Number($("caseSelect").value);
  index = 0;
  workspaceView = "operator";
  condition = "grounded";
  ((focusSensor = null), (showAllEvidence = false), (selectedFinding = null));
  renderPlatform();
};
$("graphToggle").onclick = () => {
  showAllEvidence = !showAllEvidence;
  renderEvidenceGraph();
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
  if (execution === "live" || !checkpointReached()) return;
  stopCapturedClock();
  const r = investigation();
  r.cursor = 1;
  r.playing = true;
  selectedEvidenceEvent = 0;
  selectedFinding = null;
  showAllEvidence = false;
  graphZoom = 1;
  renderPlatform();
};
$("captureSkip").onclick = () => {
  if (execution === "live" || !checkpointReached()) return;
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
    const preferred = cases.findIndex(
      (caseData) => caseData.saved_investigation,
    );
    if (preferred >= 0) {
      current = preferred;
      execution = "saved";
    }
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
