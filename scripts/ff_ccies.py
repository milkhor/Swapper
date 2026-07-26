"""
Dump the currency codes FixedFloat actually supports, so FF_CCY in
services/fixedfloat.py can be verified/corrected.

Usage (with FIXEDFLOAT_API_KEY / FIXEDFLOAT_API_SECRET set in .env):
    python -m scripts.ff_ccies
    python -m scripts.ff_ccies btc usdt   # filter by substring
"""
import asyncio
import sys

from services.fixedfloat import list_currencies


async def main():
    filters = [a.lower() for a in sys.argv[1:]]
    ccies = await list_currencies()
    if not ccies:
        print("No currencies returned — check API key/secret and network.")
        return
    print(f"{len(ccies)} currencies\n")
    print(f"{'code':<16}{'network':<12}{'coin':<8}name")
    print("-" * 60)
    for c in ccies:
        code = str(c.get("code", ""))
        network = str(c.get("network", ""))
        coin = str(c.get("coin", ""))
        name = str(c.get("name", ""))
        blob = f"{code} {network} {coin} {name}".lower()
        if filters and not any(f in blob for f in filters):
            continue
        print(f"{code:<16}{network:<12}{coin:<8}{name}")


if __name__ == "__main__":
    asyncio.run(main())
