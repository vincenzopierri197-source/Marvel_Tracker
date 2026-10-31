const {onCall, HttpsError} = require("firebase-functions/v2/https");
const {initializeApp} = require("firebase-admin/app");
const {getAuth} = require("firebase-admin/auth");
const {getDatabase} = require("firebase-admin/database");
const {createHash, randomInt} = require("node:crypto");

initializeApp({databaseURL: "https://marvel-tracker-c2402-default-rtdb.europe-west1.firebasedatabase.app"});
const db = getDatabase();
const CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const CODE_LENGTH = 6;
const WINDOW_MS = 15 * 60 * 1000;
const MAX_ATTEMPTS = 8;

function makeCode() {
  let value = "";
  for (let i = 0; i < CODE_LENGTH; i++) value += CHARS[randomInt(CHARS.length)];
  return value;
}

exports.createProfileCode = onCall({region: "europe-west1", maxInstances: 10}, async (request) => {
  if (!request.auth) throw new HttpsError("unauthenticated", "Accedi prima di creare il profilo.");
  const uid = request.auth.uid;
  const userRef = db.ref("users/" + uid);
  const existing = await userRef.child("profileCode").get();
  if (existing.exists()) return {code: existing.val()};

  for (let attempt = 0; attempt < 12; attempt++) {
    const code = makeCode();
    const mappingRef = db.ref("profileCodes/" + code);
    const result = await mappingRef.transaction(current => current === null ? {
      uid,
      createdAt: new Date().toISOString()
    } : undefined);
    if (!result.committed) continue;
    await userRef.child("profileCode").set(code);
    return {code};
  }
  throw new HttpsError("resource-exhausted", "Non riesco a generare un codice ora. Riprova.");
});

exports.recoverProfileWithCode = onCall({region: "europe-west1", maxInstances: 10}, async (request) => {
  const rawCode = request.data && request.data.code;
  if (typeof rawCode !== "string" || !/^[A-HJ-NP-Z2-9]{6}$/i.test(rawCode.trim())) {
    throw new HttpsError("invalid-argument", "Inserisci un codice valido di 6 caratteri.");
  }

  const ip = request.rawRequest && request.rawRequest.ip || "unknown";
  const bucket = createHash("sha256").update(ip).digest("hex").slice(0, 32);
  const attemptRef = db.ref("recoveryRateLimits/" + bucket);
  const now = Date.now();
  const rate = await attemptRef.transaction(current => {
    if (!current || now - current.windowStart >= WINDOW_MS) {
      return {windowStart: now, count: 1};
    }
    if (current.count >= MAX_ATTEMPTS) return;
    return {...current, count: current.count + 1};
  });
  if (!rate.committed) {
    throw new HttpsError("resource-exhausted", "Troppi tentativi. Attendi 15 minuti e riprova.");
  }

  const code = rawCode.trim().toUpperCase();
  const snapshot = await db.ref("profileCodes/" + code + "/uid").get();
  if (!snapshot.exists() || typeof snapshot.val() !== "string") {
    throw new HttpsError("not-found", "Codice non valido o non trovato.");
  }

  const uid = snapshot.val();
  const userSnapshot = await db.ref("users/" + uid).get();
  if (!userSnapshot.exists()) throw new HttpsError("not-found", "Profilo non trovato.");
  const customToken = await getAuth().createCustomToken(uid);
  return {customToken};
});
