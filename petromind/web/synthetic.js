/* Separately versioned, captured-only M1 viewer. No API client or live execution. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const names = { "P-TPT": "Tree pressure", "P-MON-CKP": "Pressure before the choke",
    "T-TPT": "Tree temperature", "SYN-Q-PROD": "Production flow", "SYN-P-SEP": "Separator pressure" };
  let data, loading, active = false, cursor = 0, timer, started = false, selected = null;
  const node = (tag, text, cls) => {
    const n = document.createElement(tag);
    if (text !== undefined) n.textContent = text;
    if (cls) n.className = cls;
    return n;
  };
  const button = (text, action, cls = "quiet") => {
    const n = node("button", text, cls); n.type = "button"; n.onclick = action; return n;
  };
  function stop() { clearInterval(timer); timer = null; }
  function start() {
    stop(); started = true;
    if (cursor >= data.events.length) cursor = 0;
    cursor = Math.max(1, cursor); render();
    // Editorial pacing: original call timestamps do not exist in the capture.
    timer = setInterval(() => {
      if (!active) return stop();
      cursor = Math.min(data.events.length, cursor + 1);
      const completed = cursor === data.events.length;
      if (completed) stop();
      render();
      if (completed) $("syntheticFinal").scrollIntoView({block: "start", behavior: "auto"});
    }, 1800);
    render();
  }
  async function activate(value) {
    active = value;
    if (!active) return stop();
    if (!loading) loading = fetch("/api/synthetic").then(async (r) => {
      if (!r.ok) throw Error("Verified synthetic recording was not supplied.");
      const result = await r.json();
      if (result.version !== "synthetic-hydraulic-replay-v1" || result.synthetic !== true)
        throw Error("Unrecognized synthetic replay contract.");
      data = result;
    }).catch((e) => { $("syntheticLoadStatus").textContent = e.message; });
    await loading;
    if (data && active) render();
  }
  function measurementLabel(sensor, measurement) {
    const good = measurement.samples.filter((s) => s.quality === "GOOD" && s.value !== null);
    if (!good.length) return `${names[sensor] || sensor}: unavailable`;
    const scale = measurement.unit === "Pa" ? 1e-6 : measurement.unit === "m3/s" ? 1e3 : 1;
    const unit = measurement.unit === "Pa" ? "MPa" : measurement.unit === "m3/s" ? "L/s" : measurement.unit;
    return `${names[sensor] || sensor}: ${(good[0].value * scale).toFixed(3)} → ${(good.at(-1).value * scale).toFixed(3)} ${unit}`;
  }
  function currentMeasurements(events) {
    const measurements = {};
    for (const e of events) {
      if (e.measurements) Object.assign(measurements, e.measurements);
      if (e.measurement) measurements[e.sensor] = e.measurement;
    }
    return measurements;
  }
  function svgElement(name, attrs, text) {
    const n = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attrs).forEach(([k, v]) => n.setAttribute(k, String(v)));
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function schematic() {
    const box = node("div", undefined, "synthetic-system");
    const svg = svgElement("svg", { viewBox: "0 0 820 175", role: "img", "aria-label": "Declared synthetic M1: tree U, section L, node D, choke K, separator S. Same flow through L and K." });
    svg.append(svgElement("title", {}, "Declared synthetic M1 topology, not an installed Petrobras well"));
    svg.append(svgElement("path", { d: "M45 88 H775", stroke: "#6b9ba7", "stroke-width": 8, fill: "none" }));
    [[80, "Tree U", "P-TPT"], [320, "Section L", "Resistance under investigation"], [505, "Before choke D", "P-MON-CKP"], [635, "Choke K", ""], [755, "Separator S", "SYN-P-SEP"]].forEach(([x, label, sub]) => {
      svg.append(svgElement("circle", { cx: x, cy: 88, r: 13, fill: "#a1e6d3", stroke: "#092b35", "stroke-width": 3 }));
      svg.append(svgElement("text", { x, y: 44, "text-anchor": "middle", fill: "#e8f3f5", "font-size": 15 }, label));
      svg.append(svgElement("text", { x, y: 131, "text-anchor": "middle", fill: "#abc3cd", "font-size": 12 }, sub));
    });
    svg.classList.add("synthetic-system-desktop");
    const mobile = svgElement("svg", { viewBox: "0 0 350 290", role: "img", "aria-label": "Synthetic M1: tree, section L, before choke, choke and separator in series" });
    mobile.classList.add("synthetic-system-mobile");
    mobile.append(svgElement("path", {d:"M32 25 V255",stroke:"#6b9ba7","stroke-width":6,fill:"none"}));
    [["Tree pressure", "P-TPT · node U"], ["Section L", "Resistance under investigation"], ["Pressure before the choke", "P-MON-CKP · node D"], ["Production choke", "Choke K"], ["Separator pressure", "SYN-P-SEP · node S"]].forEach(([title,sub],i) => {
      const y=25+i*57;
      mobile.append(svgElement("circle",{cx:32,cy:y,r:9,fill:"#a1e6d3"}));
      mobile.append(svgElement("text",{x:58,y:y-1,fill:"#e8f3f5","font-size":15},title));
      mobile.append(svgElement("text",{x:58,y:y+19,fill:"#abc3cd","font-size":12},sub));
    });
    box.append(svg, mobile, node("p", "Synthetic model geometry · same production flow Q through L and K · not a real well diagram", "fine-print"));
    return box;
  }
  function plot(measurements) {
    const box = node("div", undefined, "synthetic-plot");
    const sensor = measurements["SYN-Q-PROD"] ? "SYN-Q-PROD" : "P-TPT";
    const m = measurements[sensor], good = m.samples.filter((s) => s.quality === "GOOD" && s.value !== null);
    box.append(node("h3", sensor === "SYN-Q-PROD" ? "New evidence: production flow fell" : "Initial evidence: tree pressure rose"));
    const svg = svgElement("svg", { viewBox: "0 0 740 190", role: "img", "aria-label": `${names[sensor]}: received GOOD samples, no interpolation` });
    const min = Math.min(...good.map((s) => s.value)), max = Math.max(...good.map((s) => s.value));
    const span = max - min || 1;
    svg.append(svgElement("path", { d: "M25 15 V155 H715", stroke: "#63808b", fill: "none" }));
    for (const s of good) svg.append(svgElement("circle", { cx: 25 + 690 * s.t_s / 2400, cy: 142 - 112 * (s.value - min) / span, r: 3, fill: sensor === "SYN-Q-PROD" ? "#87c6f4" : "#e5be7d" }));
    svg.append(svgElement("text", { x: 25, y: 180, fill: "#abc3cd", "font-size": 13 }, "0 simulated minutes"));
    svg.append(svgElement("text", { x: 715, y: 180, fill: "#abc3cd", "font-size": 13, "text-anchor": "end" }, "40 minutes"));
    box.append(svg, node("p", measurementLabel(sensor, m), "synthetic-reading"),
      node("small", `81 returned samples · 30-second spacing · original unit ${m.unit} · GOOD points only · no interpolation`));
    return box;
  }
  function graph(events) {
    const nodes = new Map(), edges = [];
    const add = (id, label, kind, details) => { if (!nodes.has(id)) nodes.set(id, { id, label, kind, details }); };
    const link = (from, to, label, kind) => { if (nodes.has(from) && nodes.has(to)) edges.push({ from, to, label, kind }); };
    for (const e of events) {
      for (const [sensor, m] of Object.entries(e.measurements || {})) add(m.id, names[sensor], "measurement", m);
      if (e.measurement) add(e.measurement.id, names[e.sensor], "measurement", e.measurement);
      for (const d of e.documents || []) add(d.id, d.id === "model:M1" ? "Governing model M1" : d.id, "document", d);
      for (const f of e.facts || []) {
        add(f.id, `${f.subject} → ${f.relation} → ${f.object}`, "fact", f);
        add("entity:" + f.subject, f.subject, "entity", { entity: f.subject, returned_in: f.id });
        add("entity:" + f.object, f.object, "entity", { entity: f.object, returned_in: f.id });
        link("entity:" + f.subject, "entity:" + f.object, f.relation, f.status);
      }
      if (e.assessment) e.assessment.findings.forEach((f, i) => {
        add("finding:" + i, f.statement, "finding", f);
        for (const cite of f.citations) link(cite, "finding:" + i, "cited by Muse · not proof of entailment", "citation");
      });
    }
    return { nodes: [...nodes.values()], edges };
  }
  function graphDrawing(g) {
    const groups = [g.nodes.filter((n) => ["measurement", "document"].includes(n.kind)),
      g.nodes.filter((n) => ["fact", "entity"].includes(n.kind)), g.nodes.filter((n) => n.kind === "finding")];
    const height = Math.max(250, Math.max(...groups.map((v) => v.length)) * 94 + 45);
    const svg = svgElement("svg", { viewBox: `0 0 960 ${height}`, role: "img", "aria-label": "Actual received sources, returned relationships and Muse citation links" });
    const locations = new Map();
    groups.forEach((group, col) => group.forEach((n, row) => locations.set(n.id, { x: 12 + col * 320, y: 20 + row * 94 })));
    for (const e of g.edges) {
      const a = locations.get(e.from), b = locations.get(e.to);
      const line = svgElement("path", { d: `M${a.x+145} ${a.y+34} L${b.x+145} ${b.y+34}`, stroke: e.kind === "citation" ? "#8babc9" : "#c4a76f", "stroke-width": 1.5, fill: "none", "stroke-dasharray": e.kind === "citation" ? "5 4" : "2 3" });
      line.append(svgElement("title", {}, `${e.from} → ${e.label} → ${e.to} [${e.kind}]`)); svg.append(line);
    }
    for (const n of g.nodes) {
      const {x,y} = locations.get(n.id), group = svgElement("g", {});
      group.append(svgElement("title", {}, `${n.id}: ${n.label}`));
      group.append(svgElement("rect", { x, y, width: 292, height: 70, rx: 12, fill: n.kind === "finding" ? "#174137" : "#112e3d", stroke: "#638e9f" }));
      const text = `${n.label}`;
      [text.slice(0, 32), text.length > 32 ? text.slice(32, 61) + (text.length > 61 ? "…" : "") : ""].forEach((line, i) => group.append(svgElement("text", { x:x+12, y:y+27+i*22, fill:"#e8f3f5", "font-size":15 }, line)));
      svg.append(group);
    }
    return svg;
  }
  function evidencePanel(g) {
    const section = node("section", undefined, "synthetic-evidence");
    section.append(node("h2", "Supporting engineering context"), node("p", "The evidence graph contains only received relationships and citation links. Select a source, measurement or finding to inspect its original content.", "fine-print"));
    const drawing = node("div", undefined, "synthetic-graph-drawing");
    drawing.append(graphDrawing(g)); section.append(drawing);
    const cards = node("div", undefined, "synthetic-evidence-nodes");
    for (const n of g.nodes) {
      const b = button(n.label, () => { selected = n.id; render(); });
      b.dataset.evidenceId = n.id; b.dataset.kind = n.kind;
      b.classList.toggle("selected", n.id === selected); b.setAttribute("aria-pressed", String(n.id === selected));
      cards.append(b);
    }
    section.append(cards);
    const chosen = g.nodes.find((n) => n.id === selected);
    if (chosen) {
      const inspect = node("div", undefined, "synthetic-source"); inspect.tabIndex = -1; inspect.id = "syntheticSelectedEvidence";
      inspect.append(node("h3", chosen.label), node("p", chosen.id, "fine-print"), node("pre", JSON.stringify(chosen.details, null, 2)));
      section.append(inspect);
    }
    const details = node("details"), list = node("ul");
    details.append(node("summary", `${g.edges.length} returned relationships and citation links`));
    for (const e of g.edges) list.append(node("li", `${e.from} → ${e.label} → ${e.to} [${e.kind}]`));
    details.append(list); section.append(details);
    return section;
  }
  function eventCard(e, i) {
    const li = node("li", undefined, "synthetic-event"); li.dataset.kind = e.kind;
    const sensor = e.sensor || e.arguments?.sensor;
    let title = e.title || "Investigation complete";
    if (e.tool === "query_sensor") title = `${e.kind === "tool_request" ? "Muse requests" : "Muse receives"} ${(names[sensor] || sensor).toLowerCase()}`;
    if (e.tool === "lookup_graph") title = e.kind === "tool_request" ? "Muse looks up supporting engineering context" : "Supporting engineering context returned";
    if (e.tool === "read_document") title = e.kind === "tool_request" ? "Muse requests a source document" : "Source document returned";
    if (e.tool) li.dataset.tool = e.tool;
    li.append(node("small", e.kind === "tool_request" ? "ACTUAL RECORDED REQUEST" : e.kind === "tool_result" ? "ACTUAL RETURNED EVIDENCE" : e.kind === "completion" ? "RECORDED COMPLETION" : "ORIGINAL RECEIVED CONTEXT"), node("h3", title));
    if (sensor) li.title = sensor; // Canonical ID remains available without dominating the story.
    if (e.measurement) li.append(node("p", measurementLabel(e.sensor, e.measurement)));
    if (e.documents) for (const d of e.documents) {
      li.append(node("p", d.summary || d.identifiability));
      if (d.scope_limitations) li.append(node("p", d.scope_limitations, "fine-print"));
    }
    if (e.facts) li.append(node("p", `${e.facts.length} returned graph relationships, retaining their synthetic assumptions and hypothesis status.`));
    if (e.assessment) li.append(node("p", "Accepted overall verdict: " + e.assessment.verdict.replaceAll("_", " ")));
    const full = node("details"); full.append(node("summary", "Inspect exact public event"), node("pre", JSON.stringify(e, null, 2))); li.append(full);
    li.dataset.eventIndex = i;
    return li;
  }
  function finalPanel() {
    const section = node("section", undefined, "synthetic-final"); section.id = "syntheticFinal";
    section.append(node("p", "SCOPED HYDRAULIC INTERPRETATION · SYNTHETIC M1", "eyebrow"),
      node("h2", data.editorial_conclusion),
      node("p", "Evidence interpretation, not an additional or upgraded Muse verdict.", "fine-print"));
    const f = data.assessment.findings[2];
    section.append(node("h3", "What the hydraulic evidence supports"),
      node("p", "Muse requested production flow and separator pressure. Flow decreased, while separator pressure remained approximately stable."),
      node("p", "Under the declared synthetic model M1, the received pressure and flow measurements support an increase in effective resistance in section L."));
    const premise = node("details");
    premise.append(node("summary", "Accepted Muse premise · exact wording"), node("blockquote", f.premises[0]),
      node("p", "R_L means effective resistance in section L. This is a premise in the accepted assessment, not a separate SUPPORTED resistance verdict.", "fine-print"));
    section.append(premise, node("h3", "What Muse did not establish"),
      node("p", "The evidence does not identify hydrate obstruction as the specific cause. Hydrate, scale and debris cannot be distinguished as the obstruction material from the supplied evidence alone."),
      node("p", `Original hydrate-cause finding: ${f.verdict}`, "fine-print"),
      node("h3", "What evidence would help next"),
      node("p", `${f.next_evidence.target}: ${f.next_evidence.purpose}`),
      node("p", "This recorded request names a category of additional evidence, not an available, validated field procedure. No validated material-discriminating test is supplied.", "fine-print"));
    const original = node("details"); original.id = "syntheticScientificAssessment";
    original.append(node("summary", "Exact scientific assessment"),
      node("p", `Original aggregate verdict: ${data.assessment.verdict}`), node("p", data.conclusion_basis, "fine-print"));
    data.assessment.findings.forEach((finding) => {
      const block = node("div", undefined, "synthetic-atomic");
      block.append(node("h3", finding.statement), node("strong", finding.verdict), node("p", finding.justification));
      for (const cite of finding.citations) block.append(button(cite, () => {
        selected = cite; render();
        const target = $("syntheticSelectedEvidence");
        if (target) { target.scrollIntoView({ block: "center" }); target.focus({ preventScroll: true }); }
      }));
      original.append(block);
    });
    const exact = node("pre", JSON.stringify(data.assessment, null, 2)); exact.id = "syntheticOriginalAssessment";
    original.append(exact); section.append(original);
    return section;
  }
  function render() {
    if (!data || !active) return;
    $("syntheticLoadStatus").hidden = true;
    const root = $("syntheticContent"); root.hidden = false;
    const intro = node("div", undefined, "synthetic-intro");
    intro.append(node("p", "CONTROLLED SYNTHETIC PHYSICS · CAPTURED MUSE SPARK", "eyebrow"), node("h2", "A larger pressure gap. More flow—or greater resistance?"),
      node("p", "The pressure difference increased, but pressure alone could not distinguish increased flow from increased resistance. Watch Muse request production flow and separator pressure to investigate the competing explanations."),
      node("p", "Synthetic model M1 relates pressure differences, production flow and effective resistance under declared assumptions.", "fine-print"));
    const content = [intro];
    if (!started) {
      content.push(button("Watch Muse investigate", start, "primary"), node("p", "Previously completed synthetic Muse investigation · five sensors total · no new live run", "fine-print"), schematic());
    } else {
      const controls = node("div", undefined, "synthetic-controls");
      const completed = cursor === data.events.length;
      controls.append(button(completed ? "Replay completed" : timer ? "Pause investigation replay" : "Resume investigation replay", () => { if (timer) { stop(); render(); } else start(); }));
      if (completed) controls.firstChild.disabled = true;
      controls.append(button("Restart synthetic investigation", () => { cursor = 0; selected = null; start(); }), node("span", `Recorded events ${cursor} / ${data.events.length}`, "fine-print"));
      content.push(controls, node("p", "Edited replay pacing; individual event timestamps were not captured. Original investigation: 62.6 seconds. Not live execution.", "fine-print"));
      const events = data.events.slice(0, cursor), measurements = currentMeasurements(events);
      const latest = node("section", undefined, "synthetic-current-activity");
      latest.id = "syntheticCurrentActivity";
      latest.append(node("h2", "Muse investigation · current recorded step"), eventCard(events.at(-1), cursor-1));
      content.push(latest);
      const sensorBox = node("section", undefined, "synthetic-sensors");
      for (const [sensor, m] of Object.entries(measurements)) {
        const b = button(measurementLabel(sensor, m), () => { selected = m.id; render(); });
        b.title = `${sensor} · original unit ${m.unit} · GOOD sample endpoints`; sensorBox.append(b);
      }
      content.push(sensorBox, plot(measurements));
      if (completed) content.splice(1, 0, finalPanel());
      const layout = node("div", undefined, "synthetic-investigation");
      const transcript = node("details"); transcript.append(node("summary", "Inside Muse · full recorded sequence"));
      const list = node("ol", undefined, "synthetic-conversation"); events.forEach((e, i) => list.append(eventCard(e, i))); transcript.append(list);
      layout.append(transcript, evidencePanel(graph(events))); content.push(layout);
      const scope = node("details"); scope.append(node("summary", "Synthetic assumptions, provenance and limitations"), node("p", "This scenario has no recorded monitoring alarm or statistical classifier. The initial competing-explanation question is editorial framing, not a predeclared Muse experiment."), node("p", data.scope), node("p", data.selection), node("pre", JSON.stringify(data.model, null, 2)));
      content.push(scope);
    }
    root.replaceChildren(...content);
  }
  window.PetroMindSynthetic = { activate };
})();
