# Basis Pengetahuan: Agen Analisis Asuransi Umum
## Versi Bahasa Indonesia

> **Peran Agen:** Menganalisis laporan keuangan dan kondisi bisnis perusahaan asuransi umum (non-jiwa) Indonesia, mengidentifikasi tren pasar, dan menulis komentar analis dalam Bahasa Indonesia yang profesional untuk laporan pembaruan pasar bulanan.
>
> **Referensi silang:** Untuk definisi istilah dasar, rujuk ke `glossary-id.md`. File ini berfokus pada pengetahuan khusus asuransi umum.
>
> **Anti-halusinasi:** Hanya gunakan data dari file Excel yang diekstrak, tabel terstruktur, atau sumber pengetahuan yang disetujui. Jangan mengarang angka. Jika data tidak tersedia, nyatakan secara eksplisit.

---

## 1. Ruang Lingkup Asuransi Umum di Indonesia

Asuransi umum (asuransi kerugian / non-life insurance) memberikan perlindungan finansial terhadap kerugian atau kerusakan harta benda dan tanggung jawab hukum akibat peristiwa yang tidak pasti. Di Indonesia, asuransi umum diatur oleh OJK dan diasosiasikan melalui AAUI (Asosiasi Asuransi Umum Indonesia).

**Lini Bisnis Utama Asuransi Umum Indonesia:**
- Asuransi Kebakaran (Fire Insurance)
- Asuransi Kendaraan Bermotor (Motor Vehicle Insurance)
- Asuransi Pengangkutan / Marine Cargo
- Asuransi Rekayasa / Engineering Insurance
- Asuransi Tanggung Gugat (Liability Insurance)
- Asuransi Kecelakaan Diri (Personal Accident)
- Asuransi Kesehatan (Health Insurance) — jika dijual oleh perusahaan umum
- Asuransi Kredit (Credit Insurance)
- Asuransi Aneka (Miscellaneous Insurance)

---

## 2. Konsep Keuangan Utama Asuransi Umum

### 2.1 Premi

**Premi Bruto (Gross Written Premium / GWP)**
Total premi yang ditulis/diterima sebelum dikurangi premi reasuransi. Ukuran utama skala bisnis perusahaan.

**Premi Neto (Net Written Premium / NWP)**
Premi bruto dikurangi premi yang direasuransikan. Mencerminkan risiko yang benar-benar ditanggung sendiri oleh perusahaan.

**Premi Earned (Earned Premium)**
Bagian dari premi yang sudah "diterima manfaatnya" karena periode pertanggungan sudah berlalu. Digunakan sebagai penyebut dalam menghitung loss ratio.

Rumus: Premi Earned = Premi Ditulis + Cadangan Premi Awal - Cadangan Premi Akhir

**Cession Rate / Rasio Sesi**
Persentase premi yang direasuransikan terhadap premi bruto. Semakin tinggi, semakin banyak risiko yang dialihkan ke reasuransi.

Rumus: Cession Rate = Premi Reasuransi / Premi Bruto × 100%

### 2.2 Klaim

**Klaim Bruto (Gross Claims)**
Total klaim yang dibayarkan sebelum pemulihan dari reasuransi.

**Klaim Neto (Net Claims)**
Klaim bruto dikurangi pemulihan reasuransi (klaim yang diklaim kembali ke reasuradur).

**IBNR (Incurred But Not Reported)**
Estimasi klaim yang sudah terjadi tetapi belum dilaporkan. Wajib dicadangkan.

**Outstanding Claims Reserve (OCR)**
Cadangan untuk klaim yang sudah dilaporkan tetapi belum selesai dibayar.

### 2.3 Rasio Kunci Asuransi Umum

**Loss Ratio / Rasio Klaim**
Perbandingan klaim neto terhadap premi neto earned.

Rumus: Loss Ratio = Klaim Neto / Premi Neto Earned × 100%

Interpretasi:
- Loss Ratio < 60%: Kinerja underwriting sangat baik
- Loss Ratio 60–70%: Kinerja underwriting baik (rata-rata industri)
- Loss Ratio 70–80%: Mulai tertekan; perlu pengawasan
- Loss Ratio > 80%: Tanda bahaya; kemungkinan underwriting loss

**Expense Ratio / Rasio Biaya**
Biaya operasional (administrasi + akuisisi/komisi) terhadap premi neto.

Rumus: Expense Ratio = Total Biaya Operasional / Premi Neto × 100%

**Combined Ratio / COR (Combined Operating Ratio)**
Gabungan loss ratio dan expense ratio; ukuran profitabilitas underwriting.

Rumus: COR = Loss Ratio + Expense Ratio

Interpretasi:
- COR < 100%: Underwriting profit (operasi menguntungkan dari underwriting)
- COR > 100%: Underwriting loss (bergantung pada pendapatan investasi)

**Commission Ratio / Rasio Komisi**
Komisi yang dibayarkan kepada agen/broker terhadap premi neto.

**Underwriting Result / Hasil Underwriting**
Premi neto earned dikurangi klaim neto dikurangi biaya-biaya. Hasil murni dari operasi underwriting sebelum pendapatan investasi.

**Retention Ratio / Rasio Retensi**
Proporsi premi yang ditahan sendiri (tidak direasuransikan).

Rumus: Retention Ratio = Premi Neto / Premi Bruto × 100%

**RBC (Risk-Based Capital)**
Rasio solvabilitas berbasis risiko. Minimum 120% sesuai ketentuan OJK.

**Rasio Kecukupan Investasi (RKI)**
Perbandingan aset investasi terhadap total kewajiban. Mengukur kemampuan memenuhi kewajiban dari pendapatan investasi.

---

## 3. Struktur Laporan Keuangan Asuransi Umum

### 3.1 Laporan Laba Rugi (Income Statement)

```
(+) Premi Bruto
(-) Premi Reasuransi
(=) Premi Neto

(-) Perubahan Cadangan Premi
(=) Premi Neto Earned

(-) Klaim Bruto
(+) Klaim Reasuransi (Recover)
(=) Klaim Neto

(-) Biaya Akuisisi Neto (Komisi)
(-) Biaya Umum dan Administrasi
(=) Hasil Underwriting

(+) Pendapatan Investasi
(-) Biaya Investasi
(=) Laba/Rugi Sebelum Pajak
```

### 3.2 Neraca (Balance Sheet) — Pos Penting

**Aset:**
- Investasi (saham, obligasi, deposito, reksadana)
- Piutang Premi
- Piutang Reasuransi
- Aset Tetap

**Liabilitas:**
- Cadangan Teknis (cadangan premi + cadangan klaim)
- Hutang Klaim
- Hutang Komisi
- Hutang Reasuransi

**Ekuitas:**
- Modal Disetor
- Saldo Laba
- Total Ekuitas

---

## 4. Prinsip-Prinsip Asuransi yang Relevan untuk Analisis

**Utmost Good Faith (Itikad Baik Tertinggi)**
Tertanggung wajib mengungkapkan semua fakta material. Pelanggaran dapat membatalkan polis.

**Insurable Interest (Kepentingan yang Dapat Diasuransikan)**
Tertanggung harus memiliki kepentingan finansial yang diakui hukum atas objek yang diasuransikan.

**Indemnity (Ganti Rugi)**
Penanggung hanya mengembalikan kondisi finansial tertanggung ke posisi sebelum kerugian. Tidak boleh menguntungkan tertanggung.

**Subrogasi**
Setelah membayar klaim, penanggung berhak menuntut pihak ketiga yang menyebabkan kerugian atas nama tertanggung.

**Kontribusi**
Jika dua atau lebih polis menanggung risiko yang sama, kerugian dibagi secara proporsional.

**Proximate Cause**
Klaim hanya dibayar jika penyebab terdekat kerugian merupakan peril yang dijamin dalam polis.

---

## 5. Produk Asuransi Umum di Indonesia

### 5.1 Asuransi Kebakaran
- Menjamin kerugian akibat kebakaran, petir, ledakan, kejatuhan pesawat, dan asap
- Perluasan tersedia: banjir, gempa bumi, angin topan, RSMD (Risiko Sosial, Meteorologi, dan Dinamika)
- **Faktor underwriting:** konstruksi bangunan, penggunaan, lokasi, sistem proteksi kebakaran

### 5.2 Asuransi Kendaraan Bermotor
- Cover: Comprehensive (all risks), Total Loss Only (TLO), Third Party Liability (TPL)
- Faktor penentu premi: usia kendaraan, jenis kendaraan, wilayah, catatan klaim tertanggung
- Salah satu lini bisnis dengan volume premi terbesar di industri

### 5.3 Asuransi Pengangkutan (Marine Cargo)
- Menjamin kerugian atas barang dalam pengangkutan
- Institute Cargo Clauses (ICC A, B, atau C) sebagai standar
- **Faktor:** jenis komoditas, rute pengiriman, jenis kemasan

### 5.4 Asuransi Rekayasa (Engineering)
- Contractor's All Risks (CAR), Erection All Risks (EAR), Machinery Breakdown (MB)
- Penting untuk proyek infrastruktur dan industri

### 5.5 Asuransi Tanggung Gugat (Liability)
- Public Liability, Product Liability, Professional Indemnity, Employer's Liability
- Cover atas kewajiban hukum kepada pihak ketiga

### 5.6 Asuransi Kecelakaan Diri (Personal Accident)
- Menjamin kematian, cacat tetap, dan biaya perawatan akibat kecelakaan
- Bersifat benefit policy (bukan indemnity)

---

## 6. Kerangka Analisis Asuransi Umum

### 6.1 Analisis Pertumbuhan Premi
Bandingkan premi bruto periode ini vs periode sebelumnya:
- Pertumbuhan premi bruto YoY (Year-on-Year) atau MoM (Month-on-Month)
- Pertumbuhan per lini bisnis
- Market share: porsi perusahaan terhadap total industri

### 6.2 Analisis Kinerja Underwriting
Hitung dan interpretasikan:
- Loss ratio neto
- Expense ratio
- Combined ratio (COR)
- Underwriting result (profit/loss)

### 6.3 Analisis Reasuransi
- Cession rate: apakah naik atau turun?
- Perubahan program reasuransi
- Ketergantungan pada reasuransi asing vs domestik

### 6.4 Analisis Solvabilitas dan Modal
- Rasio RBC: apakah di atas 120%?
- Ekuitas: apakah tumbuh atau menyusut?
- KPPE: perusahaan termasuk kategori mana?

### 6.5 Analisis Investasi
- Komposisi portofolio investasi
- Yield investasi
- Rasio Kecukupan Investasi (RKI)

---

## 7. Tanda Bahaya (Red Flags) Asuransi Umum

Agen harus menandai hal-hal berikut sebagai temuan penting:

| Indikator | Tanda Bahaya |
|-----------|--------------|
| Loss Ratio | > 80% atau naik signifikan (>10 poin) dalam 1 periode |
| Combined Ratio | > 100% secara konsisten |
| RBC | Di bawah 120% atau mendekati 120% |
| Ekuitas | Mengalami penurunan atau negatif |
| Premi Bruto | Penurunan tajam > 20% YoY tanpa penjelasan |
| Cession Rate | Sangat tinggi (>70%) — ketergantungan tinggi pada reasuransi |
| Lapse Rate | Tidak berlaku langsung untuk umum, tapi perhatikan non-renewal rate |
| Cadangan Teknis | Tidak mencukupi (RKI < 100%) |
| Piutang Premi | Meningkat signifikan tanpa pertumbuhan premi setara |

---

## 8. Regulasi Penting Asuransi Umum Indonesia

**UU No. 40 Tahun 2014 tentang Perasuransian**
Dasar hukum utama seluruh kegiatan perasuransian di Indonesia. Mendefinisikan asuransi, asuransi syariah, reasuransi, dan ketentuan umum industri.

**POJK 23 Tahun 2023 tentang Perizinan Usaha dan Kelembagaan**
Mengatur persyaratan izin usaha, ekuitas minimum, struktur kelembagaan, tenaga ahli, dan pengawasan perusahaan asuransi dan reasuransi.

**POJK 8 Tahun 2024 tentang Produk Asuransi dan Saluran Pemasaran**
Mengatur persyaratan produk asuransi: polis, RIPLAY, penetapan premi, saluran pemasaran.

**Peta Jalan Perasuransian 2023–2027**
Dokumen arah kebijakan OJK untuk pengembangan dan penguatan industri perasuransian Indonesia, termasuk target RBC, ekuitas minimum, dan penetrasi asuransi.

---

## 9. Konteks Pasar Asuransi Umum Indonesia

Berdasarkan data industri:
- Asuransi umum merupakan segmen dengan aset terbesar kedua setelah asuransi jiwa
- Aset asuransi umum tumbuh sekitar 8% CAGR, mencapai Rp197 triliun pada akhir 2022
- Premi asuransi umum tumbuh sekitar 7% CAGR, mencapai Rp78 triliun pada akhir 2022
- Klaim asuransi umum meningkat sekitar 8,3% dalam 5 tahun terakhir
- Reinsurance share: sekitar 70% dari total premi reasuransi Indonesia berasal dari asuransi umum

---

## 10. Format Output Analisis

### Contoh Komentar Baik (Asuransi Umum)

**Contoh 1: Pertumbuhan Premi Positif**
> "PT XYZ mencatatkan pertumbuhan premi bruto sebesar 12,3% YoY menjadi Rp450 miliar pada periode ini, didorong oleh ekspansi lini kendaraan bermotor dan kebakaran komersial. Loss ratio neto terjaga di level 58,4%, lebih baik dari rata-rata industri, mencerminkan seleksi risiko yang disiplin. Rasio RBC tercatat di 187%, jauh di atas batas minimum 120% OJK, mengindikasikan ketahanan modal yang kuat."

**Contoh 2: Tekanan Kinerja**
> "PT ABC mengalami tekanan underwriting pada periode ini dengan combined ratio mencapai 107,2%, di atas breakeven. Kenaikan loss ratio menjadi 82,1% (dari 74,3% periode sebelumnya) terutama disebabkan oleh lonjakan klaim kebakaran dan banjir di kuartal tersebut. Meski penanggung berhasil memitigasi sebagian melalui program reasuransi excess of loss, underwriting result tercatat rugi Rp15 miliar. Manajemen perlu meninjau penetapan premi dan seleksi risiko pada lini properti."

### Struktur Komentar yang Disarankan
1. **Gambaran umum:** kinerja premi (pertumbuhan/penurunan)
2. **Analisis underwriting:** loss ratio, combined ratio, underwriting result
3. **Solvabilitas:** RBC, ekuitas
4. **Hal penting:** perubahan material, kejadian luar biasa, tren
5. **Implikasi:** apa artinya bagi posisi kompetitif atau outlook

---

## 11. Instruksi Anti-Halusinasi

- Jangan pernah mengarang angka. Jika data tidak tersedia dalam file Excel atau tabel terstruktur, tulis: *"Data tidak tersedia untuk periode ini."*
- Setiap angka yang disebutkan harus dapat ditelusuri ke sumber file yang spesifik.
- Jika terdapat anomali atau perubahan besar yang tidak dapat dijelaskan dari data, sebutkan sebagai *"perlu konfirmasi lebih lanjut"*.
- Hindari generalisasi industri kecuali didukung data aktual dari sumber pengetahuan yang disetujui.

---

*Sumber: UU No. 40/2014, POJK 23/2023, POJK 8/2024, CGI 001 Indonesia Re, Peta Jalan Perasuransian 2023–2027, Eco Bulletin Reinsurance 101, SKKNI 2024.*
