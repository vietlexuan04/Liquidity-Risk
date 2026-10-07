# Liquidity Risk Analytics Toolkit

Mô phỏng quy trình phân tích rủi ro thanh khoản ngân hàng theo Basel III (LCR, NSFR) +
stress testing, xây dựng trên dữ liệu công khai FDIC của **JPMorgan Chase Bank, N.A.**
(Cert #628), Q1/2023 - Q2/2026. Mục tiêu minh hoạ quy trình phân tích (data pipeline → mapping có kiểm
chứng → ratio engine → sensitivity/benchmark → stress testing → SQL; dashboard Power BI), không phải
tái tạo số liệu quản trị chính thức của JPMorgan.

**Đơn vị**: mọi số tiền trong dữ liệu gốc và các file CSV tính bằng **nghìn USD** (đơn vị của FDIC); các bảng kết
quả trong README đã quy đổi sang tỷ USD ($B).

**Đọc trước khi dùng số trong repo này**: toàn bộ LCR/NSFR là **proxy**, tính từ dữ liệu
Call Report công khai (không đủ chi tiết để tính đúng 100% theo quy định) - baseline proxy
thấp hơn số LCR thật JPMorgan công bố khoảng **19-33 điểm %** (xem benchmark bên dưới). Đây
là đặc tính đã biết của mô hình, có giải thích đầy đủ, không phải lỗi.

## Tech stack

Python 3.8+ (đã chạy thử trên 3.12; pandas-free, chỉ dùng thư viện chuẩn: `csv`, `sqlite3`, `random`) cho
pipeline + tính toán · SQLite cho lưu trữ/truy vấn · Power BI cho dashboard (**dự kiến, chưa có file nào
trong repo**) · dữ liệu nguồn: FDIC BankFind (tải thủ công, không cần code để lấy dữ liệu thô).
Không cần cài thêm thư viện nào; các script phải chạy từ **thư mục gốc** của repo (đường dẫn viết cứng).

## Luồng xử lý (chạy theo thứ tự)

```
data/raw/jpm_628_raw.csv                 (tải tay từ website FDIC BankFind)
        │
src/parse_fdic_raw.py      ──→  data/processed/jpm_628_wide.csv, mnemonic_labels.csv
        │                        (duỗi định dạng FDIC quirky → bảng sạch: 1 dòng/quý)
src/build_mapping.py       ──→  mapping/liquidity_mapping.csv, nhnn_ratio_reference.csv
        │                        (gán từng dòng bảng cân đối vào vai trò LCR/NSFR theo
        │                         Basel III BCBS 238/295, đối chiếu NHNN TT22/TT25;
        │                         RECONCILED chính xác 0 sai lệch với ASSET/LIABEQ, 14/14 quý)
src/mapping_to_long.py     ──→  mapping/liquidity_mapping_long.csv
        │                        (bản long/tidy phái sinh, để SQL/Power BI dễ query)
src/ratios.py              ──→  data/processed/ratios_by_quarter.csv
        │                        (HQLA, LCR, ASF/RSF, NSFR, LDR — 14 quý)
src/sensitivity.py         ──→  data/processed/sensitivity_results.csv
        │                        (OAT sensitivity trên 17/19 dòng confidence=Low)
src/benchmark.py           ──→  data/processed/lcr_benchmark.csv
        │                        (so proxy LCR với LCR thật JPMorgan công bố; cột LCR thật là
        │                         SỐ NHẬP TAY từ 10-Q/LCR Disclosure, không tính từ code)
src/stress_testing.py      ──→  data/processed/stress_*.csv
        │                        (3 kịch bản cố định x 14 quý, Monte Carlo deposit run-off,
        │                         survival horizon, reverse stress test — chỉ LCR)
src/db.py                  ──→  liquidity_risk.db
                                 (gộp toàn bộ 12 bảng CSV vào 1 SQLite để Power BI kết nối)
```

Chạy lại toàn bộ: `for f in src/parse_fdic_raw.py src/build_mapping.py src/mapping_to_long.py src/ratios.py src/sensitivity.py src/benchmark.py src/stress_testing.py src/db.py; do python3 $f; done`

## Cấu trúc thư mục

```
data/raw/            FDIC Call Report gốc (tải tay, xem hướng dẫn bên dưới)
data/processed/      Toàn bộ output trung gian + kết quả (CSV)
mapping/             Bảng mapping LCR/NSFR + README phương pháp luận chi tiết
src/                 Toàn bộ code Python, chạy độc lập từng bước
liquidity_risk.db    SQLite gộp — nguồn cho Power BI / truy vấn SQL
README.md            File này
STRESS_TESTING_README.md   Kết quả stress testing đầy đủ
```

## Cách lấy dữ liệu gốc

File raw trong repo (`data/raw/jpm_628_raw.csv`) là báo cáo **"Assets, Liabilities, and Capital"** của
Cert #628, đơn vị nghìn USD, 14 quý từ 31/03/2023 đến 30/06/2026, xuất dạng CSV từ công cụ
**"Customize a Report"** của FDIC BankFind (banks.data.fdic.gov/bankfind-suite/financialreporting).
`parse_fdic_raw.py` được viết cho đúng bố cục này (mỗi quý là một khối 3 cột: mã, giá trị, khoảng trống),
nên **chỉ tái tạo được pipeline nếu xuất đúng loại báo cáo và bố cục đó**.

URL API bên dưới chỉ lấy 8 trường cơ bản, ở **định dạng khác** (mỗi quý một dòng), nên **không dùng trực tiếp
với `parse_fdic_raw.py`**. Ghi lại ở đây chỉ để tham khảo cách lấy nhanh số liệu tổng hợp:

```
https://banks.data.fdic.gov/api/financials?filters=CERT:628 AND REPDTE:[20230101 TO 20261231]&fields=REPDTE,ASSET,DEP,DEPDOM,LNLSNET,SC,EQ,CHBAL&sort_by=REPDTE&sort_order=DESC&limit=100&format=csv&download=true
```

## Phát hiện chính

### 1. Xu hướng LCR/NSFR (baseline, 14 quý)
LCR: 113% (Q1/23) → 85% (Q2/26); NSFR: 140% → 115%. Cả hai giảm dần theo thời gian, LDR ổn
định quanh 45-55%.

### 2. Sensitivity & Benchmark (kiểm định trước khi stress)
2 giả định "0% dòng tiền vào" (`L_OTH_LE12`, `A_REVREPO`, tổng ~$1,200B) có độ nhạy đủ lớn
(+48 đến +49pp mỗi dòng khi chuyển sang biên trên, vốn là trần lý thuyết) để có thể giải thích một phần đáng kể khoảng lệch -19 đến -33pp so với
LCR thật JPMorgan Chase Bank, N.A. công bố (10-Q SEC) - đo bằng OAT sensitivity trên 17 trong 19 dòng
`confidence=Low`. Đây là bằng chứng về độ nhạy, chưa phải chứng minh nguyên nhân duy nhất (xem mục Giới hạn).
Chi tiết: `mapping/mapping_README.md`.

### 3. Hai lỗi phát hiện khi rà soát mapping, đã sửa và ghi lại quá trình
`CHCOIN` trùng lặp với `CHBAL` (xác minh đúng ở 14/14 quý trước khi sửa); thang kỳ hạn khoản
vay dùng nhầm giá trị ròng thay vì gộp, gây dư nợ "âm" vô nghĩa. Cả hai đã sửa, reconciliation
vẫn khớp tuyệt đối sau khi sửa. Chi tiết: `mapping/mapping_README.md`, mục "Lỗi đã phát hiện khi rà soát và cách
sửa" (mỗi lỗi đều được xác minh lại bằng số liệu 14 quý trước khi sửa).

### 4. Stress testing (chỉ LCR; đầy đủ: `STRESS_TESTING_README.md`)
Combined scenario kéo LCR Q2/2026 từ 85% → 51% (Δ-34pp); Idiosyncratic (-31pp) nặng hơn so với Market-wide (-6pp) vì rút tiền gửi/drawdown cam kết là khoản $ lớn hơn haircut chứng
khoán. Reverse stress test cho thấy baseline đã <100% ngay cả khi chưa stress - minh chứng
trực quan cho đặc tính bảo thủ của proxy nói ở trên.

## Giới hạn đã biết (đọc trước khi dùng số trong repo)

- Không mô hình hoá dòng tiền vào (LCR inflow) ở hầu hết các dòng → proxy thấp hơn thực tế
- Trading liabilities (`B_TRADEL`) bị bỏ sót hoàn toàn khỏi LCR outflow → ngược chiều, proxy cao hơn thực tế ở điểm này
- Giả định kỳ hạn đều (uniform maturity) cho các dòng gộp ≤1 năm
- Không mô hình hoá management action/counterbalancing capacity trong stress testing
- 19/48 dòng mapping có `confidence=Low` - đã lượng hoá mức ảnh hưởng qua sensitivity, không chỉ cảnh báo suông
- Hệ số trong mapping theo Basel (BCBS 238/295), còn LCR thật dùng để benchmark theo quy tắc của Mỹ; số thật là
  **trung bình quý**, proxy tính từ **số cuối kỳ** - một phần khoảng lệch đến từ khác biệt phương pháp
- Dữ liệu là Call Report của riêng ngân hàng (solo), không phải toàn tập đoàn JPMorgan Chase & Co.
- **NSFR chưa có benchmark** với số thật (chỉ LCR có), nên NSFR proxy chưa được đối chiếu
- Số LCR thật trong benchmark là số **nhập tay** (8 quý), không do code tạo ra
- Các hệ số sốc trong stress testing là **giả định minh hoạ**, chưa hiệu chỉnh từ kịch bản giám sát hay khủng
  hoảng thực tế; stress không thay đổi dòng tiền vào và không mô hình hoá bán tháo tài sản
- Monte Carlo lấy mẫu 4 dòng tiền gửi **độc lập** (tương quan = 0), độ lệch chuẩn 20% là tham số tuỳ chọn;
  Monte Carlo, survival horizon và reverse stress chỉ chạy cho Q2/2026
- Công thức trong CSV được tính bằng `eval()` (đã khoá `__builtins__`, phù hợp cho dữ liệu tự quản lý trong
  repo này, **không an toàn nếu nhận CSV từ nguồn không tin cậy**); chưa có test tự động

Danh sách đầy đủ, kèm căn cứ từng dòng: `mapping/mapping_README.md`.
