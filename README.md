# SAR Interactive Model

Streamlit app for exploring how Signed Annual Revenue (SAR) changes when you adjust sales levers.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Open the URL shown in the terminal (usually `http://localhost:8501`).

## Update baseline values

Edit [`baseline.json`](baseline.json):

- `levers` — starting slider positions and reset values
- `slider_ranges` — min, max, step for each slider
- Fixed inputs — headcounts, lead counts, conversion rate, price per rooftop

Restart the app after saving changes.

## Deploy for a client link (Streamlit Cloud)

1. Push this folder to a GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo.
3. Set the main file to `app.py`.
4. Share the generated URL with your client.

## Model logic

- **SAR** = total rooftops × price per rooftop ($6,500 default)
- **Dealer** = (# dealers × active dealer rate) × ((dealer leads + GP leads) × conversion rate)
- **Inside Sales** = # leads × (SDR productivity × # SDRs)
- **Field** = (# field reps × active rate) × rooftops per rep
