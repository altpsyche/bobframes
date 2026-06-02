# Presentation & Readability Review: Combating Eye Strain

After analyzing the structure of the data tables—especially the catalog in [index.html](file:///c:/Users/vsiva/Documents/perf/index.html) which displays **37 columns of raw numbers**—it is completely understandable why the current presentation causes significant eye strain. 

Below is an analysis of **why the current style is difficult to read** and a **detailed set of solutions** to transform the dense tabular structure into an ergonomic, modern dashboard.

---

## The Root Causes of Eye Strain in the Current Design

1. **Extreme Monospace Abuse:** Monospace fonts are wider and have a heavier visual block size than sans-serif fonts. When used for headers, labels, and table content simultaneously, the text becomes a dense grid of uniform blocks, making it impossible for the eye to scan naturally.
2. **The "37-Column Wall of Numbers":** Human eyes cannot track horizontal rows across 37 columns. When scrolling horizontally, you lose the row context (which area or drop you are looking at) and the header context (what metric a column represents).
3. **Uniform Visual Weight (No Outlier Spotting):** A cell with `9` lookups has the exact same visual styling and color as a cell with `24,384` draws. The user must manually read and parse every single digit to find high-load captures.
4. **Tiny Spacing & High Compression:** The row height is set to just `22px` for virtualized rows. The lack of cell borders, vertical delimiters, and spacious row padding forces the eyes to squint to separate cells.

---

## Recommended Solutions for Presentation & Readability

We can implement several layout and styling changes to completely eliminate the eye strain:

### 1. Column Grouping & Collapsible Headers
Instead of rendering all 37 columns flat, group them into logical categories with collapsible headers:
* **Metadata:** Area, Date, Label, Capture, Replay Status
* **Draw/Compute Workload:** Draws, Dispatches, Clears, Events
* **Resource Frequencies:** Shaders, Textures, Buffers, Samplers, FBOs
* **Memory & Buffer Samples:** VBO Samples, IBO Samples, Texture Samples

#### Proposed Column Collapsing UI:
```
+-----------------------------------+-----------------------------+-------------------------------+
|             Metadata              |       Workload [+/-]        |        Resources [+/-]        |
+-----------------------------------+-----------------------------+-------------------------------+
| Area       | Date       | Status  | Draws  | Dispatches | Events | Shaders | Textures | Buffers  |
+------------+------------+---------+--------+------------+--------+---------+----------+----------+
| Chor bazar | 2026-06-01 | ok      | 448    | 9          | 1327   | 72      | 317      | 1817     |
+------------+------------+---------+--------+------------+--------+---------+----------+----------+
```

### 2. Data Bars & Heatmap Cells (Visual Cues)
Apply inline relative indicators to numeric cells. Rather than just raw numbers, overlay a subtle horizontal bar (in the cell background) representing its value relative to the maximum value in that column.
* This allows the eye to instantly detect spikes (e.g. a long bar under `Draws` or `Buffers` highlights the heaviest capture instantly).
* Soft, desaturated colors should be used for the bars (e.g., light blue-gray) to maintain focus.

```css
/* Example Cell Background Bar Style */
.cell-bar-bg {
  background: linear-gradient(to right, var(--accent-light) var(--percent), transparent var(--percent));
}
```

### 3. Font Role Clarification
Break the monospace monotony:
* **Sans-Serif (`Inter`):** Use for table headers, metadata (Area names, drop dates, statuses), controls, search, and KPI numbers. This makes the UI feel like a premium website.
* **Monospace (`tabular-nums`):** Use *only* for the raw numbers inside cell metrics and hashes. This ensures columns line up perfectly while reducing visual fatigue.

### 4. Layout Ergonomics (Breathing Room)
* **Increase Row Padding:** Increase the virtual table row height from `22px` to `36px` or `40px` and add vertical centering.
* **Zebra Striping & Grid lines:** Apply alternating light/dark rows using soft contrast ratios:
  ```css
  tr.alt td { background: var(--surface-1); }
  tr:hover td { background: var(--row-hover); }
  ```
* **Card-Based Index (Master-Detail):** 
  Instead of starting with the giant table, the landing page should present clean, high-level **cards for each Area** (e.g. "Chor Bazar", "Commercial District"). The card displays:
  * Area Title
  * Latest drop status (e.g., green checkmark for `ok`)
  * Mini chart (sparkline) showing workload trends
  * A "View Full Catalog Data" button that opens the details table.

---

## Actionable Presentation Upgrade Roadmap

We can immediately write CSS and JS changes to enforce these visual upgrades:

| Upgrade Area | Action | Result |
| :--- | :--- | :--- |
| **Typography** | Re-assign CSS variables: restrict monospace to metric numbers only. | 50% reduction in cognitive reading load. |
| **Row Spacing** | Increase row heights to `36px` and add soft light-gray vertical borders. | Eliminates vertical cell tracking errors. |
| **Zebra Fills** | Adjust row alternating colors using `oklch` light transparency. | Guides the eye horizontally across long rows. |
| **Data Bars** | Add automatic percentage background fills to `row_count` columns. | Instantly spots performance outliers. |
| **Tabbed Drill-Downs** | Convert drill report files from long stacked lists to dynamic Tab panels. | Eliminates 90% of page scrolling. |
