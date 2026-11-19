import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='ProductCreator AI', page_icon='🎁', layout='wide')
st.title('🎁 ProductCreator AI')
st.caption('MVP 0.4 · Live-Produktsuche · Schweiz · CHF')
st.info('Suchresultate sind Produktkandidaten, keine bestätigten Einkaufsangebote. Prüfe Preis, Variante, Versand, Lieferbarkeit und Bildrechte beim Händler.')

with st.sidebar:
    st.header('Auftrag')
    idea = st.text_area('Produktidee', 'Hochwertige Onboarding-Geschenkbox für neue Mitarbeitende')
    budget = st.number_input('Max. Materialkosten pro Box (CHF)', min_value=1.0, value=30.0, step=1.0)
    quantity = st.number_input('Anzahl Boxen', min_value=1, value=10, step=1)
    margin = st.number_input('Ziel-Deckungsbeitragsmarge (%)', min_value=0.0, max_value=90.0, value=30.0)
    packing = st.number_input('Verpackung, Füllmaterial, Karte pro Box (CHF)', min_value=0.0, value=4.0, step=0.5)
    other = st.number_input('Weitere variable Kosten pro Box (CHF)', min_value=0.0, value=3.0, step=0.5)

try:
    api_key = st.secrets.get('SERPAPI_API_KEY', '') or os.environ.get('SERPAPI_API_KEY', '')
except Exception:
    api_key = os.environ.get('SERPAPI_API_KEY', '')

if not api_key:
    st.error('SERPAPI_API_KEY fehlt in Streamlit Secrets. Bitte unter App settings → Secrets speichern.')
    st.stop()

st.subheader('1 · Suchbegriffe')
st.write('Die Suchbegriffe sind editierbar. Starte zunächst mit 2–4 Produkttypen; jede Zeile verursacht eine Suchanfrage.')
default_terms = 'A5 Notizbuch schwarz\nTrinkflasche wiederverwendbar\nSchweizer Schokolade 100g\nGeschenkbox Karton schwarz'
terms_text = st.text_area('Ein Produkttyp pro Zeile', value=default_terms, height=125)
shops = st.multiselect('Shops für gezielte Suche', ['galaxus.ch', 'coop.ch', 'migros.ch', 'ikea.com', 'brack.ch'], default=['galaxus.ch', 'coop.ch', 'migros.ch'])
max_queries = st.slider('Maximale Suchanfragen pro Durchlauf', 1, 12, 6)

if 'results' not in st.session_state:
    st.session_state['results'] = []
if 'selected' not in st.session_state:
    st.session_state['selected'] = {}

def price_from_text(s):
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s)
    m = re.search(r'(?:CHF\s*)?(\d{1,5}(?:[\'’ ]\d{3})*(?:[.,]\d{1,2})?)', s)
    if not m:
        return None
    raw = m.group(1).replace(' ', '').replace("'", '').replace('’', '')
    if ',' in raw and '.' in raw:
        raw = raw.replace('.', '').replace(',', '.')
    elif ',' in raw:
        raw = raw.replace(',', '.')
    try:
        return float(raw)
    except ValueError:
        return None

def serp_search(term, domain):
    q = f'{term} kaufen CHF Schweiz site:{domain}' if domain else f'{term} kaufen CHF Schweiz'
    response = requests.get('https://serpapi.com/search.json', params={
        'engine': 'google', 'q': q, 'gl': 'ch', 'hl': 'de', 'num': 10, 'api_key': api_key
    }, timeout=25)
    response.raise_for_status()
    data = response.json()
    if data.get('error'):
        raise RuntimeError(data['error'])
    results = []
    for r in data.get('organic_results', []):
        link = r.get('link', '')
        if not link.startswith('https://'):
            continue
        rich = r.get('rich_snippet', {})
        top = rich.get('top', {}) if isinstance(rich, dict) else {}
        bottom = rich.get('bottom', {}) if isinstance(rich, dict) else {}
        extracted = r.get('price') or r.get('extracted_price')
        if extracted is None:
            for v in (top, bottom):
                if isinstance(v, dict):
                    extracted = v.get('detected_extensions', {}).get('price') if isinstance(v.get('detected_extensions'), dict) else None
                    if extracted is not None:
                        break
        price = price_from_text(extracted) if extracted is not None else None
        thumb = r.get('thumbnail') or ''
        results.append({'Suchbegriff': term, 'Produkt': r.get('title', '')[:200],
                        'Händler': urlparse(link).netloc, 'Preis CHF': price,
                        'Produktlink': link, 'Bild-URL': thumb,
                        'Status': 'Preis unbestätigt' if price is not None else 'Preis fehlt',
                        'Abgerufen UTC': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})
    return results

if st.button('🔎 Produkte online suchen', type='primary'):
    terms = [x.strip() for x in terms_text.splitlines() if x.strip()]
    queries = [(t, d) for t in terms for d in (shops or [''])][:max_queries]
    if not queries:
        st.warning('Bitte mindestens einen Suchbegriff eingeben.')
    else:
        found = []
        with st.spinner(f'Suche läuft: {len(queries)} Abfragen …'):
            for term, domain in queries:
                try:
                    found.extend(serp_search(term, domain))
                except Exception as exc:
                    st.warning(f'Suche {term} / {domain or "allgemein"} fehlgeschlagen: {exc}')
        seen = set()
        unique = []
        for item in found:
            if item['Produktlink'] not in seen:
                unique.append(item)
                seen.add(item['Produktlink'])
        st.session_state['results'] = unique
        st.success(f'{len(unique)} unterschiedliche Suchtreffer gefunden. Nicht alle enthalten auslesbare Preise.')

st.subheader('2 · Gefundene Angebote prüfen')
results = st.session_state['results']
if not results:
    st.write('Noch keine Suchergebnisse. Starte die Recherche oben.')
else:
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True,
                 column_config={'Produktlink': st.column_config.LinkColumn('Produktlink'),
                                'Bild-URL': st.column_config.LinkColumn('Bild-URL'),
                                'Preis CHF': st.column_config.NumberColumn('Preis CHF', format='%.2f')})
    st.caption('Google-Suchtreffer liefern nicht immer Preise oder Produktbilder. Leere Preisfelder werden bewusst nicht erfunden.')
    st.subheader('3 · Artikel für deine Box auswählen')
    candidates = [r for r in results if r['Preis CHF'] is not None]
    if not candidates:
        st.warning('Keine maschinenlesbaren Preise gefunden. Prüfe die Händlerlinks und trage Preise in einer späteren Version manuell nach.')
    else:
        options = list(range(len(candidates)))
        chosen = st.multiselect('Artikel auswählen (pro ausgewähltem Artikel 1 Stück je Box)', options,
                                format_func=lambda i: f"{candidates[i]['Produkt'][:75]} · CHF {candidates[i]['Preis CHF']:.2f} · {candidates[i]['Händler']}")
        chosen_items = [candidates[i] for i in chosen]
        material = sum(x['Preis CHF'] for x in chosen_items) + packing
        variable = material + other
        min_sale = variable / (1 - margin / 100) if margin < 100 else float('inf')
        c1, c2, c3 = st.columns(3)
        c1.metric('Material pro Box', f'CHF {material:.2f}', delta=f'{budget-material:+.2f} CHF zum Budget')
        c2.metric('Material für alle Boxen', f'CHF {material*quantity:.2f}')
        c3.metric('Rechnerischer Mindestpreis', f'CHF {min_sale:.2f}')
        if material > budget:
            st.error('Budget überschritten.')
        else:
            st.success('Vorläufig innerhalb des Materialbudgets (ohne nicht erfasste Kosten).')
        st.caption('Mindestpreis = (Material + weitere variable Kosten) / (1 − Zielmarge). Vereinfachte Rechnung ohne MWST, Plattformgebühren, Beschaffungsversand und Mengenrabatte. Nicht als endgültige Verkaufspreiskalkulation verwenden.')
        for item in chosen_items:
            with st.expander(item['Produkt']):
                st.write(f"Händler: {item['Händler']} · Preisindikator: CHF {item['Preis CHF']:.2f}")
                st.link_button('Originalangebot öffnen', item['Produktlink'])
                if item['Bild-URL'] and item['Bild-URL'].startswith('https://'):
                    st.image(item['Bild-URL'], width=220, caption='Suchmaschinen-Vorschaubild; Identität und Nutzungsrechte prüfen')
        st.download_button('Einkaufsliste als CSV exportieren', pd.DataFrame(chosen_items).to_csv(index=False).encode('utf-8-sig'), file_name='productcreator_einkaufsliste.csv', mime='text/csv')

st.divider()
st.caption('MVP 0.4: Recherchiert über SerpAPI/Google, aber noch keine autonome KI-Komposition, keine verifizierte Produktbild-Montage, keine Shopify-Veröffentlichung. Preise und Bestellbarkeit vor Kauf direkt beim Händler prüfen.')
