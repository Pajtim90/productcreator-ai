import io
import json
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

st.set_page_config(page_title='ProductCreator AI', page_icon='🎁', layout='wide')
st.title('🎁 ProductCreator AI')
st.caption('Produktgetreuer Geschenkbox-Konfigurator · MVP 0.3 · CHF')
st.info('Diese Version recherchiert noch nicht autonom. Erfasse reale Produktangebote mit Händlerlink und Originalbild-URL. Preise, Verfügbarkeit und Bildrechte müssen vor dem Verkauf geprüft werden.')

DEFAULT = [
    {'Produkt':'Notizbuch A5, schwarz','Händler':'','Produktlink':'','Originalbild-URL':'','Stückpreis CHF':6.70,'Anzahl je Box':1,'Verfügbarkeit für Gesamtmenge':'Ungeprüft'},
    {'Produkt':'Trinkflasche','Händler':'','Produktlink':'','Originalbild-URL':'','Stückpreis CHF':2.95,'Anzahl je Box':1,'Verfügbarkeit für Gesamtmenge':'Ungeprüft'},
    {'Produkt':'Schokolade 100 g','Händler':'','Produktlink':'','Originalbild-URL':'','Stückpreis CHF':3.95,'Anzahl je Box':1,'Verfügbarkeit für Gesamtmenge':'Ungeprüft'},
    {'Produkt':'Geschenkverpackung','Händler':'','Produktlink':'','Originalbild-URL':'','Stückpreis CHF':6.80,'Anzahl je Box':1,'Verfügbarkeit für Gesamtmenge':'Ungeprüft'},
    {'Produkt':'Füllmaterial und Karte (Schätzung)','Händler':'','Produktlink':'','Originalbild-URL':'','Stückpreis CHF':1.30,'Anzahl je Box':1,'Verfügbarkeit für Gesamtmenge':'Ungeprüft'},
]
if 'items' not in st.session_state:
    st.session_state.items = pd.DataFrame(DEFAULT)

with st.sidebar:
    st.header('Auftrag')
    idea = st.text_area('Produktidee', 'Hochwertige Onboarding-Geschenkbox für neue Mitarbeitende')
    budget = st.number_input('Max. Materialkosten je Box (CHF)', min_value=0.01, value=30.0, step=1.0)
    qty = st.number_input('Anzahl Boxen', min_value=1, value=10, step=1)
    margin = st.number_input('Ziel-Deckungsbeitragsmarge (%)', min_value=0.0, max_value=95.0, value=30.0, step=1.0)
    vat = st.number_input('MWST auf Verkauf (%)', min_value=0.0, max_value=30.0, value=8.1, step=0.1)
    payment_fee = st.number_input('Zahlungsgebühr auf Bruttoverkauf (%)', min_value=0.0, max_value=30.0, value=3.0, step=0.1)
    extra = st.number_input('Zusätzliche variable Kosten je Box (CHF, netto)', min_value=0.0, value=5.0, step=0.5)
    st.caption('Beschaffungsversand, Versand an Kunden, Arbeitszeit, Retouren etc. hier berücksichtigen. Alle Artikelpreise werden in diesem MVP vereinfachend als Kosten ohne Vorsteuerkorrektur behandelt.')

st.subheader('1 · Echte Artikel erfassen')
st.caption('Pro Zeile einen konkreten Artikel und dessen Originalbild-URL eintragen. Keine KI-erfundenen Produkte oder Bilder.')
df = st.data_editor(st.session_state.items, num_rows='dynamic', use_container_width=True, hide_index=True, key='editor', column_config={
    'Produktlink':st.column_config.LinkColumn('Produktlink'),
    'Originalbild-URL':st.column_config.LinkColumn('Originalbild-URL'),
    'Stückpreis CHF':st.column_config.NumberColumn('Stückpreis CHF',min_value=0,format='%.2f'),
    'Anzahl je Box':st.column_config.NumberColumn('Anzahl je Box',min_value=0,step=1),
})
st.session_state.items = df.copy()
prices = pd.to_numeric(df.get('Stückpreis CHF',pd.Series(dtype=float)),errors='coerce').fillna(0).clip(lower=0)
counts = pd.to_numeric(df.get('Anzahl je Box',pd.Series(dtype=float)),errors='coerce').fillna(0).clip(lower=0)
material = float((prices*counts).sum())
# Gross sale price needed for target contribution margin on net sales, assuming fee as percent of gross sales.
net_factor = 1/(1+vat/100)
fee_factor = payment_fee/100
required_gross = (material+extra) / ((1-margin/100)*net_factor-fee_factor) if (1-margin/100)*net_factor>fee_factor else float('inf')
left = budget-material
c1,c2,c3,c4 = st.columns(4)
c1.metric('Material / Box',f'CHF {material:.2f}')
c2.metric('Material für Auftrag',f'CHF {material*qty:.2f}')
c3.metric('Restbudget / Box',f'CHF {left:.2f}')
c4.metric('Min. Verkaufspreis brutto*',f'CHF {required_gross:.2f}' if required_gross != float('inf') else 'Nicht möglich')
if left < 0: st.error('Materialbudget überschritten.')
else: st.success('Materialbudget rechnerisch eingehalten – Verfügbarkeit und Nebenkosten noch prüfen.')
st.caption('*Vereinfachte Kalkulation: Materialpreise ohne Vorsteuerkorrektur, variable Zusatzkosten netto, Zahlungsgebühr auf Bruttoverkauf, Zielmarge auf Nettoerlös. Kein bestätigter Endverkaufspreis.')

st.subheader('2 · Produktgetreue Bildübersicht')
st.caption('Die Vorschau zeigt ausschließlich die Originalbilder der eingetragenen URLs. Fehlt ein Bild, wird bewusst kein Ersatzprodukt erfunden.')
cols = st.columns(3)
for i, (_, r) in enumerate(df.iterrows()):
    with cols[i%3]:
        st.markdown(f"**{str(r.get('Produkt','Artikel'))}**")
        url = str(r.get('Originalbild-URL','') or '').strip()
        if url.startswith('https://'):
            st.image(url, use_container_width=True)
        else:
            st.warning('Originalfoto fehlt')
        link = str(r.get('Produktlink','') or '').strip()
        if link.startswith('https://'): st.link_button('Zum Händler',link)
        st.caption(f"CHF {float(pd.to_numeric(r.get('Stückpreis CHF',0),errors='coerce') or 0):.2f} · {r.get('Verfügbarkeit für Gesamtmenge','Ungeprüft')}")

st.subheader('3 · Export für Einkauf und Shopify-Vorbereitung')
out = df.copy()
out['Gesamtmenge'] = counts.astype(int)*qty
out['Gesamtkosten CHF'] = (prices*counts*qty).round(2)
st.download_button('Einkaufsliste als CSV',out.to_csv(index=False).encode('utf-8-sig'),file_name='productcreator_einkaufsliste.csv',mime='text/csv')
report = {'produktidee':idea,'budget_pro_box_chf':budget,'boxen':qty,'zielmarge_prozent':margin,'material_pro_box_chf':round(material,2),'material_gesamt_chf':round(material*qty,2),'mindestens_verkaufspreis_brutto_chf':round(required_gross,2) if required_gross!=float('inf') else None,'recherche_status':'manuell erfasste Angebote; nicht live verifiziert','erstellt_utc':datetime.now(timezone.utc).isoformat(),'artikel':out.fillna('').to_dict(orient='records')}
st.download_button('Projekt als JSON',json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8'),file_name='productcreator_projekt.json',mime='application/json')
st.caption('Nächste Ausbaustufe: Such-API, Händlerquellen, Bildabgleich, optimierte Produktauswahl und Shopify-Entwürfe. Keine Zugangsdaten im Quellcode speichern.')
