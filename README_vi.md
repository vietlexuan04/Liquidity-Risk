# Liquidity Risk Analytics Toolkit

[English](README.md) | **Tiếng Việt**

> Bản tiếng Việt là bản phụ; bản chính là [README.md](README.md) (tiếng Anh). Nếu có khác biệt, bản tiếng Anh được ưu tiên.

Mô phỏng quy trình phân tích rủi ro thanh khoản ngân hàng theo Basel III (LCR, NSFR) và stress
testing, xây dựng trên dữ liệu Call Report công khai của FDIC cho **JPMorgan Chase Bank, N.A.**
(FDIC Cert #628), Q1/2023–Q2/2026 (14 quý). Mục tiêu là minh hoạ quy trình phân tích (data
pipeline → mapping có đối chiếu → ratio engine → sensitivity / benchmark → stress testing →
SQLite cho SQL / Power BI), không phải tái tạo số liệu quản trị chính thức của JPMorgan.

**Đơn vị**: mọi số tiền trong dữ liệu gốc và các file CSV tính bằng **nghìn USD** (đơn vị của
FDIC). Các bảng trong README đã quy đổi sang tỷ USD ($B).

**Đọc trước khi dùng bất kỳ con số nào trong repo**: toàn bộ LCR/NSFR là **proxy**, tính từ Call
Report công khai, vốn không đủ chi tiết để tính chính xác theo quy định. LCR proxy thấp hơn LCR
mà JPMorgan Chase Bank, N.A. công bố **11,5–33,0 điểm %** (đối chiếu đủ 14 quý, lệch trung bình
−22,6 điểm %). Đây là đặc tính đã biết và có giải thích của mô hình, không phải lỗi.

## Luồng xử lý (chạy theo thứ tự)

```
data/raw/jpm_628_raw.csv                 (tải tay từ FDIC BankFind)
        │
src/parse_fdic_raw.py      ──→  data/processed/jpm_628_wide.csv, jpm_628_long.csv, mnemonic_labels.csv
        │                        (duỗi định dạng xuất theo khối quý của FDIC → 1 dòng/quý)
src/build_mapping.py       ──→  mapping/liquidity_mapping.csv, nhnn_ratio_reference.csv
        │                        (gán từng dòng bảng cân đối vào vai trò LCR/NSFR theo Basel III
        │                         BCBS 238/295, kèm ngưỡng NHNN để tham chiếu;
        │                         KHỚP với ASSET / LIABEQ, lệch đúng 0, 14/14 quý)
src/mapping_to_long.py     ──→  mapping/liquidity_mapping_long.csv
        │                        (bản long/tidy phái sinh, cho SQL / Power BI)
src/ratios.py              ──→  data/processed/ratios_by_quarter.csv
        │                        (HQLA theo cấp kèm trần cấp 2 của Basel, LCR, ASF/RSF, NSFR, LDR)
src/sensitivity.py         ──→  data/processed/sensitivity_results.csv
        │                        (kiểm định từng dòng trên 17/18 dòng confidence=Low,
        │                         trần lý thuyết, kiểm định phần bị bỏ sót, biên kết hợp)
src/benchmark.py           ──→  data/processed/lcr_benchmark.csv
        │                        (so LCR proxy với LCR công bố, 14 quý; số công bố là
        │                         SỐ NHẬP TAY từ các báo cáo 10-Q)
src/stress_testing.py      ──→  data/processed/stress_*.csv
        │                        (3 kịch bản cố định x 14 quý, Monte Carlo rút tiền gửi,
        │                         survival horizon, reverse stress test — chỉ LCR)
src/db.py                  ──→  liquidity_risk.db
                                 (gộp toàn bộ 12 bảng CSV vào 1 file SQLite)
```

`src/lcr_engine.py` chứa các công thức dùng chung cho `ratios.py`, `sensitivity.py` và
`stress_testing.py`, nên ba script không thể tính lệch nhau.

Yêu cầu: Python 3.8+, chỉ dùng thư viện chuẩn (không cần cài thêm gói nào). Chạy từ thư mục gốc
của repo:

```bash
for f in src/parse_fdic_raw.py src/build_mapping.py src/mapping_to_long.py src/ratios.py \
         src/sensitivity.py src/benchmark.py src/stress_testing.py src/db.py; do python3 "$f"; done
```

Kết quả tất định (Monte Carlo dùng seed cố định), chạy lại sẽ ra đúng mọi file CSV trong repo.

## Cấu trúc thư mục

```
data/raw/                  Call Report gốc của FDIC (xem "Cách lấy dữ liệu gốc")
data/processed/            Toàn bộ output trung gian và kết quả (CSV)
mapping/                   Bảng mapping LCR/NSFR + ghi chú phương pháp luận (mapping_README.md)
src/                       Code Python, mỗi bước một script + engine dùng chung
liquidity_risk.db          SQLite chứa mọi bảng kết quả, cho SQL / Power BI
README.md                  README chính (tiếng Anh); README_vi.md là bản tiếng Việt này
STRESS_TESTING_README.md   Phương pháp và kết quả stress testing đầy đủ
```

Repo không kèm file báo cáo Power BI; `liquidity_risk.db` là nguồn dữ liệu sẵn sàng để dựng báo
cáo (Power BI kết nối SQLite qua ODBC driver).

## Cách lấy dữ liệu gốc

`data/raw/jpm_628_raw.csv` là báo cáo **"Assets, Liabilities, and Capital"** của Cert #628, đơn vị
nghìn USD, 14 quý từ 31/03/2023 đến 30/06/2026, xuất CSV từ công cụ **"Customize a Report"** của
FDIC BankFind (banks.data.fdic.gov/bankfind-suite/financialreporting). `parse_fdic_raw.py` được viết
cho đúng bố cục này (mỗi quý là một khối 3 cột: mã, giá trị, cột trống), nên **chỉ tái tạo được
pipeline nếu xuất đúng loại báo cáo và bố cục đó**.

URL API dưới đây chỉ trả về 8 trường tổng hợp, ở **định dạng khác** (mỗi quý một dòng), nên
**không dùng được với `parse_fdic_raw.py`**. Ghi lại để tham khảo nhanh số tổng:

```
https://banks.data.fdic.gov/api/financials?filters=CERT:628 AND REPDTE:[20230101 TO 20261231]&fields=REPDTE,ASSET,DEP,DEPDOM,LNLSNET,SC,EQ,CHBAL&sort_by=REPDTE&sort_order=DESC&limit=100&format=csv&download=true
```

## Phát hiện chính

### 1. Xu hướng LCR / NSFR (baseline, 14 quý)
LCR: 113% (Q1/2023) → 85% (Q2/2026); NSFR: 137% → 113%. Cả hai giảm dần trong giai đoạn; LDR tăng
từ 45% lên khoảng 54%. Tài sản cấp 2 chỉ chiếm 9,8–13,1% HQLA, nên trần cấp 2 của Basel
(40% / 15%) chưa bao giờ bị chạm.

### 2. Sensitivity và benchmark (kiểm định baseline trước khi stress)
- Proxy thấp hơn LCR công bố của ngân hàng **11,5–33,0 điểm %** ở mọi quý (trung bình −22,6), nhưng
  bám khá sát chiều biến động: tương quan theo mức 0,79, và hai chuỗi cùng chiều ở 8/11 lần thay
  đổi giữa các quý mà LCR công bố có biến động.
- Trong biên hợp lý theo Basel, các giả định ảnh hưởng lớn nhất là tỷ lệ dòng tiền ra của tiền gửi
  và cam kết (`D_FO_IPC` −23,9, `O_OTHER` −19,4, `B_REPO` −17,7 điểm %), cách xử lý tiền gửi tại
  ngân hàng nước ngoài (`A_CASH_FOREIGN` −21,7) và dòng tiền vào từ khoản vay (`L_NBFI_SHORT` +16,3,
  `L_OTH_LE12` +10,8).
- **Không có giả định đơn lẻ nào giải thích được khoảng lệch.** Khoảng lệch là tổng của nhiều lựa
  chọn thận trọng cộng với khác biệt phương pháp mà dữ liệu công khai không tách được: số trung
  bình quý so với số cuối quý, quy tắc Mỹ (12 CFR 249) so với hệ số Basel, và độ chi tiết dữ liệu.

Chi tiết: `mapping/mapping_README.md`, mục "Sensitivity and benchmark".

### 3. Các lỗi phát hiện khi rà soát, đã sửa và ghi lại
`CHCOIN` bị tính trùng bên trong `CHBAL` (xác minh ở 14/14 quý, đã truy được nguyên nhân từ định
nghĩa biểu mẫu Call Report); thang kỳ hạn khoản vay bị trừ vào dư nợ ròng thay vì dư nợ gộp, tạo ra
phần dư âm vô nghĩa; và NSFR ban đầu thiếu 5% RSF mà Basel yêu cầu trên phần chưa giải ngân của các
hạn mức tín dụng / thanh khoản cam kết (bổ sung vào làm NSFR giảm 2–3 điểm % ở mọi quý). Tất cả đã
sửa, reconciliation vẫn khớp tuyệt đối. Chi tiết: `mapping/mapping_README.md`, mục "Issues found in
review and how they were fixed".

### 4. Stress testing (chỉ LCR; đầy đủ trong `STRESS_TESTING_README.md`)
Kịch bản Combined kéo LCR Q2/2026 từ 85,0% xuống 51,0% (−34,0 điểm %). Cú sốc Idiosyncratic
(−31,2) nặng hơn nhiều so với Market-wide (−6,0) vì rút tiền gửi và giải ngân cam kết tín dụng là
khoản tiền lớn hơn hẳn phần haircut tăng thêm trên chứng khoán GSE / trái phiếu địa phương. Với
dòng tiền ra dồn vào đầu kỳ, HQLA đủ dùng 23,8 ngày ở baseline và 9,6 ngày ở kịch bản Combined.

## Giới hạn đã biết (đọc trước khi dùng số)

- Hầu hết dòng tiền vào LCR không được mô hình hoá (0%, trừ `L_NBFI_SHORT`) → proxy thấp hơn thực tế.
- Trading liabilities (`B_TRADEL`) không có dòng tiền ra LCR → proxy cao hơn thực tế ở điểm này
  (−2,5 đến −11,1 điểm % nếu áp outflow 20–100%).
- Chứng khoán cầm cố (`SCPLEDGE`, $78,2 tỷ tại Q2/2026) vẫn được tính vào HQLA; nếu trừ toàn bộ thì
  LCR giảm 7,0 điểm % (xem kiểm định phần bị bỏ sót).
- Giả định kỳ hạn đều (uniform maturity) cho các dòng gộp ≤1 năm.
- Không mô hình hoá management action / counterbalancing capacity trong stress testing.
- 18/48 dòng mapping có `confidence=Low`; mức ảnh hưởng đã được lượng hoá bằng sensitivity, không
  chỉ cảnh báo.
- Hệ số mapping theo Basel (BCBS 238/295), còn LCR công bố theo quy tắc Mỹ và là **số trung bình
  quý**; proxy dùng **số dư cuối quý**.
- Dữ liệu là Call Report của riêng ngân hàng (solo), không phải hợp nhất JPMorgan Chase & Co.
- **NSFR chưa có benchmark** (không dùng số công bố nào để so), nên NSFR proxy chưa được kiểm chứng.
  NSFR proxy cũng chưa có RSF cho nợ phái sinh, và áp 0% RSF cho hạn mức thẻ tín dụng có thể huỷ
  vô điều kiện cũng như bảo lãnh / thư tín dụng (Basel để quốc gia tự quyết).
- Số LCR công bố trong benchmark là **số nhập tay** (14 quý), không do code tạo ra.
- Hệ số sốc trong stress testing là **giả định minh hoạ**, chưa hiệu chỉnh theo kịch bản giám sát
  hay khủng hoảng thực tế; stress không thay đổi dòng tiền vào và không mô hình hoá lỗ do bán tháo.
- Monte Carlo lấy mẫu 4 dòng tiền gửi **độc lập** (tương quan 0); độ lệch chuẩn tương đối 20% là
  tham số tự chọn. Monte Carlo, survival horizon và reverse stress chỉ chạy cho Q2/2026.
- Công thức mapping được tính bằng `eval()` (đã khoá builtins) — phù hợp với CSV do repo tự quản
  lý, **không an toàn với CSV từ nguồn không tin cậy**. Chưa có test tự động.

Danh sách đầy đủ kèm căn cứ từng dòng: `mapping/mapping_README.md` và cột `rationale` trong
`mapping/liquidity_mapping.csv`.
