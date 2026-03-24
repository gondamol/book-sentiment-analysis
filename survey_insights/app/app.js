const THEME_LABELS = {
  staff_attitude: "Staff attitude and respect",
  wait_time: "Waiting time and flow",
  medicines_supplies: "Medicines and supplies",
  food_transport_support: "Food and transport support",
  equipment_space: "Equipment and infrastructure",
  confidentiality_stigma: "Confidentiality and stigma",
  access_cost: "Access and affordability",
  counseling_mental_health: "Counseling and mental wellbeing",
};

const filterIds = {
  search: "searchInput",
  survey_name: "surveyFilter",
  county: "countyFilter",
  gender: "genderFilter",
  age_group: "ageFilter",
  theme: "themeFilter",
  sentiment_label: "sentimentFilter",
  satisfaction: "satisfactionFilter",
};

const state = {
  analysis: null,
  records: [],
  filtered: [],
};

const plotLayout = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  margin: { l: 48, r: 18, t: 12, b: 42 },
  font: { family: "Manrope, sans-serif", color: "#122a42" },
};

function formatNumber(value) {
  return new Intl.NumberFormat().format(value);
}

function formatPercent(value) {
  return `${value.toFixed(1)}%`;
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function shareOf(records, predicate) {
  if (!records.length) return 0;
  return (records.filter(predicate).length / records.length) * 100;
}

function countBy(records, getter) {
  return records.reduce((acc, record) => {
    const key = getter(record) || "Unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function sortEntries(counts) {
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}

function themeCounts(records) {
  const counts = {};
  records.forEach((record) => {
    (record.themes || []).forEach((theme) => {
      counts[theme] = (counts[theme] || 0) + 1;
    });
  });
  return counts;
}

function tokenize(text) {
  const stop = new Set([
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "have",
    "has",
    "had",
    "their",
    "they",
    "them",
    "your",
    "from",
    "there",
    "would",
    "should",
    "were",
    "been",
    "into",
    "about",
    "while",
    "what",
    "which",
    "when",
    "where",
    "because",
    "facility",
    "facilities",
    "service",
    "services",
    "care",
    "treatment",
    "client",
    "clients",
    "received",
    "like",
    "none",
    "nothing",
    "comment",
    "comments",
  ]);
  const matches = (text || "").toLowerCase().match(/[a-z][a-z'-]+/g) || [];
  return matches.filter((word) => word.length > 2 && !stop.has(word));
}

function topTerms(records, extractor, limit = 14) {
  const counts = {};
  records.forEach((record) => {
    tokenize(extractor(record)).forEach((word) => {
      counts[word] = (counts[word] || 0) + 1;
    });
  });
  return sortEntries(counts)
    .slice(0, limit)
    .map(([term, count]) => ({ term, count }));
}

function filterRecords() {
  const filters = Object.fromEntries(
    Object.entries(filterIds).map(([key, id]) => [key, document.getElementById(id).value.trim().toLowerCase()]),
  );

  state.filtered = state.records.filter((record) => {
    const haystack = [record.snippet, record.facility_name, record.organization, record.county].join(" ").toLowerCase();

    if (filters.search && !haystack.includes(filters.search)) return false;
    if (filters.survey_name && record.survey_name.toLowerCase() !== filters.survey_name) return false;
    if (filters.county && record.county.toLowerCase() !== filters.county) return false;
    if (filters.gender && record.gender.toLowerCase() !== filters.gender) return false;
    if (filters.age_group && record.age_group.toLowerCase() !== filters.age_group) return false;
    if (filters.sentiment_label && record.sentiment_label.toLowerCase() !== filters.sentiment_label) return false;
    if (filters.satisfaction && record.satisfaction.toLowerCase() !== filters.satisfaction) return false;
    if (filters.theme && !(record.themes || []).includes(filters.theme)) return false;
    return true;
  });

  render();
}

function populateSelect(id, values, emptyLabel) {
  const select = document.getElementById(id);
  select.innerHTML = "";
  const base = document.createElement("option");
  base.value = "";
  base.textContent = emptyLabel;
  select.appendChild(base);

  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function populateFilters() {
  populateSelect("surveyFilter", [...new Set(state.records.map((record) => record.survey_name))].sort(), "All survey modules");
  populateSelect("countyFilter", [...new Set(state.records.map((record) => record.county))].sort(), "All counties");
  populateSelect("genderFilter", [...new Set(state.records.map((record) => record.gender))].sort(), "All genders");
  populateSelect("ageFilter", [...new Set(state.records.map((record) => record.age_group))].sort(), "All age groups");
  populateSelect("satisfactionFilter", [...new Set(state.records.map((record) => record.satisfaction))].sort(), "All satisfaction levels");

  const themeSelect = document.getElementById("themeFilter");
  themeSelect.innerHTML = '<option value="">All themes</option>';
  Object.entries(THEME_LABELS).forEach(([id, label]) => {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = label;
    themeSelect.appendChild(option);
  });
}

function renderKpis(records) {
  const metrics = [
    {
      label: "Responses",
      value: formatNumber(records.length),
      note: "Records in the current filtered view.",
    },
    {
      label: "Positive Satisfaction",
      value: formatPercent(shareOf(records, (record) => ["Satisfied", "Very satisfied"].includes(record.satisfaction))),
      note: "Share of responses marked satisfied or very satisfied.",
    },
    {
      label: "Access Challenges",
      value: formatPercent(shareOf(records, (record) => record.access_challenge === "Yes")),
      note: "Share reporting service-access barriers.",
    },
    {
      label: "Confidentiality",
      value: formatPercent(shareOf(records, (record) => record.confidentiality === "Yes")),
      note: "Share reporting confidentiality was respected.",
    },
    {
      label: "Average Sentiment",
      value: average(records.map((record) => record.sentiment_score)).toFixed(3),
      note: "Compound VADER score on available open comments.",
    },
  ];

  const grid = document.getElementById("kpiGrid");
  grid.innerHTML = "";
  const template = document.getElementById("kpiCardTemplate");

  metrics.forEach((metric) => {
    const node = template.content.cloneNode(true);
    node.querySelector(".kpi-label").textContent = metric.label;
    node.querySelector(".kpi-value").textContent = metric.value;
    node.querySelector(".kpi-note").textContent = metric.note;
    grid.appendChild(node);
  });
}

function renderInsights(records) {
  const resultCount = document.getElementById("resultCount");
  resultCount.textContent = `${formatNumber(records.length)} matching responses`;

  const themeEntry = sortEntries(themeCounts(records))[0];
  const countyEntry = sortEntries(countBy(records, (record) => record.county))[0];
  const surveyEntry = sortEntries(countBy(records, (record) => record.survey_name))[0];
  const positiveShare = shareOf(records, (record) => ["Satisfied", "Very satisfied"].includes(record.satisfaction));
  const accessShare = shareOf(records, (record) => record.access_challenge === "Yes");

  const bullets = [
    `${surveyEntry ? surveyEntry[0] : "No survey module"} accounts for the largest share of the current filtered view.`,
    `${countyEntry ? countyEntry[0] : "No county"} contributes the highest volume of filtered responses.`,
    `${themeEntry ? THEME_LABELS[themeEntry[0]] : "No dominant theme"} appears most often in the open comments.`,
    `${formatPercent(positiveShare)} of filtered responses are satisfied or very satisfied, while ${formatPercent(accessShare)} report access challenges that may require follow-up.`,
  ];

  const container = document.getElementById("insightBullets");
  container.innerHTML = "";
  bullets.forEach((text) => {
    const p = document.createElement("p");
    p.textContent = text;
    container.appendChild(p);
  });
}

function renderTrend(records) {
  const grouped = {};
  records.forEach((record) => {
    if (!record.response_month || record.response_month === "Unknown") return;
    if (!grouped[record.response_month]) grouped[record.response_month] = [];
    grouped[record.response_month].push(record);
  });

  const months = Object.keys(grouped).sort();
  if (!months.length) {
    Plotly.newPlot(
      "trendChart",
      [],
      {
        ...plotLayout,
        annotations: [{ text: "No records match the current filters.", showarrow: false }],
      },
      { displayModeBar: false, responsive: true },
    );
    return;
  }
  const sentiment = months.map((month) => average(grouped[month].map((record) => record.sentiment_score)));
  const satisfaction = months.map((month) =>
    shareOf(grouped[month], (record) => ["Satisfied", "Very satisfied"].includes(record.satisfaction)),
  );

  Plotly.newPlot(
    "trendChart",
    [
      {
        type: "scatter",
        mode: "lines+markers",
        x: months,
        y: sentiment,
        name: "Average sentiment",
        line: { color: "#0f8b8d", width: 3 },
        marker: { size: 7 },
        yaxis: "y1",
      },
      {
        type: "scatter",
        mode: "lines+markers",
        x: months,
        y: satisfaction,
        name: "Positive satisfaction share",
        line: { color: "#c75146", width: 3, dash: "dot" },
        marker: { size: 7 },
        yaxis: "y2",
      },
    ],
    {
      ...plotLayout,
      yaxis: { title: "Sentiment", zeroline: true, gridcolor: "rgba(18,42,66,0.08)" },
      yaxis2: {
        title: "Satisfaction %",
        overlaying: "y",
        side: "right",
        rangemode: "tozero",
      },
      legend: { orientation: "h", y: 1.15 },
    },
    { displayModeBar: false, responsive: true },
  );
}

function renderBarChart(elementId, entries, color, horizontal = false) {
  const top = entries.slice(0, 8);
  if (!top.length) {
    Plotly.newPlot(
      elementId,
      [],
      {
        ...plotLayout,
        annotations: [{ text: "No records match the current filters.", showarrow: false }],
      },
      { displayModeBar: false, responsive: true },
    );
    return;
  }
  const labels = top.map(([label]) => label);
  const values = top.map(([, value]) => value);
  Plotly.newPlot(
    elementId,
    [
      {
        type: "bar",
        orientation: horizontal ? "h" : "v",
        x: horizontal ? values : labels,
        y: horizontal ? labels : values,
        marker: { color, borderRadius: 8 },
      },
    ],
    {
      ...plotLayout,
      margin: horizontal ? { l: 100, r: 18, t: 12, b: 42 } : plotLayout.margin,
      xaxis: { gridcolor: "rgba(18,42,66,0.08)" },
      yaxis: { automargin: true },
    },
    { displayModeBar: false, responsive: true },
  );
}

function renderTermCloud(targetId, items) {
  const container = document.getElementById(targetId);
  container.innerHTML = "";
  if (!items.length) {
    const empty = document.createElement("span");
    empty.textContent = "No terms available for this view.";
    container.appendChild(empty);
    return;
  }
  items.forEach(({ term, count }) => {
    const pill = document.createElement("span");
    pill.className = "term-pill";
    pill.innerHTML = `${term} <strong>${count}</strong>`;
    container.appendChild(pill);
  });
}

function renderQuotes(records) {
  const container = document.getElementById("quoteList");
  container.innerHTML = "";
  const template = document.getElementById("quoteCardTemplate");
  const candidates = [...records]
    .filter((record) => record.snippet && record.snippet.toLowerCase() !== "unknown")
    .sort((a, b) => Math.abs(b.sentiment_score) - Math.abs(a.sentiment_score))
    .slice(0, 12);

  if (!candidates.length) {
    const empty = document.createElement("p");
    empty.textContent = "No comments match the current filters.";
    container.appendChild(empty);
    return;
  }

  candidates.forEach((record) => {
    const node = template.content.cloneNode(true);
    const chips = node.querySelectorAll(".quote-chip");
    chips[0].textContent = record.county;
    chips[1].textContent = record.survey_name;
    node.querySelector(".quote-text").textContent = record.snippet;
    const themeText = (record.themes || []).map((theme) => THEME_LABELS[theme] || theme).slice(0, 2).join(" • ") || "No theme tag";
    node.querySelector(".quote-footer").textContent = `${record.sentiment_label} sentiment • ${record.facility_name || "Unknown facility"} • ${themeText}`;
    container.appendChild(node);
  });
}

function render() {
  const records = state.filtered;
  renderKpis(records);
  renderInsights(records);
  renderTrend(records);
  renderBarChart("surveyChart", sortEntries(countBy(records, (record) => record.survey_name)), "#c75146");
  renderBarChart(
    "themeChart",
    sortEntries(themeCounts(records)).map(([themeId, count]) => [THEME_LABELS[themeId] || themeId, count]),
    "#0f8b8d",
    true,
  );
  renderBarChart("countyChart", sortEntries(countBy(records, (record) => record.county)), "#122a42", true);
  renderTermCloud("positiveTerms", topTerms(records.filter((record) => record.sentiment_score >= 0.2), (record) => record.snippet));
  renderTermCloud(
    "improvementTerms",
    topTerms(
      records.filter((record) => record.sentiment_score <= -0.2 || record.access_challenge === "Yes"),
      (record) => record.snippet,
    ),
  );
  renderQuotes(records);
}

async function bootstrap() {
  const [analysis, records] = await Promise.all([
    fetch("./assets/analysis.json").then((response) => response.json()),
    fetch("./assets/records.json").then((response) => response.json()),
  ]);

  state.analysis = analysis;
  state.records = records;
  state.filtered = [...records];

  document.getElementById("heroResponses").textContent = `${formatNumber(analysis.response_count)} responses`;

  populateFilters();
  Object.values(filterIds).forEach((id) => {
    document.getElementById(id).addEventListener("input", filterRecords);
    document.getElementById(id).addEventListener("change", filterRecords);
  });

  document.getElementById("resetFilters").addEventListener("click", () => {
    Object.values(filterIds).forEach((id) => {
      document.getElementById(id).value = "";
    });
    state.filtered = [...state.records];
    render();
  });

  render();
}

bootstrap().catch((error) => {
  console.error(error);
  document.body.innerHTML =
    '<main style="padding:40px;font-family:Manrope,sans-serif"><h1>Unable to load the survey dashboard.</h1><p>Please ensure the processed JSON assets are available in <code>app/assets</code>.</p></main>';
});
