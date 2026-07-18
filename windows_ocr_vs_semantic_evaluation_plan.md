# Danh Gia Windows Build: OCR vs Vision vs Semantic Automation

## Tom tat ket luan

Nhanh hien tai `refactor/semantic-automation` la huong dung nhat de build ban Windows rieng.

- GlobalProtect: giu OpenCV + log parser hien tai, chua nen doi sang OCR.
- CAPAM Address/Login: dung Java Access Bridge la chinh, tot hon OCR va tot hon vision pixel.
- CAPAM Device List: van phai dung vision/template matching vi CAPAM custom-rendered khong expose control tree.
- Windows Security: dung focus mac dinh + keyboard, khong nen OCR neu dialog khong expose child controls.
- OCR kha thi lam lop phu de doc label/text, nhung khong nen lam primary actuator de click/input.

## Trang thai repo

- Dang checkout: `refactor/semantic-automation`
- Track remote: `origin/refactor/semantic-automation`
- Syntax check: `python3 -m py_compile main.py config.py adapters/*.py automation/*.py core/*.py vision/*.py ui/*.py` pass.
- Luu y: truoc khi checkout, thay doi local tren `main` da duoc stash voi ten `before-checkout-refactor-semantic-automation`.

## So sanh nhanh cac nhanh

### `main`

`main` la ban legacy mot-file, dung OpenCV contour, template matching va toa do fallback.

Diem manh:

- Don gian, it module.
- Da co flow Linux dang chay.
- Co template matching cho RDP.

Diem yeu:

- Phu thuoc pixel, DPI, theme, focus, timing.
- CAPAM Java Swing co the render khac nhau theo scale, nen contour de sai.
- Windows Security trong `main` co logic detect 2 field bang vision, nhung thuc te dialog khong expose control va anh/dialog co the thay doi theo Windows build.
- Kho bao tri vi UI, adapter, workflow va vision nam chung mot file.

### `origin/windows`

`windows` da tach module va cai thien Windows adapter, capture HWND, focus HWND, template scale, FSM.

Diem manh:

- Kien truc tot hon `main`.
- Co `adapters/windows.py`, `core/*`, `vision/*`.
- Template matching co scale scan cho DPI 100/125/150.
- RDP click co verify foreground, stable frames, exact device-list window.

Diem yeu:

- CAPAM Address/Login van primary bang OpenCV contour.
- Khi Java Swing tu ve field, contour va ROI van phu thuoc giao dien.
- Neu window render cham/bi che/scale la nguon loi chinh.

### `refactor/semantic-automation`

Nhanh nay them `automation/java_access_bridge.py` va dung Java Access Bridge cho CAPAM.

Diem manh:

- CAPAM Address/Login chuyen sang semantic automation khi JAB doc duoc tree.
- `CAPAMJAB` attach theo HWND, tim node theo role/name, set text/click action truc tiep.
- Vision chi la fallback cho CAPAM Address/Login va primary cho Device List.
- Windows Security da bo detect contour, dung focus mac dinh + keyboard + postcondition.
- Build Windows da them hidden imports cho JAB wrapper.

Diem yeu/rui ro:

- `CAPAMJAB.find_bridge()` dang hardcode `runtime-17.0.10_7`; da co fallback `runtime/bin` va `jre/bin`, nhung runtime version khac nam trong folder `runtime-xx` se fail.
- `jab.has()` chi catch `JABUnavailable`; neu `_find_node()` raise `RuntimeError` vi khong thay node, exception co the thoat ra ngoai thay vi return `False`.
- `CAPAMJAB.set_text()` va `set_combo_text()` insert text nhung khong clear field truoc, co nguy co append neu field co san noi dung.
- CAPAM Login dang truyen `password_prefix + otp` vao CAPAM. Theo tai lieu truoc do CAPAM login dung password tinh, khong cong OTP. Can xac minh nghiep vu.
- GlobalProtect van dung vision/click, chua dung UIA vi plan ghi UIA tree rebuild khong on dinh.

## OCR co kha thi khong

OCR kha thi, nhung chi nen dung de bo sung evidence, khong nen thay primary flow.

Ly do:

- OCR doc text/label, khong biet control action that su. Sau khi doc duoc label van phai suy ra toa do click.
- CAPAM Java Address/Login da co Java Access Bridge doc duoc role/name/control. JAB chinh xac hon OCR vi lay semantic tree that.
- Device List custom-rendered co the OCR doc duoc ten may/IP/nhan row, nhung nut RDP la icon/button. OCR khong giai quyet tot viec click dung nut cung dong bang template matching.
- GlobalProtect co log parser lam source state tot hon OCR. Field detection hien tai du de tim 1/2 input, OCR khong tang do tin cay nhieu neu label thay doi/ngon ngu/theme.
- Windows Security child fields khong expose, nhung thuc te focus mac dinh vao Username. OCR tim field se kem hon keyboard deterministic neu dialog layout thay doi.

Truong hop nen dung OCR:

- Doc label trong Device List de xac nhan dung row khi template label `template_200.png`/`template_12.png` hay bi fail.
- Doc loi dang nhap CAPAM/GP tren man hinh khi log khong co.
- Tao debug report: screenshot + OCR text + template scores + state.

Truong hop khong nen dung OCR:

- Click/input primary vao CAPAM Address/Login khi JAB doc duoc control.
- Thay template matching RDP hoan toan.
- Thay keyboard flow Windows Security.

## Do chinh xac du kien

| Thanh phan | Main vision | Windows vision | OCR | Semantic/JAB |
|---|---:|---:|---:|---:|
| GP Portal/Credentials | Trung binh | Kha | Trung binh | Thap-kha thi nhung chua on dinh |
| CAPAM Address | Trung binh | Kha | Trung binh | Cao |
| CAPAM Login | Trung binh | Kha | Trung binh | Cao |
| CAPAM Device List row | Kha neu template dung | Kha-cao voi scale | Kha cho text, yeu cho icon | Khong kha dung |
| RDP button | Kha | Kha-cao | Yeu-trung binh | Khong kha dung |
| Windows Security | Yeu-trung binh | Kha bang keyboard | Trung binh | Khong expose child controls |

## De xuat kien truc Windows build rieng

Primary stack:

- FSM hien tai trong `core/state_machine.py`.
- Windows adapter trong `adapters/windows.py`.
- GP: log parser + OpenCV field detector + foreground guard.
- CAPAM Address/Login: Java Access Bridge.
- Device List: OpenCV template matching tren exact HWND.
- Windows Security: exact dialog HWND + keyboard + postcondition.
- OCR: optional diagnostic/fallback cho Device List va error text.

Khong nen fork ra codebase moi neu chua can. Nen giu nhanh Windows rieng nhung code modular hien tai da du tot de dong goi Windows-only EXE.

## Plan thuc hien

### Phase 1: Lam on dinh refactor hien tai

1. Sua `CAPAMJAB.find_bridge()` de scan runtime linh hoat: `runtime-*`, `runtime`, `jre`.
2. Sua `CAPAMJAB.has()` de catch moi exception lookup va return `False`.
3. Them clear text truoc `insert_text()` trong JAB field/combo neu wrapper ho tro select/delete hoac fallback focus + Ctrl+A.
4. Xac minh CAPAM password co can OTP khong. Neu khong, sua `core/state_machine.py` de CAPAM Login dung `password_prefix`, GP dung `password_prefix + otp`.
5. Them log evidence cho JAB path: HWND, bridge DLL path, role/name da tim thay, action da goi.

### Phase 2: Build Windows EXE rieng

1. Chay `build_windows.bat` tren Windows co Python 3.11+.
2. Kiem tra PyInstaller gom du `JABWrapper.*` hidden imports.
3. Khong bundle `WindowsAccessBridge-64.dll` vao EXE; lay DLL tu runtime CAPAM nhu code hien tai.
4. Test EXE tren may co CAPAM Client bundled Java 17.
5. Ghi log artifact rieng theo run: screenshot fail, template scores, JAB init result.

### Phase 3: Test flow thuc te

1. VPN da connected san: skip GP, launch CAPAM, Address, Login.
2. VPN chua connected: GP Portal, GP Credentials, wait connected, CAPAM.
3. Sai password/OTP GP: phai fail nhanh tu log.
4. CAPAM Address JAB pass: khong dung vision.
5. CAPAM Login JAB pass: khong dung Tab/click toa do.
6. Device List 100%, 125%, 150% DPI: template score >= 0.70 va stable 2 frame.
7. Windows Security: username focus mac dinh, Tab sang password, Enter, verify RDP window.

### Phase 4: OCR spike neu can

1. Thu `pytesseract` hoac `easyocr` tren crop Device List, khong dua vao build truoc.
2. Do accuracy tren screenshot 100/125/150 va cac theme/font.
3. Dung OCR chi de xac nhan row text, khong thay click logic.
4. Neu OCR dependency qua nang hoac can cai engine ngoai, loai khoi production build.

## Checklist truoc khi goi la san sang build

- `python3 -m py_compile ...` pass tren Linux/dev.
- `build_windows.bat` pass tren Windows.
- EXE chay khong can console.
- JAB init thanh cong voi CAPAM runtime thuc te.
- Device List click dung RDP o 3 scale DPI.
- Windows Security verify co RDP window moi hoac title RDP doi trang thai.
- Co log fail du de debug: state, rect, hwnd, scores, screenshot path.

## Quyet dinh ky thuat de xuat

Chon `refactor/semantic-automation` lam base.

Khong chon OCR lam primary. Them OCR sau, nhu diagnostic/fallback rieng cho Device List/error text neu template matching con fail.

Muc tieu gan nhat: fix JAB edge cases, xac minh password CAPAM co OTP hay khong, build Windows EXE va test tren may that.
