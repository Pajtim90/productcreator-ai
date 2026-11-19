import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='ProductCreator AI', page_icon='🎁', layout='wide')
st.title('🎁 ProductCreator AI')
st.caption('MVP 0.5 · Schweizer Preisvergleich · Schweiz · CHF')
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
st.caption('Shopübergreifende Suche in öffentlich indexierten Schweizer Händlerangeboten (nicht garantiert alle Shops).')
max_queries = st.slider('Maximale Produkttypen pro Durchlauf', 1, 8, 4)

if 'results' not in st.session_state:
    st.session_state['results'] = []
if 'selected' not in st.session_state:
    st.session_state['selected'] = {}

def price_from_text(s):
    if isinstance(s, (int, float)):
        return float(s) if 0 < float(s) < 100000 else None
    if not s:
        return None
    m = re.search(r"(?:CHF|Fr\.?)\s*([0-9][0-9'’., ]*)|([0-9][0-9'’., ]*)\s*(?:CHF|Fr\.?)", str(s), re.I)
    if not m:
        return None
    raw = (m.group(1) or m.group(2)).strip().replace(' ', '').replace("'", '').replace('’', '')
    if ',' in raw and '.' in raw:
        raw = raw.replace(',', '') if raw.rfind('.') > raw.rfind(',') else raw.replace('.', '').replace(',', '.')
    else:
        raw = raw.replace(',', '.')
    try:
        value = float(raw)
        return round(value, 2) if 0 < value < 100000 else None
    except ValueError:
        return None

def serp_search(term):
    params = {'engine': 'google_shopping', 'q': f'{term} Schweiz CHF', 'gl': 'ch', 'hl': 'de', 'api_key': api_key}
    response = requests.get('https://serpapi.com/search.json', params=params, timeout=(8, 40))
    response.raise_for_status()
    data = response.json()
    if data.get('error'):
        raise RuntimeError(data['error'])
    results = []
    for r in data.get('shopping_results', []):
        link = r.get('link') or r.get('product_link') or ''
        if not isinstance(link, str) or not link.startswith('https://'):
            continue
        host = urlparse(link).netloc.lower().removeprefix('www.')
        if not host.endswith('.ch') or any(x in host for x in ('google.', 'toppreise.', 'comparis.')):
            continue
        title = str(r.get('title') or '').strip()
        if len(title) < 8 or any(x in title.lower() for x in ('kategorie', 'preisvergleich', 'alle produkte', 'gebraucht')):
            continue
        raw_price = r.get('extracted_price')
        price = float(raw_price) if isinstance(raw_price, (int, float)) and 0 < raw_price < 100000 else price_from_text(r.get('price'))
        if price is None:
            continue
        results.append({'Suchbegriff': term, 'Produkt': title[:180], 'Händler': host,
                        'Preis CHF': price, 'Produktlink': link,
                        'Bild-URL': r.get('thumbnail') or '',
                        'Status': 'Suchpreis – beim Händler prüfen',
                        'Abgerufen UTC': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})
    return results

if st.button('🔎 Produkte online suchen', type='primary'):
    terms = [x.strip() for x in terms_text.splitlines() if x.strip()]
    queries = terms[:max_queries]
    if not queries:
        st.warning('Bitte mindestens einen Suchbegriff eingeben.')
    else:
        found = []
        with st.spinner(f'Suche läuft: {len(queries)} Abfragen …'):
            for term in queries:
                try:
                    found.extend(serp_search(term))
                except Exception as exc:
                    st.warning(f'Suche {term} fehlgeschlagen: {exc}')
        seen = set()
        unique = []
        for item in found:
            if item['Produktlink'] not in seen:
                unique.append(item)
                seen.add(item['Produktlink'])
        st.session_state['results'] = unique
        st.success(f'{len(unique)} Angebote mit auslesbarem Preis und direktem Schweizer Händlerlink gefunden.')

st.subheader('2 · Gefundene Angebote mit direkten Preisen')
results = st.session_state['results']
if not results:
    st.write('Noch keine Suchergebnisse. Starte die Recherche oben.')
else:
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True,
                 column_config={'Produktlink': st.column_config.LinkColumn('Produktlink'),
                                'Bild-URL': st.column_config.ImageColumn('Suchbild'),
                                'Preis CHF': st.column_config.NumberColumn('Preis pro Stück CHF', format='%.2f CHF')})
    st.caption('Nur Angebote mit maschinenlesbarem Suchpreis und Händlerlink. Preise, Produktidentität, Versand und Verfügbarkeit für die benötigte Menge sind nicht verifiziert.')
    st.subheader('Preisvergleich: günstigster Suchtreffer je Produkttyp')
    cheapest = []
    for category in dict.fromkeys(r['Suchbegriff'] for r in results):
        matches = [r for r in results if r['Suchbegriff'] == category]
        if matches:
            cheapest.append(min(matches, key=lambda r: r['Preis CHF']))
    st.dataframe(pd.DataFrame(cheapest)[['Suchbegriff','Produkt','Händler','Preis CHF','Produktlink']], hide_index=True, use_container_width=True, column_config={'Preis CHF': st.column_config.NumberColumn('Preis / Stück', format='%.2f CHF'), 'Produktlink': st.column_config.LinkColumn('Händlerangebot')})
    st.subheader('3 · Artikel für deine Box auswählen')
    st.caption('Die Auswahl ist manuell. Für jeden Produkttyp zeigt der Preisvergleich die günstigste gefundene Option; noch keine automatische Qualitätsprüfung.')
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
st.caption('MVP 0.5: Recherchiert über SerpAPI/Google, aber noch keine autonome KI-Komposition, keine verifizierte Produktbild-Montage, keine Shopify-Veröffentlichung. Preise und Bestellbarkeit vor Kauf direkt beim Händler prüfen.')
