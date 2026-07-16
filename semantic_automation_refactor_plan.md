# Semantic Automation Refactor Plan

## 1. Muc tieu

Refactor AutoSignCAPAM tu screen automation phu thuoc anh, toa do, DPI va timing sang semantic automation theo control that cua ung dung.

Muc tieu chinh:

- Dien dung truong dua tren role/name/help text, khong dua vao vi tri pixel.
- Goi action cua nut truc tiep khi accessibility provider ho tro.
- Xac minh postcondition sau moi thao tac, khong coi gui `Enter` la thanh cong.
- Giu vision chi cho man hinh CAPAM Device List khong expose accessibility tree.
- Giu FSM, UI, VPN log parser, process launcher va build flow hien tai.
- Trien khai Windows truoc. Linux dung backend AT-SPI rieng trong giai doan sau.

## 2. Ket qua khao sat thuc te

### 2.1 GlobalProtect

Accessibility Insights doc duoc cac control semantic:

| Control | Selector kha dung |
|---|---|
| Portal | `ControlType=Edit`, `Name=Portal` |
| Username | `ControlType=Edit`, `HelpText=Username` |
| Password + OTP | `ControlType=Edit`, `HelpText=Password` |
| Connect/Login | `ControlType=Button`, `Name=Connect` |

`AutomationId` khong ton tai. Username co `Name=Password` sai, vi vay khong duoc dung `Name` de phan biet hai credential fields.

Ket luan: GlobalProtect expose mot phan UIA, nhung tree bi rebuild sau khi set
value va khong on dinh khi automation truy cap lai control. Khong dung UIA lam
primary path trong flow hien tai. Giu OpenCV + keyboard/click logic cu.

### 2.2 CAPAM Address

CAPAM chay Java 17 bundled runtime:

```text
C:\Users\congl\CA PAM Client\runtime-17.0.10_7
```

Process da load:

```text
jvm.dll
javaaccessbridge.dll
jawt.dll
awt.dll
java.dll
```

Runtime co day du:

```text
jabswitch.exe
jaccessinspector.exe
jaccesswalker.exe
javaaccessbridge.dll
windowsaccessbridge-64.dll
```

Java Access Bridge da enable qua:

```text
%USERPROFILE%\.accessibility.properties
assistive_technologies=com.sun.java.accessibility.AccessBridge
```

JAccessWalker doc duoc:

```text
Address: [label]
Address: [combo box]
  [text]
Connect Mode: [label]
Connect Mode: [combo box]
  WEB [label]
  CONNECT [label]
Connect [push button]
Back [push button]
Cancel [push button]
```

Ket luan: man hinh Address co the dung Java Access Bridge; bo Canny, ROI va click toa do.

### 2.3 CAPAM Login

JAccessWalker doc duoc:

```text
Username: [label]
Username [text]
Password: [label]
Password [password text]
Authentication Type [combo box]
Passcode (PIN+Tokencode) [password text]
RADIUS Password [panel]
Login [push button]
Back [push button]
Cancel [push button]
```

Ket luan: co the tim Username va Password rieng theo accessible role/name, bo OpenCV va bo `Tab` de chuyen Password.

### 2.4 CAPAM Device List

JAccessWalker chi doc duoc khung ngoai:

```text
[frame] Symantec Privileged Access Manager Client - <CAPAM_IP>
  [page tab list]
    [page tab]
      [panel]
```

Khong thay device rows, Address, icon hay nut RDP. Keyboard navigation cung khong di den nut RDP cua row chua active mot cach on dinh.

Ket luan: man hinh nay la custom-rendered. Tiep tuc dung template matching hien tai cho device label va nut RDP cung dong.

### 2.5 Windows Security

Accessibility Insights, ke ca Raw View, chi doc duoc:

```text
ControlType=Window
Name=Windows Security
```

Hai input fields khong expose UI Automation. Test keyboard thuc te xac nhan:

- Khi dialog moi mo, caret da o Username.
- Nhap text di vao Username.
- Mot lan `Tab` chuyen dung sang Password.
- `Enter` ket noi vao may.

Ket luan: bo OpenCV field detection. Dung focus mac dinh + keyboard, kem xac minh dialog/result.

## 3. Kien truc muc tieu

```text
AutomationWorker / FSM
  |
  +-- ProcessWindowAdapter
  |     PID, HWND, owner, class, executable, foreground
  |
  +-- WindowsUIAAdapter
  |     GlobalProtect
  |
  +-- JavaAccessBridgeAdapter
  |     CAPAM Address
  |     CAPAM Login
  |
  +-- VisionAdapter
  |     CAPAM Device List only
  |
  +-- KeyboardAdapter
  |     Windows Security
  |
  +-- StateValidator
        precondition, postcondition, timeout, evidence
```

Thu tu actuator:

1. Semantic set/invoke neu action spike da qua.
2. Semantic focus + keyboard neu transaction da duoc kiem chung.
3. Vision trong ROI gioi han.
4. Logic cu co guard va postcondition.

## 4. Cong nghe

### 4.1 GlobalProtect

Dung OpenCV + keyboard/click logic hien tai.

Ly do:

- Logic cu da chay duoc tren GP thuc te.
- Tranh UIA tree rebuild lam mat control sau moi thao tac.
- UIA chi giu lam spike rieng, khong vao production path.

### 4.2 CAPAM Java

Dung package:

```text
java-access-bridge-wrapper==2.0.0
```

Khong bundle Java DLL vao EXE. Tu tim `WindowsAccessBridge-64.dll` trong runtime nam canh `CAPAMClient.exe`, sau do set:

```text
RC_JAVA_ACCESS_BRIDGE_DLL=<absolute path>
```

Ly do:

- Runtime CAPAM va process deu la 64-bit.
- JAB tree da doc duoc control that.
- Wrapper Apache-2.0, dependency nho, phu hop hon full `rpaframework`.
- Khong chon `pyjab` lam production path vi package cu va GPLv2.

### 4.3 Device List

Giu OpenCV template matcher:

- `template_200.png`
- `template_12.png`
- `template_rdp.png`

Gioi han:

- Match tren exact CAPAM device-list HWND.
- Device va RDP phai cung row.
- Hai frame on dinh.
- Kiem tra foreground va rect ngay truoc click.
- Click xong phai thay Windows Security trong timeout.

### 4.4 Windows Security

Dung native window discovery + keyboard:

```text
wait exact dialog
focus exact HWND
confirm foreground
type Username at default focus
Tab once
type Password
Enter
wait dialog close or RDP success window
```

Khong click vao contour dau tien. Khong dung UIA cho child fields vi provider khong expose.

## 5. Selector strategy

### 5.1 GlobalProtect Portal

```text
Window: exact title GlobalProtect + target process
Field: ControlType=Edit + Name=Portal
Button: ControlType=Button + Name=Connect
```

Postcondition:

- Portal field bien mat va credential controls xuat hien; hoac
- GP log chuyen state.

### 5.2 GlobalProtect Credentials

```text
Username: ControlType=Edit + HelpText=Username
Password: ControlType=Edit + HelpText=Password
Submit: ControlType=Button + Name=Connect
```

Quy tac:

- Khong dung `Name` de tim Username.
- Moi selector phai match chinh xac mot control.
- Match 0 hoac >1 control: fail ro rang, khong fallback click mu.

Postcondition:

- GP log `CONNECTED`; hoac
- GP log `AUTH_FAILED`; hoac
- timeout co phan loai.

### 5.3 CAPAM Address

```text
Window: CAPAM exact HWND/PID
Address combo: role=combo box + name=Address:
Address editor: child role=text + editable/enabled/showing
Connect Mode combo: role=combo box + name=Connect Mode:
Option: name=CONNECT
Submit: role=push button + name=Connect
```

Set Address bang `setTextContents`/`insert_text`. Combo selection dung AccessibleSelection neu CAPAM yeu cau chon mode.

Postcondition:

- Login label `Login to <CAPAM_IP>` xuat hien; hoac
- Username/Password controls xuat hien.

### 5.4 CAPAM Login

```text
Username: role=text + name=Username + editable/enabled/showing
Password: role=password text + name=Password + editable/enabled/showing
Submit: role=push button + name=Login
```

Authentication Type va Passcode khong duoc nham voi Password. Selector role `password text + name=Password` la bat buoc.

Postcondition:

- Device-list window xuat hien; hoac
- Accessible error label xuat hien; hoac
- timeout.

### 5.5 CAPAM Device List

```text
Window: exact HWND va title co CAPAM IP
Device: template_200/template_12
Action: template_rdp trong cung row
```

Postcondition:

- Windows Security dialog xuat hien.

### 5.6 Windows Security

```text
Window: exact title + owner/process/session checks
Username: default focused field
Password: one Tab from Username
```

Precondition:

- Dialog vua xuat hien trong state hien tai.
- Exact HWND visible va foreground.
- Khong co user input chen ngang.

Postcondition:

- Dialog dong; va
- RDP client/session window xuat hien hoac state ket noi duoc xac minh.

## 6. Cau truc file du kien

```text
automation/
  __init__.py
  errors.py
  windows_uia.py
  java_access_bridge.py

core/
  gp_handler.py
  capam_handler.py
  rdp_handler.py
  state_machine.py

vision/
  template_matcher.py
  field_detector.py
```

Khong dua UIA/JAB method truc tiep vao FSM. Handler goi adapter qua API nho:

```python
class WindowsUIAAdapter:
    def detect_gp_screen(self, hwnd): ...
    def fill_gp_portal(self, hwnd, portal): ...
    def fill_gp_credentials(self, hwnd, username, password): ...
    def invoke_gp_connect(self, hwnd): ...

class JavaAccessBridgeAdapter:
    def attach(self, hwnd): ...
    def detect_capam_screen(self): ...
    def fill_address(self, address, connect_mode): ...
    def fill_login(self, username, password): ...
    def invoke(self, role, name): ...
    def close(self): ...
```

## 7. Giai doan trien khai

### Phase 0: Baseline va diagnostics

- Giu nguyen pipeline hien tai.
- Them structured error category va backend name vao log.
- Ghi Windows build, DPI, session ID, CAPAM path/runtime version.
- Khong ghi username, password, OTP, clipboard content.
- Tao smoke-test command dump UIA/JAB tree da redact.

Ket qua:

- Co the chan doan backend fail vi selector, provider, focus hay timeout.

### Phase 1: GlobalProtect stability

- Giu OpenCV detect va keyboard/click logic cu.
- Khong truy cap lai UIA control sau khi set value.
- Them retry co gioi han, khong lap credential khi `AUTH_FAILED`.
- Giu log parser lam authoritative postcondition.

Acceptance:

- `detect_input_fields(profile="gp")` van la primary path.
- Chay duoc DPI 100%, 125%, 150%.
- Khong lap nhap khi GP window rebuild/bi an.

### Phase 2: CAPAM JAB discovery va lifecycle

- Tim exact `CAPAMClient.exe` path.
- Tim bundled `WindowsAccessBridge-64.dll`.
- Kiem tra Python va DLL cung 64-bit.
- Khoi tao JAB wrapper tren thread co Windows message pump.
- Serialize moi JAB call qua mot queue/thread owner.
- Attach bang exact HWND/PID, khong title don doc.
- Refresh tree sau moi screen transition.
- Release stale Java contexts va close wrapper khi workflow ket thuc.

Acceptance:

- Attach/restart CAPAM nhieu lan khong crash.
- Khong giu stale node qua thay doi man hinh.
- Khong leak JVM object tang lien tuc.

### Phase 3: CAPAM Address semantic

- Tim Address combo/editor.
- Set IP bang JAB native text API.
- Chon `CONNECT` neu nghiep vu yeu cau.
- Invoke `Connect`.
- Wait Login controls.
- Loai Address ratio, ROI va Canny khoi primary path.

Acceptance:

- Khong click toa do.
- Khong phu thuoc window ratio `<0.55`.
- IP khac nhau van set dung.

### Phase 4: CAPAM Login semantic

- Tim Username va Password theo role/name.
- Set rieng hai fields.
- Khong dung `Tab`.
- Invoke `Login`.
- Wait device list hoac error label.
- Neu `server_choice=none`, chi bao DONE sau khi xac minh login thanh cong.

Acceptance:

- Khong nham `Password`, `Passcode`, `RADIUS Password`.
- Khong bao thanh cong ngay sau action.

### Phase 5: Windows Security keyboard flow

- Bo screenshot va `detect_input_fields(profile="windows_security")`.
- Wait exact dialog.
- Focus exact HWND.
- Nhap Username tai default focus.
- `Tab` mot lan, nhap Password, `Enter`.
- Wait dialog close/RDP success.
- Neu focus hoac HWND thay doi, fail; khong retry nhap credential mu.

Acceptance:

- Khong click toa do field.
- Credential sai khong bi bao DONE.
- Modal bat ngo duoc phan loai.

### Phase 6: Device List hardening

- Giu matcher hien tai.
- Gioi han ROI va quan he same-row chat hon neu anh calibration cho phep.
- Validate exact HWND, frame stability, confidence va postcondition.
- Khong them OCR/filter workflow trong phase nay.

Acceptance:

- Khong click neu device/RDP confidence khong dat.
- Khong click RDP khac row.
- Windows Security phai xuat hien sau click.

### Phase 7: Test va packaging

- Unit test selectors voi fake UIA/JAB nodes.
- Unit test FSM transitions va postconditions.
- Regression test template tren calibration images.
- Integration test tren hai may.
- Test DPI 100%, 125%, 150%.
- Test monitor phu, resize, minimize/restore.
- Test focus bi browser/notification gianh.
- Test sai password, sai OTP, timeout, CAPAM restart.
- Build PyInstaller `onedir` truoc, sau do `onefile`.
- Test EXE tren may sach khong cai Python/JDK.

## 8. Fallback policy

Feature flags du kien:

```text
AUTOMATION_BACKEND=semantic
AUTOMATION_ALLOW_VISION_FALLBACK=true
AUTOMATION_DIAGNOSTICS=false
```

Fallback duoc phep:

- UIA unavailable tren GlobalProtect: vision cu, co warning ro.
- JAB unavailable truoc khi nhap credential: vision cu, co warning ro.
- Device List: vision la primary path.
- Windows Security: keyboard la primary path.

Fallback khong duoc phep:

- Semantic selector match nhieu controls.
- Foreground/HWND thay doi trong luc nhap credential.
- Da set mot phan credential roi mat state.
- Postcondition bao auth error.
- Secure desktop, lock screen hoac disconnected session.

Trong cac truong hop tren, workflow phai fail an toan.

## 9. Error model

Tao error categories:

```text
BACKEND_UNAVAILABLE
WINDOW_NOT_FOUND
WINDOW_CHANGED
SELECTOR_NOT_FOUND
SELECTOR_AMBIGUOUS
CONTROL_NOT_EDITABLE
ACTION_UNSUPPORTED
FOCUS_LOST
POSTCONDITION_TIMEOUT
AUTH_FAILED
SECURE_DESKTOP_UNSUPPORTED
SESSION_NOT_INTERACTIVE
VISION_LOW_CONFIDENCE
```

Moi error ghi:

- State.
- Backend.
- Target process/HWND.
- Selector da redact.
- Timeout.
- Screenshot da che credential neu can.

Khong ghi secret hoac accessible text cua password controls.

## 10. Bao mat

- Khong dump password, OTP, passcode vao log/UI tree snapshot.
- Khong luu screenshot sau khi credential da hien neu chua redact.
- Giam clipboard usage khi UIA/JAB set text truc tiep.
- Windows Security van dung keyboard; can xoa clipboard nhanh va xac minh foreground.
- Khong tu dong hoa UAC secure desktop/Winlogon.
- Khong them `uiAccess=true` de bypass security boundary.
- Khong bundle DLL Java tu runtime CAPAM vao san pham neu chua xac minh license.

## 11. Linux roadmap

Khong dung Windows Java Access Bridge tren Linux.

Backend du kien:

```text
GlobalProtect: AT-SPI2
CAPAM Java: Java ATK Wrapper -> AT-SPI2
Window/session: X11 hoac Wayland-specific APIs
Device List: vision fallback
```

FSM va selector model co the dung chung; implementation adapter tach rieng. Linux chi bat dau sau khi Windows semantic flow dat acceptance criteria.

## 12. Tieu chi hoan thanh

Functional:

- GlobalProtect Portal/Credentials dung UIA primary path.
- CAPAM Address/Login dung JAB primary path.
- Device List chi con mot diem vision primary.
- Windows Security khong dung field detector.
- Moi submit co postcondition.

Reliability:

- Toi thieu 50 lan lien tiep tren moi may test khong nhap sai field.
- Test thanh cong tai DPI 100%, 125%, 150%.
- Khong click neu selector ambiguous hoac vision confidence thap.
- Focus bi gianh phai fail an toan.

Packaging:

- Source run thanh cong trong `.venv`.
- PyInstaller `onedir` thanh cong tren may sach.
- PyInstaller `onefile` thanh cong neu JAB lifecycle va DLL discovery on dinh.
- CAPAM bundled runtime duoc discover tu installation path, khong phu thuoc `JAVA_HOME`.

## 13. Thu tu commit de xuat

```text
docs: add semantic automation refactor plan
feat(uia): add GlobalProtect semantic adapter
feat(jab): add CAPAM Java accessibility adapter
refactor(capam): use semantic address controls
refactor(capam): use semantic login controls
refactor(rdp): use keyboard credential flow
fix(rdp): validate credential dialog result
test: add semantic selector and workflow coverage
build: package semantic automation dependencies
```

Moi commit phai giu ung dung build/run duoc va khong xoa fallback truoc khi backend moi duoc test tren may that.

## 14. Cac diem can complain va chot truoc khi code lon

### 14.1 Accessibility tree chua chung minh action hoat dong

JAccessWalker va Accessibility Insights moi chung minh control duoc nhin thay. Chua chung minh:

- UIA `ValuePattern.SetValue` hoat dong voi GP fields.
- UIA `InvokePattern` hoat dong voi nut `Connect`.
- JAB `setTextContents` hoat dong voi Address, Username va Password.
- JAB AccessibleSelection commit duoc `Connect Mode=CONNECT`.
- JAB action `click` tren `Connect` va `Login` thuc su fire Swing event.

Bat buoc co action spike truoc Phase 1/3:

1. Set gia tri gia vao field, khong submit.
2. Doc lai non-secret field neu provider cho phep.
3. Invoke action an toan hoac dung test endpoint.
4. Xac minh screen transition.
5. Neu native action khong hoat dong, chot semantic focus + keyboard fallback truoc khi sua handler.

Khong xoa path cu chi vi inspector thay control.

### 14.2 Chua chot mapping credential CAPAM

CAPAM Login expose nhieu truong:

```text
Password
Authentication Type
Passcode (PIN+Tokencode)
RADIUS Password
```

Code hien tai nhap `password_prefix + otp` vao `Password`, nhung UI semantic cho thay co cac field MFA rieng. Can xac minh nghiep vu that theo tung Authentication Type:

| Authentication Type | Username | Password | Passcode/RADIUS |
|---|---|---|---|
| Local | Chua chot | Chua chot | Chua chot |
| RSA | Chua chot | Chua chot | Chua chot |
| LDAP+RSA | Chua chot | Chua chot | Chua chot |
| RADIUS | Chua chot | Chua chot | Chua chot |
| LDAP+RADIUS | Chua chot | Chua chot | Chua chot |
| LDAP | Chua chot | Chua chot | Chua chot |

Truoc Phase 4 phai ghi lai:

- Authentication Type dang duoc chon thuc te.
- OTP duoc noi vao Password hay nhap field rieng.
- Domain co can chon `vp.tct.vn` khong.
- Field nao visible/enabled theo mode.

Sai mapping co the gay auth fail hoac lock account, du selector dung.

### 14.3 JAB enable la state theo user va runtime

`%USERPROFILE%\.accessibility.properties` da enable tren may test, nhung may khac co the chua co. Plan can chot deployment policy:

- App chi probe va huong dan user enable; hoac
- Installer enable JAB mot lan voi chap thuan; hoac
- App tu enable roi restart CAPAM.

Khuyen nghi ban dau: probe read-only, fail voi `BACKEND_UNAVAILABLE` va huong dan ro. Khong tu sua global user accessibility config trong background.

Can test:

- User profile moi.
- CAPAM runtime version khac.
- CAPAM upgrade thay runtime folder.
- User khong co admin.
- Tool va CAPAM khac integrity level.

### 14.4 JAB/PyQt thread ownership la blocker ky thuat

`AutomationWorker` hien la `QThread`. JAB wrapper can Windows message pump va context lifetime tren thread owner. Khong duoc tao wrapper tren mot thread roi goi truc tiep tu `AutomationWorker`.

Can chot mot model:

```text
JAB service thread owns wrapper + message pump
AutomationWorker sends commands through Queue
JAB service returns immutable results/fresh handles
```

Bat buoc dinh nghia:

- Startup timeout.
- Command timeout.
- Cancel behavior.
- Wrapper shutdown.
- CAPAM process restart/re-attach.
- Release Java objects.
- App exit khi message pump dang block.

Khong trien khai JAB calls truc tiep trong UI thread.

### 14.5 Windows Security focus default chua du manh

Focus Username da test thanh cong tren mot Windows build va mot credential dialog. No co the khac khi:

- Windows nho credential cu.
- Username bi prefilled hoac an.
- Dialog co `More choices`.
- Credential Provider thay doi.
- Password sai va dialog mo lai.
- RDP certificate/NLA prompt xuat hien truoc.
- User click vao dialog trong luc automation chay.

Plan can them keyboard focus probe khong tiet lo secret:

- Sau dialog open, xac minh foreground exact HWND.
- Neu co the, dung `GetGUIThreadInfo` de lay focused child HWND/control class.
- Khong nhap neu dialog da ton tai truoc state hoac vua retry sau auth fail.
- Moi dialog HWND chi duoc submit mot lan.
- Sau auth fail, fail workflow; khong tu dong nhap lai password.

Neu khong xac minh duoc focused child, day van la diem heuristic con lai va phai duoc ghi ro trong UI/log.

### 14.6 Postcondition RDP chua duoc dinh nghia cu the

`Dialog dong` khong du de ket luan thanh cong; dialog co the dong do Cancel, crash hoac timeout. `RDP window xuat hien` cung can selector cu the.

Truoc Phase 5 can khao sat va chot mot trong cac signal:

- Process `mstsc.exe` moi voi PID/start time sau click.
- Cua so RDP moi theo process/class/title.
- CAPAM progress dialog chuyen sang connected state.
- Windows Security dialog dong va remote session client visible.
- Error dialog/text xuat hien.

Thanh cong phai can it nhat hai signal doc lap neu kha thi, vi du:

```text
Windows Security dialog closed
AND new mstsc window/process appeared
```

Them state ket qua rieng:

```text
RDP_CONNECTED
RDP_AUTH_FAILED
RDP_CERTIFICATE_PROMPT
RDP_TIMEOUT
RDP_UNKNOWN_RESULT
```

### 14.7 Device template van la diem yeu chinh

Sau refactor, Device List van phu thuoc template. `50 lan khong sai field` khong bao phu failure mode nay.

Can bo sung test matrix:

- CAPAM 100%, 125%, 150%.
- Font smoothing khac.
- Window maximize/restore.
- Row position khac va co scroll.
- Device khong nam trong viewport.
- Nhieu row co text/icon gan giong.
- Hover/disabled/loading state cua RDP button.
- CAPAM version/theme khac.

Click chi duoc phep khi:

- Device score dat threshold.
- RDP score dat threshold.
- Hai match on dinh tren hai frame.
- RDP nam trong cung row va dung vung cot action.
- Windows Security xuat hien sau click.

Neu device khong trong viewport, matcher hien tai khong scroll. Can fail voi loi ro, khong retry blind.

### 14.8 Process/window identity chua duoc gan chat voi launch

Adapter hien launch process nhung bo `Popen` handle/PID. Sau do tim window theo title. Semantic adapter nen:

- Tra PID/start time tu `launch_capam()` va `launch_gp_ui()` khi co the.
- Track process tree neu launcher spawn child process.
- Verify executable path cua HWND.
- Verify session ID va integrity level.
- Gan dialog owner/process voi workflow hien tai.
- Khong attach window trung title tu session/process khac.

Day la dieu kien de selector semantic "dung control" nam trong "dung app instance".

### 14.9 Fallback co the tao hai hanh vi khac nhau

`AUTOMATION_ALLOW_VISION_FALLBACK=true` lam may A chay semantic, may B am tham chay heuristic. Dieu nay che loi deployment.

Khuyen nghi rollout:

```text
development: fallback=true + diagnostics=true
pilot: fallback=false, thu loi semantic that
production transition: fallback=true co warning tren UI
production target: fallback=false cho GP/CAPAM fields
```

Backend da chon phai hien trong UI/log ket qua. Khong ghi chung chung "thanh cong" khi da dung fallback.

### 14.10 Plaintext credential storage nam ngoai refactor nhung can xu ly

UI hien luu credential trong:

```text
~/.capam_autosign_settings.json
```

Day la plaintext local storage. Semantic automation giam click sai nhung khong sua rui ro nay.

Can issue/phase rieng:

- Khong luu password mac dinh; hoac
- Dung Windows Credential Manager/DPAPI.
- Migration/xoa plaintext file cu co chap thuan.
- Khong dua secret qua command line/environment.
- Zero/replace in-memory values sau workflow trong gioi han Python cho phep.

Khong block semantic PoC, nhung phai block production release neu yeu cau bao mat noi bo khong cho plaintext.

### 14.11 Package/version va PyInstaller chua duoc verify trong repo

Pin `java-access-bridge-wrapper==2.0.0` la de xuat, chua duoc install/build trong project. Truoc khi dua vao `requirements.txt` can spike rieng:

- Xac minh package/API tren Python version hien tai.
- Xac minh import name that va wrapper API.
- Xac minh license file duoc giu khi phan phoi.
- Xac minh import-time logging khong ghi vao cwd khong co quyen.
- Xac minh hidden imports `pywin32`/JABWrapper.
- Xac minh `--onedir` truoc `--onefile`.
- Xac minh antivirus/EDR tren artifact.

Neu wrapper khong dat, dung fork pin commit hoac ctypes adapter toi thieu. Khong doi library giua phase ma khong cap nhat plan.

### 14.12 Linux khong chi la them adapter

Linux hien con khac:

- AT-SPI tree/provider co the khac Windows JAB.
- Java ATK Wrapper co the khong nam trong bundled runtime.
- Wayland han che global input/screenshot.
- GlobalProtect Linux UI/version co the khac.
- Windows Security/RDP credential flow khong tuong duong.

Vi vay "dung chung selector model" chi la muc tieu, khong phai cam ket. Linux can discovery PoC rieng truoc khi estimate.

## 15. Decision gates

Khong chuyen phase neu gate truoc chua dat:

| Gate | Dieu kien dat | Neu khong dat |
|---|---|---|
| G0 Baseline | Flow cu reproduce duoc tren hai may, co log baseline | Sua baseline truoc refactor |
| G1 GP UIA | Set/invoke va postcondition thanh cong 20 lan | Giu GP vision, danh gia keyboard/API |
| G2 JAB lifecycle | Attach/restart/close 50 lan, khong crash/leak ro | Doi wrapper/model thread |
| G3 CAPAM Address | Set IP + Connect semantic 20 lan | Semantic focus + keyboard fallback |
| G4 CAPAM Login | Mapping credential duoc xac nhan, login semantic 20 lan | Dung phase, khong thu credential mu |
| G5 Windows Security | Submit mot lan, phan loai success/failure dung | Giu human-in-the-loop |
| G6 Device vision | Test matrix DPI/theme/row dat threshold | Bat buoc filter/manual selection |
| G7 Packaging | `onedir` va `onefile` tren may sach | Ship `onedir` hoac sua packaging |

## 16. Definition of success can do duoc

Thay vi chi dem tong so lan chay, thu thap:

```text
semantic selector success rate
fallback rate
wrong-field count (must be 0)
wrong-device click count (must be 0)
auth duplicate-submit count (must be 0)
median/P95 duration per state
timeout count by category
JAB attach/re-attach failure rate
memory growth of controller and CAPAM JVM
```

Muc tieu pilot de xuat:

- `wrong-field count = 0`.
- `wrong-device click count = 0`.
- `auth duplicate-submit count = 0`.
- Semantic GP + CAPAM field flow `>=99%` tren cau hinh da support.
- Fallback rate duoc hien thi, khong an.
- Moi failure co state/backend/error category, khong chi co `ERROR`.
