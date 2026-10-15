# Stress testing — phương pháp luận và kết quả

[English](STRESS_TESTING_README.md) | **Tiếng Việt**

> Bản tiếng Việt là bản phụ; bản chính là [STRESS_TESTING_README.md](STRESS_TESTING_README.md). Nếu có khác biệt, bản tiếng Anh được ưu tiên.

Áp dụng `src/stress_testing.py` lên baseline đã kiểm định (xem `mapping/mapping_README.md`, mục
"Sensitivity and benchmark") — **chỉ stress LCR**, phiên bản này chưa stress NSFR. Toàn bộ số
liệu nằm trong `data/processed/stress_*.csv`, hoặc trong `liquidity_risk.db` (các bảng `stress_*`).

Dữ liệu gốc tính bằng nghìn USD; các bảng dưới đây đã quy đổi sang tỷ USD ($B).

## Các giả định tường minh quan trọng

**Không mô hình hoá management action / counterbalancing capacity.** Mô hình không giả định ngân
hàng bán tài sản ngoài HQLA, rút hạn mức dự phòng hay cắt giảm cho vay mới để ứng phó cú sốc. Kết
quả là phản ứng thuần cơ học của bảng cân đối như đã báo cáo, nên **cố tình bi quan hơn** những gì
một ngân hàng thật sẽ trải qua.

**Baseline proxy đã thấp hơn LCR JPMorgan công bố 11,5–33,0 điểm %** (xem benchmark). Vì vậy mọi
kết quả đều báo cả LCR tuyệt đối lẫn **mức chênh so với baseline của chính mô hình**. Nếu chỉ đọc
số tuyệt đối sẽ dễ hiểu nhầm là ngân hàng đang gặp khó; thực ra đó là đặc tính bảo thủ của proxy,
không phải điểm yếu thật của JPMorgan.

**Hệ số bị chặn trong [0%, 100%].** Tỷ lệ rút tiền hay haircut trên 100% không có ý nghĩa kinh tế,
nên mọi hệ số sau khi stress đều bị chặn trên ở 100% (điều này ảnh hưởng tới reverse stress test).

## 1. Ba kịch bản cố định

| | Idiosyncratic | Market-wide | Combined |
|---|---|---|---|
| Tiền gửi được bảo hiểm, không qua môi giới (`D_INS_STABLE`) | 5% → 10% | không đổi | 10% |
| Tiền gửi môi giới được bảo hiểm (`D_INS_BRO`) | 10% → 25% | không đổi | 25% |
| Tiền gửi DN không được bảo hiểm / chi nhánh nước ngoài (`D_DOM_UNINS_OTH` / `D_FO_IPC`) | 40% → 70% | không đổi | 70% |
| Cam kết tín dụng chưa giải ngân (`O_*`) | giải ngân x1,5 | không đổi | x1,5 |
| Haircut HQLA GSE / trái phiếu địa phương (`S_GSE` / `S_MUNI`) | không đổi | 15% → 25% / 50% → 65% | 25% / 65% |
| Vốn repo (`B_REPO`) | không đổi | 25% → 50% | 50% |

`B_ST` (vay khác / ứng vốn FHLB kỳ hạn ≤1 năm) **không bị stress**: baseline đã giả định 100% không
tái tục đối với phần đáo hạn trong 30 ngày, đây là mức tối đa của Basel cho nguồn vốn bán buôn
không có tài sản đảm bảo đến hạn. Phần còn lại chưa đến hạn theo hợp đồng trong cửa sổ 30 ngày, nên
muốn stress thì phải đổi giả định kỳ hạn chứ không phải đổi tỷ lệ rút.

**Về độ lớn các cú sốc**: đây là **giả định minh hoạ**, chưa hiệu chỉnh theo một kịch bản giám sát
cụ thể (Fed, Basel) hay dữ liệu của một cuộc khủng hoảng trong quá khứ. Kết quả dùng để so sánh độ
nhạy tương đối giữa các nhóm rủi ro, không phải dự báo LCR trong khủng hoảng thật.

**Kết quả (LCR %, Q2/2026; đủ 14 quý trong `stress_scenarios_by_quarter.csv`):**

| Kịch bản | LCR | Δ so với baseline (điểm %) | Δ so với baseline (%) |
|---|---:|---:|---:|
| Baseline (không stress) | 85,0% | — | — |
| Idiosyncratic | 53,8% | −31,2 | −36,7% |
| Market-wide | 79,0% | −6,0 | −7,1% |
| Combined | 51,0% | −34,0 | −40,0% |

**Nhận xét**: Idiosyncratic nặng hơn Market-wide rất nhiều (−31 so với −6 điểm %) vì rút tiền gửi
và giải ngân cam kết là khoản tiền lớn hơn hẳn phần haircut tăng thêm trên chứng khoán GSE / trái
phiếu địa phương. Các chứng khoán này chỉ chiếm phần nhỏ trong $957 tỷ HQLA: tài sản cấp 1 chiếm
$838 tỷ (chủ yếu $483 tỷ trái phiếu Kho bạc Mỹ và $244 tỷ tiền gửi tại ngân hàng nước ngoài, giả
định là dự trữ tại ngân hàng trung ương nước ngoài) và giữ haircut 0%. Xu hướng này **đúng ở cả 14
quý** (Idiosyncratic −31 đến −44, Market-wide −4 đến −7, Combined −34 đến −46 điểm %).

## 2. Monte Carlo rút tiền gửi (Q2/2026, 10.000 lần mô phỏng)

Tỷ lệ rút của 4 dòng tiền gửi (`D_INS_STABLE`, `D_INS_BRO`, `D_DOM_UNINS_OTH`, `D_FO_IPC`) được lấy
từ phân phối Beta có trung bình bằng giá trị kịch bản Combined (độ lệch chuẩn = 20% trung bình).
Các tham số khác (haircut, giải ngân cam kết, repo) **giữ cố định ở giá trị Combined**; không ngẫu
nhiên hoá cùng lúc vì không có cơ sở để chọn tương quan giữa các loại rủi ro khác nhau.

Hai lựa chọn mô hình quyết định phần đuôi: (1) 4 dòng tiền gửi được lấy mẫu **độc lập** (tương quan
0), nên đuôi phân phối có thể mỏng hơn thực tế — khi khủng hoảng, các loại tiền gửi thường bị rút
cùng lúc; (2) độ lệch chuẩn tương đối 20% là **tham số tự chọn**, chưa hiệu chỉnh.

| Phân vị | LCR | Δ so với baseline (điểm %) |
|---|---:|---:|
| p5 | 44,5% | −40,5 |
| p25 | 47,7% | −37,4 |
| p50 | 50,7% | −34,4 |
| p75 | 54,5% | −30,5 |
| p95 | 61,7% | −23,3 |

**Kiểm tra chéo**: trung vị (50,7%) sát với kịch bản Combined điểm (51,0%), đúng như kỳ vọng khi phân
phối có tâm ở cùng các hệ số. Trung vị thấp hơn một chút vì phân phối Beta của hai dòng rút 70% lệch
trái (trung vị tỷ lệ rút nhỉnh hơn 70%), và hai dòng này chiếm phần lớn dòng tiền ra.

## 3. Survival horizon (Q2/2026)

Số ngày cho tới khi dòng tiền ra ròng luỹ kế làm cạn HQLA (giả định HQLA dùng được ngay từ ngày 1),
theo hai dạng phân bổ của cùng một lượng dòng tiền ra ròng 30 ngày:

- **Đều** (`net_outflow / 30` mỗi ngày). Lưu ý con số này chính là **30 × LCR** — không thêm thông
  tin gì ngoài LCR, chỉ giữ để tham chiếu.
- **Dồn đầu kỳ** (minh hoạ): 40% dòng tiền ra 30 ngày rơi vào ngày 1–5 (8%/ngày), 60% còn lại rải
  trong ngày 6–30 (2,4%/ngày), phản ánh việc rút tiền thường dồn vào đầu khủng hoảng. Đây là cột
  mang thông tin.

| Kịch bản | HQLA | Dòng tiền ra ròng 30 ngày | LCR | Số ngày (đều) | Số ngày (dồn đầu kỳ) |
|---|---:|---:|---:|---:|---:|
| Baseline | $957,1B | $1.125,7B | 85,0% | 25,5 | 23,8 |
| Idiosyncratic | $957,1B | $1.779,3B | 53,8% | 16,1 | 10,7 |
| Market-wide | $940,6B | $1.190,5B | 79,0% | 23,7 | 21,3 |
| Combined | $940,6B | $1.844,1B | 51,0% | 15,3 | 9,6 |

Dồn đầu kỳ chỉ làm mất khoảng 2 ngày ở baseline nhưng mất 5–6 ngày ở các kịch bản rút tiền gửi:
cú sốc càng nặng thì thời điểm rút càng quan trọng. Baseline đã dưới 30 ngày vì baseline proxy thấp
hơn LCR công bố — không phải JPMorgan thật sự chỉ trụ được khoảng 24 ngày.

## 4. Reverse stress test (Q2/2026)

Cường độ sốc θ (θ = 0: baseline, θ = 1: đúng kịch bản Combined). Mỗi hệ số được nội suy tuyến tính
(ngoại suy ra ngoài [0, 1] khi cần) rồi **chặn trong [0%, 100%]**:

| LCR mục tiêu | θ cần | Diễn giải |
|---|---:|---|
| 100% | **−0,23** | Baseline đã dưới 100%, nên phải **giảm stress xuống dưới cả baseline** 23% khoảng cách của kịch bản Combined. Đây là minh chứng cho tính bảo thủ của proxy, không phải JPMorgan thật sự dưới ngưỡng quy định. |
| 75% | 0,20 | Chỉ cần 20% cường độ Combined đã chạm 75%. |
| 50% | 1,05 | Cần hơi quá (105%) cường độ Combined để chạm 50%. |
| Sàn | — | Khi **mọi** hệ số bị stress đều ở 100% (toàn bộ tiền gửi và cam kết bị stress đều bị rút/giải ngân, mất toàn bộ vốn repo, chứng khoán GSE / địa phương mất hết giá trị), LCR chạm đáy ở **17,0%**. Muốn thấp hơn phải có cú sốc nằm ngoài các đòn bẩy của kịch bản này (ví dụ lỗ trên tài sản cấp 1), nên trạng thái "cạn hoàn toàn HQLA" không đạt được trong họ kịch bản này. |

## Giới hạn của phần stress testing

- Chỉ stress LCR; NSFR chưa stress.
- Kịch bản chỉ thay đổi tỷ lệ dòng tiền ra và haircut. **Không stress dòng tiền vào**, không mô hình
  hoá lỗ do bán tháo HQLA.
- Mục 2 (Monte Carlo), 3 (survival horizon) và 4 (reverse stress) chỉ chạy cho **Q2/2026**.
- Reverse stress nội suy **tuyến tính** theo θ; phân bổ dồn đầu kỳ trong survival horizon là minh hoạ.
- Không có management action (xem phần giả định ở đầu file).

## Cách tra cứu

Toàn bộ bảng trên nằm trong `liquidity_risk.db` (SQLite): `stress_scenarios_by_quarter`,
`stress_montecarlo_2026q2`, `stress_survival_horizon`, `stress_reverse_test`. Join với
`ratios_by_quarter` qua `report_period` (lưu dạng TEXT, `YYYYMMDD`) để so với baseline. Build lại DB
bất cứ lúc nào bằng `python3 src/db.py` (đọc trực tiếp từ các CSV trong `data/processed/` và
`mapping/`; không sửa tay file `.db`).
