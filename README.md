# Marvel Tracker

Tracker responsive per film e serie Marvel, con progressi personali sincronizzati tramite Firebase e catalogo JSON valido.

## Funzionalità

- Ordine Marvel e ordine di uscita.
- Ricerca e filtri Film / Serie.
- Progressi salvati nel database Firebase per codice profilo.
- Novità recenti ricercate tramite Gemini 3.5 Flash-Lite con Google Search grounding.
- Link alle fonti restituite da Google Search; le sezioni curate manualmente non vengono riscritte dall'AI.
- Aggiornamento e pubblicazione programmati tramite GitHub Actions e GitHub Pages.

## Configurazione richiesta

### 1. Aggiungi la chiave Gemini ai Secrets

1. Apri **Settings → Secrets and variables → Actions** nel repository.
2. Premi **New repository secret**.
3. Nome: `GEMINI_API_KEY`.
4. Valore: la chiave API creata in [Google AI Studio](https://aistudio.google.com/apikey).

Non inserire mai la chiave in `index.html`, in un file JSON o in un commit. Il segreto viene usato esclusivamente dal workflow GitHub Actions. Il modello predefinito è `gemini-3.5-flash-lite`.

### 2. Abilita GitHub Pages

1. Apri **Settings → Pages**.
2. In **Build and deployment → Source**, scegli **GitHub Actions**.
3. Dopo aver unito il ramo di lavoro in `main`, apri **Actions** e avvia manualmente **Marvel Tracker - aggiornamento e pubblicazione** con **Run workflow**.

Il workflow è programmato ogni giorno alle **05:17 UTC** e può essere avviato manualmente. Quando l'aggiornamento riesce, pubblica il sito e salva il catalogo aggiornato nel repository.

### 3. Verifica Firebase

Il frontend usa il progetto Firebase già configurato nel repository. Controlla in Firebase Console → Realtime Database → Rules che gli utenti possano leggere e aggiornare solo il proprio profilo. Il codice profilo a sei caratteri è un identificatore semplice, non un sistema di autenticazione forte: non archiviare dati sensibili. Le configurazioni Firebase client sono visibili nel browser; la sicurezza dipende dalle regole del database.

## Come funziona l'aggiornamento

- Lo script invia a Gemini una richiesta di ricerca con Google Search grounding.
- Le notizie vengono visualizzate in una sezione separata con fonti cliccabili.
- I nuovi titoli proposti sono isolati in **Nuovi titoli** e marcati come **da verificare**; non modificano automaticamente l'ordine curato.
- Gli URL accettati sono limitati a quelli effettivamente restituiti dai metadati di grounding.
- In caso di errore API o JSON non valido, lo script fallisce senza sostituire il catalogo con dati vuoti.

Google Search grounding può avere limiti o costi in base al progetto e al numero di query generate. Controlla l'utilizzo nella console Google AI.

## Test locale

Richiede Python 3.12 o successivo:

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m http.server 8000
```

Poi visita http://localhost:8000. Il caricamento JSON non funziona correttamente aprendo direttamente il file con doppio clic.

## Struttura

```text
index.html
data/marvel.json
scripts/update_marvel.py
tests/test_update_marvel.py
requirements.txt
.github/workflows/pages.yml
```
