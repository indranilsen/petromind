# Three scenes, two clicks

Actual Chromium screenshots at **1440×900** and **390×844**. All images are
viewport captures, not stitched scrolling pages. Lossless WebP conversion retains
the screenshot pixels. They show the genuine captured audits and actual endpoint
summaries; the raw dataset was unavailable here. No synthetic raw data appears.

| Story | Desktop | Mobile |
|---|---|---|
| Two sensors, one observed change | [Scene 1](well-desktop.webp) | [Scene 1](well-mobile.webp) |
| The plausible diagnosis | [Scene 2](diagnosis-desktop.webp) | [Scene 2](diagnosis-mobile.webp) |
| Muse finds the unsupported causal premise | [Scene 3](verdict-desktop.webp) | [Scene 3](verdict-mobile.webp) |
| Second case: example match, not root-cause proof | [Verdict](comparison-desktop.webp) | [Verdict](comparison-mobile.webp) |

![The two-sensor opening](well-desktop.webp)

![The central verdict](verdict-desktop.webp)

![Mobile verdict](verdict-mobile.webp)

Visual review: the three-scene layout is retained. Pressure values, signed changes,
and warm/cool marker states now make scrubbing visible. Two pressures remain
primary; choke opening is a smaller measured indicator, while two temperature
indicators honestly say “Not observed in audit.” No chart appears by default.
The diagnosis explains the measurements, proposed restriction and conditional
plausibility. Muse's three checks precede the verdict, followed by an exact
captured excerpt and a plain-language missing premise. Full outputs remain in
**Explore evidence**.

Compare actual endpoints: [start — desktop](replay-start-desktop.webp) →
[end — desktop](well-desktop.webp), or [start — mobile](replay-start-mobile.webp) →
[end — mobile](well-mobile.webp). Gray starts become orange higher readings in
this case; the second case also includes a blue lower reading. Colors do not
encode danger. These are real captured endpoint values, not intermediate samples.

See the [exact change inventory and boundaries](../ux-refinement.md).

Both cases were visually reviewed on desktop/mobile. Browser assertions separately
check that all three desktop scenes fit without scrolling, the main actions remain
in view on mobile, no horizontal scrolling occurs, and closing evidence restores
keyboard focus. This is not a measured 30-second user comprehension study.

The illustration is explanatory, not verified individual-well geometry. Sensor
colors/arrows indicate change from the first valid value, not danger. No raw
dataset, evaluator labels, private protocol or credentials are included.
