# Basis Pengetahuan: Agen Reasuransi (Bahasa Indonesia)
> File ini merupakan basis pengetahuan utama untuk Agen Reasuransi dalam sistem RIU Market Update Automation.  
> Sumber: UU No. 40/2014, POJK 14/2015 beserta perubahannya, IFG Progress ECO Bulletin No. 16 (Reasuransi 101), CGI-001, Peta Jalan OJK 2023–2027.

---

## 1. Peran Agen Reasuransi

Agen ini bertugas menganalisis kondisi keuangan dan bisnis **perusahaan reasuransi** di Indonesia untuk laporan market update bulanan. Agen **tidak boleh mengarang data**. Semua analisis harus bersumber dari file Excel atau PDF yang tersedia.

---

## 2. Definisi dan Konsep Reasuransi

**Reasuransi** adalah perjanjian antara perusahaan asuransi (ceding company) dengan perusahaan reasuransi (reasuradur), di mana perusahaan asuransi setuju menyerahkan sebagian dan/atau seluruh risiko yang ditanggungnya kepada reasuransi, dengan reasuransi menerima sejumlah proporsi premi dan setuju menanggung proporsi yang sama atas klaim yang terjadi.

**Usaha Reasuransi** menurut UU No. 40/2014: Usaha jasa pertanggungan ulang terhadap risiko yang dihadapi oleh perusahaan asuransi, perusahaan penjaminan, atau perusahaan reasuransi lainnya.

---

## 3. Fungsi dan Manfaat Reasuransi bagi Perusahaan Asuransi

1. **Meningkatkan kapasitas penerimaan risiko**: Asuransi dapat menerima risiko yang nilainya jauh melebihi kemampuan modalnya sendiri.
2. **Menjaga stabilitas keuangan**: Mengurangi fluktuasi beban klaim dengan membagi risiko kepada reasuradur.
3. **Mendukung ekspansi bisnis**: Ketidakpastian risiko berkurang sehingga asuransi lebih berani memasuki lini bisnis baru.
4. **Perlindungan dari risiko katastropik**: Melindungi perusahaan asuransi dari kerugian tunggal yang sangat besar.
5. **Penyebaran risiko (spread of risk)**: Mendistribusikan risiko ke pasar yang lebih luas.

---

## 4. Lima Pihak dalam Bisnis Reasuransi

| Pihak | Peran |
|-------|-------|
| Tertanggung (Insured) | Individu atau perusahaan yang membeli jasa asuransi |
| Perusahaan Asuransi (Direct Insurer) | Penanggung utama; menerima risiko dari tertanggung |
| Ceding Company | Perusahaan asuransi yang menempatkan reasuransi |
| Reasuradur (Reinsurer) | Menanggung sebagian risiko dari ceding company |
| Retrocedent & Retrocessionaire | Reasuradur yang mengasuransikan kembali risikonya ke reasuradur lain |
| Broker Reasuransi | Perantara antara ceding company dan reasuradur |

---

## 5. Metode dan Bentuk Reasuransi

### 5.1 Berdasarkan Metode

#### Treaty (Otomatis)
- Kontrak tertulis berlaku untuk portfolio bisnis tertentu.
- Ceding company secara otomatis mensesikan; reasuradur secara otomatis menerima sesuai kriteria perjanjian.
- Biasanya berlaku 12 bulan (tahunan).
- **Lebih efisien secara administrasi** karena tidak perlu negosiasi per risiko.

#### Fakultatif (Case by Case)
- Setiap risiko ditawarkan dan dinegosiasikan secara individual.
- Ceding company bebas mensesikan atau tidak; reasuradur bebas menerima atau menolak.
- Digunakan untuk risiko di luar kapasitas treaty, risiko yang tidak termasuk dalam treaty, atau risiko yang luar biasa besar.

### 5.2 Berdasarkan Bentuk

#### Proporsional (Proportional)
Ceding company dan reasuradur berbagi premi dan klaim berdasarkan proporsi yang telah disepakati.

**a. Quota Share**
- Proporsi tetap untuk setiap risiko dalam portfolio.
- Contoh: 40% ceding company, 60% reasuradur → semua premi dan klaim dibagi dengan rasio yang sama.
- Kelebihan: sederhana, melindungi merata.
- Kekurangan: tidak protektif terhadap klaim besar (loss ratio bruto = loss ratio neto).

**b. Surplus Treaty**
- Reasuradur menanggung kelebihan risiko di atas retensi ceding company.
- Retensi dinyatakan dalam "lines" (1 line = retensi sendiri).
- Contoh: retensi Rp 250 juta + surplus 4 lines = kapasitas maksimum Rp 1,25 miliar.
- Kelebihan: kapasitas lebih besar dari quota share; retensi dapat berbeda per jenis risiko.
- Kekurangan: administrasi lebih kompleks.

**c. Facultative Obligatory (Fac-Ob)**
- Ceding company bebas mensesikan; reasuradur wajib menerima.
- Merupakan hybrid antara fakultatif dan treaty.

#### Non-Proporsional
Ceding company dan reasuradur tidak berbagi berdasarkan proporsi tetap. Reasuradur menanggung klaim hanya jika melewati ambang batas tertentu.

**a. Excess of Loss (XoL)**
- Reasuradur menanggung klaim yang melebihi net retensi ceding company.
- Dapat dibuat dalam beberapa **layer** untuk kapasitas yang lebih besar.
- Contoh:
  - Layer 1: Cover limit Rp 1 miliar XoL Rp 250 juta (reasuradur bayar Rp 250 juta s.d. Rp 1,25 miliar)
  - Layer 2: Cover limit Rp 2 miliar XoL Rp 1,25 miliar

**b. Stop Loss**
- Melindungi perusahaan asuransi dari kerugian agregat yang melebihi jumlah tertentu.
- Dinyatakan dalam persentase loss ratio.

---

## 6. Terminologi Khusus Reasuransi

| Istilah | Penjelasan |
|---------|-----------|
| Cession / Sesi | Bagian nilai pertanggungan yang diserahkan ke reasuradur |
| Retensi | Bagian risiko yang ditahan ceding company |
| Retensi Sendiri | Bagian yang benar-benar ditahan satu perusahaan tanpa dibagi lebih lanjut |
| Line | Jumlah yang ditetapkan sebagai retensi ceding company dalam treaty surplus |
| Limit | Jumlah maksimum yang dapat diterima reasuradur per class of business |
| Retrosesi | Pengalihan risiko dari reasuradur ke reasuradur lain |
| Retrocessionaire | Reasuradur dari reasuradur |
| Reciprocity | Timbal balik dalam penempatan bisnis reasuransi |
| Reinsurance Commission | Komisi reasuransi sebagai persentase premi dari reasuradur ke ceding company |
| Profit Commission | Keuntungan reasuradur yang dikembalikan ke ceding company |
| Pools | Kerjasama beberapa insurer/reinsurer untuk menanggung jenis risiko tertentu secara bersama |
| Guarantee Policy | Istilah untuk reasuransi dalam cabang kebakaran |

---

## 7. Metrik Keuangan Utama Perusahaan Reasuransi

### 7.1 Premi (Premi Bruto vs. Premi Neto)
```
Premi Bruto = Total premi yang diterima dari ceding companies (sebelum retrosesi)
Premi Neto = Premi Bruto - Premi Retrosesi
```

### 7.2 Hasil Underwriting (Underwriting Result)
```
Hasil Underwriting = Premi Neto - Beban Klaim - Komisi - Biaya Operasional
```
**Konteks Indonesia**: Hasil underwriting reasuransi Indonesia menunjukkan tren **negatif** dalam 5 tahun terakhir (2016–2021), dengan CAGR -184%. Beban klaim tumbuh lebih cepat (~19%/tahun) dari pertumbuhan premi (~11%/tahun).

### 7.3 Beban Klaim (Beban Klaim Neto)
```
Beban Klaim Neto = Klaim yang Terjadi - Klaim yang Dipulihkan dari Retrocession
```

### 7.4 Loss Ratio
```
Loss Ratio = Beban Klaim Neto / Premi Neto × 100%
```
Loss ratio reasuransi cenderung lebih volatile dibanding asuransi primer karena terkena risiko besar dan katastropik.

### 7.5 Combined Ratio (COR)
```
COR = Loss Ratio + Commission Ratio + Expense Ratio
```

### 7.6 Pendapatan Investasi (Investment Income)
- Sangat penting sebagai buffer dari hasil underwriting yang negatif.
- Aset investasi reasuransi Indonesia didominasi deposito (37%), obligasi (32%), reksa dana (18%), saham (3%).
- Tren: hasil investasi reasuransi Indonesia masih positif dan tumbuh ~10%/tahun (CAGR 2016–2021).

### 7.7 RBC (Risk Based Capital)
- OJK mewajibkan minimum 120%.
- Reasuransi memiliki profil risiko lebih volatile → modal yang kuat sangat krusial.

### 7.8 Cession Rate
```
Cession Rate = Premi Reasuransi yang Diterima / Total Premi Industri Asuransi
```
Di Indonesia: cession rate asuransi umum jauh lebih tinggi daripada asuransi jiwa (~50%+ vs ~3%).

### 7.9 Struktur Aset Reasuransi
- Aset investasi: ~57% dari total aset
- Aset non-investasi: ~43%
- Aset reasuransi Indonesia hanya ~2% dari total industri asuransi (sangat kecil).

### 7.10 Cadangan Teknis (Technical Reserves)
Komponen cadangan teknis reasuransi:
- Cadangan klaim: ~48% dari total cadangan teknis
- UPR (Unearned Premium Reserve): ~29%
- Cadangan premi dan cadangan bencana alam: sisanya

---

## 8. Pasar Reasuransi Indonesia: Konteks

### 8.1 Struktur Pasar (2016–2022)
- Jumlah perusahaan reasuransi konvensional: **6–7 perusahaan**
- Semua BUMN & Swasta Nasional (tidak ada joint venture)
- Market leader: PT Reasuransi Indonesia Utama (IndonesiaRe, BUMN)
- Total aset reasuransi akhir 2022: ~Rp 34 triliun (+12% CAGR 5 tahun)
- Premi reasuransi didominasi dari asuransi umum (70% dari total premi reasuransi)

### 8.2 Masalah Struktural
- **Kapabilitas domestik rendah**: Hanya 6 perusahaan untuk pasar senilai ratusan triliun rupiah → porsi reasuransi ke luar negeri sangat tinggi (0,11% dari PDB).
- **Ketergantungan pada broker**: Jumlah pialang reasuransi (~42) jauh melebihi jumlah reasuradur (7) — rasio 6:1.
- **Komisi broker tumbuh lebih cepat dari premi**: CAGR komisi broker 21%/tahun vs CAGR premi 10%/tahun (2017–2021).

### 8.3 Pasar Global (Konteks)
- Pasar reasuransi global senilai USD 262 miliar (50 perusahaan top, 2020).
- Non-life mendominasi: 66% dari total premi global.
- Eropa mendominasi: 50% dari premi global.
- Munich Re (16%), Swiss Re (13%), Hannover Re (10%) adalah tiga besar.
- CAGR 10 tahun reasuransi global: 4,8% (lebih tinggi dari CAGR asuransi global 3,8%).

### 8.4 Komposisi Treaty vs. Fakultatif di Indonesia
- Treaty mendominasi (~70% dari total portofolio dalam 10 tahun terakhir).
- Pengecualian: aviasi didominasi fakultatif (risiko per kejadian sangat tinggi).

---

## 9. Regulasi Reasuransi di Indonesia

| Regulasi | Isi Pokok |
|----------|-----------|
| UU No. 40/2014 Pasal 2(3) | Perusahaan reasuransi hanya dapat menyelenggarakan Usaha Reasuransi |
| POJK No. 14/2015 | Dukungan reasuransi wajib 100% dari reasuradur dalam negeri (minimal 2 perusahaan domestik) |
| POJK No. 19/2019 (Perubahan 1) | Menambahkan definisi dukungan reasuransi otomatis (treaty) dan risiko sederhana |
| POJK No. 39/2020 (Perubahan 2) | Reasuransi luar negeri hanya dari negara yang memiliki perjanjian bilateral dengan Indonesia |
| SEOJK No. 31/2015 | Batas retensi sendiri, besar dukungan reasuransi, dan laporan program reasuransi ke OJK |
| POJK 23/2023 | Perizinan usaha reasuransi |

### 9.1 Kewajiban Reasuransi Dalam Negeri
Berdasarkan POJK 14/2015 beserta perubahannya:
- Dukungan reasuransi wajib 100% dari reasuradur dalam negeri terlebih dahulu.
- Pengecualian: produk bersifat worldwide, produk untuk perusahaan multinasional, produk baru yang didukung oleh reasuradur luar negeri.
- Reasuransi luar negeri hanya diperbolehkan dari negara mitra yang memiliki perjanjian bilateral dengan Indonesia (cross-border supply).

---

## 10. Kerangka Analisis Agen

### 10.1 Pertanyaan Kunci Bulanan
1. Apakah premi bruto reasuransi tumbuh atau turun?
2. Bagaimana tren loss ratio? Apakah ada klaim besar (catastrophe) yang mempengaruhi?
3. Apakah hasil underwriting positif atau negatif?
4. Apakah pendapatan investasi mampu mengkompensasi defisit underwriting?
5. Bagaimana komposisi antara treaty dan fakultatif?
6. Apakah RBC masih di atas 120%?
7. Bagaimana porsi premi dari asuransi umum vs. asuransi jiwa?

### 10.2 Sinyal Peringatan (Red Flags)
- Hasil underwriting negatif yang semakin dalam tanpa kompensasi investasi
- Loss ratio > 80% secara konsisten
- Klaim bencana tunggal yang mempengaruhi lebih dari 30% premi
- RBC mendekati 120% atau di bawah
- Ketergantungan retrosesi yang sangat tinggi (> 40% dari premi bruto)
- Beban klaim tumbuh jauh lebih cepat dari pertumbuhan premi

### 10.3 Sinyal Positif
- Pertumbuhan premi didukung oleh ekspansi bisnis baru
- Hasil underwriting membaik meski masih negatif
- Diversifikasi lini bisnis dan geografi
- Hasil investasi stabil dan positif
- RBC jauh di atas 120%
- Komisi reasuransi yang diterima (dari ceding companies) kompetitif

---

## 11. Format Komentar Analisis

### 11.1 Panduan Gaya
- Bahasa: **Bahasa Indonesia** formal dan profesional
- Sertakan angka dengan perbandingan MoM dan YoY
- Berikan konteks: kondisi pasar reasuransi global, tingkat suku bunga, risiko katastropik
- Sebutkan perusahaan secara spesifik

### 11.2 Contoh Komentar Analisis yang Baik
> "PT Reasuransi Indonesia Utama (IndonesiaRe) mencatat pendapatan premi bruto sebesar Rp 3,2 triliun pada kuartal pertama 2026, tumbuh 7,8% dibandingkan kuartal pertama 2025 (Rp 2,97 triliun), terutama didorong oleh peningkatan sesi dari lini kebakaran dan rekayasa. Namun demikian, hasil underwriting masih mencatat defisit sebesar Rp 215 miliar, meskipun membaik dari defisit Rp 320 miliar di periode yang sama tahun lalu. Beban klaim meningkat 12,3% akibat klaim kebakaran industri besar di Jawa Tengah. Pendapatan investasi sebesar Rp 380 miliar mampu mengkompensasi sebagian defisit underwriting, sehingga laba bersih tercatat Rp 145 miliar. RBC masih terjaga di 172%, di atas batas minimum OJK 120%."

### 11.3 Yang Harus Dihindari
- ❌ Menggunakan angka tanpa sumber
- ❌ Menyatakan tren dari satu titik data
- ❌ Menyebut angka yang tidak ada di file data

---

## 12. Instruksi Anti-Halusinasi

1. **Hanya gunakan data dari file yang disediakan** (folder data/).
2. **Cantumkan nama file dan tab/sheet sumber** saat mengutip angka.
3. **Jika data tidak tersedia**, nyatakan "data tidak tersedia untuk periode ini."
4. **Verifikasi konsistensi**: premi bruto - retrosesi = premi neto; klaim neto = klaim bruto - pemulihan dari retrosesi.
5. **Jangan membuat asumsi** atas angka yang tidak ada.
6. **Tandai inkonsistensi** antar sumber sebagai "perlu verifikasi" alih-alih memilih satu angka secara diam-diam.
