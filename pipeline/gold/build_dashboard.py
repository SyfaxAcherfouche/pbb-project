"""
Génère dashboard/dashboard.html : reconstruction fidèle d'une maquette de
référence (générée via Lovable/Tailwind), en extrayant les vraies classes
utilitaires du fichier source (padding, marges, tailles de police, rayons,
ombres) plutôt que de les approximer -- valeurs traduites de rem/Tailwind
en pixels exacts.

Autonome : Chart.js vendorisé localement, seule dépendance réseau les
polices Google Fonts (dégradation propre vers police système hors-ligne).

Usage :
    python pipeline/gold/build_dashboard.py
"""

import json
import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "pbb.duckdb"
OUTPUT = ROOT / "dashboard" / "dashboard.html"
CHARTJS_VENDOR = Path(__file__).resolve().parent / "vendor" / "chart.umd.js"


def get_data() -> list[dict]:
    if not WAREHOUSE.exists():
        raise FileNotFoundError(f"{WAREHOUSE} introuvable. Lance d'abord le pipeline complet.")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    df = con.execute("SELECT * FROM gold.fact_match ORDER BY date").fetchdf()
    con.close()

    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    for col in ["billets_vendus", "entrees_ok"]:
        df[col] = df[col].astype("Int64")
    return json.loads(df.to_json(orient="records"))


def get_digital_data() -> dict:
    """
    Requêtes live sur silver.web_sessions et bronze.raw_campagnes_evenements
    pour le funnel e-commerce et la performance des campagnes -- données
    réellement calculées, pas des chiffres codés en dur dans le HTML.
    """
    if not WAREHOUSE.exists():
        raise FileNotFoundError(f"{WAREHOUSE} introuvable. Lance d'abord le pipeline complet.")
    con = duckdb.connect(str(WAREHOUSE), read_only=True)

    conversion = con.execute("""
        SELECT source, medium, COUNT(*) AS sessions,
               ROUND(COUNT(*) FILTER (WHERE revenue > 0) * 100.0 / COUNT(*), 2) AS taux_conversion_pct
        FROM silver.web_sessions
        GROUP BY source, medium
        HAVING COUNT(*) > 1000
        ORDER BY taux_conversion_pct DESC
    """).fetchdf()

    campagnes = con.execute("""
        SELECT canal,
               COUNT(*) FILTER (WHERE evenement = 'DELIVRE') AS delivres,
               ROUND(COUNT(*) FILTER (WHERE evenement = 'OUVERTURE') * 100.0
                     / NULLIF(COUNT(*) FILTER (WHERE evenement = 'DELIVRE'), 0), 1) AS taux_ouverture_pct,
               ROUND(COUNT(*) FILTER (WHERE evenement = 'CLIC') * 100.0
                     / NULLIF(COUNT(*) FILTER (WHERE evenement = 'OUVERTURE'), 0), 1) AS taux_clic_pct
        FROM bronze.raw_campagnes_evenements
        GROUP BY canal
    """).fetchdf()

    con.close()
    return {
        "conversion": json.loads(conversion.to_json(orient="records")),
        "campagnes": json.loads(campagnes.to_json(orient="records")),
    }


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Paris Basketball — Remplissage des matchs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap">
<script>__CHARTJS_INLINE__</script>
<style>
  :root {
    --background: #14161b;
    --surface: #1d1f26;
    --surface-2: #24262e;
    --sidebar: #191b21;
    --muted: #24262e;
    --border: #33353f;
    --foreground: #f4f4f5;
    --muted-foreground: #a7a8b0;
    --primary: #e3392f;
    --accent: #3552c4;
    --comp-playoffs: #e3392f;
    --comp-euroleague: #4c6fe0;
    --comp-championnat: #c7c8ce;
    --positive: #6fcb8e;
    --radius: 14px;
    --radius-xl: 18px;
    --font-display: "Space Grotesk", ui-sans-serif, system-ui, sans-serif;
    --font-sans: "DM Sans", ui-sans-serif, system-ui, sans-serif;
    --font-mono: "JetBrains Mono", ui-monospace, monospace;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: var(--font-sans);
    background: var(--background);
    color: var(--foreground);
    -webkit-font-smoothing: antialiased;
  }
  h1, h2, h3 { font-family: var(--font-display); letter-spacing: -0.02em; margin: 0; }

  .panel {
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    box-shadow: 0 1px 0 0 rgba(255,255,255,0.06) inset, 0 20px 40px -28px rgba(0,0,0,0.8);
  }

  header.court-glow {
    border-bottom: 1px solid var(--border);
    background-image:
      radial-gradient(120% 80% at 12% 0%, rgba(227,57,47,0.22) 0%, transparent 60%),
      radial-gradient(90% 70% at 95% 10%, rgba(53,82,196,0.22) 0%, transparent 65%);
  }
  .header-inner { max-width: 1240px; margin: 0 auto; padding: 48px 24px; }
  @media (min-width: 768px) { .header-inner { padding: 64px 40px; } }

  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    border: 1px solid var(--border);
    background: rgba(36,38,46,0.6);
    border-radius: 999px;
    padding: 4px 12px;
    font-size: 11px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: var(--muted-foreground);
  }
  .eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--primary); }

  header h1 {
    margin-top: 20px;
    max-width: 768px;
    font-size: 36px;
    font-weight: 700;
    line-height: 1.05;
  }
  @media (min-width: 768px) { header h1 { font-size: 60px; } }
  header h1 span { display: block; color: var(--primary); }

  header .subtitle {
    margin-top: 16px;
    max-width: 576px;
    font-size: 14px;
    color: var(--muted-foreground);
  }
  header .subtitle .mono { font-family: var(--font-mono); color: rgba(244,244,245,0.8); }

  main { max-width: 1240px; margin: 0 auto; padding: 0 24px 96px; }
  @media (min-width: 768px) { main { padding: 0 40px 96px; } }

  .kpis {
    margin-top: -32px;
    display: grid;
    gap: 12px;
    grid-template-columns: repeat(2, 1fr);
    position: relative;
  }
  @media (min-width: 1024px) { .kpis { grid-template-columns: repeat(5, 1fr); } }

  .kpi { padding: 20px; }
  .kpi .kpi-top { display: flex; align-items: flex-start; justify-content: space-between; }
  .kpi .stat-num {
    font-family: var(--font-display);
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.03em;
    font-size: 30px;
    font-weight: 700;
    margin: 0;
  }
  .kpi .label {
    margin-top: 8px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--muted-foreground);
  }
  .kpi .icon { width: 16px; height: 16px; }

  .chart-grid { margin-top: 24px; display: grid; gap: 24px; }
  @media (min-width: 1024px) { .chart-grid { grid-template-columns: repeat(2, 1fr); } }

  .card { padding: 24px; }
  .card h2 { font-size: 16px; font-weight: 600; }
  .card .subtitle { margin-top: 4px; font-size: 12px; color: var(--muted-foreground); }
  .card .chart-wrap { margin-top: 20px; }

  .chart-legend {
    margin-top: 16px;
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    font-size: 12px;
    color: var(--muted-foreground);
  }
  .chart-legend span { display: inline-flex; align-items: center; gap: 8px; }
  .chart-legend .dot { width: 10px; height: 10px; border-radius: 50%; }
  .chart-note { margin-top: 16px; font-size: 12px; color: var(--muted-foreground); }

  .table-section { margin-top: 24px; padding: 24px; }
  table { width: 100%; min-width: 720px; border-collapse: collapse; font-size: 14px; }
  thead tr { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted-foreground); }
  th { padding-bottom: 12px; font-weight: 500; }
  td { padding-top: 12px; padding-bottom: 12px; }
  tbody tr { border-top: 1px solid rgba(51,53,63,0.7); }
  td.mono-xs { font-family: var(--font-mono); font-size: 12px; color: var(--muted-foreground); }
  td.muted { color: var(--muted-foreground); }
  td.medium { font-weight: 500; }

  .badge {
    display: inline-block;
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
    background: var(--muted);
    color: var(--muted-foreground);
  }
  .badge.euroleague { background: rgba(76,111,224,0.15); color: var(--comp-euroleague); }
  .badge.playoffs { background: rgba(227,57,47,0.15); color: var(--comp-playoffs); }

  .fill-cell { display: flex; align-items: center; gap: 12px; }
  .fill-track { width: 80px; height: 6px; border-radius: 999px; background: var(--muted); overflow: hidden; flex-shrink: 0; }
  .fill-bar { height: 100%; border-radius: 999px; background: var(--primary); }
  .fill-value { font-family: var(--font-display); font-variant-numeric: tabular-nums; font-size: 14px; font-weight: 600; }

  .day-cell { display: inline-flex; align-items: center; gap: 6px; color: var(--muted-foreground); }
  .day-cell .icon { width: 14px; height: 14px; }

  .insights-section { margin-top: 24px; }
  .insights-section h2 { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; }
  .insights-section h2 .icon { width: 16px; height: 16px; color: var(--primary); }
  .insight-grid { margin-top: 16px; display: grid; gap: 16px; grid-template-columns: 1fr; }
  @media (min-width: 768px) { .insight-grid { grid-template-columns: repeat(2, 1fr); } }
  @media (min-width: 1280px) { .insight-grid { grid-template-columns: repeat(3, 1fr); } }
  .insight-card { padding: 20px; }
  .insight-card h3 { font-size: 14px; font-weight: 600; }
  .insight-card p { margin-top: 8px; font-size: 14px; line-height: 1.625; color: var(--muted-foreground); }

  footer {
    margin-top: 48px;
    border-top: 1px solid var(--border);
    padding-top: 24px;
    font-size: 12px;
    color: var(--muted-foreground);
  }
  footer .mono { font-family: var(--font-mono); }
</style>
</head>
<body>

<header class="court-glow">
  <div class="header-inner">
    <span class="eyebrow"><span class="dot"></span>Saison 2025-2026</span>
    <h1>Paris Basketball<span>Remplissage des matchs</span></h1>
    <p class="subtitle">41 matchs à domicile · source&nbsp;<span class="mono">gold.fact_match</span></p>
  </div>
</header>

<main>
  <div class="kpis" id="kpis"></div>

  <div class="chart-grid">
    <section class="panel card">
      <h2>Taux de remplissage par match</h2>
      <div class="subtitle">Ordre chronologique · couleur = compétition</div>
      <div class="chart-wrap"><canvas id="chartRemplissage" height="260"></canvas></div>
      <div class="chart-legend" id="legendRemplissage"></div>
    </section>
    <section class="panel card">
      <h2>Remplissage vs classement de l'adversaire</h2>
      <div class="subtitle">Rang 1 = meilleur adversaire</div>
      <div class="chart-wrap"><canvas id="chartClassement" height="260"></canvas></div>
      <p class="chart-note">Pente nette : plus l'adversaire est bien classé, plus la salle se remplit.</p>
    </section>
  </div>

  <div class="chart-grid">
    <section class="panel card">
      <h2>Remplissage moyen par compétition</h2>
      <div class="chart-wrap"><canvas id="chartCompetition" height="220"></canvas></div>
    </section>
    <section class="panel card">
      <h2>Remplissage moyen par jour de semaine</h2>
      <div class="chart-wrap"><canvas id="chartJour" height="220"></canvas></div>
    </section>
  </div>

  <section class="panel table-section">
    <h2>Les 8 matchs les plus faibles</h2>
    <div class="subtitle" style="margin-top:4px;font-size:12px;">Candidats prioritaires pour une action tarifaire ou marketing</div>
    <div style="margin-top:20px;overflow-x:auto;">
      <table id="tableFaibles">
        <thead>
          <tr>
            <th>Match</th><th>Date</th><th>Adversaire</th><th>Compétition</th>
            <th>Remplissage</th><th>Rang adv.</th><th>Jour</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <section class="insights-section">
    <h2>
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h20"/><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"/><path d="m7 21 5-5 5 5"/></svg>
      Performance digitale — boutique en ligne et campagnes
    </h2>
    <div class="chart-grid" style="margin-top:16px;">
      <section class="panel card">
        <h2>Taux de conversion par canal d'acquisition</h2>
        <div class="chart-wrap"><canvas id="chartConversion" height="220"></canvas></div>
      </section>
      <section class="panel card">
        <h2>Performance des campagnes par canal</h2>
        <div id="campagnesStats" style="margin-top:20px;"></div>
      </section>
    </div>
  </section>

  <section class="insights-section">
    <h2>
      <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11.017 2.814a1 1 0 0 1 1.966 0l1.051 5.558a2 2 0 0 0 1.594 1.594l5.558 1.051a1 1 0 0 1 0 1.966l-5.558 1.051a2 2 0 0 0-1.594 1.594l-1.051 5.558a1 1 0 0 1-1.966 0l-1.051-5.558a2 2 0 0 0-1.594-1.594l-5.558-1.051a1 1 0 0 1 0-1.966l5.558-1.051a2 2 0 0 0 1.594-1.594z"/><path d="M20 2v4"/><path d="M22 4h-4"/><circle cx="4" cy="20" r="2"/></svg>
      Ce que montrent les données
    </h2>
    <div class="insight-grid" id="insightGrid"></div>
  </section>

  <footer>Généré automatiquement par <span class="mono">pipeline/gold/build_dashboard.py</span> — voir NOTES.md et analysis/exploration.ipynb pour l'analyse complète.</footer>
</main>

<script>
const DATA = __DATA_JSON__;
const DIGITAL = __DIGITAL_JSON__;

const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const MUTED_FG = cssVar('--muted-foreground');
const BORDER = cssVar('--border');
const C_PLAYOFFS = cssVar('--comp-playoffs');
const C_EUROLEAGUE = cssVar('--comp-euroleague');
const C_CHAMPIONNAT = cssVar('--comp-championnat');
const C_PRIMARY = cssVar('--primary');
const C_POSITIVE = cssVar('--positive');

Chart.defaults.color = MUTED_FG;
Chart.defaults.borderColor = BORDER;
Chart.defaults.font.family = "'DM Sans', ui-sans-serif, system-ui, sans-serif";

const competitionColor = c => c.includes('Playoffs') ? C_PLAYOFFS : c.includes('EuroLeague') ? C_EUROLEAGUE : C_CHAMPIONNAT;
const competitionShort = c => c.includes('Playoffs') ? 'Playoffs' : c.includes('EuroLeague') ? 'EuroLeague' : 'Betclic ÉLITE';
const competitionBadgeClass = c => c.includes('Playoffs') ? 'playoffs' : c.includes('EuroLeague') ? 'euroleague' : '';

const avg = arr => { const v = arr.filter(x => x != null); return v.length ? v.reduce((a,b)=>a+b,0) / v.length : 0; };
const remplissages = DATA.map(d => d.taux_remplissage).filter(x => x != null);
const annulations = DATA.map(d => d.taux_annulation).filter(x => x != null);

const ICON_DOWN = `<svg class="icon" style="color:${C_PRIMARY}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m7 7 10 10"/><path d="M17 7v10H7"/></svg>`;
const ICON_TROPHY = `<svg class="icon" style="color:${C_POSITIVE}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 14.66v1.626a2 2 0 0 1-.976 1.696A5 5 0 0 0 7 21.978"/><path d="M14 14.66v1.626a2 2 0 0 0 .976 1.696A5 5 0 0 1 17 21.978"/><path d="M18 9h1.5a1 1 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M6 9a6 6 0 0 0 12 0V3a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1z"/><path d="M6 9H4.5a1 1 0 0 1 0-5H6"/></svg>`;
const ICON_CALENDAR = `<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/></svg>`;

const kpiValues = [
  { label: 'Remplissage moyen', value: (avg(remplissages)*100).toFixed(1) + '%' },
  { label: 'Match le plus faible', value: (Math.min(...remplissages)*100).toFixed(1) + '%', icon: ICON_DOWN },
  { label: 'Match le plus fort', value: (Math.max(...remplissages)*100).toFixed(1) + '%', icon: ICON_TROPHY },
  { label: "Taux d'annulation moyen", value: annulations.length ? (avg(annulations)*100).toFixed(1) + '%' : 'N/A' },
  { label: 'Matchs analysés', value: String(DATA.length) },
];
document.getElementById('kpis').innerHTML = kpiValues.map(k => `
  <div class="panel kpi">
    <div class="kpi-top"><p class="stat-num">${k.value}</p>${k.icon || ''}</div>
    <p class="label">${k.label}</p>
  </div>
`).join('');

new Chart(document.getElementById('chartRemplissage'), {
  type: 'bar',
  data: {
    labels: DATA.map(d => d.match_id),
    datasets: [{
      data: DATA.map(d => (d.taux_remplissage*100).toFixed(1)),
      backgroundColor: DATA.map(d => competitionColor(d.competition)),
      borderRadius: 3,
    }]
  },
  options: {
    plugins: { legend: { display: false },
      tooltip: { callbacks: { label: c => `${DATA[c.dataIndex].adversaire} — ${c.formattedValue}%` } } },
    scales: {
      y: { min: 0, max: 100, grid: { color: BORDER, borderDash: [3, 3] }, ticks: { stepSize: 25, callback: v => v + '%', color: MUTED_FG } },
      x: { grid: { display: false } }
    }
  }
});
document.getElementById('legendRemplissage').innerHTML = `
  <span><span class="dot" style="background:${C_PLAYOFFS}"></span>Playoffs</span>
  <span><span class="dot" style="background:${C_EUROLEAGUE}"></span>EuroLeague</span>
  <span><span class="dot" style="background:${C_CHAMPIONNAT}"></span>Betclic ÉLITE</span>
`;

new Chart(document.getElementById('chartClassement'), {
  type: 'scatter',
  data: {
    datasets: [{
      data: DATA.map(d => ({ x: d.rang_adversaire_avant, y: d.taux_remplissage*100 })),
      backgroundColor: DATA.map(d => competitionColor(d.competition)),
      pointRadius: 5,
      pointHoverRadius: 6,
    }]
  },
  options: {
    plugins: { legend: { display: false },
      tooltip: { callbacks: { label: c => `${DATA[c.dataIndex].adversaire} — ${c.formattedValue}` } } },
    scales: {
      x: { title: { display: true, text: "Rang de l'adversaire avant match", color: MUTED_FG },
           grid: { color: BORDER, borderDash: [3, 3] } },
      y: { min: 0, max: 100, grid: { color: BORDER, borderDash: [3, 3] },
           ticks: { stepSize: 25, callback: v => v + '%', color: MUTED_FG } }
    }
  }
});

const byComp = {};
DATA.forEach(d => { if (d.taux_remplissage != null) (byComp[d.competition] ||= []).push(d.taux_remplissage); });
new Chart(document.getElementById('chartCompetition'), {
  type: 'bar',
  data: {
    labels: Object.keys(byComp),
    datasets: [{
      data: Object.values(byComp).map(v => (avg(v)*100).toFixed(1)),
      backgroundColor: Object.keys(byComp).map(competitionColor),
      borderRadius: 3,
    }]
  },
  options: { plugins: { legend: { display: false } },
    scales: {
      y: { min: 0, max: 100, grid: { color: BORDER, borderDash: [3, 3] }, ticks: { stepSize: 25, callback: v => v + '%', color: MUTED_FG } },
      x: { grid: { display: false } }
    } }
});

const jourOrdre = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const jourAbbr = { Monday:'Lun', Tuesday:'Mar', Wednesday:'Mer', Thursday:'Jeu', Friday:'Ven', Saturday:'Sam', Sunday:'Dim' };
const jourFull = { Monday:'Lundi', Tuesday:'Mardi', Wednesday:'Mercredi', Thursday:'Jeudi', Friday:'Vendredi', Saturday:'Samedi', Sunday:'Dimanche' };
const byJour = {};
DATA.forEach(d => { if (d.taux_remplissage != null) (byJour[d.jour_semaine] ||= []).push(d.taux_remplissage); });
const joursPresents = jourOrdre.filter(j => byJour[j]);
new Chart(document.getElementById('chartJour'), {
  type: 'bar',
  data: {
    labels: joursPresents.map(j => jourAbbr[j]),
    datasets: [{
      data: joursPresents.map(j => (avg(byJour[j])*100).toFixed(1)),
      backgroundColor: C_PLAYOFFS,
      borderRadius: 3,
    }]
  },
  options: { plugins: { legend: { display: false } },
    scales: {
      y: { min: 0, max: 100, grid: { color: BORDER, borderDash: [3, 3] }, ticks: { stepSize: 25, callback: v => v + '%', color: MUTED_FG } },
      x: { grid: { display: false } }
    } }
});

const faibles = [...DATA].sort((a,b) => a.taux_remplissage - b.taux_remplissage).slice(0, 8);
document.querySelector('#tableFaibles tbody').innerHTML = faibles.map(d => `
  <tr>
    <td class="mono-xs">${d.match_id}</td>
    <td class="muted">${d.date}</td>
    <td class="medium">${d.adversaire}</td>
    <td><span class="badge ${competitionBadgeClass(d.competition)}">${competitionShort(d.competition)}</span></td>
    <td>
      <div class="fill-cell">
        <div class="fill-track"><div class="fill-bar" style="width:${(d.taux_remplissage*100).toFixed(1)}%"></div></div>
        <span class="fill-value">${(d.taux_remplissage*100).toFixed(1)}%</span>
      </div>
    </td>
    <td class="muted">${d.rang_adversaire_avant}</td>
    <td><span class="day-cell">${ICON_CALENDAR}${jourFull[d.jour_semaine] || d.jour_semaine}</span></td>
  </tr>
`).join('');

// Conversion par canal (données live depuis silver.web_sessions)
const convData = [...DIGITAL.conversion].sort((a, b) => a.taux_conversion_pct - b.taux_conversion_pct);
new Chart(document.getElementById('chartConversion'), {
  type: 'bar',
  data: {
    labels: convData.map(d => `${d.source} / ${d.medium}`),
    datasets: [{
      data: convData.map(d => d.taux_conversion_pct),
      backgroundColor: convData.map(d => d.taux_conversion_pct > 15 ? C_EUROLEAGUE : C_CHAMPIONNAT),
      borderRadius: 3,
    }]
  },
  options: {
    indexAxis: 'y',
    plugins: { legend: { display: false },
      tooltip: { callbacks: { label: c => `${c.formattedValue}% de sessions converties` } } },
    scales: {
      x: { min: 0, max: 25, grid: { color: BORDER, borderDash: [3, 3] }, ticks: { callback: v => v + '%', color: MUTED_FG } },
      y: { grid: { display: false }, ticks: { color: MUTED_FG, font: { size: 11 } } }
    }
  }
});

// Performance des campagnes par canal (données live depuis bronze.raw_campagnes_evenements)
document.getElementById('campagnesStats').innerHTML = DIGITAL.campagnes.map(c => `
  <div style="margin-bottom:16px;">
    <div style="display:flex;justify-content:space-between;align-items:baseline;">
      <span style="font-family:var(--font-display);font-weight:600;font-size:15px;">${c.canal}</span>
      <span style="font-size:11px;color:${MUTED_FG};font-family:var(--font-mono);">${c.delivres.toLocaleString('fr-FR')} envois</span>
    </div>
    <div style="display:flex;gap:24px;margin-top:6px;">
      <div>
        <div class="fill-track" style="width:120px;"><div class="fill-bar" style="width:${c.taux_ouverture_pct}%;background:${C_EUROLEAGUE};"></div></div>
        <span style="font-size:11px;color:${MUTED_FG};">Ouverture ${c.taux_ouverture_pct}%</span>
      </div>
      <div>
        <div class="fill-track" style="width:120px;"><div class="fill-bar" style="width:${c.taux_clic_pct}%;"></div></div>
        <span style="font-size:11px;color:${MUTED_FG};">Clic ${c.taux_clic_pct}%</span>
      </div>
    </div>
  </div>
`).join('');

const INSIGHTS = [
  { h: "Le classement de l'adversaire domine tout",
    p: "Le remplissage chute de ~90% face à un top adversaire à ~65% face à un adversaire en bas de tableau. Confirmé par un modèle de régression : feature la plus influente, de loin." },
  { h: "Écart net entre compétitions",
    p: "Playoffs et EuroLeague remplissent mieux (~83-85%) que le championnat national Betclic ÉLITE (~75%)." },
  { h: "Le dimanche sous-performe",
    p: "~75% de remplissage le dimanche contre 81-82% les mardis et jeudis." },
  { h: "Les vacances scolaires pèsent",
    p: "75% pendant les vacances contre 81% hors vacances — effet vérifié indépendamment du classement adversaire." },
  { h: "Satisfaction = résultat, pas remplissage",
    p: "8.1/10 en victoire contre 6.2/10 en défaite. Remplissage et satisfaction sont deux conséquences distinctes du niveau de l'adversaire." },
  { h: "Les annulations suivent la demande",
    p: "Corrélation 0.62 : les matchs à forte affluence attendue génèrent plus d'achats annulés — piste pour une politique d'annulation adaptée." },
  { h: "Bassin de fans au nord-est parisien",
    p: "Les 18e et 19e arrondissements affichent la plus forte pénétration (>60 contacts pour 1000 habitants), cohérent avec la proximité de la salle." },
  { h: "Le SMS surperforme largement l'email",
    p: "SMS, newsletter et Google Ads convertissent 3x mieux (~22.5%) que l'organique/social (~6.5-7%). Le SMS atteint 38.4% d'ouverture contre 21.3% pour l'email." },
];
document.getElementById('insightGrid').innerHTML = INSIGHTS.map(i => `
  <article class="panel insight-card">
    <h3>${i.h}</h3>
    <p>${i.p}</p>
  </article>
`).join('');
</script>

</body>
</html>
"""


def build_dashboard():
    records = get_data()
    logger.info("Données récupérées : %d matchs", len(records))

    digital = get_digital_data()
    logger.info(
        "Données digitales : %d canaux d'acquisition, %d canaux de campagne",
        len(digital["conversion"]), len(digital["campagnes"]),
    )

    if not CHARTJS_VENDOR.exists():
        raise FileNotFoundError(f"{CHARTJS_VENDOR} introuvable. Chart.js doit être vendorisé localement.")
    chartjs_code = CHARTJS_VENDOR.read_text(encoding="utf-8")

    html = HTML_TEMPLATE.replace("__CHARTJS_INLINE__", chartjs_code)
    html = html.replace("__DATA_JSON__", json.dumps(records, ensure_ascii=False))
    html = html.replace("__DIGITAL_JSON__", json.dumps(digital, ensure_ascii=False))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    logger.info("Dashboard généré : %s (%.0f Ko)", OUTPUT, OUTPUT.stat().st_size / 1024)


if __name__ == "__main__":
    build_dashboard()
