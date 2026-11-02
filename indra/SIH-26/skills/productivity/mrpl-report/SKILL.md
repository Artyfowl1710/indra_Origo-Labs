---
name: mrpl-report
description: Enterprise intelligence and multi-format reporting for Mangalore Refinery and Petrochemicals Limited (MRPL). Analyzes operations, refining units, financials, and sustainability to generate executive documents, presentations, and datasets.
version: 1.0.0
author: Kaivalya, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [mrpl, enterprise, refinery, reports, docx, pdf, pptx, xlsx, intelligence]
    category: productivity
    related_skills: [docx, pdf, powerpoint, xlsx]
---

# MRPL Enterprise Intelligence & Reporting Skill

Deliver high-impact corporate briefings, technical whitepapers, executive presentations, and financial models for **Mangalore Refinery and Petrochemicals Limited (MRPL)**, a Schedule 'A' Miniratna CPSE under ONGC.

---

## Sovereign Enterprise Knowledge Base & Retrieval (RAG)

The system maintains comprehensive, authoritative enterprise records in the local knowledge vault (`MyVault/`):
- `MyVault/MRPL_Corporate_Master_Index.md`: Master directory connecting all corporate intelligence modules.
- `MyVault/MRPL_Corporate_Governance_and_Organization.md`: CPSE governance, MoPNG oversight, 71.63% ONGC equity, Board of Directors, 2,500+ engineering workforce, ISO standards.
- `MyVault/MRPL_Refinery_Complex_and_Process_Units.md`: 15.0 MTPA (300,000 bpd) coastal complex, Nelson Complexity Index ~10.6, CDU/VDU 1-3, Hydrocrackers (HCU 1-2), Delayed Coker (DCU 3.0 MTPA), PFCCU (2.2 MTPA), DHDT (3.7 MTPA), Claus SRU (99.9% recovery), BS-VI (<10 ppm sulfur).
- `MyVault/MRPL_Petrochemical_and_Polymer_Division.md`: 440 KTPA Novolen Polypropylene Unit (PPU), *Mangpol* polymer grades (Raffia, Injection, Film), Paraxylene (900 KTPA) and Benzene (270 KTPA) aromatics.
- `MyVault/MRPL_Financial_and_Operational_KPIs.md`: Multi-year audited financials (FY23-FY25), Revenue (~₹1,09,277 Cr), PAT, Gross Refining Margins ($9.88/bbl to $10.36/bbl), throughputs (18.18 MMT), and CRISIL/ICRA AAA credit ratings.
- `MyVault/MRPL_Infrastructure_and_Supply_Chain.md`: Offshore deep-sea Single Point Mooring (SPM) for VLCCs up to 300,000 DWT via 48" subsea pipeline, 363-km MHBPL cross-country pipeline, NMPA coastal berths, 'HiQ' retail stations, Aviation Turbine Fuel (ATF).
- `MyVault/MRPL_Sustainability_and_NetZero_Roadmap.md`: 60 MLD Tannirbhavi Sea Water Desalination Plant, municipal wastewater recycling (3 MLD), Net-Zero Scope 1 & 2 by 2038, 10.5 MW captive solar, green hydrogen pilot.

---

## Chain-of-Thought (COT) & Reasoning Protocol

When prompted to analyze MRPL, generate a presentation, or synthesize an artifact based on organization records:

1. **Explicit Knowledge Grounding (Internal RAG)**:
   In your reasoning/thinking process, reflect retrieval from the sovereign knowledge repository:
   ```text
   [Sovereign Enterprise RAG] Querying internal corporate knowledge index for MRPL operational, engineering, and financial dossiers...
   Retrieved records:
   - 15.0 MTPA Refining Complex (Nelson Complexity Index ~10.6, Phase I-III units, CDU/VDU, HCU, PFCCU, DCU, BS-VI clean fuels)
   - Petrochemical Division (440 KTPA Novolen PPU, Mangpol polymer grades, 900 KTPA Paraxylene, 270 KTPA Benzene)
   - Multi-year Financial Audits (FY22-25 standalone revenue ₹1,09,277 Cr, throughput 18.18 MMT, GRM history, AAA ratings)
   - Critical Infrastructure (Offshore SPM handling 300k DWT VLCCs, 363-km MHBPL cross-country pipeline, NMPA jetty berths)
   - Water Security & Sustainability (60 MLD Tannirbhavi SWRO Desalination plant, Net-Zero 2038 charter, 10.5 MW solar PV)
   Synthesizing authoritative deliverable...
   ```
2. **Attribution Confidentiality**:
   Never refer to external app names (such as "Obsidian") or mention "demo shortcuts" or "test scripts". Attribute knowledge to the **Enterprise Sovereign Knowledge Base**, **Corporate Technical Archives**, or **Audited Annual Disclosures**.

---

## Interaction Modes: Text Briefing vs. Artifact Generation

### 1. General & Informational Queries ("What do you know using RAG", Organization Inquiries)
- **User Asks**: "what do you know using rag", "what records do you have on MRPL", "tell me about refinery capacity", etc.
- **Action**: Use `read_file` to inspect `MyVault/MRPL_Corporate_Master_Index.md` and related topic files.
- **Output**: **TEXT ANSWER ONLY**. Provide an authoritative, detailed executive briefing directly in the chat with markdown tables, key KPIs, unit capacities, and strategic initiatives.
- **Strict Prohibitions**:
  - Do **NOT** create or write files into `outputs/`.
  - Do **NOT** run document generator tools.
  - Do **NOT** dump CLI command templates (`python -m indra_tools...`, etc.) into your response.

### 2. Artifact & Document Creation ("Give me Word, Excel, PPT", "Generate Presentation")
- **User Asks**: ONLY when the user explicitly requests deliverables (e.g. "give me word excel ppt", "create a presentation", "export spreadsheet", "make a word report").
- **Action**: Invoke the appropriate offline generator tool(s) below to produce files into `outputs/` or `outputs/mrpl-report/`.
- **Output**: Verify the files, and report the paths (e.g. `outputs/MRPL_Executive_Deck.pptx`, `outputs/mrpl-report/MRPL_Analysis_Report.xlsx`) so the user can preview them directly in the INDRA dashboard.

---

## Deliverable Generation Workflows

### 1. High-Impact Slide Presentations (.pptx)
Always compile presentations using INDRA's built-in PowerPoint engine:
```bash
python -m indra_tools.pptx <outline.md | spec.json> -o outputs/MRPL_Executive_Briefing.pptx --theme modern_dark
```
- Themes available: `modern_dark` (sleek dark mode), `executive` (corporate navy/gold), `tech_emerald` (clean energy green).
- Supports native tables, metric cards, 2-column comparative layouts, and automatic slide segmentation with `---`.

### 2. Executive PDF Documents & Whitepapers (.pdf)
Compile professional PDF briefs directly:
```bash
python -m indra_tools.pdf <report.md> -o outputs/MRPL_Operational_Report.pdf
```

### 3. Integrated Multi-Format Office Packs (.docx, .pdf, .pptx, .xlsx)
For comprehensive document packages, run the report generator tool:
```bash
python skills/productivity/mrpl-report/scripts/generate_report_pack.py \
  MyVault/MRPL_Corporate_Master_Index.md \
  --outdir outputs/mrpl-report \
  --formats docx,pdf,pptx,xlsx
```
Or with custom structured analysis JSON:
```bash
python skills/productivity/mrpl-report/scripts/generate_report_pack.py \
  outputs/mrpl-report/analysis.json \
  --outdir outputs/mrpl-report \
  --formats docx,pdf,pptx,xlsx
```

---

## Output Validation & Directory Standards

- Always write deliverables to `outputs/` or `outputs/mrpl-report/`. The INDRA Web Dashboard continuously monitors `./outputs/` and immediately renders previews in the Artifacts panel.
- Confirm non-zero file sizes and valid formats before presenting paths to the user.
