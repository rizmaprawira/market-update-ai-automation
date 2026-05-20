# Basis Pengetahuan: Agen Asuransi Jiwa (Bahasa Indonesia)
> File ini merupakan basis pengetahuan utama untuk Agen Asuransi Jiwa dalam sistem RIU Market Update Automation.  
> Sumber: UU No. 40/2014, POJK 8/2024, AAJI (Panduan Underwriting & Hidup Cerdas dengan Asuransi Jiwa), Panduan Tata Kelola TI, Peta Jalan OJK 2023–2027.

---

## 1. Peran Agen Asuransi Jiwa

Agen ini bertugas menganalisis kondisi keuangan dan bisnis perusahaan **asuransi jiwa** di Indonesia untuk laporan market update bulanan. Agen **tidak boleh mengarang data**. Semua analisis harus bersumber dari file Excel atau PDF yang tersedia.

---

## 2. Definisi dan Ruang Lingkup Asuransi Jiwa

**Asuransi Jiwa** adalah usaha yang menyelenggarakan jasa penanggulangan risiko yang memberikan pembayaran kepada pemegang polis, tertanggung, atau pihak lain yang berhak dalam hal:
- Tertanggung **meninggal dunia**, atau
- Tertanggung **tetap hidup** pada waktu tertentu, atau
- Pembayaran lain pada waktu tertentu sesuai perjanjian dengan manfaat yang besarnya telah ditetapkan dan/atau didasarkan pada hasil pengelolaan dana.

(Berdasarkan UU No. 40/2014 Pasal 1 dan 2)

---

## 3. Jenis Produk Asuransi Jiwa di Indonesia

### 3.1 Asuransi Jiwa Berjangka (Term Life Insurance)
- Memberikan **santunan kematian** jika tertanggung meninggal dalam periode yang ditentukan (1, 5, 10, 20 tahun, atau hingga usia tertentu).
- Tidak memiliki nilai tunai.
- Premi paling rendah di antara semua produk asuransi jiwa.
- Cocok untuk perlindungan murni jangka pendek (misalnya: perlindungan cicilan KPR).

### 3.2 Asuransi Jiwa Seumur Hidup (Whole Life Insurance)
- Memberikan santunan kematian **seumur hidup** tertanggung.
- Memiliki nilai tunai yang dapat diambil oleh pemegang polis.
- Berfungsi sebagai instrumen investasi dengan imbal hasil tetap.

### 3.3 Asuransi Jiwa Dwiguna (Endowment)
- Dua manfaat: santunan kematian jika meninggal dalam masa asuransi, DAN manfaat habis kontrak jika masih hidup di akhir masa asuransi.
- Masa asuransi: 5, 10, 15, 20, atau 30 tahun.
- Imbal hasil pasti, cocok untuk dana pendidikan atau persiapan pensiun.

### 3.4 Asuransi Unit Link / PAYDI (Investment-Linked)
- Menggabungkan perlindungan jiwa dan nilai investasi yang berfluktuasi.
- Nilai investasi bergantung pada kinerja sub-dana yang dipilih.
- Produk paling kompleks; wajib memiliki aktuaris perusahaan.
- OJK mengatur ketat melalui POJK 8/2024 (pencatatan aset dan liabilitas PAYDI secara terpisah).

### 3.5 Lini Usaha Tambahan yang Dapat Dijual Perusahaan Asuransi Jiwa
- **Asuransi Kesehatan (Health Insurance)**: Rawat inap, rawat jalan, penyakit kritis.
- **Asuransi Kecelakaan Diri (Personal Accident)**: Perlindungan kematian, cacat, biaya medis akibat kecelakaan.
- **Asuransi Kredit (Jiwa Kredit)**: Perlindungan atas saldo pinjaman jika debitur meninggal atau cacat.
- **Anuitas (Annuity)**: Pembayaran berkala kepada pemegang polis, biasanya digunakan untuk program pensiun.

---

## 4. Prinsip Underwriting Asuransi Jiwa

### 4.1 Tujuan Underwriting
Menilai kelayakan calon nasabah sebelum penerbitan polis, meliputi:
- Penilaian risiko mortalita (kematian) dan morbidita (kesakitan)
- Memastikan kewajaran uang pertanggungan sesuai kondisi keuangan tertanggung
- Pencegahan anti-seleksi dan moral hazard
- Kepatuhan terhadap prinsip AML/KYC

### 4.2 Tiga Subjek Penilaian Underwriting Jiwa
1. **Pemegang Polis**: Harus memiliki hubungan insurable interest dengan tertanggung (orang tua-anak, suami-istri, badan hukum-karyawan, dll). Domisili, usia, dan legalitas harus diperiksa.
2. **Tertanggung**: Orang yang atas hidupnya perlindungan asuransi diberikan. Penilaian meliputi usia, jenis kelamin, pekerjaan, kondisi kesehatan, hobi, gaya hidup, dan pendapatan.
3. **Penerima Manfaat**: Harus memiliki insurable interest yang jelas dan wajar dengan tertanggung. Bisa berupa perorangan, wali amanat, atau institusi.

### 4.3 Faktor Underwriting Utama

| Faktor | Penjelasan |
|--------|------------|
| Usia | Semakin tua → risiko mortalita lebih tinggi → premi lebih mahal |
| Jenis Kelamin | Pria dan wanita memiliki tingkat mortalita berbeda |
| Kondisi Kesehatan | Riwayat penyakit, tekanan darah, diabetes, kanker, dll |
| Pekerjaan | Risiko tinggi (pertambangan, penanganan bahan berbahaya) → premi ekstra |
| Hobi/Olahraga Berbahaya | Balap motor, diving, paragliding → premi ekstra atau pengecualian |
| Merokok / Penggunaan Tembakau | Non-perokok mendapat premi lebih rendah |
| Riwayat Kesehatan Keluarga | Diabetes, jantung, kanker dalam keluarga = faktor risiko |
| Uang Pertanggungan | Harus proporsional dengan pendapatan/kondisi keuangan tertanggung |
| Kepemilikan Polis Lain | Anti-seleksi jika tertanggung sudah memiliki banyak polis |

### 4.4 Keputusan Underwriting
- **Accept Standard**: Risiko sesuai standar, premi normal.
- **Accept Substandard**: Risiko lebih tinggi, premi tambahan (extra premium) atau pengecualian tertentu.
- **Postpone**: Penundaan keputusan menunggu informasi lebih lanjut.
- **Decline**: Risiko terlalu tinggi atau tidak memenuhi kriteria penanggung.

---

## 5. Metrik Keuangan Utama Asuransi Jiwa

### 5.1 Pendapatan Premi (Premium Income)
```
Premi Bruto = Total premi yang diterima sebelum dikurangi reasuransi
Premi Neto = Premi Bruto - Premi Reasuransi Disesikan
```
Pertumbuhan premi adalah indikator utama ekspansi bisnis.

### 5.2 Beban Klaim/Manfaat (Claims and Benefits Expense)
Meliputi:
- Klaim kematian (death claims)
- Klaim penyakit kritis (critical illness claims)
- Klaim kesehatan (health claims)
- Manfaat habis kontrak (maturity benefits)
- Nilai tunai yang dibayarkan (surrender value paid)
- Klaim kecelakaan (accident claims)

### 5.3 Loss Ratio / Rasio Klaim
```
Loss Ratio = Beban Klaim dan Manfaat / Pendapatan Premi Neto × 100%
```
- Angka ini bervariasi per jenis produk
- Asuransi jiwa jangka panjang umumnya memiliki loss ratio lebih stabil dibanding asuransi umum

### 5.4 RBC (Risk Based Capital)
- OJK mewajibkan minimum **120%**
- RBC < 120%: wajib setor modal tambahan; OJK dapat melakukan intervensi

### 5.5 Cadangan Teknis (Technical Reserve / Liability)
Komponen utama liabilitas asuransi jiwa:
- **Cadangan Premi (Premium Reserve)**: Dana untuk memenuhi kewajiban klaim mendatang dari polis yang masih aktif.
- **IBNR (Incurred But Not Reported)**: Estimasi klaim yang sudah terjadi tapi belum dilaporkan.
- **Nilai Tunai Polis (Policy Surrender Value)**: Kewajiban kepada pemegang polis jika mereka membatalkan polis.
- **Dana Investasi PAYDI**: Aset yang dikelola atas nama nasabah Unit Link.

### 5.6 Hasil Investasi (Investment Income)
Asuransi jiwa sangat bergantung pada pendapatan investasi karena:
- Dana premi dikumpulkan jauh sebelum klaim jatuh tempo (terutama produk jangka panjang)
- Alokasi investasi umum: deposito, obligasi pemerintah, reksa dana, saham

Indikator investasi yang dipantau:
- Return on Investment (ROI)
- Yield obligasi pemerintah yang menjadi benchmark
- Portofolio investasi per instrumen

### 5.7 Rasio Klaim vs Pendapatan (Claims-to-Revenue Ratio)
Perbandingan beban klaim terhadap total pendapatan premi dan investasi.

### 5.8 Persistency Rate
Persentase polis yang masih aktif setelah periode tertentu (misal: 13 bulan). Indikator kualitas penjualan dan kepuasan nasabah.

### 5.9 Solvabilitas dan Ekuitas
- Ekuitas = Total Aset - Total Liabilitas
- Pertumbuhan ekuitas mencerminkan kemampuan perusahaan mengakumulasi modal.

---

## 6. Laporan Keuangan Asuransi Jiwa: Pos-Pos Penting

### 6.1 Laporan Laba Rugi (Income Statement)
| Pos | Penjelasan |
|-----|------------|
| Pendapatan Premi Bruto | Total premi sebelum reasuransi |
| Premi Reasuransi | Premi yang disesikan ke reasuradur |
| Pendapatan Premi Neto | Premi Bruto – Premi Reasuransi |
| Hasil Investasi | Bunga, dividen, keuntungan investasi |
| Beban Klaim dan Manfaat | Semua pembayaran klaim dan manfaat |
| Beban Komisi | Komisi agen dan broker |
| Beban Operasional | Gaji, sewa, TI, dll |
| Laba/Rugi Underwriting | Pendapatan – Beban Klaim – Komisi – Operasional |
| Laba/Rugi Bersih | Setelah pajak |

### 6.2 Neraca (Balance Sheet)
| Aset | Liabilitas |
|------|-----------|
| Aset Investasi (deposito, obligasi, saham, reksa dana) | Cadangan Premi |
| Aset Non-Investasi (piutang premi, piutang klaim reasuransi) | Cadangan Klaim (IBNR) |
| Kas dan Setara Kas | Utang Klaim |
| Properti/Aset Tetap | Dana Investasi PAYDI |
| | Utang Lainnya |
| | Ekuitas |

---

## 7. Pasar Asuransi Jiwa Indonesia: Konteks

### 7.1 Struktur Pasar (2022–2023)
- Jumlah perusahaan asuransi jiwa: ~59–61 perusahaan
  - BUMN & Swasta Nasional: ~36–37
  - Joint Venture: ~23–24
- Total aset asuransi jiwa (akhir 2022): ~Rp 585 triliun (CAGR 5 tahun: +3%)
- Pendapatan premi (2022): ~Rp 169,95 triliun
- Beban klaim (2022): ~Rp 157,53 triliun (CAGR: -2,4% dalam 5 tahun terakhir)

### 7.2 Dominasi Produk
- PAYDI (Unit Link) mendominasi portofolio banyak perusahaan jiwa besar
- Produk kredit jiwa (bancassurance) tumbuh pesat
- Asuransi kesehatan kumpulan menjadi growth driver setelah pandemi

### 7.3 Saluran Distribusi Utama
- Agen asuransi
- Bancassurance (mitra bank)
- Telemarketing
- Digital/Online

### 7.4 Tantangan Industri
- Dampak pandemi COVID-19: kenaikan klaim kesehatan dan jiwa 2020–2022
- Kasus gagal bayar beberapa perusahaan besar (menciptakan krisis kepercayaan)
- Tingkat penetrasi dan densitas masih rendah
- Kompleksitas produk PAYDI menimbulkan banyak pengaduan nasabah
- OJK memperkuat aturan PAYDI melalui POJK 8/2024

### 7.5 Cession Rate Asuransi Jiwa
- Porsi premi yang direasuransikan pada asuransi jiwa jauh lebih kecil dari asuransi umum (~3% rata-rata dari premi bruto).
- Reasuransi jiwa terutama untuk risiko kematian dan cacat (mortality dan disability reinsurance).
- Banyak perusahaan jiwa joint venture mengreasuransikan ke grup induk di luar negeri.

---

## 8. Regulasi Utama Asuransi Jiwa

| Regulasi | Isi Pokok |
|----------|-----------|
| UU No. 40/2014 | Landasan hukum usaha asuransi jiwa |
| POJK 8/2024 | Produk asuransi, termasuk ketentuan ketat untuk PAYDI |
| POJK 23/2023 | Perizinan kelembagaan |
| SEOJK terkait PAYDI | Ketentuan pengelolaan aset dan liabilitas PAYDI |
| Ketentuan OJK terkait aktuaris | Kewajiban memiliki Aktuaris Perusahaan |
| Peta Jalan OJK 2023–2027 | Arah pengembangan industri asuransi jiwa 5 tahun ke depan |

---

## 9. Kerangka Analisis Agen

### 9.1 Pertanyaan Kunci Bulanan
1. Apakah pendapatan premi tumbuh atau turun vs bulan lalu dan tahun lalu?
2. Apakah beban klaim/manfaat meningkat secara proporsional?
3. Bagaimana tren hasil investasi? Apakah ROI menurun?
4. Apakah ada kenaikan signifikan dalam surrender value yang dibayarkan? (Indikasi polis banyak yang lapse)
5. Apakah RBC masih di atas 120%?
6. Bagaimana komposisi portofolio produk? (PAYDI vs Non-PAYDI)

### 9.2 Sinyal Peringatan (Red Flags)
- Pendapatan premi turun tajam → potensi masalah distribusi atau reputasi
- Beban klaim melonjak → possible epidemic/pandemic trigger atau klaim tidak wajar
- Surrender value meningkat drastis → masalah kepercayaan nasabah
- ROI investasi turun di bawah 4% → pengelolaan aset kurang optimal
- RBC mendekati 120% → perlu perhatian permodalan
- Cadangan teknis tidak cukup → risiko solvabilitas jangka panjang
- Pengaduan nasabah meningkat → kualitas produk atau pelayanan bermasalah

### 9.3 Sinyal Positif
- Pertumbuhan premi konsisten dengan klaim terkontrol
- Persistency rate tinggi (nasabah mempertahankan polis)
- Diversifikasi produk yang baik
- ROI investasi stabil dan di atas benchmark
- RBC jauh di atas 120%
- Ekspansi bancassurance atau digital

---

## 10. Format Komentar Analisis

### 10.1 Panduan Gaya
- Bahasa: **Bahasa Indonesia** formal dan profesional
- Sertakan angka spesifik dengan perbandingan periode (MoM, YoY)
- Sebutkan konteks makroekonomi jika relevan (suku bunga, inflasi medis)
- Hindari istilah terlalu teknis tanpa penjelasan

### 10.2 Contoh Komentar Analisis yang Baik
> "PT Asuransi Jiwa ABC mencatat pendapatan premi bruto sebesar Rp 12,3 triliun pada Januari–April 2026, tumbuh 6,2% dibandingkan periode yang sama tahun lalu (Rp 11,6 triliun). Produk PAYDI tetap mendominasi dengan kontribusi 68% dari total premi. Beban klaim dan manfaat meningkat 9,4% menjadi Rp 9,8 triliun, terutama didorong oleh kenaikan klaim kesehatan pasca-pandemi dan peningkatan surrender value. Hasil investasi tercatat Rp 2,1 triliun, sedikit di bawah periode yang sama tahun lalu (Rp 2,3 triliun), mencerminkan tekanan pada yield obligasi. RBC perusahaan tetap terjaga di 148%, masih memadai meski sedikit menurun dari 155% akhir tahun 2025."

### 10.3 Yang Harus Dihindari
- ❌ Mencampur angka dari perusahaan berbeda tanpa keterangan
- ❌ Menyatakan kesimpulan tanpa angka pendukung
- ❌ Menyebutkan angka yang tidak ada di file data
- ❌ Mengasumsikan tren tanpa data historis yang cukup

---

## 11. Instruksi Anti-Halusinasi

1. **Hanya gunakan data dari file yang disediakan** dalam folder data/.
2. **Cantumkan nama file dan tab/sheet sumber** saat mengutip angka.
3. **Jika data tidak tersedia**, tuliskan "data tidak tersedia untuk periode ini."
4. **Verifikasi konsistensi internal angka** (premi bruto – premi reasuransi = premi neto, dll).
5. **Jangan membuat asumsi** atas angka yang tidak terbaca atau tidak ada.
6. **Jika ada ketidakkonsistenan** antar sumber, tandai sebagai "perlu verifikasi" dan laporkan ke agen Financial Data Analyst.
