# Marvel Tracker

Tracker responsive per film e serie Marvel, con progressi personali sincronizzati tramite Firebase e catalogo JSON valido.

## Funzionalità

- Ordine Marvel e ordine di uscita.
- Ricerca e filtri Film / Serie.
- Autenticazione anonima Firebase e progressi salvati per UID autenticato.
- Importazione dei progressi da un profilo legacy con codice a sei caratteri.
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

### 3. Firebase Authentication e migrazione dei profili

1. In Firebase Console → **Authentication → Sign-in method**, abilita **Anonymous**.
2. La nuova versione crea/riusa un'identità anonima persistente nel browser e salva i progressi in users/<auth.uid>/progress.
3. Per importare un profilo precedente, usa **Importa progressi esistenti** oppure lascia che l'app provi a importare il vecchio codice salvato nel browser.
4. Il file database.rules.json contiene le regole restrittive per i profili associati a UID autenticati.

**Non pubblicare ancora le regole restrittive.** Prima occorre completare e verificare la migrazione dei profili legacy. Le regole attuali consentono lettura e scrittura pubbliche, e il vecchio codice a sei caratteri non dimostra la proprietà del profilo: chiunque conosca o indovini il codice potrebbe importare quei progressi. La migrazione client è una misura transitoria, non una verifica sicura della proprietà. Per un cutover senza questa finestra di rischio, serve una procedura amministrativa fidata (ad esempio uno script Admin SDK eseguito dal proprietario del progetto) per associare i dati ai nuovi UID.

Le regole restrittive impediscono l'accesso ai vecchi percorsi users/<codice> dopo il cutover; non applicarle finché non è stata decisa e verificata la strategia per i profili che non hanno ancora migrato. L'autenticazione anonima è legata al browser/dispositivo e non permette da sola il recupero dell'account su un altro dispositivo.

Le configurazioni Firebase client sono visibili nel browser; la sicurezza effettiva dipende dalle regole del database.

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
