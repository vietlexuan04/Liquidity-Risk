# mapping/ — Ghi chú phương pháp luận

[English](mapping_README.md) | **Tiếng Việt**

> Bản tiếng Việt là bản phụ; bản chính là [mapping_README.md](mapping_README.md). Nếu có khác biệt, bản tiếng Anh được ưu tiên.

## Thư mục này dùng để làm gì

`liquidity_mapping.csv` gán mỗi khoản mục trong `data/processed/jpm_628_wide.csv` (JPMorgan Chase
Bank, N.A., FDIC Cert #628, Q1/2023–Q2/2026) vào một vai trò trong khung LCR/NSFR của Basel III,
kèm hệ số (%) áp dụng. `liquidity_mapping_long.csv` là bản xuất phái sinh dạng "long/tidy" (1 dòng
= 1 khoản mục × 1 vai trò trong 1 ratio) để nạp SQL / Power BI dễ hơn. **File wide mới là nguồn dữ
liệu gốc**; file long được sinh lại bất cứ lúc nào bằng `src/mapping_to_long.py`, không sửa tay.

**Quan trọng: đây là ước tính proxy minh hoạ phương pháp, không phải LCR/NSFR chính thức của
JPMorgan.** Call Report công khai của FDIC không đủ chi tiết để tính đúng theo quy định (không có
lịch dòng tiền ra theo từng ngày trong 30 ngày, không tách tiền gửi "operational" / "non-operational"
theo đúng định nghĩa Basel...). JPMorgan tự công bố LCR chính thức trong hồ sơ SEC — số trong repo
này **không nhằm khớp với số đó**, mục tiêu là minh hoạ cách phân loại và tính toán.

## Cấu trúc `liquidity_mapping.csv` (wide, nguồn gốc)

| Cột | Ý nghĩa |
|---|---|
| `line_id` | Mã tự đặt cho dòng (không phải mnemonic FDIC, vì nhiều dòng là công thức) |
| `side` | `asset` / `liability` / `equity` / `offbs` (ngoại bảng) / `memo` |
| `group` | Nhóm chức năng: cash, securities, loans, deposits, borrowings, capital, commitments... |
| `definition` | Công thức tính từ các mnemonic FDIC trong `jpm_628_wide.csv` |
| `hqla_level` / `hqla_haircut` | Chỉ điền cho dòng đủ điều kiện HQLA (tử số LCR) |
| `lcr_outflow` / `lcr_inflow` | Tỷ lệ dòng tiền ra / vào trong 30 ngày (mẫu số LCR), chỉ điền khi liên quan |
| `nsfr_asf` / `nsfr_rsf` | Hệ số nguồn vốn ổn định sẵn có / hệ số nguồn vốn ổn định yêu cầu (NSFR) |
| `in_balance_sum` | 1 = tính vào tổng đối chiếu bảng cân đối; 0 = ngoại bảng / memo |
| `confidence` | High / Medium / Low — mức tin cậy của hệ số đã chọn (xem bên dưới) |
| `rationale` / `source` | Căn cứ chọn hệ số, trích BCBS 238 (LCR) / BCBS 295 (NSFR) |

**Vì sao nhiều ô để trống**: mỗi dòng chỉ tham gia đúng những vai trò nó có. Khoản cho vay không bao
giờ là HQLA nên các cột `hqla_*` trống ở dòng `loans`. Tiền gửi không có RSF (RSF là chỉ tiêu phía
tài sản) nên cột `nsfr_rsf` trống ở dòng `deposits`. Đây là thiết kế có chủ đích, không phải thiếu
dữ liệu.

## Cách chọn hệ số

- **HQLA level / haircut và LCR outflow / inflow**: theo Basel LCR (BCBS 238), đối chiếu thêm quy tắc
  của Mỹ, Reg WW (12 CFR 249), cho phần phân loại chứng khoán GSE / GNMA vì văn bản Basel không nói
  theo thuật ngữ của Mỹ.
- **ASF / RSF**: theo Basel NSFR (BCBS 295).
- **Ngưỡng NHNN** (LDR/CDR, tỷ lệ vốn ngắn hạn cho vay trung dài hạn, lộ trình LCR/NSFR dự thảo): xem
  `nhnn_ratio_reference.csv`, trích Thông tư 22/2019/TT-NHNN, Thông tư 25/2026/TT-NHNN (nâng trần
  vốn ngắn hạn cho vay trung dài hạn từ 30% lên 40%, hiệu lực 1/7/2026) và dự thảo thông tư thay
  thế Thông tư 22 (công bố 29/4/2026). Chỉ dùng **để đối chiếu ngưỡng**, không đưa vào công thức.
- Khi Call Report không đủ chi tiết theo định nghĩa Basel (ví dụ tiền gửi operational /
  non-operational, xếp hạng trái phiếu địa phương), chọn hệ số **thận trọng hơn** trong hai mức Basel
  cho phép, đánh dấu `confidence=Low` và ghi lý do vào cột `rationale`.

## Đối chiếu tổng (reconciliation) — đã kiểm chứng

Tổng các dòng `side=asset` khớp `ASSET` **lệch đúng 0**, và tổng các dòng
`side in (liability, equity)` khớp `LIABEQ` **lệch đúng 0**, ở **cả 14 quý** (`src/build_mapping.py`
in bảng đối chiếu này mỗi lần chạy). Đây là điều kiện cần để tin rằng mapping bao phủ đủ 100% bảng
cân đối, không thiếu hay trùng dòng nào.

## Lỗi phát hiện khi rà soát và cách sửa

Các lỗi dưới đây được phát hiện khi rà soát lại mapping và được xác minh trên cả 14 quý dữ liệu
(hoặc đối chiếu văn bản Basel) trước khi sửa — không sửa theo suy đoán.

### 1. `CHCOIN` trùng với `CHBAL` (dòng `A_CIPC` / `A_CASH_SCOPE_ADJ`)

Xác minh: đẳng thức `CHBAL = CHFRB + CHNUS + CHUS + CHCIC` đúng **tuyệt đối ở 14/14 quý**. Nếu cộng
thêm `CHCOIN` như một khoản riêng, tổng tài sản sẽ **vượt** `ASSET` đã báo cáo ở mọi quý, đúng bằng
giá trị `CHCOIN`. Kết luận: `CHCOIN` không phải tài sản cộng thêm; giá trị của nó đã nằm sẵn trong
một trong bốn mã kia.

Nguyên nhân (đã xác nhận): bốn mã thành phần theo cấu trúc FFIEC 031 Schedule RC-A, trong đó mục 1
(mã MDRM `RCFD0022`) là "Cash items in process of collection, unposted debits, **and currency and
coin**" — tổng của mục `0020` (khoản đang thu hộ) và `0080` (tiền mặt). Vì vậy `CHCIC` đã gồm cả
tiền mặt, và `CHCOIN` ("Currency and Coin in Domestic Offices", `RCON0080`) là một phần của nó. Khớp
với điều này, `CHCIC ≥ CHCOIN` ở cả 14 quý.

Cách sửa: tách thành hai dòng tường minh — `A_CIPC` = `CHCIC` (giữ nguyên giá trị, đúng nhãn báo cáo)
và `A_CASH_SCOPE_ADJ` = `-CHCOIN` (dòng khử trùng lặp, có ghi lý do) — thay vì giấu phép trừ vào
`A_CIPC` như bản đầu (`CHCIC - CHCOIN`: đúng tổng nhưng tên dòng không phản ánh phép trừ). Bản thân
tiền mặt được tính một lần, là HQLA cấp 1, ở dòng `A_COIN`; phần còn lại của `CHCIC` (khoản đang thu
hộ và tiền mặt tại chi nhánh nước ngoài) vẫn coi là không phải HQLA, hơi thận trọng. Do đã xác nhận
được nguyên nhân, `A_CASH_SCOPE_ADJ` nay là `confidence=High`.

### 2. Dư nợ "phần dư" bị âm (dòng `L_RECON`)

Nguyên nhân: lịch kỳ hạn / định giá lại khoản vay (`LNRS3LES`, `LNRS3T12`, ... `LNOTOV15` — Schedule
RC-C Part I) được báo cáo theo **giá trị gộp**, chưa trừ dự phòng. Bản đầu lấy `LNLSNET` (dư nợ
ròng) trừ đi các bucket, tạo ra phần dư **âm** (khoảng **−16,5 tỷ USD** tại Q2/2026) — vô nghĩa về
kinh tế vì khoản vay không thể âm.

Xác minh: `LNLSNET = LNLSGR − LNATRES` đúng tuyệt đối, và `LNLSGR − Σ(bucket)` luôn **dương**, ổn định
ở **0,5–0,7% tổng dư nợ gộp** qua cả 14 quý (hợp lý: phần dư nợ nằm ngoài lịch, ví dụ nợ ngừng dự
thu lãi).

Cách sửa: `L_RECON` nay lấy gốc là `LNLSGR`, và thêm dòng riêng `A_ALLOW` = `−LNATRES` để thể hiện dự
phòng một cách tường minh (dòng giảm trừ tài sản, không có trọng số RSF riêng vì không phải rủi ro
thanh khoản kinh tế).

**Cơ sở tính RSF cho khoản vay**: NSFR áp hệ số RSF lên **giá trị ghi sổ ròng**, không phải giá trị
gộp. Vì lịch `LNRS*/LNOT*` chỉ có ở mức gộp, `lcr_engine.py` nhân mọi dòng `group=loans` với hệ số
`LNLSNET / LNLSGR` (≈98,3% tại Q2/2026, thay đổi theo quý) **trước khi** áp `nsfr_rsf`. Cách này xấp
xỉ RSF trên cơ sở ròng mà vẫn giữ độ chi tiết kỳ hạn của lịch gộp. Hệ số được áp ở bước tính toán,
không lưu vào `liquidity_mapping.csv`, vì nó thay đổi mỗi quý.

### 3. NSFR thiếu RSF trên cam kết chưa giải ngân (các dòng `O_*`)

Basel NSFR yêu cầu **5% RSF trên phần chưa giải ngân của các hạn mức tín dụng và thanh khoản không
huỷ ngang hoặc huỷ ngang có điều kiện**; RSF cho các nghĩa vụ tài trợ tiềm tàng khác (hạn mức có thể
huỷ vô điều kiện, bảo lãnh, thư tín dụng) do quốc gia tự quyết. Bản đầu chỉ gán outflow LCR cho các
dòng ngoại bảng, nên thiếu phần RSF này.

Cách sửa: `O_HELOC`, `O_CRE`, `O_OTHER` (hạn mức cam kết) nay có RSF 5%; `O_CARD` (hạn mức thẻ tín
dụng, có thể huỷ vô điều kiện) và `O_SBLC` (thư tín dụng dự phòng và bảo lãnh) để 0% theo lựa chọn
quốc gia tự quyết, có ghi lý do trong `rationale` (5% cho `O_SBLC` là một mục sensitivity; 5% cho hạn
mức thẻ sẽ cộng thêm khoảng $56 tỷ RSF). Tác động: NSFR giảm 2,1–2,9 điểm % ở mọi quý (Q2/2026:
115,1% → 112,9%); LCR không đổi.

## Các giả định lớn khác cần biết

1. **Hầu hết dòng tiền vào LCR không được mô hình hoá** — mặc định 0%, trừ `L_NBFI_SHORT`. Đây là giả
   định thận trọng, kéo LCR proxy **xuống**. Riêng với reverse repo (`A_REVREPO`), 0% thực ra là hệ
   số đúng theo Basel nếu tài sản đảm bảo là cấp 1 (LCR40.79); cơ cấu tài sản đảm bảo chưa biết.
2. **Trading liabilities / phái sinh** (`B_TRADEL`) **không có dòng tiền ra LCR** — với ngân hàng có
   hoạt động trading lớn như JPMorgan, đây có thể là khoản outflow đáng kể bị thiếu (kéo proxy
   **lên**, ngược chiều với giả định 1).
3. **Chứng khoán cầm cố** (`M_SCPLEDGE`, $78,2 tỷ tại Q2/2026) là dòng memo và **không bị trừ khỏi
   HQLA**. Theo quy tắc Mỹ, chứng khoán cầm cố tại Ngân hàng Dự trữ Liên bang nhưng chưa dùng để
   bảo đảm khoản vay nào vẫn là HQLA hợp lệ, và Call Report không cho biết bên nhận cầm cố. Trường
   hợp trừ toàn bộ được kiểm định riêng (−7,0 điểm % LCR).
4. **Giả định kỳ hạn đều** cho các dòng gộp `<=1 năm` (30/365 được coi là rơi vào 30 ngày đầu), vì
   Call Report không chia nhỏ dưới mốc 1 năm ở nhiều dòng nguồn vốn.

Toàn bộ giả định khác (gồm 18/48 dòng `confidence=Low`) được ghi theo từng dòng trong cột
`rationale` của CSV thay vì lặp lại ở đây, để tránh hai nguồn lệch nhau.

## Sensitivity và benchmark (kiểm định baseline trước khi stress test)

Baseline được kiểm định qua hai bước trước khi thiết kế kịch bản stress — vì stress một con số mà
bản thân nó đã là ước lượng không chắc chắn (18/48 dòng `confidence=Low`) sẽ chồng hai lớp bất định
mà không tách được lớp nào đóng góp bao nhiêu.

### 1. Sensitivity từng dòng (one-at-a-time) trên các dòng `confidence=Low`, Q2/2026

Baseline: LCR = 85,0%, NSFR = 112,9%. Mỗi dòng được đổi giữa hai giá trị mà Basel cho phép đối với
nhóm thay thế mà dòng đó có thể thuộc về (`src/sensitivity.py`, dict `BOUNDS`), giữ nguyên các dòng
khác. **Δ = (ratio ở hệ số cao) − (ratio ở hệ số thấp)**, tức độ rộng khoảng dao động do riêng giả
định đó gây ra, không phải mức chênh so với baseline hiện tại (baseline nằm đâu đó giữa hai biên).

| Dòng (biên đã thử) | Δ LCR (điểm %) | Dòng (biên đã thử) | Δ NSFR (điểm %) |
|---|---:|---|---:|
| `D_FO_IPC` (outflow 25%→100%) | −23,9 | `A_TRADE` (RSF 15%→100%) | −39,9 |
| `A_CASH_FOREIGN` (haircut 0%→100%) | −21,7 | `D_DOM_FOR` (ASF 0%→50%) | +2,5 |
| `O_OTHER` (outflow 10%→50%) | −19,4 | `A_CASH_FOREIGN` (RSF 0%→15%) | −2,0 |
| `B_REPO` (outflow 0%→100%) | −17,7 | 8 dòng khác | <1,5 mỗi dòng |
| `L_NBFI_SHORT` (inflow 0%→100%) | +16,3 | | |
| `L_OTH_LE12` (inflow 0%→15,3%*) | +10,8 | | |
| `D_DOM_FOR` (outflow 40%→100%) | −4,9 | | |
| `A_REVREPO` (inflow 0%→15%) | +4,9 | | |
| `B_OTHL`, `S_MUNI`, `O_SBLC` | <3,5 mỗi dòng | | |

\* 15,3% = tỷ lệ inflow 50% của Basel chỉ áp cho phần của dòng có thể đáo hạn trong 30 ngày (30/90
của bucket ≤3 tháng, cùng quy tắc kỳ hạn đều đã dùng cho `L_NBFI_SHORT`), quy ra tỷ lệ trên toàn dòng.

**Trần lý thuyết (không dùng làm bằng chứng).** Nếu cho hai dòng inflow 0% mức inflow tối đa có thể
tưởng tượng — 50% trên toàn bộ dòng `L_OTH_LE12` ≤12 tháng, bỏ qua kỳ hạn, và 100% trên toàn bộ
$407 tỷ reverse repo (toàn bộ tài sản đảm bảo không phải HQLA và toàn bộ đáo hạn trong 30 ngày) —
LCR sẽ tăng lần lượt +49,1 và +48,2 điểm %. Bản README trước đã dùng hai con số này để lập luận rằng
hai giả định đó có thể giải thích khoảng lệch benchmark. Lập luận đó bị phóng đại: tác động hợp lý
theo Basel, có tính đến kỳ hạn, chỉ là +10,8 và +4,9 điểm %.

**Kiểm định phần bị bỏ sót.** `B_TRADEL` (trading liabilities, hiện không có outflow): outflow
20% / 50% / 100% làm LCR giảm 2,5 / 6,0 / 11,1 điểm %. `M_SCPLEDGE` (chứng khoán cầm cố, hiện vẫn
tính vào HQLA): trừ toàn bộ khỏi cấp 1 làm LCR giảm 7,0 điểm % (85,0% → 78,1%).

**Biên kết hợp**: đẩy cả 22 biên hợp lý của 17 dòng đã thử cùng một hướng thì LCR dao động
35,7%–180,0%, NSFR 104,0%–157,3%. **Đây là giới hạn ngoài lý thuyết, không phải khoảng tin cậy**
(xác suất cả 17 giả định cùng sai một hướng gần bằng 0) — khi trích dẫn hãy dùng bảng từng dòng ở trên.

Chưa kiểm định từng dòng: `B_TRADEL` (đã có kiểm định phần bị bỏ sót). 17 dòng Low còn lại đều đã
được kiểm định. Kết quả đầy đủ: `data/processed/sensitivity_results.csv`
(cột `test_type`: plausible / ceiling / omission / envelope).

### 2. Benchmark với LCR do JPMorgan Chase Bank, N.A. công bố (đủ 14 quý)

| Quý | LCR proxy | LCR công bố (ngân hàng, trung bình) | Lệch (điểm %) |
|---|---:|---:|---:|
| Q1/23 | 113,2% | 140% | −26,8 |
| Q2/23 | 105,3% | 129% | −23,7 |
| Q3/23 | 104,9% | 123% | −18,1 |
| Q4/23 | 117,5% | 129% | −11,5 |
| Q1/24 | 107,3% | 129% | −21,7 |
| Q2/24 | 105,6% | 125% | −19,4 |
| Q3/24 | 95,7% | 121% | −25,3 |
| Q4/24 | 107,7% | 124% | −16,3 |
| Q1/25 | 97,2% | 124% | −26,8 |
| Q2/25 | 100,1% | 120% | −19,9 |
| Q3/25 | 91,7% | 117% | −25,3 |
| Q4/25 | 95,3% | 115% | −19,7 |
| Q1/26 | 90,5% | 120% | −29,5 |
| Q2/26 | 85,0% | 118% | −33,0 |

Nguồn số công bố: Form 10-Q của JPMorgan Chase & Co. (SEC EDGAR, CIK 0000019617), bảng
"Consolidated financial highlights", dòng "JPMorgan Chase Bank, N.A. LCR (average)" — 10-Q quý
1Q24 (gồm Q1/23–Q1/24), 1Q25 (Q2/24–Q1/25) và 2Q26 (Q2/25–Q2/26). Lưu ý: số công bố là **trung bình
quý**, còn proxy dùng **số dư cuối quý** — khác biệt về phương pháp, không chỉ về độ chi tiết dữ liệu.

**Cách đọc benchmark**:
- Proxy **thấp hơn số công bố ở mọi quý, 11,5–33,0 điểm %** (trung bình −22,6). Khoảng lệch rộng hơn
  ở hai quý gần nhất (−29,5 và −33,0) nhưng không nới rộng đều theo thời gian.
- Proxy **bám khá sát chiều biến động**: tương quan theo mức 0,79, và hai chuỗi cùng chiều ở 8/11
  lần thay đổi giữa các quý mà LCR công bố có biến động.
- **Không thể quy khoảng lệch cho một giả định duy nhất.** Trong biên hợp lý của Basel, không dòng
  nào làm LCR dịch chuyển quá ~24 điểm %, và khoảng lệch đến từ nhiều nguồn mà dữ liệu công khai
  không tách được: giả định inflow thận trọng (`L_OTH_LE12`, `A_REVREPO`, `L_NBFI_SHORT`), lựa chọn
  outflow thận trọng (ví dụ `D_DOM_FOR` ở mức 100%), hệ số Basel so với quy tắc Mỹ, số trung bình so
  với số cuối quý — bù trừ một phần bởi các lựa chọn tác động ngược chiều (bỏ sót `B_TRADEL`, coi
  `A_CASH_FOREIGN` là cấp 1, giữ chứng khoán cầm cố trong HQLA).
- Baseline **cố tình không tinh chỉnh** để thu hẹp khoảng lệch: giữ giả định Basel thận trọng, nhất
  quán dễ bảo vệ hơn là hiệu chỉnh theo số công bố của một ngân hàng (rủi ro overfitting).

**Nguồn gốc file**: cột LCR công bố là **số nhập tay** từ hồ sơ (`src/benchmark.py`, dict
`REAL_LCR`), không do code tính; script chỉ ghép với LCR proxy từ `ratios_by_quarter.csv` và tính
chênh lệch. NSFR **chưa có benchmark**, nên NSFR proxy chưa được đối chiếu với số công bố.

Dữ liệu đầy đủ: `data/processed/lcr_benchmark.csv`.

## Phạm vi dữ liệu và đơn vị

- Mọi số tiền tính bằng **nghìn USD** (đơn vị FDIC). Ví dụ 957.000.000 nghĩa là $957 tỷ.
- Dữ liệu là Call Report của **riêng JPMorgan Chase Bank, N.A.** (solo), không phải báo cáo hợp nhất
  của JPMorgan Chase & Co.
- Hệ số mapping theo Basel (BCBS 238/295); chỉ phần phân loại chứng khoán có đối chiếu Reg WW. LCR
  công bố dùng để benchmark tính theo quy tắc Mỹ, nên một phần khoảng lệch đến từ khác biệt phương
  pháp, không chỉ từ độ chi tiết dữ liệu.

## Công thức tính ratio (cài đặt trong `src/lcr_engine.py`)

```
HQLA theo cấp   = Σ(giá trị tài sản × (1 − haircut))           trên các dòng có hqla_level = L1 / L2A / L2B
HQLA            = L1 + L2A + L2B − điều chỉnh trần              Basel LCR30.45–30.46 (giản lược)
điều chỉnh trần = max(L2A + L2B − 2/3 × L1,  L2B − 15/85 × (L1 + L2A),  0)
                  → cấp 2 ≤ 40% HQLA, cấp 2B ≤ 15% HQLA (chưa bị chạm trong dữ liệu này)
LCR outflow     = Σ(giá trị nợ phải trả × lcr_outflow) + Σ(giá trị ngoại bảng × lcr_outflow)
LCR inflow      = Σ(giá trị tài sản × lcr_inflow)
LCR             = HQLA / max(LCR outflow − LCR inflow, 25% × LCR outflow)   [trần inflow 75%]

ASF             = Σ(giá trị nợ phải trả × nsfr_asf) + Σ(giá trị vốn chủ sở hữu × nsfr_asf)
RSF             = Σ(giá trị tài sản × nsfr_rsf × k) + Σ(phần ngoại bảng chưa giải ngân × nsfr_rsf)
                  [k = LNLSNET / LNLSGR cho group=loans, còn lại 1]
NSFR            = ASF / RSF

LDR             = LNLSNET / DEP
```

Mỗi dòng chỉ đóng góp qua đúng những vai trò nó có (dòng ngoại bảng không cộng vào tổng bảng cân đối
nhưng vẫn cộng vào outflow LCR và RSF của NSFR; dòng memo không đóng góp vào đâu cả).
