# Deploying the FixedFloat migration on Railway

This release switches the crypto swap flow from SimpleSwap to **FixedFloat (ff.io)**
and adds the FixedFloat data-retention/compliance layer. Follow these steps to
update the running Railway service.

## 0. Before you deploy

- [ ] **Verify FixedFloat currency codes.** The `FF_CCY` map in
  `services/fixedfloat.py` is best-effort. With your keys set locally, run:
  ```bash
  python -m scripts.ff_ccies
  ```
  and correct any code that doesn't match FixedFloat's real `/ccies` output.
- [ ] Run the tests: `python -m pytest -q` (should be all green).

## 1. Environment variables (Railway → your service → Variables)

Add / confirm these:

| Variable | Notes |
|---|---|
| `FIXEDFLOAT_API_KEY` | **New.** From your FixedFloat account. |
| `FIXEDFLOAT_API_SECRET` | **New.** From your FixedFloat account. |
| `DB_PATH` | **New.** Set to a path on a persistent volume, e.g. `/data/swaps.db` (see step 2). |
| `BOT_TOKEN` | Existing. |
| `ADMIN_ID` | Existing. Single admin who can access customer records. |
| `WEBHOOK_HOST` | Existing, e.g. `tg-swap-bot-production.up.railway.app`. |
| `WEBHOOK_PATH` | Existing, e.g. `/webhook`. |
| `PUBLIC_CHANNEL_ID` / `PRIVATE_CHANNEL_ID` | Existing. **PRIVATE channel must be private** — it receives user_id/username. |
| `SIMPLESWAP_API_KEY` | Keep only if you still use the (hidden) "Buy with card" flow. |

> Do **not** rely on the committed `.env`. Secrets belong in Railway Variables.

## 2. Persistent storage (REQUIRED — otherwise data is lost on every deploy)

Railway's container filesystem is **ephemeral**. Without a volume the SQLite
database is wiped on each redeploy — which loses all order records and breaks the
≥1-year retention requirement.

1. Railway → your service → **Volumes** → **New Volume**.
2. Mount path: `/data`.
3. Set `DB_PATH=/data/swaps.db` (step 1).
4. (Optional) To carry over existing records, upload the current `swaps.db` into
   the volume once (Railway shell / `railway run`).

## 3. Deploy

Railway builds from `requirements.txt` (nixpacks) and runs the start command
`python main.py`. Push the merged branch (or connect the PR) and let Railway
redeploy. Confirm in **Settings** that the start command is `python main.py`.

## 4. Post-deploy checks

- [ ] Logs show: `Database initialized`, `Background swap checker started`,
  `Webhook set: …`.
- [ ] `/start` works; the "💳 Buy with card" button is gone (FixedFloat is
  crypto-only; the fiat code stays in the repo, just unlinked).
- [ ] Do **one small real swap** end-to-end: create → send deposit → status
  updates to `finished`. This is the only way to validate the live FixedFloat
  integration (it can't be tested offline).
- [ ] As admin: **🔎 Find by Order ID** returns the Telegram user record for a
  FixedFloat order ID, and **🛡 Access log** shows the lookup.
- [ ] `/privacy` shows the Privacy Policy.

## 5. Security follow-ups (do these once)

- [ ] **Rotate secrets** that were committed to git history: `BOT_TOKEN`
  (via @BotFather) and `SIMPLESWAP_API_KEY`.
- [ ] Stop tracking secrets/data/venv in git (a `.gitignore` is now included):
  ```bash
  git rm -r --cached venv .env swaps.db logs/bot.log
  git rm -r --cached $(git ls-files '*.pyc' '__pycache__')
  git commit -m "chore: stop tracking venv/secrets/db"
  ```
- [ ] Ensure the private monitoring channel is actually private.

## Rollback

The FixedFloat client is additive; `services/simpleswap.py` is untouched. To roll
back, revert this branch — the SimpleSwap-based flow returns as-is.
