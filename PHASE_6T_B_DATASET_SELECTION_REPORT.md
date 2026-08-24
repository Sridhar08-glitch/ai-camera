# PHASE 6T-B — DATASET SELECTION REPORT (GATE D)

**Purpose:** find the strongest zero-cost, internet-available traffic/vehicle datasets whose
**verified primary terms** permit our intended **commercial** training (attribution accepted),
and prepare the Gate D unblock. **No training started; no large data downloaded.**
**Date:** 2026-07-16

> **Key result:** two real fixed-CCTV traffic datasets are primary-verified **CC BY 4.0**
> (commercial use with attribution) → **Gate D can be unblocked pending explicit human approval.**

---

## 1. RESEARCH METHODOLOGY
Discovery via web search; **final classification only from primary/official sources** actually
fetched this session (official publisher repos + LICENSE frontmatter). Attribution-based
commercial licenses (CC BY, CC0, government open licenses) are **acceptable** per this task;
NC/ND/research-only remain excluded; ShareAlike is analyzed separately. Where a primary source
could not be fetched, the dataset stays **YELLOW** (never inferred RED/GREEN from secondary).

## 2. PRIMARY SOURCES CHECKED (this session)
- ✅ **UVH-26** — `huggingface.co/datasets/iisc-aim/UVH-26/raw/main/README.md` (official AIM@IISc release): `license: cc-by-4.0`.
- ✅ **BMD-45** — `huggingface.co/datasets/iisc-aim/BMD-45/raw/main/README.md` (official AIM@IISc release): `license: cc-by-4.0`.
- ✅ **DSEC dsec-det code** — `raw.githubusercontent.com/uzh-rpg/dsec-det/master/LICENSE`: **GPL-3.0** (code only).
- ⚠ DSEC **dataset** license (CC BY-SA 4.0): secondary (search) + UZH site reachable but license not in fetched HTML → treat as strong-secondary, re-verify page.
- ⚠ Open Images (Google) reachable (prior sessions); COCO home reachable (JS terms); Canada open-gov portal + most other dataset domains NOT fetchable this session → YELLOW.

## 3. DATASET RIGHTS TABLE (primary-verified rows marked ✅)
| Dataset | Publisher | Primary src | License | code | images | annots | Commercial | ML-train | Attrib | ShareAlike | Class |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **UVH-26** ✅ | AIM@IISc | HF repo | **CC BY 4.0** | — | ✅ | ✅ | **YES** | yes | required | no | **GREEN** |
| **BMD-45** ✅ | AIM@IISc | HF repo | **CC BY 4.0** | — | ✅ | ✅ | **YES** | yes | required | no | **GREEN** |
| DSEC-Detection | UZH RPG | site/GH | dataset **CC BY-SA 4.0**; code GPL-3 ✅ | GPL-3 | CC BY-SA | CC BY-SA | yes | yes | required | **YES** | **GREEN-CONDITIONAL** |
| Open Images V7 | Google | Google ✅ | annots CC BY 4.0; images per-image CC | — | per-image | CC BY 4.0 | filtered | yes | required | no | **GREEN-CONDITIONAL** (filtered subset) |
| CARLA (synthetic) | CARLA | GitHub ✅ | MIT code / CC-BY assets / UE EULA | MIT | CC-BY | n/a | conditional | ? | required | no | **GREEN-CONDITIONAL** |
| COCO | COCO | — | annots CC BY 4.0; images Flickr ToU | — | Flickr | CC BY 4.0 | ambiguous | — | — | — | **YELLOW** |
| TrafficCAM | Cambridge | not fetched | not verified | — | — | — | ? | — | — | — | **YELLOW** |
| Canada open-gov traffic cam | Gov of Canada | not fetched | Open Gov Licence (likely commercial-OK) | — | — | — | likely | — | required | no | **YELLOW** (verify) |
| BDD100K / Waymo / nuScenes / nuImages / KITTI / Cityscapes / Mapillary / MIO-TCD / VisDrone / UAVDT / UA-DETRAC / AI City | various | not fetched | secondary NC / code-only / unverified | — | — | — | — | — | — | — | **YELLOW — PRIMARY NOT VERIFIED** |
| traffic-accident-cctv (HF user) | HF user | — | CC0 (unofficial provenance) | — | — | — | yes | yes | no | no | **YELLOW** (provenance/quality doubtful) |

**No dataset is asserted RED** (no primary prohibition fetched). Secondary-NC datasets remain YELLOW pending primary verification.

## 4. DSEC-DETECTION FINDINGS
Dataset **CC BY-SA 4.0** (commercial OK + attribution + **ShareAlike**); `dsec-det` **code GPL-3.0**
(verified) — we would not use their GPL code. Detection labels **auto-generated** by a tracking
algorithm then manually corrected (~390K boxes, 60 sequences). Event-camera + RGB **driving**
viewpoint (not fixed CCTV). **ShareAlike scope + trained-weight effect: NOT EXPLICITLY ADDRESSED**
→ documented uncertainty. Suitability: **supplementary/validation at best**, not primary; only if
the ShareAlike obligation is legally accepted. → **GREEN-CONDITIONAL.**

## 5. UVH-26 FINDINGS — LEADING CANDIDATE
Primary-verified **CC BY 4.0** (official AIM@IISc HF repo). **Real fixed-CCTV**: ~26,646 1080p
frames from ~2,800 Bengaluru Safe City CCTV cameras (4 weeks), **~1.8M boxes**, 14 India-specific
vehicle classes, **faces + plates masked** (privacy handled by creators). Consensus labels
(majority-vote UVH-26-MV + STAPLE UVH-26-ST). Commercial use permitted with attribution → **the
single best match: real CCTV + commercial + attribution + privacy-clean.** Suitability: **primary
training data.** Class taxonomy maps well to our 5 canonical (§15). Weakness: single city/country
(Bengaluru, India) → geographic bias.

## 6. OTHER NEW-CANDIDATE FINDINGS
- **BMD-45** (AIM@IISc): primary-verified **CC BY 4.0**; ~45K images, ~480K boxes, 3,679 Safe City
  CCTV cameras, 14 classes — **same group + taxonomy as UVH-26 → ideal companion. GREEN.**
- **TrafficCAM** (Cambridge, Indian cities): **segmentation** (not detection); license not
  fetched → YELLOW. Lower priority (task mismatch).
- **BMD-45 = strongest companion; TrafficCAM/others unverified.** `traffic-accident-cctv` (HF user
  CC0) — accident-focused, low-res, unofficial provenance → YELLOW/not recommended.

## 7. GOVERNMENT / OPEN-DATA FINDINGS
A **Government of Canada open-data** entry "Annotated images … from traffic cameras (archives)"
exists (Open Government Licence – Canada, which generally permits commercial reuse with
attribution) but its page was **not fetchable** this session → **YELLOW, promising, verify primary**.
No other government traffic-image dataset primary-verified here.

## 8. GREEN DATASETS
- **UVH-26 — CC BY 4.0** (primary-verified).
- **BMD-45 — CC BY 4.0** (primary-verified).

## 9. GREEN-CONDITIONAL
- **DSEC-Detection** (CC BY-SA 4.0 — accept ShareAlike + weight uncertainty; supplementary only).
- **Open Images filtered subset** (CC BY images + CC BY 4.0 annots; per-image legal spot-check).
- **CARLA synthetic** (MIT/CC-BY; UE-EULA legal question).

## 10. YELLOW
COCO, TrafficCAM, Canada open-gov (verify), BDD100K, Waymo, nuScenes/nuImages, KITTI, Cityscapes,
Mapillary Vistas, MIO-TCD, VisDrone, UAVDT, UA-DETRAC, AI City, traffic-accident-cctv.

## 11. RED
**None asserted** (no primary prohibition fetched this session).

## 12. ATTRIBUTION OBLIGATIONS
CC BY 4.0 (UVH-26, BMD-45) and CC BY-SA 4.0 (DSEC) require attribution — **acceptable**. Exact
records created in **`THIRD_PARTY_DATA.md`** (creator, official source, license, citation
arXiv:2511.02563, modifications, access date). Attribution will also appear in the **model card**
and, if applicable, product legal notices. Giving credit ≠ calling our trained model theirs
(ownership separation documented in `THIRD_PARTY_DATA.md`).

## 13. TRAINED-MODEL RIGHTS FINDINGS
- **UVH-26 / BMD-45 (CC BY 4.0):** trained-model weights **NOT EXPLICITLY ADDRESSED**. CC BY grants
  broad rights to use/adapt the licensed material commercially with attribution; training a model
  is within that grant. No clause claims dataset-owner ownership of derived models. → our
  random-init weights + ONNX are **our artifact**, subject to attributing the data.
- **DSEC (CC BY-SA 4.0):** ShareAlike's effect on trained weights **NOT EXPLICITLY ADDRESSED** →
  genuine uncertainty (some read SA as not reaching model weights; not guaranteed). Documented, not
  guessed.
Our process is unchanged: approved dataset → our versioning → our preprocessing → our 5-class
taxonomy → **FCOS random init** → our GPU training → our weights → our ONNX → our app. **No
third-party pretrained weights.**

## 14. TECHNICAL QUALITY SCORES (weighted, 0–10)
| Criterion (weight) | UVH-26 | BMD-45 | DSEC | OpenImages-filt |
|---|---|---|---|---|
| Fixed-CCTV similarity (20%) | 10 | 10 | 2 | 3 |
| Small/distant vehicles (15%) | 8 | 8 | 6 | 5 |
| Annotation quality (15%) | 8 | 8 | 6 | 8 |
| Dataset scale (10%) | 8 | 9 | 8 | 8 |
| Five-class coverage (10%) | 9 | 9 | 6 | 8 |
| Day/night diversity (10%) | 8 | 8 | 7 | 6 |
| Weather diversity (5%) | 6 | 6 | 6 | 5 |
| Geographic diversity (5%) | 3 | 3 | 5 | 8 |
| Licence clarity (10%) | 10 | 10 | 6 | 6 |
| **Weighted total** | **8.35** | **8.45** | **5.45** | **6.0** |

## 15. CLASS MAPPINGS (14 India classes → canonical v1)
| Source class | Canonical | Note |
|---|---|---|
| Cycle | **BICYCLE** | clean |
| 2-Wheeler (Motorcycle) | **MOTORCYCLE** | clean |
| Hatchback, Sedan, SUV, MUV | **CAR** | clean |
| Mini-bus, Bus | **BUS** | clean |
| Truck | **TRUCK** | clean |
| 3-Wheeler (auto-rickshaw) | **EXCLUDE** | no canonical equivalent — do NOT force-map |
| LCV, Van, Tempo-traveller | **EXCLUDE / review** | ambiguous (CAR vs TRUCK vs BUS) — exclude for v1 |
| Other | **EXCLUDE** | unlabeled/misc |
All five canonical classes are well supported; ambiguous/region-specific classes are **excluded,
not mis-merged** (per plan §25). Mapping recorded as a versioned `class_mapping_version`.

## 16. DATASET COMBINATION OPTIONS
- **A:** UVH-26 alone (~26.6K imgs / ~1.8M boxes).
- **B:** UVH-26 + BMD-45 (~72K imgs / ~2.3M boxes) — same publisher/taxonomy/CC BY 4.0 → clean
  merge, dedup + **source-aware leakage-safe split** (by camera/sequence). **Recommended.**
- **C:** B + Open Images cleared subset (adds geographic diversity, needs legal spot-check).
Every source independently passes the rights gate; **no YELLOW data enters a production DatasetVersion.**

## 17. SAFEST LEGAL OPTION
**UVH-26 alone** — single primary-verified CC BY 4.0 source, attribution only, no ShareAlike, no
per-image ambiguity, privacy pre-handled.

## 18. BEST TECHNICAL OPTION
**UVH-26 + BMD-45** — the most real fixed-CCTV traffic data among legally-clear candidates (~72K
CCTV images), matched taxonomy, both CC BY 4.0.

## 19. BEST BALANCED OPTION
**UVH-26 + BMD-45 now**, with **Open Images cleared subset added later** for geographic diversity —
best mix of legal clarity, CCTV relevance, scale, and diversity.

## 20. FINAL RECOMMENDED DATASET STRATEGY
**RECOMMENDED FIRST TRAINING DATASET STRATEGY: UVH-26 + BMD-45 (both CC BY 4.0), merged into one
production DatasetVersion via canonical 5-class mapping, dedup, and source-aware leakage-safe
splitting.**
- **Why:** the only primary-verified, real **fixed-CCTV** traffic datasets with commercial use +
  attribution; large (~72K imgs / ~2.3M boxes); privacy pre-handled; matched taxonomy → clean merge.
- **Legal basis:** CC BY 4.0 (commercial + attribution), primary-verified from the official
  AIM@IISc repositories; attribution obligations recorded in `THIRD_PARTY_DATA.md`.
- **Technical strengths:** real Safe City CCTV viewpoint (exact target domain), 1080p, day/night,
  dense mixed traffic, all 5 canonical classes well represented.
- **Weaknesses:** single geography (Bengaluru, India) → geographic/vehicle-mix bias; the first model
  should be labeled **EXPERIMENTAL** for other regions and later supplemented (own-data / Open Images).
- **Expected size:** ~72K images / ~2.3M boxes (before class filtering; auto-rickshaw/ambiguous
  classes excluded).
- **Five-class coverage:** strong for CAR/BUS/TRUCK/MOTORCYCLE/BICYCLE.

## 21. DOWNLOAD / PREPARATION PLAN (NOT executed)
1. **Source:** HuggingFace `iisc-aim/UVH-26`, `iisc-aim/BMD-45` (official releases).
2. **Size:** UVH-26 ~26.6K × 1080p (several GB) + BMD-45 ~45K (several GB) — tens of GB total.
3. **Registration:** HF account may be required to download (verify); license accept-click.
4. **Method:** `huggingface_hub` snapshot download to `VIDEO_STORAGE`-adjacent dataset storage
   (reference-only in DB).
5. **Checksums:** capture per-file sha256 on download → manifest.
6. **Annotation format:** convert source annotations → **canonical COCO** via `apps.datasets.coco`
   + `class_mapping_version` (§15).
7. **Manifest:** immutable hashed sample + split manifests (`apps.datasets.manifests`), source-aware
   groups (camera/sequence) for leakage-safe split.
8. **Rights evidence:** attach license (`cc-by-4.0`) + citation + access date to `DatasetLicense`.
9. **Attribution:** `THIRD_PARTY_DATA.md` (created) + model card.
**Do not download during this task.**

## 22. PROPOSED GATE D APPROVAL (NOT executed — human gate)
Proposed for explicit human approval via `apps.datasets.approval.approve_dataset_version` (audited):
```
DatasetVersion:      UVH-26  v1.0   (and BMD-45 v1.0)
rights_status:       APPROVED_WITH_OBLIGATIONS      # attribution obligation
license:             CC BY 4.0
obligations:         "Attribution per THIRD_PARTY_DATA.md + model card (AIM@IISc, arXiv:2511.02563)"
evidence:            HF repo `license: cc-by-4.0` (verified 2026-07-16); arXiv:2511.02563
approval_status:     APPROVED   (ONLY upon your explicit approval — not set automatically)
approver:            <your identity>
```
The software will **not** set this automatically; it is presented for your explicit approval.

## 23. REMAINING UNCERTAINTIES
1. HF download may require account/agreement acceptance (operational, not legal).
2. DSEC dataset CC BY-SA needs primary page re-verification if it is ever used (supplementary only).
3. Geographic bias of India-only data → plan supplementation for other regions.
4. Open Images subset + CARLA remain GREEN-CONDITIONAL pending their respective legal steps.

## 24. EXACT NEXT ACTION
Do **not** start training. Await your explicit approval of: (1) dataset choice (UVH-26 + BMD-45),
(2) attribution obligations (`THIRD_PARTY_DATA.md`), (3) dataset download, (4) Gate D approval
(run `approve_dataset_version` to create the production-eligible `DatasetVersion`), (5) pilot
training. Once approved + downloaded + converted + approved, FCOS is technically ready to train.

---

At least one genuinely verified dataset strategy (UVH-26 + BMD-45, CC BY 4.0) can pass Gate D
pending your explicit human approval.

PHASE 6T-B DATASET STATUS: READY FOR HUMAN APPROVAL
