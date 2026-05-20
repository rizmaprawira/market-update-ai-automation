# Knowledge Base: Reinsurance Agent (English)
> This file is the primary knowledge base for the Reinsurance Analyst Agent in the RIU Market Update Automation system.  
> Sources: UU No. 40/2014, POJK 14/2015 (amended 19/2019, 39/2020), IFG Progress ECO Bulletin No. 16 (Reinsurance 101), CGI-001, OJK Roadmap 2023–2027.

---

## 1. Agent Role

This agent analyzes the financial and business condition of **reinsurance companies** in Indonesia for monthly market update reports. The agent must **never fabricate data**. All analysis must be explicitly sourced from available Excel or PDF files.

---

## 2. Definition and Concept of Reinsurance

**Reinsurance (Reasuransi)** is an agreement between an insurance company (ceding company) and a reinsurance company (reinsurer/reassurer), where the ceding company agrees to transfer part or all of the risks it has assumed to the reinsurer. The reinsurer accepts a proportion of the premium and agrees to bear the same proportion of any resulting claims.

**Reinsurance Business (Usaha Reasuransi)** under UU No. 40/2014: The business of providing risk retrocession services for risks borne by insurance companies, guarantee companies, or other reinsurance companies.

---

## 3. Functions and Benefits of Reinsurance for Insurance Companies

1. **Increase risk acceptance capacity**: Insurers can accept risks far exceeding their own capital capacity.
2. **Maintain financial stability**: Reduces claim volatility by sharing risk with the reinsurer.
3. **Support business expansion**: Uncertainty reduced; insurers more willing to enter new lines.
4. **Catastrophe protection**: Protects against very large single-event losses.
5. **Risk spreading**: Distributes risk across a wider market.

---

## 4. Five Parties in the Reinsurance Business

| Party | Role |
|-------|------|
| Insured | Individual or company buying insurance |
| Direct Insurer | Primary insurer; accepts risk from the insured |
| Ceding Company | Insurance company placing reinsurance |
| Reinsurer (Reasuradur) | Accepts a portion of risk from the ceding company |
| Retrocedent & Retrocessionaire | Reinsurer ceding risk to another reinsurer |
| Reinsurance Broker | Intermediary between ceding company and reinsurer |

---

## 5. Reinsurance Methods and Forms

### 5.1 By Method

#### Treaty (Automatic)
- A written contract covering a defined portfolio of business.
- Ceding company automatically cedes; reinsurer automatically accepts risks falling within agreed criteria.
- Typically annual (12-month) contracts.
- **More administratively efficient** — no negotiation per risk.

#### Facultative (Case by Case)
- Each risk is individually offered and negotiated.
- Ceding company is free to offer or not; reinsurer is free to accept or decline.
- Used for risks outside treaty capacity, risks excluded from treaty, or unusually large/complex risks.

### 5.2 By Form

#### Proportional
Ceding company and reinsurer share premiums and claims based on agreed proportions.

**a. Quota Share Treaty**
- Fixed proportion of every risk in the portfolio is ceded.
- Example: 40% cedant, 60% reinsurer → all premium and claims split accordingly.
- Advantage: Simple, even protection across portfolio.
- Disadvantage: Does not protect against large individual claims (gross loss ratio = net loss ratio).

**b. Surplus Treaty**
- Reinsurer accepts risk in excess of the ceding company's retention (net line).
- Retention stated in "lines" (1 line = own retention amount).
- Example: Retention IDR 250 million + 4 lines surplus = maximum capacity IDR 1.25 billion.
- Advantage: Greater capacity than quota share; retention can be set differently by risk type.
- Disadvantage: More complex administration.

**c. Facultative Obligatory (Fac-Ob)**
- Ceding company is free to offer; reinsurer is obligated to accept.
- Hybrid between facultative and treaty.

#### Non-Proportional
No fixed proportional sharing. Reinsurer pays only when claims exceed a trigger threshold.

**a. Excess of Loss (XoL)**
- Reinsurer pays claims exceeding the ceding company's net retention up to the agreed limit.
- Can be structured in multiple **layers** for greater capacity.
- Example:
  - Layer 1: Cover limit IDR 1 billion xs IDR 250 million
  - Layer 2: Cover limit IDR 2 billion xs IDR 1.25 billion

**b. Stop Loss**
- Protects the ceding company against aggregate losses exceeding a specified percentage of premiums.
- Expressed as a loss ratio trigger.

---

## 6. Reinsurance-Specific Terminology

| Term (Indonesian) | English | Explanation |
|-------------------|---------|-------------|
| Sesi / Cession | Cession | Portion of risk/premium transferred to reinsurer |
| Retensi | Retention | Portion of risk kept by ceding company |
| Retensi Sendiri | Own Retention | Risk retained by a single company without further sharing |
| Line | Line | Amount equal to ceding company's retention; reinsurer may accept multiple lines |
| Limit | Limit | Maximum amount reinsurer can accept per class of business |
| Retrosesi | Retrocession | Risk transfer from one reinsurer to another |
| Retrocessionaire | Retrocessionaire | Reinsurer's reinsurer |
| Reciprocity | Reciprocity | Mutual cession exchange arrangements |
| Reinsurance Commission | Reinsurance Commission | Commission paid by reinsurer to ceding company as % of ceded premium |
| Profit Commission | Profit Commission | Reinsurer's profits returned to ceding company |
| Pools | Pools | Group arrangement where multiple insurers/reinsurers share a specific class of risk |

---

## 7. Key Financial Metrics for Reinsurance Analysis

### 7.1 Premium (Gross vs. Net)
```
Gross Premium = Total premiums received from ceding companies (before retrocession)
Net Premium = Gross Premium − Retrocession Premium
```

### 7.2 Underwriting Result (Hasil Underwriting)
```
Underwriting Result = Net Premium − Claims − Commissions − Operating Expenses
```
**Indonesian context**: Indonesian reinsurance underwriting results have shown a **negative trend** over the past 5 years (2016–2021), with a CAGR of −184%. Claims grew faster (~19%/year) than premium growth (~11%/year).

### 7.3 Net Claims (Beban Klaim Neto)
```
Net Claims = Gross Claims − Retrocession Recoveries
```

### 7.4 Loss Ratio
```
Loss Ratio = Net Claims / Net Premium × 100%
```
Reinsurance loss ratios tend to be more volatile than primary insurance due to exposure to large and catastrophic events.

### 7.5 Combined Ratio (COR)
```
COR = Loss Ratio + Commission Ratio + Expense Ratio
```

### 7.6 Investment Income
- Critical buffer against negative underwriting results.
- Indonesian reinsurance investment assets dominated by: time deposits (37%), bonds (32%), mutual funds (18%), equities (3%).
- Trend: Reinsurance investment income still positive and growing ~10%/year (CAGR 2016–2021).

### 7.7 Risk Based Capital (RBC)
- OJK minimum: 120%.
- Reinsurers have a more volatile risk profile → strong capital is even more critical.

### 7.8 Cession Rate
```
Cession Rate = Reinsurance Premiums Received / Total Industry Insurance Premium
```
In Indonesia: general insurance cession rate >> life insurance cession rate (~50%+ vs ~3%).

### 7.9 Asset Structure
- Investment assets: ~57% of total assets
- Non-investment assets: ~43%
- Indonesian reinsurance assets = only ~2% of total insurance industry assets (very small).

### 7.10 Technical Reserves
Key components:
- Claims reserve: ~48% of total technical reserves
- UPR (Unearned Premium Reserve): ~29%
- Premium reserve and catastrophe reserve: remainder

---

## 8. Indonesian Reinsurance Market Context

### 8.1 Market Structure (2016–2022)
- Number of conventional reinsurance companies: **6–7**
- All state-owned or domestic private (no joint ventures)
- Market leader: PT Reasuransi Indonesia Utama (IndonesiaRe, BUMN)
- Total reinsurance assets (end 2022): ~IDR 34 trillion (+12% CAGR 5 years)
- Reinsurance premium dominated by general insurance (~70% of total reinsurance premium)
- Number of reinsurance brokers: ~42 (7× the number of reinsurers)

### 8.2 Structural Issues
- **Low domestic capacity**: Only 6–7 companies for a trillion-rupiah market → high offshore reinsurance ratio (0.11% of GDP, same level as Germany which has 29 reinsurers).
- **Broker dependence**: Reinsurance broker commissions grew at 21%/year vs. premium growth of 10%/year (2017–2021).
- **Low domestic market share**: Indonesian reinsurers handle far less risk than offshore counterparts.

### 8.3 Global Reinsurance Market (Context)
- Global reinsurance market: USD 262 billion net premium (top 50 companies, 2020).
- Non-life dominates: 66% of global premiums.
- Europe dominates: 50% of global premiums.
- Top 3 global reinsurers: Munich Re (16%), Swiss Re (13%), Hannover Re (10%).
- 10-year global reinsurance premium CAGR: 4.8% (higher than global insurance CAGR of 3.8%).

### 8.4 Treaty vs. Facultative Composition in Indonesia
- Treaty dominates (~70% of total reinsurance portfolio over the past 10 years).
- Exception: Aviation is dominated by facultative (very high per-event risk).

---

## 9. Indonesian Reinsurance Regulation

| Regulation | Key Content |
|------------|-------------|
| UU No. 40/2014 Article 2(3) | Reinsurance companies may only conduct reinsurance business |
| POJK No. 14/2015 | Mandatory 100% domestic reinsurance support (minimum 2 domestic reinsurers) |
| POJK No. 19/2019 (Amendment 1) | Added definitions for automatic (treaty) reinsurance support and simple risks |
| POJK No. 39/2020 (Amendment 2) | Offshore reinsurance only from countries with bilateral trade agreements with Indonesia |
| SEOJK No. 31/2015 | Own retention limits, reinsurance support levels, and OJK reporting requirements |
| POJK 23/2023 | Reinsurance business licensing |

### 9.1 Mandatory Domestic Reinsurance Support
Under POJK 14/2015 and amendments:
- Insurance companies must seek 100% domestic reinsurance support first (from at least 2 domestic reinsurers).
- Exceptions: worldwide products, products designed for multinationals, new products with foreign reinsurer development support.
- Offshore reinsurance only permitted from countries with bilateral agreements on cross-border supply of reinsurance services.

---

## 10. Analysis Framework

### 10.1 Key Monthly Questions
1. Is gross reinsurance premium growing or contracting?
2. How is the loss ratio trending? Are there large catastrophe claims distorting results?
3. Is the underwriting result positive or negative?
4. Can investment income compensate for any underwriting deficit?
5. What is the treaty vs. facultative composition?
6. Is RBC still above 120%?
7. What is the split between general insurance and life insurance premiums?

### 10.2 Red Flags
- Deepening underwriting deficit without investment income compensation
- Loss ratio consistently > 80%
- Single catastrophe loss affecting > 30% of premium
- RBC approaching or below 120%
- Very high retrocession dependence (> 40% of gross premium)
- Claims growing significantly faster than premiums

### 10.3 Positive Signals
- Premium growth supported by new business expansion
- Improving (less negative) underwriting result
- Diversification across lines and geographies
- Stable, positive investment income
- RBC well above 120%
- Competitive reinsurance commission rates attracting more cessions

---

## 11. Commentary Style Guide

### 11.1 Language and Tone
- Output language: **Bahasa Indonesia** — formal, professional, precise
- Include specific numbers with MoM and YoY comparisons
- Provide context: global reinsurance market conditions, interest rate environment, catastrophe events
- Reference specific companies

### 11.2 Example of Good Commentary
> "PT Reasuransi Indonesia Utama mencatat pendapatan premi bruto Rp 3,2 triliun pada Q1 2026, tumbuh 7,8% dari Q1 2025 (Rp 2,97 triliun), terutama dari lini kebakaran dan rekayasa. Hasil underwriting masih defisit Rp 215 miliar, namun membaik dari defisit Rp 320 miliar Q1 2025. Beban klaim meningkat 12,3% akibat klaim kebakaran industri besar di Jawa Tengah. Pendapatan investasi Rp 380 miliar mampu mengkompensasi sebagian defisit, menghasilkan laba bersih Rp 145 miliar. RBC terjaga di 172%, di atas minimum OJK 120%."

### 11.3 What to Avoid
- ❌ Using figures without source reference
- ❌ Drawing trend conclusions from a single data point
- ❌ Citing figures not present in the source data files

---

## 12. Anti-Hallucination Instructions

1. **Use only data from provided files** in the data/ folder.
2. **Cite the source file name and sheet/tab** when referencing any number.
3. **If data is unavailable**, state "data not available for this period."
4. **Verify consistency**: gross premium − retrocession = net premium; net claims = gross claims − retrocession recoveries.
5. **Do not assume or estimate** missing figures.
6. **Flag discrepancies** between sources as "requires verification" rather than silently choosing one figure.
