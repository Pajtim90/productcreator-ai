import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, unquote

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="ProductCreator AI", page_icon="🎁", layout="wide")
st.title("🎁 ProductCreator AI")
st.caption("MVP 0.6 · Schweizer Online-Produktrecherche · CHF")
st.info("Preise aus Suchmaschinen sind unverifizierte Preisindikatoren. Bitte Händlerseite, Produktvariante, Liefermenge, Versand und Bildrechte prüfen.")

with st.sidebar:
    st.header("Auftrag")
    idea = st.text_area("Produktidee", "Hochwertige Onboarding-Geschenkbox für neue Mitarbeitende")
    budget = st.number_input("Max. Materialkosten pro Box (CHF)", min_value=1.0, value=30.0, step=1.0)
    quantity = st.number_input("Anzahl Boxen", min_value=1, value=10, step=1)
    margin = st.number_input("Ziel-Deckungsbeitragsmarge (%)", min_value=0.0, max_value=90.0, value=30.0)
    packing = st.number_input("Verpackung, Füllmaterial, Karte pro Box (CHF)", min_value=0.0, value=4.0, step=0.5)
    other = st.number_input("Weitere variable Kosten pro Box (CHF)", min_value=0.0, value=3.0, step=0.5)

try:
    api_key = st.secrets.get("SERPAPI_API_KEY", "") or os.environ.get("SERPAPI_API_KEY", "")
except Exception:
    api_key = os.environ.get("SERPAPI_API_KEY", "")
if not api_key:
    st.error("SERPAPI_API_KEY fehlt in Streamlit Secrets.")
    st.stop()

st.subheader("1 · Produkte recherchieren")
terms_text = st.text_area("Ein Produkttyp pro Zeile", "A5 Notizbuch schwarz\nTrinkflasche wiederverwendbar\nSchweizer Schokolade 100g\nGeschenkbox Karton schwarz", height=130)
max_queries = st.slider("Maximale Produkttypen pro Durchlauf", 1, 8, 2)
st.caption("Pro Produkttyp wird zunächst Google Shopping, bei fehlenden Ergebnissen zusätzlich Google Web Search abgefragt. Jede Anfrage zählt bei SerpAPI.")

if "results_v06" not in st.session_state:
    st.session_state["results_v06"] = []
if "diagnostics_v06" not in st.session_state:
    st.session_state["diagnostics_v06"] = []


def parse_price(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return round(float(value), 2) if 0 < float(value) < 100000 else None
    if not value:
        return None
    text = str(value).replace("\u00a0", " ")
    # Do not guess prices from bare numbers (e.g. 100 g, 2026).
    match = re.search(r"(?:CHF|Fr\.?|SFr\.?)\s*([0-9][0-9'’., ]*)|([0-9][0-9'’., ]*)\s*(?:CHF|Fr\.?|SFr\.?)", text, re.I)
    if not match:
        return None
    raw = (match.group(1) or match.group(2)).strip().replace(" ", "").replace("'", "").replace("’", "")
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    elif raw.count(",") > 1:
        raw = raw.replace(",", "")
    else:
        raw = raw.replace(",", ".")
    try:
        num = float(raw)
        return round(num, 2) if 0 < num < 100000 else None
    except ValueError:
        return None


def clean_url(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    if value.startswith("//"):
        value = "https:" + value
    if not value.startswith(("http://", "https://")):
        return ""
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host.endswith("google.com") or host.endswith("google.ch"):
        query = parse_qs(parsed.query)
        for key in ("url", "q"):
            candidate = unquote(query.get(key, [""])[0])
            if candidate.startswith(("http://", "https://")):
                return clean_url(candidate)
        return ""  # Google redirects are not verified direct retailer links.
    if not host or host in {"serpapi.com", "www.serpapi.com"}:
        return ""
    return value


def api_search(term, engine):
    q = f"{term} kaufen CHF Schweiz" if engine == "google" else f"{term} Schweiz"
    params = {"engine": engine, "q": q, "gl": "ch", "hl": "de", "api_key": api_key, "num": 20}
    response = requests.get("https://serpapi.com/search.json", params=params, timeout=(10, 35))
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    key = "shopping_results" if engine == "google_shopping" else "organic_results"
    return data.get(key, []) or []


def convert_result(term, entry, engine):
    title = str(entry.get("title") or "").strip()
    if not title:
        return None, "Ohne Produkttitel"
    # Shopping listings may link to Google intermediary pages; retain the candidate
    # but mark the direct merchant URL as missing instead of discarding the listing.
    raw_link = entry.get("link") or entry.get("product_link") or ""
    merchant_link = clean_url(raw_link)
    source = str(entry.get("source") or entry.get("seller") or "").strip()
    host = (urlparse(merchant_link).hostname or "").removeprefix("www.")
    merchant = source or host or "Nicht ermittelt"
    price = parse_price(entry.get("extracted_price"))
    if price is None:
        price = parse_price(entry.get("price"))
    if price is None and engine == "google":
        price = parse_price(entry.get("snippet"))
    img = entry.get("thumbnail") or entry.get("image") or ""
    img = img if isinstance(img, str) and img.startswith("https://") else ""
    if price is not None and merchant_link:
        status = "Preisindikator + Händlerlink (unbestätigt)"
    elif price is not None:
        status = "Preis gefunden, direkter Händlerlink fehlt"
    elif merchant_link:
        status = "Händlerlink gefunden, Preis fehlt"
    else:
        status = "Preis und Händlerlink fehlen"
    return {
        "Suchbegriff": term, "Produkt": title[:180], "Händler/Quelle": merchant,
        "Preis CHF": price, "Produktlink": merchant_link, "Bild-URL": img,
        "Status": status, "Suchquelle": "Google Shopping" if engine == "google_shopping" else "Google Web",
        "Abgerufen UTC": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }, None


if st.button("🔎 Produkte online suchen", type="primary"):
    terms = [s.strip() for s in terms_text.splitlines() if s.strip()][:max_queries]
    found, diag = [], []
    if not terms:
        st.warning("Bitte mindestens einen Suchbegriff eingeben.")
    else:
        with st.spinner("SerpAPI-Suche läuft …"):
            for term in terms:
                for engine in ("google_shopping", "google"):
                    # Use web fallback only when Shopping has no priced direct-link candidates.
                    if engine == "google" and any(x["Suchbegriff"] == term and x["Preis CHF"] is not None and x["Produktlink"] for x in found):
                        continue
                    try:
                        raw = api_search(term, engine)
                        accepted = 0
                        for entry in raw:
                            item, _ = convert_result(term, entry, engine)
                            if item:
                                found.append(item)
                                accepted += 1
                        diag.append({"Suchbegriff": term, "Suchmaschine": engine, "API-Treffer": len(raw), "Eingelesen": accepted, "Fehler": ""})
                    except Exception as exc:
                        diag.append({"Suchbegriff": term, "Suchmaschine": engine, "API-Treffer": 0, "Eingelesen": 0, "Fehler": str(exc)[:240]})
        seen, unique = set(), []
        for item in found:
            key = (item["Suchbegriff"], item["Produkt"].casefold(), item["Produktlink"])
            if key not in seen:
                unique.append(item)
                seen.add(key)
        st.session_state["results_v06"] = unique
        st.session_state["diagnostics_v06"] = diag

results = st.session_state["results_v06"]
diag = st.session_state["diagnostics_v06"]
st.subheader("2 · Gefundene Angebote und Preise")
if diag:
    with st.expander("🔧 Suchdiagnose: Anzahl Treffer und API-Fehler", expanded=not bool(results)):
        st.dataframe(pd.DataFrame(diag), hide_index=True, use_container_width=True)

if not results:
    st.warning("Keine Treffer eingelesen. Öffne die Suchdiagnose, um API-Fehler und die Anzahl der Roh-Treffer zu sehen.")
else:
    priced = sum(x["Preis CHF"] is not None for x in results)
    direct = sum(bool(x["Produktlink"]) for x in results)
    usable = sum(x["Preis CHF"] is not None and bool(x["Produktlink"]) for x in results)
    a, b, c, d = st.columns(4)
    a.metric("Suchtreffer", len(results))
    b.metric("Mit Preis", priced)
    c.metric("Mit direktem Link", direct)
    d.metric("Preis + Link", usable)
    df = pd.DataFrame(results)
    st.dataframe(df, hide_index=True, use_container_width=True,
                 column_config={"Produktlink": st.column_config.LinkColumn("Händlerlink"),
                                "Bild-URL": st.column_config.ImageColumn("Suchbild"),
                                "Preis CHF": st.column_config.NumberColumn("Preis / Stück CHF", format="%.2f")})
    st.caption("Leere Preise bleiben leer. Suchbilder können vom tatsächlich bestellbaren Artikel abweichen. Händler/Quelle ist bei Shopping-Daten nicht zwingend die Domain des Angebots.")
    valid = [r for r in results if r["Preis CHF"] is not None and r["Produktlink"]]
    st.subheader("3 · Preisvergleich und Geschenkbox-Kalkulation")
    if not valid:
        st.warning("Noch keine Treffer mit Preis UND direktem Händlerlink. Bitte Suchdiagnose prüfen; nicht mit unbestätigten Preisen kalkulieren.")
    else:
        cheapest = []
        for term in dict.fromkeys(x["Suchbegriff"] for x in valid):
            cheapest.append(min((x for x in valid if x["Suchbegriff"] == term), key=lambda x: x["Preis CHF"]))
        st.dataframe(pd.DataFrame(cheapest)[["Suchbegriff", "Produkt", "Händler/Quelle", "Preis CHF", "Produktlink"]],
                     hide_index=True, use_container_width=True,
                     column_config={"Produktlink": st.column_config.LinkColumn("Händlerlink"),
                                    "Preis CHF": st.column_config.NumberColumn("Preis CHF", format="%.2f")})
        options = list(range(len(valid)))
        selected = st.multiselect("Artikel auswählen (je 1 Stück pro Box)", options,
                                  format_func=lambda i: f"{valid[i]['Produkt'][:70]} · CHF {valid[i]['Preis CHF']:.2f} · {valid[i]['Händler/Quelle']}")
        chosen = [valid[i] for i in selected]
        if chosen:
            material = sum(x["Preis CHF"] for x in chosen) + packing
            variable = material + other
            min_sale = variable / (1 - margin / 100)
            x, y, z = st.columns(3)
            x.metric("Material pro Box", f"CHF {material:.2f}")
            y.metric(f"Material für {quantity} Boxen", f"CHF {material * quantity:.2f}")
            z.metric("Rechnerischer Mindestpreis", f"CHF {min_sale:.2f}")
            if material > budget:
                st.error(f"Materialbudget um CHF {material - budget:.2f} überschritten.")
            else:
                st.success(f"Vorläufig CHF {budget - material:.2f} unter Materialbudget.")
            st.caption("Vereinfachte Deckungsbeitragsrechnung: ohne MWST, Zahlungs-/Shopify-Gebühren, Beschaffungsversand, Mengenverfügbarkeit und Rabatte.")
            st.download_button("📥 Einkaufsliste als CSV", pd.DataFrame(chosen).to_csv(index=False).encode("utf-8-sig"),
                               "productcreator_einkaufsliste.csv", "text/csv")
        else:
            st.info("Wähle Produkte aus, um die Box zu kalkulieren.")

st.divider()
st.caption("MVP 0.6: Suchdaten-Diagnose, Preisindikatoren und Händlerlinks. Noch keine verbindliche Preisprüfung, autonome Produktauswahl oder produktgetreue Gesamtvisualisierung.")
