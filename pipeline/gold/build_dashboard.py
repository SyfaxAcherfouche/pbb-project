"""
Génère dashboard/dashboard.html : dashboard autonome (données embarquées en
JSON dans le HTML, pas de connexion live à la base), à partir de
gold.fact_match. Utilise Chart.js via CDN pour les graphiques -- seule
dépendance réseau, avec dégradation propre si absente.

Usage :
    python pipeline/gold/build_dashboard.py
    (nécessite d'avoir lancé le pipeline jusqu'à gold avant)
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
    records = json.loads(df.to_json(orient="records"))
    return records


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Paris Basketball — Remplissage des matchs</title>
<script>__CHARTJS_INLINE__</script>
<style>
  :root {
    --navy: #111111;
    --navy-light: #1439B0;
    --amber: #E4032E;
    --red: #E4032E;
    --cream: #FAFAFA;
    --gray: #6B7280;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    background: var(--cream);
    color: var(--navy);
  }
  header {
    background: var(--navy);
    color: white;
    padding: 32px 40px;
  }
  header h1 {
    margin: 0 0 6px;
    font-size: 26px;
    letter-spacing: 0.02em;
  }
  header p {
    margin: 0;
    color: #B9C4D6;
    font-size: 14px;
  }
  main {
    max-width: 1200px;
    margin: 0 auto;
    padding: 32px 40px 60px;
  }
  .kpis {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 36px;
  }
  .kpi {
    background: white;
    border-radius: 10px;
    padding: 20px;
    border-left: 4px solid var(--amber);
  }
  .kpi .value {
    font-size: 28px;
    font-weight: 700;
    color: var(--navy);
  }
  .kpi .label {
    font-size: 12px;
    color: var(--gray);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-top: 4px;
  }
  .grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
  }
  @media (max-width: 900px) {
    .grid-2 { grid-template-columns: 1fr; }
  }
  .card {
    background: white;
    border-radius: 10px;
    padding: 24px;
  }
  .card h2 {
    margin: 0 0 4px;
    font-size: 16px;
  }
  .card .subtitle {
    font-size: 12px;
    color: var(--gray);
    margin-bottom: 16px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  th, td {
    text-align: left;
    padding: 8px 10px;
    border-bottom: 1px solid #EDEBE5;
  }
  th {
    color: var(--gray);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.03em;
  }
  tr.low-fill td:first-child {
    border-left: 3px solid var(--red);
  }
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge.euroleague { background: #E8EEFB; color: var(--navy-light); }
  .badge.championnat { background: #FBEFE3; color: #8A5A1E; }
  .badge.playoffs { background: #FCE9E7; color: var(--red); }
  .insights {
    background: white;
    border-radius: 10px;
    padding: 24px;
    margin-top: 24px;
  }
  .insights h2 { margin-top: 0; font-size: 16px; }
  .insights ul { margin: 0; padding-left: 20px; line-height: 1.7; font-size: 14px; }
  footer {
    text-align: center;
    color: var(--gray);
    font-size: 12px;
    padding: 24px;
  }
</style>
</head>
<body>

<header>
  <h1>Paris Basketball — Analyse du remplissage des matchs</h1>
  <p>Saison 2025-2026 · __N_MATCHS__ matchs à domicile · généré depuis gold.fact_match</p>
</header>

<main>
  <div class="kpis" id="kpis"></div>

  <div class="grid-2">
    <div class="card">
      <h2>Taux de remplissage par match</h2>
      <div class="subtitle">Trié par date, couleur = compétition</div>
      <canvas id="chartRemplissage" height="220"></canvas>
    </div>
    <div class="card">
      <h2>Remplissage vs classement de l'adversaire</h2>
      <div class="subtitle">Rang 1 = meilleur adversaire</div>
      <canvas id="chartClassement" height="220"></canvas>
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Remplissage moyen par compétition</h2>
      <canvas id="chartCompetition" height="200"></canvas>
    </div>
    <div class="card">
      <h2>Remplissage moyen par jour de semaine</h2>
      <canvas id="chartJour" height="200"></canvas>
    </div>
  </div>

  <div class="card">
    <h2>Les 8 matchs les plus faibles</h2>
    <div class="subtitle">Candidats prioritaires pour une action tarifaire ou marketing</div>
    <table id="tableFaibles">
      <thead>
        <tr>
          <th>Match</th><th>Date</th><th>Adversaire</th><th>Compétition</th>
          <th>Remplissage</th><th>Rang adversaire</th><th>Jour</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>

  <div class="insights">
    <h2>Ce que montrent les données</h2>
    <ul>
      <li><strong>Le classement de l'adversaire est le facteur le plus discriminant</strong> :
      le remplissage chute de ~90% face à un top adversaire à ~65% face à un
      adversaire en bas de tableau. Confirmé statistiquement par un modèle
      de régression (feature la plus influente, de loin).</li>
      <li><strong>Écart net entre compétitions</strong> : Playoffs et EuroLeague
      remplissent mieux (~83-85%) que le championnat national Betclic ÉLITE (~75%).</li>
      <li><strong>Le dimanche sous-performe</strong> systématiquement (~75%) par
      rapport aux mardis/jeudis (~81-82%).</li>
      <li><strong>Les vacances scolaires réduisent le remplissage</strong> (75% vs
      81% hors vacances) — effet vérifié indépendamment du classement adversaire.</li>
      <li><strong>La satisfaction du public dépend du résultat, pas du remplissage</strong> :
      8.1/10 en victoire contre 6.2/10 en défaite. Le remplissage et la
      satisfaction semblaient liés, mais sont en fait deux conséquences
      distinctes du niveau de l'adversaire.</li>
      <li><strong>Les annulations augmentent avec la demande</strong> (corrélation 0.62) :
      les matchs à forte affluence attendue génèrent plus d'achats annulés
      ensuite — piste pour une politique d'annulation adaptée.</li>
      <li><strong>Bassin de fans concentré au nord-est parisien</strong> : les 18e et
      19e arrondissements affichent la plus forte pénétration (>60 contacts
      pour 1000 habitants), cohérent avec la proximité de la salle.</li>
    </ul>
  </div>
</main>

<footer>Généré automatiquement par pipeline/gold/build_dashboard.py — voir NOTES.md et analysis/exploration.ipynb pour l'analyse complète</footer>

<script>
const DATA = __DATA_JSON__;

const competitionColor = c => c.includes('Playoffs') ? '#E4032E' : c.includes('EuroLeague') ? '#1439B0' : '#111111';
const competitionLabel = c => c.includes('Playoffs') ? 'playoffs' : c.includes('EuroLeague') ? 'euroleague' : 'championnat';

// KPIs
const avg = arr => { const v = arr.filter(x => x != null); return v.length ? v.reduce((a,b)=>a+b,0) / v.length : 0; };
const remplissages = DATA.map(d => d.taux_remplissage).filter(x => x != null);
const tauxAnnulations = DATA.map(d => d.taux_annulation).filter(x => x != null);
const kpis = [
  { label: 'Remplissage moyen', value: (avg(remplissages)*100).toFixed(1) + '%' },
  { label: 'Match le plus faible', value: (Math.min(...remplissages)*100).toFixed(1) + '%' },
  { label: 'Match le plus fort', value: (Math.max(...remplissages)*100).toFixed(1) + '%' },
  { label: "Taux d'annulation moyen", value: tauxAnnulations.length ? (avg(tauxAnnulations)*100).toFixed(1) + '%' : 'N/A' },
  { label: 'Matchs analysés', value: DATA.length },
];
document.getElementById('kpis').innerHTML = kpis.map(k =>
  `<div class="kpi"><div class="value">${k.value}</div><div class="label">${k.label}</div></div>`
).join('');

// Chart 1: remplissage par match (bar, chronologique)
new Chart(document.getElementById('chartRemplissage'), {
  type: 'bar',
  data: {
    labels: DATA.map(d => d.match_id),
    datasets: [{
      data: DATA.map(d => (d.taux_remplissage*100).toFixed(1)),
      backgroundColor: DATA.map(d => competitionColor(d.competition)),
    }]
  },
  options: {
    plugins: { legend: { display: false },
      tooltip: { callbacks: { label: c => `${DATA[c.dataIndex].adversaire} — ${c.formattedValue}%` } } },
    scales: { y: { title: { display: true, text: '% rempli' }, min: 0, max: 100 } }
  }
});

// Chart 2: scatter remplissage vs rang adversaire
new Chart(document.getElementById('chartClassement'), {
  type: 'scatter',
  data: {
    datasets: [{
      data: DATA.map(d => ({ x: d.rang_adversaire_avant, y: d.taux_remplissage*100 })),
      backgroundColor: '#1439B0',
    }]
  },
  options: {
    plugins: { legend: { display: false } },
    scales: {
      x: { title: { display: true, text: "Rang de l'adversaire avant match" } },
      y: { title: { display: true, text: '% rempli' }, min: 0, max: 100 }
    }
  }
});

// Chart 3: moyenne par compétition
const byComp = {};
DATA.forEach(d => { if (d.taux_remplissage != null) (byComp[d.competition] ||= []).push(d.taux_remplissage); });
new Chart(document.getElementById('chartCompetition'), {
  type: 'bar',
  data: {
    labels: Object.keys(byComp),
    datasets: [{
      data: Object.values(byComp).map(v => (avg(v)*100).toFixed(1)),
      backgroundColor: Object.keys(byComp).map(competitionColor),
    }]
  },
  options: { plugins: { legend: { display: false } },
    scales: { y: { title: { display: true, text: '% rempli moyen' }, min: 0, max: 100 } } }
});

// Chart 4: moyenne par jour de semaine
const jourOrdre = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday'];
const jourLabel = { Monday:'Lun', Tuesday:'Mar', Wednesday:'Mer', Thursday:'Jeu', Friday:'Ven', Saturday:'Sam', Sunday:'Dim' };
const byJour = {};
DATA.forEach(d => { if (d.taux_remplissage != null) (byJour[d.jour_semaine] ||= []).push(d.taux_remplissage); });
const joursPresents = jourOrdre.filter(j => byJour[j]);
new Chart(document.getElementById('chartJour'), {
  type: 'bar',
  data: {
    labels: joursPresents.map(j => jourLabel[j]),
    datasets: [{
      data: joursPresents.map(j => (avg(byJour[j])*100).toFixed(1)),
      backgroundColor: '#E4032E',
    }]
  },
  options: { plugins: { legend: { display: false } },
    scales: { y: { title: { display: true, text: '% rempli moyen' }, min: 0, max: 100 } } }
});

// Table des 8 matchs les plus faibles
const faibles = [...DATA].sort((a,b) => a.taux_remplissage - b.taux_remplissage).slice(0, 8);
document.querySelector('#tableFaibles tbody').innerHTML = faibles.map(d => `
  <tr class="low-fill">
    <td>${d.match_id}</td>
    <td>${d.date}</td>
    <td>${d.adversaire}</td>
    <td><span class="badge ${competitionLabel(d.competition)}">${d.competition}</span></td>
    <td><strong>${(d.taux_remplissage*100).toFixed(1)}%</strong></td>
    <td>${d.rang_adversaire_avant}</td>
    <td>${jourLabel[d.jour_semaine] || d.jour_semaine}</td>
  </tr>
`).join('');
</script>

</body>
</html>
"""


def build_dashboard():
    records = get_data()
    logger.info("Données récupérées : %d matchs", len(records))

    if not CHARTJS_VENDOR.exists():
        raise FileNotFoundError(
            f"{CHARTJS_VENDOR} introuvable. Chart.js doit être vendorisé localement "
            f"pour un dashboard vraiment autonome (pas de dépendance réseau le jour J)."
        )
    chartjs_code = CHARTJS_VENDOR.read_text(encoding="utf-8")

    html = HTML_TEMPLATE.replace("__CHARTJS_INLINE__", chartjs_code)
    html = html.replace("__DATA_JSON__", json.dumps(records, ensure_ascii=False))
    html = html.replace("__N_MATCHS__", str(len(records)))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    logger.info("Dashboard généré : %s (%.0f Ko)", OUTPUT, OUTPUT.stat().st_size / 1024)


if __name__ == "__main__":
    build_dashboard()
