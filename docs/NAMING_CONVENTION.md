# Naming Convention

Dokumen ini mendefinisikan mapping URL sumber ke nama folder company (snake_case full legal name), beserta pola file output per company.

## Aturan Umum

- Periode output: `data/YYYY-MM/`
- Folder company: `data/YYYY-MM/{company_snake_case}/`
- Raw JSON: `{company_snake_case}_raw.json`
- CSV row: `{company_snake_case}_row.csv`
- Status: `status.txt`

## Mapping URL -> Folder Company

1. `https://inare.co.id/en/report/`
   - Legal name: PT Indoperkasa Suksesjaya Reasuransi
   - Folder: `pt_indoperkasa_suksesjaya_reasuransi`

2. `https://marein-re.com/laporan-keuangan`
   - Legal name: PT Maskapai Reasuransi Indonesia
   - Folder: `pt_maskapai_reasuransi_indonesia`

3. `https://www.orionre.id/assets/dokumen/publikasi/bulanan/`
   - Legal name: PT Orion Reasuransi Indonesia
   - Folder: `pt_orion_reasuransi_indonesia`

4. `https://www.indonesiare.co.id/id/investor-relations/financial-report`
   - Legal name: PT Reasuransi Indonesia Utama
   - Folder: `pt_reasuransi_indonesia_utama`

5. `https://maipark.com/id/corporate/laporan?financePage=1&type=financial&yearlyPage=1`
   - Legal name: PT Reasuransi Maipark Indonesia
   - Folder: `pt_reasuransi_maipark_indonesia`

6. `https://nasionalre.id/laporan-tahunan`
   - Legal name: PT Reasuransi Nasional Indonesia
   - Folder: `pt_reasuransi_nasional_indonesia`

7. `https://nusantarare.com/report/`
   - Legal name: PT Reasuransi Nusantara Makmur
   - Folder: `pt_reasuransi_nusantara_makmur`

8. `https://www.tugure.id/id/financial/monthly?page=1`
   - Legal name: PT Tugu Reasuransi Indonesia
   - Folder: `pt_tugu_reasuransi_indonesia`
