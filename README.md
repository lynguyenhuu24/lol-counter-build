# LoL Counter Build

Đọc đội hình địch ngay khi vào trận, rồi cho **build đầy đủ 6 món** + **gợi ý Lõi
(ARAM: Mayhem)** + món khắc chế, kèm lý do nêu đích danh tướng địch.
Chạy local, không cần API key, không đọc bộ nhớ game.

## Bản .exe (không cần cài Python)

Nhấp đôi `LoLCounterBuild.exe` trong thư mục `dist/` là overlay mở ra, tự dò trận.
Vào trận ARAM: Mayhem là nó tự biết chế độ (queue 2400) và hiện luôn phần gợi ý lõi.
Muốn tự đóng gói lại:

```
build_exe.bat
```

Bản `.exe` cũng nhận tham số (chạy trong `cmd`):

```
LoLCounterBuild.exe --text --champion Jinx --enemies Malphite,Zac,Sion,Ornn,Shen
LoLCounterBuild.exe --selftest          # kiểm tra bảng luật + build + lõi
LoLCounterBuild.exe --update-data       # tải lại dữ liệu tướng/trang bị (sau patch)
LoLCounterBuild.exe --update-builds     # tải lại build chuẩn của tướng (op.gg)
LoLCounterBuild.exe --update-augments   # tải lại danh sách lõi ARAM: Mayhem
```

Icon tải về được cache ở `data/icons/` cạnh file exe, lần sau mở là hiện ngay.

## Chạy từ mã nguồn

```
python -m lcbuild.fetch_data       # tướng + trang bị (1 lần, ~3 phút)
python -m lcbuild.fetch_builds     # build chuẩn của tướng (op.gg)
python -m lcbuild.fetch_augments   # danh sách lõi ARAM: Mayhem
python -m lcbuild.ui               # mở overlay, tự dò trận
```

Không có trận để thử?

```
python -m lcbuild.ui --text --champion Jinx --enemies Malphite,Zac,Sion
```

## Chế độ ARAM: Mayhem

ARAM khác hẳn Summoner's Rift, nên công cụ xử lý riêng:

- **Không hỏi vai trò.** ARAM không có vai trò cố định, nên công cụ tự suy **nhóm tướng**
  từ chính tướng bạn chơi (`role_of()`: xạ thủ / pháp sư / đỡ đòn / đấu sĩ / hỗ trợ)
  rồi dùng nhóm đó để lọc đồ. Bro không phải chọn gì cả.
- **Tự nhận tướng của bạn.** Không cần nhập tay: overlay đọc tướng bạn chọn từ client.
  Quy trình: vào chọn tướng → hiện ngay **build mẫu + lõi** của tướng đó → vào trận →
  tự lấy **đội hình địch** → **cập nhật lại** build (thêm món khắc chế) và lõi
  (thêm lõi chống địch).
- **Build 6 món** = 1 giày + tối đa 3 món chủ lực của tướng (lấy từ op.gg) + tối đa
  2 món khắc chế đội địch + ô còn lại là món chỉ số hợp nhóm tướng. Có **hạn mức ô**
  cho từng nhóm, vì nếu để món khắc chế chiếm hết 6 ô thì bạn ra trận với 0 sát thương.
- **Lõi (Augment)**: dữ liệu lõi KHÔNG có trong Data Dragon/CommunityDragon nên lấy từ
  [playaram.gg](https://playaram.gg/en/loi-aram-hon-loan) — **211 lõi**, có:
  * **tên + mô tả tiếng Việt đã giải đầy đủ số liệu**;
  * **bậc mạnh yếu S+ → D** do họ xếp hạng (17 lõi S+, 36 S, 53 A…);
  * **độ hiếm** (Kim Cương / Vàng / Bạc) và **nhóm** (ad / ap / tank / crit / support / cd).

  Nguồn cũ (arammayhem.com) bị bỏ vì trả cả placeholder chưa giải ở 16 lõi, ví dụ
  `Gain the required number of Omnivamp` — không dùng được. Giờ kiểm tra tự động chặn
  trường hợp này (`selftest` báo lỗi nếu còn chuỗi `the required number of`).

  Trong game bạn chọn lõi đầu trận rồi cấp 3 / 7 / 11 / 15; API của game **không** cho
  biết 3 lựa chọn đang hiện ra, nên công cụ xếp hạng cả pool theo bậc và bạn tự đối
  chiếu tên.

Lõi được chấm theo hai tín hiệu, **trộn lại** chứ không dùng riêng cái nào:

```
điểm = 0,55 × (điểm luật hợp tướng/đội hình) + 0,45 × (điểm theo bậc S+…D)
```

Chỉ dùng điểm luật thì lõi bậc D có thể vượt lõi bậc S+; chỉ dùng bậc thì mất hết yếu
tố "hợp tướng này, hợp đội hình kia". Luật ví dụ: `Rút Kiếm Ra` chỉ hiện cho tướng đánh
xa hệ AD; địch 2+ tướng trâu thì lõi xuyên giáp vọt lên.

Luật bám **khoá lõi** (`drawyoursword`) chứ không bám tên hiển thị, vì nguồn đổi cách
viết slug theo thời gian và tên hiển thị là tiếng Việt có thể đổi bản dịch.

## Hàng đợi tướng (bench) + hẹn giờ đổi tướng

Trong màn hình chọn tướng ARAM, overlay liệt kê các tướng đang nằm trên **bench**.
Bấm vào một tướng là **đổi ngay khi client cho phép** (hết khoá 3 giây), để không bị
người khác lấy mất. Trễ tối đa là **một nhịp hỏi trạng thái (0,4 giây)**.

Bấm vào tướng nào thì overlay **xem build + lõi của tướng đó** ngay, và nhãn
"Tướng của bạn" ghi rõ `đang xem build; bạn đang giữ …`. Muốn quay lại xem tướng
mình đang giữ thì bấm vào chính tướng đó trong danh sách bench (nếu nó còn trên bench),
hoặc đợi overlay tự cập nhật.

Đồng hồ ở góc phải hiện **thời gian còn lại của pha chọn tướng**, kèm tên pha
(ví dụ `BAN_PICK · còn 60s`). Đây là đồng hồ của client, không phải đếm ngược riêng
cho việc đổi tướng. Vào trận rồi thì cả khối hàng đợi tướng tự ẩn.

```
POST /lol-champ-select/v1/session/bench/swap/{championId}
```

Chi tiết đáng lưu ý:

- Sau khi bench xuất hiện, client **khoá đổi tướng ~3 giây**; trong khoảng đó công cụ
  không gửi (gửi cũng bị từ chối).
- **ARAM không còn lượt đổi tướng (reroll).** Từ V25.13, ARAM dùng **Thẻ Tướng**:
  đầu trận bạn được phát **2 thẻ** (5% cơ hội ra **3**, cộng thêm 0,15% mỗi tướng bạn
  sở hữu) và chọn trong **12 giây đầu**. **Thẻ bạn không chọn sẽ rơi xuống bench** cho
  cả đội chọn. Nên bench sẽ có tướng ngay sau khi bạn chọn thẻ — không cần ai reroll.
- Mặc định gửi sớm **1 giây** trước khi hết giờ, và hỏi trạng thái mỗi **0,4 giây**.
  Chỉnh trong `lcbuild/bench.py` (`DEFAULT_LEAD`, `POLL_INTERVAL`).
- Phần quyết định thời điểm chạy ở **luồng nền**. Ban đầu em để trên luồng giao diện và
  lệnh bị trễ tới 0,0s (thậm chí sau khi hết giờ) chỉ vì giao diện đang tải icon.
- Tướng biến mất khỏi bench thì lệnh tự huỷ. Bấm lại vào tướng khác là đổi lệnh.
- Bấm vào tướng không có trên bench (hoặc không mua được) thì client sẽ từ chối —
  overlay hiện luôn thông báo lỗi nhận được.

### Không thấy tướng trên bench thì kiểm tra thế nào

```
python -m lcbuild.bench      # hoặc: LoLCounterBuild.exe --bench
```

Lệnh này in **đúng những gì client đang trả về**: `benchEnabled`,
`benchChampionIds` (id thô), tướng nhận diện được, phòng tự tạo hay không, chế độ chơi,
và kết luận vì sao chưa có tướng.

Thêm `--raw` để in **toàn bộ** phiên chọn tướng (đã ẩn mật khẩu chat):

```
python -m lcbuild.bench --raw
```

Overlay cũng hiện đúng kết luận đó ngay dưới tiêu đề "Hàng đợi tướng (bench)",
nên không còn im lặng khó hiểu.

Các trường hợp thường gặp:

| Client báo | Nghĩa là |
|---|---|
| `benchEnabled=false` | Chế độ/phòng hiện tại không cho đổi tướng → không có bench để hiện |
| Chưa ai chọn thẻ | Lúc mới vào, bench còn rỗng cho tới khi ai đó chọn thẻ tướng |
| Danh sách rỗng, ARAM thật | Thẻ bạn không chọn mới rơi xuống bench — nếu vẫn rỗng, có thể chế độ không dùng Thẻ Tướng |
| Rỗng ở phòng tự tạo | Phòng tự tạo có thể không dùng Thẻ Tướng nên bench không được phát sẵn |
| Có id nhưng không nhận diện được | Tướng mới chưa có trong dữ liệu → chạy `--update-data` |

Tên chế độ được dịch từ `data/queues.json`, ví dụ queue **3220 = "Howling Abyss All
Random"** (phòng tự tạo ARAM), **450 = ARAM**, **2400 = ARAM: Mayhem**.

Lưu ý về việc đọc dữ liệu bench: client mới trả `benchChampions` (mảng object
`{championId, isPriority}`), bản cũ trả `benchChampionIds` (mảng id). Công cụ đọc
**cả hai** — nếu chỉ đọc một dạng thì sẽ luôn thấy bench rỗng trên client mới.

## Nguồn dữ liệu (không phải Blitz)

Blitz không mở API cho bên ngoài, nhưng không cần Blitz: đội hình địch lấy trực tiếp
từ game qua hai API **công khai, chỉ chạy trên máy bạn**:

| Nguồn | Cổng | Dùng khi nào | Cho biết gì |
|---|---|---|---|
| Live Client Data API | `127.0.0.1:2999` | ngay khi vào trận (màn hình load) | 10 tướng 2 đội, tướng của bạn, chế độ chơi (queue 2400 = Mayhem) |
| LCU API | port trong `lockfile` | màn hình chọn tướng | tướng địch đã lộ |

Trang bị/tướng thì lấy từ dữ liệu công khai, có tiếng Việt:

- **Data Dragon** (`ddragon.leagueoflegends.com`, locale `vi_VN`): tên, giá, mô tả
  trang bị, mô tả kỹ năng, enemytips.
- **CommunityDragon**: `tacticalInfo` (sát thương phép/vật lý, cận chiến/đánh xa),
  thẻ cơ chế do Riot gán (`Self Healing`, `Auto-attack`, `Durable`, …), icon.
- **Meraki Analytics**: chỉ số 1–3 của tướng (control / toughness / mobility / utility).
- **op.gg** (`lol-api-champion.op.gg`): build chuẩn của tướng (giày, món chủ lực) —
  dùng làm khung xương cho build 6 món.
- **arammayhem.com**: danh sách lõi ARAM: Mayhem (Data Dragon không có dữ liệu lõi).

Điểm mấu chốt: **Live Client Data có dữ liệu ngay từ lúc load trận**, đúng thời điểm
bạn cần biết đội hình địch — trước khi ra khỏi bệ.

## Cách nó quyết định

Ba tầng đặc điểm cho mỗi tướng địch:

1. **Cụm từ trong mô tả kỹ năng** (`lcbuild/traits.py` → `PHRASES`). Ví dụ
   `"hồi máu cho bản thân"`, `"sát thương chuẩn"`, `"hất tung"`.
   Kiểm chứng: `python -m lcbuild.traits_audit heal` in ra câu văn làm căn cứ.
2. **Thẻ cơ chế của Riot** (`TAG_MAP`) — bắt các trường hợp mô tả không nói rõ:
   Warwick `Self Healing`, Twitch `Auto-attack`, …
3. **Bảng ghi tay** (`KIT`) cho cơ chế không nằm trong cả hai nguồn trên
   (Vladimir hút máu theo % máu tối đa của bản thân, Malzahar áp chế, …).
   Có chú thích nguồn; khi Riot đổi chiêu thì sửa ở đây.

Từ đặc điểm của cả 5 tướng địch, `lcbuild/advisor.py` bật các luật có thật:

```
Rule(id, kind, item_ids, reason, score, trigger, roles)
```

`trigger(profile)` trả về **danh sách tướng địch kích hoạt luật** — nên lý do đưa ra
luôn nêu đích danh ai, không có gợi ý chung chung. `roles` giới hạn đồ theo **nhóm
tướng** của bạn (đồ pháp sư không lọt vào gợi ý cho tướng đỡ đòn).

Ví dụ output:

```
• Địch nặng sát thương vật lý (4/5 tướng) → ưu tiên Giáp.
• 3 tướng hồi máu (Darius, Lee Sin, Ahri…) → phải có Giảm Hồi Máu.
[  giảm hồi máu] Giáp Gai      2450  Darius, Lee Sin, Ahri hồi máu mạnh, Giáp Gai vừa giảm hồi máu vừa cho giáp
[     phá khiên] Kiếm Ác Xà   2500  Lee Sin, Leona tạo lá chắn, Phá Khiên cắt phần lớn lượng đó
[       giày]    Giày Thủy Ngân 1250  Ahri, Jinx, Leona khống chế nhiều, cần giảm thời gian bị giữ
```

## Dùng

```bash
python -m lcbuild.ui                         # overlay, tự dò trận, làm mới 4 giây
python -m lcbuild.ui --text --champion Jinx \
      --enemies Darius,LeeSin,Ahri,Jinx,Leona   # chỉ in ra terminal
python -m lcbuild.ui --text --champion Ahri --enemies Malphite,Zac,Sion,Ornn,Shen
python -m lcbuild.selftest                    # 10 kịch bản đội hình, kiểm luật
python -m lcbuild.traits_audit heal shield    # xem căn cứ gán đặc điểm
```

Tên tướng nhận cả `Malphite`, `Malphite` (vi), `Dr. Mundo`, `Nunu & Willump`,
`Kai'Sa` và id số. Đội hình tự lấy từ game; `--enemies` để thử tay.

Phím tắt trong overlay: `F5` cập nhật, `Esc` thoát.

## Yêu cầu

- **Bản .exe:** Windows 10/11. Không cần cài gì thêm. File ~13 MB, khởi động chậm
  vài giây ở lần đầu (phải giải nén).
- **Bản mã nguồn:** Python 3.11+ (đã thử 3.14). Phần đọc dữ liệu/gợi ý chỉ dùng thư
  viện chuẩn; đóng gói cần `pyinstaller`; `--shot` cần `pillow` (chỉ để chụp ảnh kiểm tra).
- Game chạy cùng máy, cùng tài khoản Windows (API local chỉ mở cho máy đó).

## Cấu trúc

```
launcher.py             điểm vào của .exe (tự gắn console, ghi log lỗi ra file)
build_exe.bat           đóng gói bằng PyInstaller
lcbuild/paths.py        định vị dữ liệu: chạy mã nguồn hay đã đóng gói
lcbuild/fetch_data.py   tải + cache dữ liệu vào data/ (có resume khi mạng lỗi)
lcbuild/data.py         nạp dữ liệu, tra tướng theo key/vi/en/tên trong game/id
lcbuild/traits.py       3 tầng đặc điểm tướng
lcbuild/advisor.py      bảng luật + máy gợi ý (tự kiểm tra id trang bị)
lcbuild/detect.py       đọc Live Client Data + LCU champ-select
lcbuild/bench.py        đọc hàng đợi tướng ARAM + gửi yêu cầu đổi tướng
lcbuild/swapsched.py    máy trạng thái hẹn giờ đổi tướng (tách để test được)
lcbuild/build.py        ghép build 6 món: giày + món chuẩn + khắc chế + chỉ số
lcbuild/augments.py     122 luật gợi ý lõi ARAM: Mayhem + điểm nền theo meta
lcbuild/fetch_builds.py tải build chuẩn của tướng (op.gg)
lcbuild/fetch_augments.py tải danh sách lõi ARAM: Mayhem
lcbuild/ui.py           overlay tkinter + icon, chế độ --text/--shot
lcbuild/selftest.py     10 kịch bản đội hình địch
lcbuild/traits_audit.py in câu văn làm căn cứ gán đặc điểm
```

## Giới hạn

- Gợi ý là luật theo cơ chế + chỉ số, **không** phải xác suất thắng theo meta
  (không có nguồn thống kê miễn phí ổn định cho thứ đó). Muốn meta win-rate thì phải
  tự crawl op.gg/lolalytics — nằm ngoài phạm vi công cụ này.
- Tướng mới chưa có trong Meraki sẽ thiếu chỉ số (control/toughness) — vẫn nhận diện
  được, chỉ bớt vài luật dựa trên chỉ số (ví dụ Locke, Zaahen ở patch hiện tại).
- Data Dragon và bản việt hoá cập nhật chậm hơn game vài ngày sau patch.
- Dữ liệu cache hiện có 173 tướng / 227 trang bị / 211 lõi / 43 luật đồ / 122 luật lõi.
  Sau khi Riot ra patch mới, chạy lại các lệnh `fetch_data`, `fetch_builds`,
  `fetch_augments`.
- Tên và mô tả lõi giờ là **tiếng Việt**, lấy từ playaram.gg.

## Kiểm chứng

```
python -m lcbuild.selftest        # luật đồ + build 6 món + lõi + hẹn giờ đổi tướng
python -m lcbuild.traits_audit    # in câu văn trong mô tả kỹ năng làm căn cứ gán đặc điểm
```

`selftest` kiểm cả hai chiều: món bắt buộc **phải** có (đội 3 tướng hồi máu thì xạ thủ
phải được gợi ý Lời Nhắc Tử Vong) và món sai nhóm tướng **không được** có (đồ pháp sư
không lọt vào gợi ý cho tướng đỡ đòn). Nó cũng kiểm build 6 món cho **cả 173 tướng**:
đúng 6 ô, không trùng món, không quá 1 giày, không có món thành phần, và tướng sát thương
phải có ít nhất 2 món gây sát thương.

Bản `.exe` được kiểm bằng cách dựng mock Live Client API (HTTPS, đúng cổng 2999 như
game) rồi chạy thật: overlay tự nhận diện tướng của bạn, 5 tướng địch, và ra đúng kết
quả như bản mã nguồn.
