"""Classification for Kartik's site (domain "ai"): machine-learning, data and quant roles count."""
from classify import classify


def c(title, desc="", org="", loc="", **hints):
    return classify({"title": title, "description": desc, "org": org, "location": loc, "hints": hints})


def test_ml_internship_at_a_frontier_lab():
    j = c("Research Engineer Intern, Machine Learning (Summer 2027)", "Large language model training and interpretability in PyTorch.",
          "Anthropic", "London, UK", sector="ai-lab")
    assert j["relevant"] and j["kind"] == "internship" and j["sector"] == "ai-lab" and j["region"] == "europe"
    assert {"ml.core", "ml.llm"} <= set(j["topics"])


def test_fellowship_needs_no_phd():
    f = c("Anthropic Fellows Program — AI Safety Fellow", "Four-month paid fellowship on AI safety research. You don't need a PhD.",
          "Anthropic", "London, UK", sector="ai-lab")
    assert f["relevant"] and f["kind"] == "fellowship" and "ml.safety" in f["topics"] and not f["needs_phd"]


def test_climate_ml_and_gaussian_processes():
    j = c("Machine Learning Intern (weather forecasting)", "Gaussian processes and deep learning for probabilistic weather and climate "
          "forecasting; uncertainty quantification.", "Skyline Climate", "Remote")
    assert j["relevant"] and j["kind"] == "internship" and {"ml.prob", "sci.climate", "ds.ts"} <= set(j["topics"])


def test_non_ml_roles_are_dropped():
    assert not c("Senior Backend Engineer", "Go, Postgres, Kubernetes.", "ShopCart", "New York, NY")["relevant"]
    assert not c("Account Executive, Enterprise", "Sell our AI platform to large customers.", "OpenAI", "San Francisco",
                 sector="ai-lab")["relevant"]
    assert not c("Physics Teacher", "Teach physics to high-school students.", "A School", "Pune, India")["relevant"]


def test_ml_software_engineer_is_kept():
    j = c("Software Engineer, ML Infrastructure", "Distributed training and inference serving for large language models.",
          "Databricks", "Bengaluru, India", sector="tech")
    assert j["relevant"] and "ml.eng" in j["topics"] and j["region"] == "india" and j["sector"] == "tech"


def test_phd_positions_and_phd_required_roles():
    s = c("Staff Research Scientist (alignment)", "PhD in machine learning required, 8+ years of experience.", "Frontier Labs",
          "San Francisco, CA")
    assert s["relevant"] and s["needs_phd"]
    p = c("PhD position in machine learning for climate", "Doctoral position on Gaussian processes.", "TU Delft", "Delft, Netherlands")
    assert p["kind"] == "phd" and not p["relevant"]                 # he is not looking for a PhD (scraper/site.yaml)


def test_quant_roles():
    q = c("Quantitative Researcher (new grad)", "Probability, statistics and machine learning on market data. Visa sponsorship available.",
          "Delta Quant", "London, UK", sector="quant")
    assert q["relevant"] and "quant.research" in q["topics"] and q["sector"] == "quant"
