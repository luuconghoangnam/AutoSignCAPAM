# Báo cáo Kiểm thử Khả năng Phục hồi & Độ tin cậy (GlobalProtect)
Tài liệu này ghi nhận kết quả chạy giả lập tự động trên nhiều môi trường hiển thị khác nhau để kiểm định cơ chế Nhận diện Nhãn chữ mới.

## 📊 Bảng tổng hợp kết quả chạy thử nghiệm

| ID | Màn hình | DPI Scale | Điều kiện giả lập | Trạng thái | Lỗi tọa độ (px) | Độ khớp (Min Score) |
|----|----------|-----------|-------------------|------------|-----------------|---------------------|
| 1 | Portal | 80% | Empty Fields | PASSED | 0.4px | 1.00 |
| 2 | Credentials | 80% | Empty Fields | PASSED | 1.0px | 1.00 |
| 3 | Portal | 80% | Pre-filled Text | PASSED | 0.4px | 1.00 |
| 4 | Credentials | 80% | Pre-filled Text | PASSED | 1.0px | 1.00 |
| 5 | Portal | 80% | Win11 Rounded+Noise | PASSED | 0.4px | 1.00 |
| 6 | Credentials | 80% | Win11 Rounded+Noise | PASSED | 1.0px | 1.00 |
| 7 | Portal | 80% | Pre-filled + Win11 Noise | PASSED | 0.4px | 1.00 |
| 8 | Credentials | 80% | Pre-filled + Win11 Noise | PASSED | 1.0px | 1.00 |
| 9 | Portal | 100% | Empty Fields | PASSED | 0.0px | 1.00 |
| 10 | Credentials | 100% | Empty Fields | PASSED | 0.0px | 1.00 |
| 11 | Portal | 100% | Pre-filled Text | PASSED | 0.0px | 1.00 |
| 12 | Credentials | 100% | Pre-filled Text | PASSED | 0.0px | 1.00 |
| 13 | Portal | 100% | Win11 Rounded+Noise | PASSED | 0.0px | 1.00 |
| 14 | Credentials | 100% | Win11 Rounded+Noise | PASSED | 0.0px | 1.00 |
| 15 | Portal | 100% | Pre-filled + Win11 Noise | PASSED | 0.0px | 1.00 |
| 16 | Credentials | 100% | Pre-filled + Win11 Noise | PASSED | 0.0px | 1.00 |
| 17 | Portal | 125% | Empty Fields | PASSED | 1.6px | 1.00 |
| 18 | Credentials | 125% | Empty Fields | PASSED | 1.3px | 1.00 |
| 19 | Portal | 125% | Pre-filled Text | PASSED | 1.6px | 1.00 |
| 20 | Credentials | 125% | Pre-filled Text | PASSED | 1.3px | 1.00 |
| 21 | Portal | 125% | Win11 Rounded+Noise | PASSED | 1.6px | 1.00 |
| 22 | Credentials | 125% | Win11 Rounded+Noise | PASSED | 1.3px | 1.00 |
| 23 | Portal | 125% | Pre-filled + Win11 Noise | PASSED | 1.6px | 1.00 |
| 24 | Credentials | 125% | Pre-filled + Win11 Noise | PASSED | 1.3px | 1.00 |
| 25 | Portal | 150% | Empty Fields | PASSED | 0.7px | 1.00 |
| 26 | Credentials | 150% | Empty Fields | PASSED | 1.1px | 1.00 |
| 27 | Portal | 150% | Pre-filled Text | PASSED | 0.7px | 1.00 |
| 28 | Credentials | 150% | Pre-filled Text | PASSED | 1.1px | 1.00 |
| 29 | Portal | 150% | Win11 Rounded+Noise | PASSED | 0.7px | 1.00 |
| 30 | Credentials | 150% | Win11 Rounded+Noise | PASSED | 1.1px | 1.00 |
| 31 | Portal | 150% | Pre-filled + Win11 Noise | PASSED | 0.7px | 1.00 |
| 32 | Credentials | 150% | Pre-filled + Win11 Noise | PASSED | 1.1px | 1.00 |
| 33 | Portal | 175% | Empty Fields | PASSED | 1.0px | 1.00 |
| 34 | Credentials | 175% | Empty Fields | PASSED | 1.8px | 1.00 |
| 35 | Portal | 175% | Pre-filled Text | PASSED | 1.0px | 1.00 |
| 36 | Credentials | 175% | Pre-filled Text | PASSED | 1.8px | 1.00 |
| 37 | Portal | 175% | Win11 Rounded+Noise | PASSED | 1.0px | 1.00 |
| 38 | Credentials | 175% | Win11 Rounded+Noise | PASSED | 1.8px | 1.00 |
| 39 | Portal | 175% | Pre-filled + Win11 Noise | PASSED | 1.0px | 1.00 |
| 40 | Credentials | 175% | Pre-filled + Win11 Noise | PASSED | 1.8px | 1.00 |
| 41 | Portal | 200% | Empty Fields | PASSED | 0.0px | 1.00 |
| 42 | Credentials | 200% | Empty Fields | PASSED | 0.0px | 1.00 |
| 43 | Portal | 200% | Pre-filled Text | PASSED | 0.0px | 1.00 |
| 44 | Credentials | 200% | Pre-filled Text | PASSED | 0.0px | 1.00 |
| 45 | Portal | 200% | Win11 Rounded+Noise | PASSED | 0.0px | 1.00 |
| 46 | Credentials | 200% | Win11 Rounded+Noise | PASSED | 0.0px | 1.00 |
| 47 | Portal | 200% | Pre-filled + Win11 Noise | PASSED | 0.0px | 1.00 |
| 48 | Credentials | 200% | Pre-filled + Win11 Noise | PASSED | 0.0px | 1.00 |

## 📈 Kết luận thống kê
- **Tổng số kịch bản kiểm thử giả lập:** 48 lượt.
- **Số lượt thành công đạt chuẩn (Sai số click < 3px):** 48 lượt.
- **Tỷ lệ chính xác tin cậy:** **100.00%**