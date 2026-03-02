# Fund Copilot — PDF Sourcing Guide

**Target: ~100 PDFs across 10 providers**

Save PDFs into `data/raw_pdfs/{provider}/` — e.g. `data/raw_pdfs/vanguard/`, `data/raw_pdfs/ishares/`, etc.

Name files clearly: `{fund_name}_{doc_type}.pdf` — e.g. `lifestrategy_60_factsheet.pdf`, `core_msci_world_kid.pdf`

---

## Provider 1: Vanguard UK (~15 docs)

**Document hub**: https://www.vanguardinvestor.co.uk/investment-information  
**Fund pages**: https://www.vanguardinvestor.co.uk/investments/all

**How to download**: Go to each fund page → scroll to "Documents" section → download Factsheet and KIID/KID.

**KIID direct URL pattern**: `https://fund-docs.vanguard.com/{isin_lowercase}-en.pdf`

| Fund | ISIN | Docs to grab |
|---|---|---|
| LifeStrategy 60% Equity | GB00B3TYHH97 | Factsheet + KIID |
| LifeStrategy 80% Equity | GB00B4PQW151 | Factsheet + KIID |
| LifeStrategy 100% Equity | GB00B41XG308 | Factsheet + KIID |
| FTSE Global All Cap Index | GB00BD3RZ582 | Factsheet + KIID |
| FTSE 100 Index Unit Trust | GB00B4M93C90 | Factsheet + KIID |
| S&P 500 UCITS ETF (VUSA) | IE00B3XXRP09 | Factsheet + KID |
| ESG Global All Cap UCITS ETF | IE00BNG8L278 | Factsheet + KID |
| **UK Domiciled Prospectus** | — | https://fund-docs.vanguard.com/uk-domiciled-prospectus.pdf |

**Target: ~15 PDFs (7 funds × 2 docs + 1 prospectus)**

---

## Provider 2: iShares / BlackRock UK (~15 docs)

**Document hub**: https://www.ishares.com/uk/individual/en/products/etf-investments  
**How to download**: Go to fund page → "Literature" tab → download Factsheet and KID

**Factsheet URL pattern**: `https://www.ishares.com/uk/individual/en/literature/fact-sheet/{ticker}-ishares-{fund-slug}-fund-fact-sheet-en-gb.pdf`  
**KID URL pattern**: `https://www.ishares.com/uk/individual/en/literature/kiid/kiid-ishares-{fund-slug}-gb-{isin}-en.pdf`

| Fund | Ticker | ISIN | Docs |
|---|---|---|---|
| Core MSCI World UCITS ETF | SWDA | IE00B4L5Y983 | Factsheet + KID |
| Core S&P 500 UCITS ETF | CSPX | IE00B5BMR087 | Factsheet + KID |
| Core FTSE 100 UCITS ETF | ISF | IE0005042456 | Factsheet + KID |
| Core MSCI EM IMI UCITS ETF | EIMI | IE00BKM4GZ66 | Factsheet + KID |
| Physical Gold ETC | IGLN | IE00B4ND3602 | Factsheet + KID |
| Global Clean Energy UCITS ETF | INRG | IE00B1XNHC34 | Factsheet + KID |
| MSCI World SRI UCITS ETF | SUSW | IE00BYX2JD69 | Factsheet + KID |

**Target: ~14 PDFs (7 funds × 2 docs)**

---

## Provider 3: HSBC (~10 docs)

**Fund hub**: https://www.assetmanagement.hsbc.co.uk/en/individual-investor/fund-centre  
**How to download**: Search fund → click into it → "Documents" tab → Factsheet + KIID

| Fund | Docs |
|---|---|
| FTSE All-World Index Fund | Factsheet + KIID |
| American Index Fund | Factsheet + KIID |
| European Index Fund | Factsheet + KIID |
| Japan Index Fund | Factsheet + KIID |
| Pacific Index Fund | Factsheet + KIID |

**Target: ~10 PDFs (5 funds × 2 docs)**

---

## Provider 4: Legal & General (L&G) (~10 docs)

**Fund hub**: https://fundcentres.lgim.com/uk/ad/fund-centre/  
**How to download**: Search fund → Documents section → Factsheet + KID

| Fund | Docs |
|---|---|
| Global Technology Index Fund | Factsheet + KID |
| International Index Trust | Factsheet + KID |
| UK Index Trust | Factsheet + KID |
| Global 100 Index Trust | Factsheet + KID |
| Commodity Composite | Factsheet + KID |

**Target: ~10 PDFs (5 funds × 2 docs)**

---

## Provider 5: Fidelity (~10 docs)

**Fund hub**: https://www.fidelity.co.uk/funds/  
**How to download**: Search fund → "Key documents" section → Factsheet + KID

| Fund | Docs |
|---|---|
| Index World Fund | Factsheet + KID |
| Global Technology Fund | Factsheet + KID |
| Sustainable Water & Waste Fund | Factsheet + KID |
| China Consumer Fund | Factsheet + KID |
| Global Industrials Fund | Factsheet + KID |

**Target: ~10 PDFs (5 funds × 2 docs)**

---

## Provider 6: Invesco (~10 docs)

**Fund hub**: https://www.invesco.com/uk/en/products.html  
**How to download**: Search fund → "Documents" tab → Factsheet + KID

| Fund | Docs |
|---|---|
| Physical Gold ETC (SGLD) | Factsheet + KID |
| EQQQ NASDAQ-100 UCITS ETF | Factsheet + KID |
| S&P 500 UCITS ETF | Factsheet + KID |
| Global Clean Energy UCITS ETF | Factsheet + KID |
| CoinShares Global Blockchain UCITS ETF | Factsheet + KID |

**Target: ~10 PDFs (5 funds × 2 docs)**

---

## Provider 7: WisdomTree (~8 docs)

**Fund hub**: https://www.wisdomtree.eu/en-gb/products  
**How to download**: Search product → "Documents" tab → Factsheet + KID

| Fund | Docs |
|---|---|
| Physical Gold (PHAU) | Factsheet + KID |
| Physical Silver (PHAG) | Factsheet + KID |
| Copper (COPA) | Factsheet + KID |
| Artificial Intelligence UCITS ETF (WTAI) | Factsheet + KID |

**Target: ~8 PDFs (4 funds × 2 docs)**

---

## Provider 8: VanEck (~8 docs)

**Fund hub**: https://www.vaneck.com/gb/en/  
**How to download**: Search ETF → "Documents" section → Factsheet + KID

| Fund | Docs |
|---|---|
| Gold Miners UCITS ETF (GDX) | Factsheet + KID |
| Semiconductor UCITS ETF (SMH) | Factsheet + KID |
| Crypto & Blockchain Innovators UCITS ETF (DAPP) | Factsheet + KID |
| Rare Earth & Strategic Metals UCITS ETF (REMX) | Factsheet + KID |

**Target: ~8 PDFs (4 funds × 2 docs)**

---

## Provider 9: HANetf (~6 docs)

**Fund hub**: https://www.hanetf.com/  
**How to download**: Find product → "Documents" → Factsheet + KID

| Fund | Docs |
|---|---|
| Sprott Uranium Miners UCITS ETF (URNM) | Factsheet + KID |
| The Royal Mint Responsibly Sourced Physical Gold ETC (RMAU) | Factsheet + KID |
| Solar Energy UCITS ETF (TANN) | Factsheet + KID |

**Target: ~6 PDFs (3 funds × 2 docs)**

---

## Provider 10: Active managers (~9 docs)

### Fundsmith
**Website**: https://www.fundsmith.co.uk/  
| Fund | Docs |
|---|---|
| Fundsmith Equity Fund | Factsheet + KID + Annual Report |

### Baillie Gifford
**Website**: https://www.bailliegifford.com/  
| Fund | Docs |
|---|---|
| Scottish Mortgage Investment Trust | Factsheet + KID |
| Global Discovery Fund | Factsheet + KID |

### Jupiter
**Website**: https://www.jupiteram.com/uk/en/individual/  
| Fund | Docs |
|---|---|
| India Fund | Factsheet + KID |

**Target: ~9 PDFs**

---

## Summary

| Provider | Funds | Docs | Running total |
|---|---|---|---|
| Vanguard | 7 + prospectus | ~15 | 15 |
| iShares | 7 | ~14 | 29 |
| HSBC | 5 | ~10 | 39 |
| L&G | 5 | ~10 | 49 |
| Fidelity | 5 | ~10 | 59 |
| Invesco | 5 | ~10 | 69 |
| WisdomTree | 4 | ~8 | 77 |
| VanEck | 4 | ~8 | 85 |
| HANetf | 3 | ~6 | 91 |
| Active (Fundsmith/BG/Jupiter) | 4 | ~9 | **~100** |

---

## Speed tips

1. **Do it provider by provider** — open the fund hub, open each fund in a new tab, download both docs, close tab, repeat. Each provider takes ~5 mins.
2. **Name files consistently** — `lifestrategy_60_factsheet.pdf`, `lifestrategy_60_kid.pdf`. The ingest pipeline will parse these.
3. **Don't worry about getting exact count** — anywhere from 80–120 is fine. More is better for testing.
4. **Prospectuses are gold** — grab the Vanguard UK one at minimum. These are 100+ page documents that really test the chunking pipeline.
5. **Annual reports** — grab the Fundsmith one if you can. It's a good narrative-heavy doc.

---

## Theme coverage check

| Theme | Covered by |
|---|---|
| Global equity | Vanguard All Cap, iShares MSCI World, HSBC All-World, Fidelity Index World |
| US equity | Vanguard S&P 500, iShares S&P 500, Invesco S&P 500 |
| UK equity | Vanguard FTSE 100, iShares FTSE 100, L&G UK Index |
| Europe | HSBC European Index, L&G International |
| Japan | HSBC Japan Index |
| Pacific / Asia | HSBC Pacific Index |
| Emerging markets | iShares EM IMI, Vanguard ESG Global |
| Technology | L&G Global Technology, Fidelity Global Technology |
| AI | WisdomTree AI UCITS ETF |
| Clean energy | iShares Global Clean Energy, Invesco Global Clean Energy |
| Gold | iShares Physical Gold, Invesco Physical Gold, WisdomTree Physical Gold, HANetf Royal Mint Gold |
| Silver / Copper | WisdomTree Physical Silver, WisdomTree Copper |
| Mining / Metals | VanEck Gold Miners, VanEck Rare Earth |
| Uranium | HANetf Sprott Uranium Miners |
| Semiconductors | VanEck Semiconductor |
| Blockchain / Crypto | VanEck Crypto & Blockchain, Invesco CoinShares Blockchain |
| Multi-asset | Vanguard LifeStrategy 60/80/100 |
| ESG / Sustainable | Vanguard ESG Global, iShares World SRI, Fidelity Sustainable Water |
| India | Jupiter India Fund |
| Active growth | Fundsmith Equity, Baillie Gifford Scottish Mortgage + Global Discovery |
