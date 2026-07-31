# Compliance-Audit-Report

**Assurance-Level:** `technical-evidence-only`

Dieser Bericht trifft **keine Konformitaetsaussage**. Er weist ausschliesslich aus, welche Anforderungen sich aus Code, Infrastrukturdefinition und Runtime-Konfiguration technisch belegen lassen. Anforderungen der Klasse C erfordern organisatorische Nachweise und sind in Abschnitt 6 gesondert ausgewiesen.

---

## 1. Pruefumfang

| Feld | Wert |
|---|---|
| Lauf-ID | `9f2c1a44-8b3e-4d16-9c07-5a1e2b7d0f31` |
| Zeitraum | 2026-07-11T08:14:02Z – 2026-07-11T08:16:41Z |
| Repository | `git@github.com:example-org/kenny.git` |
| Commit | `4c1f9ae7d2b8` (main) |
| IaC-Pfade | infra/terraform |
| Cloud-Scope | GCP `organizations/412887330219` (Credentials: read-only) |
| Katalogstand | 0.1.0 (Auditor 0.1.0) |
| Evidenz-Bundle | `eb-9f2c1a44`, SHA-256 `6b1c0e83a94f27d5…` |

**Rahmenwerke:**

- bsi-grundschutz (Kompendium 2023, Profil Basis)
- cra (VO (EU) 2024/2847)
- dsgvo (VO (EU) 2016/679)

---

## 2. Deckungsgrad

### bsi-grundschutz — Profil Basis

| Kennzahl | Anzahl |
|---|---:|
| Katalogeintraege | 3 |
| **davon technisch pruefbar** | **2** |
| geprueft | 2 |
| bestanden | 1 |
| nicht erfuellt | 1 |
| teilweise erfuellt | 0 |
| nicht anwendbar | 0 |
| **ausserhalb des technischen Pruefumfangs** | **1** |
| unzureichende Evidenz | 0 |

Bezugsgroesse jeder Quote ist `technically_assessable` (2), nicht `controls_in_catalog` (3). Eine Aussage der Form „1 von 3 erfuellt" waere irrefuehrend.

### cra

| Kennzahl | Anzahl |
|---|---:|
| Katalogeintraege | 2 |
| **davon technisch pruefbar** | **2** |
| geprueft | 2 |
| bestanden | 1 |
| nicht erfuellt | 0 |
| teilweise erfuellt | 1 |
| nicht anwendbar | 0 |
| **ausserhalb des technischen Pruefumfangs** | **0** |
| unzureichende Evidenz | 0 |

Bezugsgroesse jeder Quote ist `technically_assessable` (2), nicht `controls_in_catalog` (2). Eine Aussage der Form „1 von 2 erfuellt" waere irrefuehrend.

### dsgvo

| Kennzahl | Anzahl |
|---|---:|
| Katalogeintraege | 2 |
| **davon technisch pruefbar** | **2** |
| geprueft | 2 |
| bestanden | 0 |
| nicht erfuellt | 1 |
| teilweise erfuellt | 1 |
| nicht anwendbar | 0 |
| **ausserhalb des technischen Pruefumfangs** | **0** |
| unzureichende Evidenz | 0 |

Bezugsgroesse jeder Quote ist `technically_assessable` (2), nicht `controls_in_catalog` (2). Eine Aussage der Form „0 von 2 erfuellt" waere irrefuehrend.

---

## 3. Zusammenfassung

Der Lauf prueft drei Rahmenwerke gegen Repository, Terraform-Definitionen und die GCP-Organisation. Der schwerwiegendste Befund betrifft die Transportverschluesselung: Der externe Load Balancer akzeptiert TLS 1.0, und der Bucket mit Kundendaten laeuft ohne kundenverwalteten Schluessel. Beide Abweichungen schlagen gleichzeitig auf BSI CON.1.A1 und Art. 32 Abs. 1 lit. a DSGVO durch. Bei der Datenlokalisation ist der Zustand konform, die Durchsetzung fehlt jedoch: Die Org Policy gcp.resourceLocations laeuft im dry-run-Modus und verhindert eine Ausbringung ausserhalb der EU nicht. Zwei genutzte Google-Dienste liegen ausserhalb des Scopes des herangezogenen C5-Testats; die ererbte Evidenz traegt dort nicht. Die SBOM existiert, erfuellt die Feldanforderungen aus TR-03183-2 aber nur teilweise, was mit Blick auf den 11. Dezember 2027 vor der eigentlichen Frist behoben werden sollte. Von acht Katalogeintraegen liegt einer ausserhalb des technischen Scopes und erfordert organisatorische Nachweise.

---

## 4. Verstoesse

### [FAIL] bsi-grundschutz · CON.1.A1 — Auswahl geeigneter kryptografischer Verfahren

- **Urteil:** nicht erfuellt
- **Durchsetzung:** keine
- **Evidenz:** Klasse A, selbst erhoben
- **Fundstelle:** BSI IT-Grundschutz-Kompendium, Baustein CON.1 Kryptokonzept, Anforderung A1

Die SSL-Policy des externen Load Balancers erlaubt TLS 1.0 und enthaelt CBC-Cipher-Suites. Der GCS-Bucket mit Kundendaten nutzt Google-managed Keys statt CMEK. Beide Abweichungen sind in Terraform kodiert und wirken sich unmittelbar auf die produktive Umgebung aus.

| Finding | Primitive | Schwere | Ist | Soll |
|---|---|---|---|---|
| `F-001` | `CRYPTO.TLS.MIN_VERSION` | high | google_compute_ssl_policy.min_tls_version = "TLS_1_0", profile = "COMPATIBLE" | min_tls_version >= "TLS_1_2", profile in [MODERN, RESTRICTED] |
| `F-002` | `CRYPTO.KEY.CUSTOMER_MANAGED` | high | encryption.kmsKeyName absent (Google-managed key) | encryption.kmsKeyName set, key location in EU |

**Behebung:** min_tls_version auf TLS_1_2 setzen und Profil MODERN oder RESTRICTED waehlen. Bucket auf CMEK mit Key-Ring in europe-west3 umstellen.

- `infra/terraform/lb.tf:42`
- `infra/terraform/storage.tf:17`

### [PART] cra · ANNEX-I.II.1 — SBOM in maschinenlesbarem Format, Top-Level-Abhaengigkeiten

- **Urteil:** teilweise erfuellt
- **Durchsetzung:** nur beratend
- **Evidenz:** Klasse A, selbst erhoben
- **Fundstelle:** VO (EU) 2024/2847, Anhang I Teil II Nr. 1; konkretisiert durch BSI TR-03183-2

Eine CycloneDX-1.6-SBOM wird im Build erzeugt und als Artefakt abgelegt. Bei 34 von 211 Komponenten fehlt das Feld supplier, bei 12 fehlen Hashes. TR-03183-2 fordert beide Felder. Die SBOM-Erzeugung ist im Workflow nicht als Pflichtschritt gegated, ein Build ohne SBOM ist moeglich.

| Finding | Primitive | Schwere | Ist | Soll |
|---|---|---|---|---|
| `F-003` | `SBOM.FIELDS.TR03183` | medium | 34/211 Komponenten ohne supplier, 12/211 ohne hashes | supplier, version, hashes, licenses je Top-Level-Komponente (TR-03183-2) |

**Behebung:** syft-Konfiguration um Supplier-Aufloesung erweitern, Hash-Berechnung fuer alle Komponenten erzwingen, SBOM-Erzeugung als Required Check im Branch-Protection-Ruleset verankern.

- `.github/workflows/build.yml`
- `BSI TR-03183-2, Abschnitt 5`

### [PART] dsgvo · Art.44 — Allgemeine Grundsaetze der Datenuebermittlung in Drittlaender

- **Urteil:** teilweise erfuellt
- **Durchsetzung:** nur beratend
- **Evidenz:** Klasse B, ererbt (Provider-Attestierung), Konfidenz medium
- **Fundstelle:** VO (EU) 2016/679, Art. 44 ff.

Alle 47 datenhaltenden Ressourcen liegen aktuell in europe-west3 und europe-west4. Die Org Policy gcp.resourceLocations ist jedoch nur im dry-run-Modus gesetzt und verhindert eine Ausbringung ausserhalb der EU nicht. Der Zustand ist konform, die Durchsetzung fehlt. Zusaetzlich liegen zwei genutzte Dienste ausserhalb des Scopes des BSI-C5-Testats von Google.

> **Ererbte Evidenz:** BSI C5:2020 Type 2 (Google Cloud), gueltig bis 2026-09-30
>
> Produkt-Scope geprueft: ja · CUEC-Status: unverified
>
> **Ausserhalb des Attestierungs-Scopes:** aiplatform.googleapis.com, workflows.googleapis.com

| Finding | Primitive | Schwere | Ist | Soll |
|---|---|---|---|---|
| `F-004` | `DATA.RESIDENCY.ENFORCEMENT` | high | listPolicy set, dryRunSpec only, spec absent | spec.rules[].values.allowedValues = [in:eu-locations], enforced |
| `F-005` | `PROVIDER.ATTESTATION.SCOPE` | medium | 2 genutzte Dienste ausserhalb der C5-Scope-Liste: aiplatform.googleapis.com, workflows.googleapis.com | alle genutzten Dienste in der produktscharfen Scope-Liste des Testats |

**Behebung:** gcp.resourceLocations von dry-run auf enforced umstellen mit allowedValues in:eu-locations. Fuer die beiden Dienste ausserhalb des C5-Scopes entweder Ersatz waehlen oder eine eigenstaendige Risikobewertung mit Transfer Impact Assessment dokumentieren. CUECs aus dem C5-Testat gegen die eigene Konfiguration pruefen.

- `Google Cloud C5 Product Scope List`
- `Art. 46 DSGVO`

### [FAIL] dsgvo · Art.32.1.a — Verschluesselung personenbezogener Daten

- **Urteil:** nicht erfuellt
- **Durchsetzung:** keine
- **Evidenz:** Klasse A, selbst erhoben
- **Fundstelle:** VO (EU) 2016/679, Art. 32 Abs. 1 lit. a

Dieselben Befunde wie bei CON.1.A1. TLS 1.0 am externen Endpunkt und fehlende CMEK auf dem Bucket mit Kundendaten. Das Primitive wird einmal erhoben und bedient beide Controls.

| Finding | Primitive | Schwere | Ist | Soll |
|---|---|---|---|---|
| `F-001` | `CRYPTO.TLS.MIN_VERSION` | high | google_compute_ssl_policy.min_tls_version = "TLS_1_0", profile = "COMPATIBLE" | min_tls_version >= "TLS_1_2", profile in [MODERN, RESTRICTED] |
| `F-002` | `CRYPTO.KEY.CUSTOMER_MANAGED` | high | encryption.kmsKeyName absent (Google-managed key) | encryption.kmsKeyName set, key location in EU |

**Behebung:** Identisch mit CON.1.A1. Eine Behebung schliesst beide Controls.

- `infra/terraform/lb.tf:42`
- `infra/terraform/storage.tf:17`

---

## 5. Kontrolldetails

| Rahmenwerk | Control | Urteil | Klasse | Herkunft | Durchsetzung | Findings |
|---|---|---|---|---|---|---|
| bsi-grundschutz | `CON.1.A1` | nicht erfuellt | A | selbst erhoben | keine | F-001, F-002 |
| bsi-grundschutz | `OPS.1.1.5.A3` | bestanden | A | selbst erhoben | durchgesetzt | — |
| bsi-grundschutz | `ORP.3.A1` | ausserhalb des technischen Pruefumfangs | C | organisatorisch | — | — |
| cra | `ANNEX-I.II.1` | teilweise erfuellt | A | selbst erhoben | nur beratend | F-003 |
| cra | `ANNEX-I.II.2` | bestanden | A | selbst erhoben | durchgesetzt | — |
| dsgvo | `Art.44` | teilweise erfuellt | B | ererbt (Provider-Attestierung) | nur beratend | F-004, F-005 |
| dsgvo | `Art.32.1.a` | nicht erfuellt | A | selbst erhoben | keine | F-001, F-002 |

---

## 6. Nicht technisch geprueft

Die folgenden Anforderungen lassen sich aus Code, IaC oder Runtime-Konfiguration **nicht** belegen. Sie gelten weder als erfuellt noch als verletzt. Ein Nachweis erfordert Dokumente, Prozesse oder Belege ausserhalb des technischen Pruefumfangs.

**bsi-grundschutz · ORP.3.A1** — Sensibilisierung der Institutionsleitung fuer Informationssicherheit

Schulungsnachweise und Leitungsbeteiligung sind aus Code, IaC und Runtime-Konfiguration prinzipiell nicht ableitbar. Nachweis erfordert Dokumente ausserhalb des technischen Scopes.

---

## 7. Evidenzanhang

- **Bundle:** `.compliance/evidence/eb-9f2c1a44.tar.zst`
- **SHA-256:** `6b1c0e83a94f27d5518ab0cc3f7e21904d6a8b1259ce73f0a4b8d2e6c19f8073`
- **Erhoben:** 2026-07-11T08:14:05Z

Jedes Urteil in Abschnitt 4 und 5 ist gegen diesen fixierten Snapshot reproduzierbar. Collection und Bewertung liefen in getrennten Phasen.

### Collectors

| Collector | Version | Status |
|---|---|---|
| checkov | 3.2.99 | ok |
| syft | 1.18.1 | ok |
| grype | 0.87.0 | ok |
| gcloud | 512.0.0 | ok |
| semgrep | 1.108.0 | ok |

### Abfragen

**`F-001`** (checkov)

```
checkov -d infra/terraform --framework terraform -o json
```

Antwort-Hash: `a3f0c9128e4b6d7051aa2c83f19e6b40d78c5312ffab90e6c471d0928b3e6a15`

**`F-002`** (gcloud)

```
gcloud asset search-all-resources --asset-types=storage.googleapis.com/Bucket --format=json
```

Antwort-Hash: `c72e14b8039fa6d5218cb407e9d13f6205a8c9e14b7d0362fa9e58c1d40b7e29`

**`F-003`** (sbom-validator)

```
sbom-validator --profile tr-03183-2 artifacts/sbom.cdx.json --format json
```

Antwort-Hash: `5e9b0d3271ac846f0e2b71cd93a4f0186c53d7ba28f1c6094ed7a2b5013fc846`

**`F-004`** (gcloud)

```
gcloud resource-manager org-policies describe gcp.resourceLocations --organization=412887330219 --format=json
```

Antwort-Hash: `b18d4a0c7f39e526c04b8d71fa2e690358c1b7d4092ae6f3c8150b2ad97e4f6c`

**`F-005`** (attestation-scope-checker)

```
gcloud asset search-all-resources --format='json(assetType)' | attestation-scope-checker --attestation c5-2020 --provider gcp
```

Antwort-Hash: `d40f9c31ba7e0685c2f14ad83b96e072513cfa9d6e820b174c3d5f9a2e6018bb`

