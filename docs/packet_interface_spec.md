# 단말-서버 패킷 연동 규격서

| 항목 | 내용 |
|------|------|
| 문서 번호 | NWLoad-PKT-001 |
| 버전 | 1.0 |
| 작성일 | 2026-05-11 |
| 적용 시스템 | Cell Traffic Optimizer |

---

## 1. 개요

### 1.1 목적

본 규격서는 LTE/5G NR 무선 라우터(단말)가 셀 트래픽 최적화 서버(이하 "서버")로 전송하는 UDP 패킷의 구조, 인코딩 방식, 전송 프로토콜을 정의한다.

서버는 수신된 패킷을 기반으로 셀 부하 상태를 판정하고, 필요 시 단말에 연결된 ONVIF 카메라에 화질 조정 명령을 전송한다.

### 1.2 적용 범위

- 단말 → 서버 방향 단방향 전송
- 프로토콜: UDP (비연결, 비신뢰)
- 패킷 크기: **고정 67바이트**
- 바이트 순서: **Big-Endian (Network Byte Order)**

### 1.3 용어 정의

| 용어 | 설명 |
|------|------|
| CTN | Cellular Terminal Number. 단말 식별용 전화번호 (한국: 01X-XXXX-XXXX) |
| ECGI | E-UTRAN Cell Global Identity. LTE 셀 식별자 (28bit ECI = eNB_ID 20bit + Cell_ID 8bit) |
| NCI | NR Cell Identity. 5G NR 셀 식별자 (36bit = gNB_ID 22~32bit + Cell_ID) |
| EARFCN | E-UTRA Absolute Radio Frequency Channel Number. LTE 주파수 채널 번호 |
| NR-ARFCN | NR Absolute Radio Frequency Channel Number. 5G NR 주파수 채널 번호 |
| PLMN ID | Public Land Mobile Network ID. MCC(3자리) + MNC(2~3자리) BCD 인코딩 |
| UL_RB | Uplink Resource Block. 단말이 사용 중인 업링크 자원 블록 수 (0~100) |
| RAT | Radio Access Technology. LTE / NR / RedCap 등 |
| Primary Block | 단말의 주 접속 셀 정보 (필수) |
| Secondary Block | NSA(Non-Standalone) 단말의 보조 셀 정보. LTE 앵커 단말의 NR 추가 블록 등 (선택) |

---

## 2. 전송 프로토콜

### 2.1 전송 방식

| 항목 | 값 |
|------|-----|
| 프로토콜 | UDP |
| 서버 포트 | **9000** |
| 패킷 방향 | 단말 → 서버 (단방향) |
| 응답 | 없음 (Fire-and-forget) |
| 전송 주기 | 단말 구현에 따름 (권장: 1회/분) |

### 2.2 서버 엔드포인트

```
UDP  <server_ip>:9000     ← 단말 트래픽 데이터 수신
HTTP <server_ip>:8000     ← 관리 API (카메라 등록, 설정 조회 등)
```

### 2.3 재전송 정책

UDP는 비신뢰 전송이므로 패킷 유실 시 재전송하지 않는다.  
서버는 수신된 패킷만 처리하며, 누락된 패킷에 대한 별도 응답이 없다.

---

## 3. 패킷 구조

### 3.1 전체 레이아웃

전체 크기는 **고정 67바이트**이며, 가변 길이 필드는 없다.

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER  (19 bytes)                                                 │
│  ┌──────┬──────────┬──────────────┬──────────────────────────────┐  │
│  │  Ver │ Msg_Type │ Total_Length │         Router_CTN           │  │
│  │  1B  │    1B    │      2B      │            15B               │  │
│  └──────┴──────────┴──────────────┴──────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  PRIMARY RAT BLOCK  (23 bytes)                                      │
│  ┌──────┬─────────┬──────────────┬────────┬───────────┬──────────┐  │
│  │ RAT  │ PLMN_ID │  ECGI/NRCGI  │ ARFCN  │ Timestamp │ UL_RB   │  │
│  │  1B  │   3B    │      5B      │   4B   │    8B     │   2B    │  │
│  └──────┴─────────┴──────────────┴────────┴───────────┴──────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│  SECONDARY RAT BLOCK  (23 bytes)                                    │
│  ┌──────┬─────────┬──────────────┬────────┬───────────┬──────────┐  │
│  │ RAT  │ PLMN_ID │  ECGI/NRCGI  │ ARFCN  │ Timestamp │ UL_RB   │  │
│  │  1B  │   3B    │      5B      │   4B   │    8B     │   2B    │  │
│  └──────┴─────────┴──────────────┴────────┴───────────┴──────────┘  │
│  (Secondary 미사용 시 전체 0x00으로 채움)                             │
├─────────────────────────────────────────────────────────────────────┤
│  RESERVED  (2 bytes)  — 0x0000 고정                                 │
└─────────────────────────────────────────────────────────────────────┘
Total: 19 + 23 + 23 + 2 = 67 bytes
```

### 3.2 오프셋 맵

| 오프셋 | 크기 | 필드명 | 설명 |
|--------|------|--------|------|
| 0 | 1B | Version | 프로토콜 버전 |
| 1 | 1B | Msg_Type | 메시지 타입 |
| 2 | 2B | Total_Length | 전체 패킷 길이 (항상 67) |
| 4 | 15B | Router_CTN | 단말 전화번호 (ASCII, null padding) |
| 19 | 1B | Primary.RAT_Type | Primary 셀 RAT 타입 |
| 20 | 3B | Primary.PLMN_ID | Primary 셀 PLMN ID |
| 23 | 5B | Primary.ECGI | Primary 셀 식별자 |
| 28 | 4B | Primary.ARFCN | Primary 셀 주파수 채널 번호 |
| 32 | 8B | Primary.Timestamp | 측정 시각 (Unix ms) |
| 40 | 2B | Primary.UL_RB_Usage | Primary 업링크 RB 사용량 |
| 42 | 1B | Secondary.RAT_Type | Secondary 셀 RAT 타입 (미사용 시 0x00) |
| 43 | 3B | Secondary.PLMN_ID | Secondary 셀 PLMN ID |
| 46 | 5B | Secondary.ECGI | Secondary 셀 식별자 |
| 51 | 4B | Secondary.ARFCN | Secondary 셀 주파수 채널 번호 |
| 55 | 8B | Secondary.Timestamp | 측정 시각 (Unix ms) |
| 63 | 2B | Secondary.UL_RB_Usage | Secondary 업링크 RB 사용량 |
| 65 | 2B | Reserved | 예약 (0x0000) |

---

## 4. 필드 상세 정의

### 4.1 HEADER

#### 4.1.1 Version (1 byte)

| 값 | 의미 |
|----|------|
| `0x01` | 버전 1 (현재 유일한 지원 버전) |

그 외 값 수신 시 서버는 패킷을 폐기한다.

#### 4.1.2 Msg_Type (1 byte)

| 값 | 의미 |
|----|------|
| `0x01` | 셀 트래픽 보고 (현재 유일한 지원 타입) |

그 외 값 수신 시 서버는 패킷을 폐기한다.

#### 4.1.3 Total_Length (2 bytes, Big-Endian)

전체 패킷 길이. 항상 `0x0043` (67) 이어야 한다.  
실제 수신된 바이트 수와 일치하지 않으면 서버는 패킷을 폐기한다.

#### 4.1.4 Router_CTN (15 bytes)

단말 식별자. 한국 이동전화 번호 형식의 ASCII 문자열.

- 인코딩: ASCII
- 길이: 최대 15자 (숫자만 구성, 하이픈 제외)
- 패딩: 15바이트 미만 시 우측을 `0x00`으로 채움

**예시**

| 전화번호 | 바이트 표현 (hex) |
|----------|-----------------|
| [MASKED_PHONE_NUMBER] | `31 30 31 30 39 30 30 30 30 30 30 31 00 00 00` |

---

### 4.2 RAT BLOCK (Primary / Secondary 공통 구조, 23 bytes)

#### 4.2.1 RAT_Type (1 byte)

| 값 | 상수 | 의미 |
|----|------|------|
| `0x00` | `NONE` | 미사용 블록 (Secondary에서 사용) |
| `0x01` | `LTE_PRIMARY` | LTE 주 셀 |
| `0x02` | `NR` | 5G NR 셀 (SA 또는 NSA 보조 셀) |
| `0x03` | `REDCAP` | 5G RedCap 경량 단말 셀 |

**Primary 블록 유효 값:** `0x01`, `0x02`, `0x03`  
**Secondary 블록 미사용 시:** `0x00` (블록 전체 0x00)

#### 4.2.2 PLMN_ID (3 bytes)

3GPP TS 24.008 Section 10.5.1.13 BCD 인코딩.

```
Byte 0: MCC digit2 | MCC digit1   (상위 니블 = digit2, 하위 니블 = digit1)
Byte 1: MNC digit3 | MCC digit3   (MNC가 2자리이면 digit3 = 0xF)
Byte 2: MNC digit2 | MNC digit1
```

**예시 — Uplus (MCC=450, MNC=06)**

```
MCC: 4, 5, 0  →  digit1=4, digit2=5, digit3=0
MNC: 0, 5     →  digit1=0, digit2=5, digit3=F (absent)

Byte 0: 0x54  (digit2=5, digit1=4)
Byte 1: 0xF0  (digit3=F, MCC digit3=0)
Byte 2: 0x60  (digit2=6, digit1=0)
```

#### 4.2.3 ECGI / NRCGI (5 bytes, Big-Endian)

셀 식별자. RAT 타입에 따라 계산 방식이 다르다.

**LTE — ECGI (3GPP TS 36.413)**

```
ECI(28bit) = eNB_ID(20bit) << 8 | Cell_ID(8bit)
5바이트 = 상위 12비트 예약(0) + ECI(28bit)
         → int.to_bytes(5, 'big')
```

**5G NR — NCI (3GPP TS 38.413)**

```
NCI(36bit) = gNB_ID(22bit) << 14 | Cell_ID(14bit)
5바이트 = 상위 4비트 예약(0) + NCI(36bit)
         → int.to_bytes(5, 'big')
```

#### 4.2.4 ARFCN (4 bytes, Big-Endian, unsigned)

주파수 채널 번호. RAT 타입에 따라 값 범위가 다르다.

**LTE — EARFCN (3GPP TS 36.101)**

업링크 기준 주요 Band:

| Band | UL EARFCN 범위 |
|------|---------------|
| 1 | 18000 ~ 18599 |
| 3 | 19200 ~ 19949 |
| 5 | 20400 ~ 20649 |
| 7 | 20750 ~ 21449 |
| 8 | 21450 ~ 21799 |

**5G NR — NR-ARFCN (3GPP TS 38.101)**

주요 Band:

| Band | NR-ARFCN 범위 | 주파수 대역 |
|------|--------------|------------|
| 1 | 422000 ~ 434000 | 2.1 GHz |
| 3 | 361000 ~ 376000 | 1.8 GHz |
| 5 | 173800 ~ 178800 | 850 MHz |
| 7 | 524000 ~ 538000 | 2.6 GHz |
| 8 | 185000 ~ 192000 | 900 MHz |
| 28 | 151600 ~ 160600 | 700 MHz |
| 78 | 620000 ~ 653333 | 3.5 GHz |

> **주의:** ARFCN 값은 서버에서 Band 번호 매핑에 사용된다.  
> 알 수 없는 ARFCN 값이 전달되면 해당 이벤트는 처리되지 않는다.

#### 4.2.5 Timestamp (8 bytes, Big-Endian, unsigned)

패킷 측정 시각. Unix epoch 기준 밀리초(ms).

```
예시: 2026-05-11 09:00:00 UTC
     = 1746954000000 (ms)
     = 0x0000019738A0E400
```

#### 4.2.6 UL_RB_Usage (2 bytes, Big-Endian, unsigned)

해당 셀에서 단말이 사용 중인 업링크 자원 블록(Resource Block) 수.

| 값 | 의미 |
|----|------|
| 0 | 업링크 트래픽 없음 (idle) |
| 1 ~ 100 | 사용 중인 RB 수 |

> 유효 범위: 0 ~ 100. 100 초과 값은 서버에서 100으로 클램핑되지 않고 그대로 사용되므로 단말에서 반드시 범위를 준수해야 한다.

---

### 4.3 RESERVED (2 bytes)

`0x0000` 고정. 향후 확장용으로 예약.

---

## 5. 단말 타입별 패킷 구성

### 5.1 LTE 전용 단말 (LTE-Only)

- Primary: RAT_Type = `0x01` (LTE), EARFCN, ECGI 포함
- Secondary: 전체 `0x00` (RAT_Type = `0x00`)

```
[Header 19B]
[Primary: LTE 셀 정보 23B]
[Secondary: 0x00 × 23 = 23B]
[Reserved: 0x00 0x00]
```

### 5.2 5G NR 단독 단말 (NR-SA)

- Primary: RAT_Type = `0x02` (NR), NR-ARFCN, NRCGI 포함
- Secondary: 전체 `0x00`

```
[Header 19B]
[Primary: NR 셀 정보 23B]
[Secondary: 0x00 × 23 = 23B]
[Reserved: 0x00 0x00]
```

### 5.3 5G NR 비단독 단말 (NSA — Non-Standalone)

LTE 앵커 셀 + NR 보조 셀 동시 연결.

- Primary: RAT_Type = `0x01` (LTE 앵커)
- Secondary: RAT_Type = `0x02` (NR 보조)

```
[Header 19B]
[Primary: LTE 앵커 셀 정보 23B]
[Secondary: NR 보조 셀 정보 23B]
[Reserved: 0x00 0x00]
```

### 5.4 RedCap 단말

- Primary: RAT_Type = `0x03` (REDCAP)
- Secondary: 전체 `0x00`

---

## 6. 인코딩 규칙 요약

| 항목 | 규칙 |
|------|------|
| 바이트 순서 | **Big-Endian** (모든 멀티바이트 정수 필드) |
| 문자열 인코딩 | ASCII |
| 미사용 필드 | `0x00` 으로 채움 |
| Secondary 미사용 | Secondary 블록 전체 23바이트를 `0x00`으로 채움 |

**C 언어 구현 시 바이트 순서 변환 함수**

```c
#include <arpa/inet.h>   // htons, htonl
#include <endian.h>      // htobe64

// 2바이트 필드
uint16_t total_len   = htons(67);
uint16_t ul_rb_usage = htons(rb_value);

// 4바이트 필드
uint32_t arfcn = htonl(arfcn_value);

// 8바이트 필드
uint64_t timestamp = htobe64(unix_ms);

// 5바이트 ECGI — 수동 변환
uint64_t eci = ((uint64_t)enb_id << 8) | cell_id;
uint8_t ecgi_bytes[5];
for (int i = 4; i >= 0; i--) {
    ecgi_bytes[i] = eci & 0xFF;
    eci >>= 8;
}
```

---

## 7. 패킷 예시

### 7.1 LTE 단독 단말 패킷 (hex dump)

조건:
- CTN: [MASKED_PHONE_NUMBER] → `3031303930303030303030303031` + `00`
- PLMN: Uplus (MCC=450, MNC=06) → `54 F0 60`
- ECGI: eNB_ID=0x12A00, Cell_ID=0 → ECI = 0x12A0000 → `00 12 A0 00 00`
- EARFCN: 19200 (Band 3 UL) → `00 00 4B 00`
- Timestamp: 1746954000000 ms → `00 00 01 97 38 A0 E4 00`
- UL_RB_Usage: 15 → `00 0F`

```
Offset  Hex Bytes                                    설명
------  ----------------------------------------     --------
00      01                                           Version = 1
01      01                                           Msg_Type = 1
02      00 43                                        Total_Length = 67
04      30 31 30 39 30 30 30 30 30 30 30 30 31 00 00  Router_CTN = "[MASKED_PHONE_NUMBER]"
                                                     --- Primary RAT Block ---
19      01                                           RAT_Type = LTE
20      54 F0 60                                     PLMN_ID = Uplus
23      00 12 A0 00 00                               ECGI
28      00 00 4B 00                                  EARFCN = 19200 (Band3 UL)
32      00 00 01 97 38 A0 E4 00                      Timestamp (ms)
40      00 0F                                        UL_RB_Usage = 15
                                                     --- Secondary RAT Block (미사용) ---
42      00 00 00 00 00 00 00 00 00 00 00 00 00 00
56      00 00 00 00 00 00 00 00 00
                                                     --- Reserved ---
65      00 00
```

### 7.2 NSA 단말 패킷 구조 (개념도)

```
[01][01][00 43][CTN 15B]          ← Header
[01][PLMN][LTE_ECGI][EARFCN][TS][RB]  ← Primary (LTE 앵커)
[02][PLMN][NR_NCI][NR-ARFCN][TS][RB]  ← Secondary (NR 보조)
[00 00]                               ← Reserved
```

---

## 8. 서버 처리 동작

수신 패킷은 아래 순서로 처리된다.

```
UDP 수신 (port 9000)
    │
    ▼
패킷 유효성 검사
    ├─ 길이 ≠ 67B        → 폐기
    ├─ Version ≠ 0x01    → 폐기
    ├─ Msg_Type ≠ 0x01   → 폐기
    ├─ Total_Length ≠ 67 → 폐기
    └─ Primary RAT_Type 불명 → 폐기
    │
    ▼
ARFCN → Band 번호 매핑 (3GPP TS 36.101 / 38.101)
    │
    ▼
슬라이딩 윈도우(60초) UL_RB_Usage 누적
    │
    ▼
윈도우 만료 시 셀 상태 판정 (per Band)
    ├─ ul_rb_sum < warning         → NORMAL
    ├─ warning ≤ ul_rb_sum < congestion  → WARNING
    ├─ congestion ≤ ul_rb_sum < overload_enter → CONGESTION
    └─ ul_rb_sum ≥ overload_enter  → OVERLOAD
              │
              ▼ OVERLOAD 진입 시
    단말에 매핑된 ONVIF 카메라에 화질 저하 명령 (SetVideoEncoderConfiguration)
    bitrate = default × degraded_ratio (기본 25%)
```

### 8.1 기본 임계값 (서버 설정 파일 기준)

| Band | Warning | Congestion | Overload Enter | Overload Exit |
|------|---------|------------|----------------|---------------|
| 1 | 8,000 | 16,000 | 25,000 | 20,000 |
| 3 | 10,000 | 20,000 | 30,000 | 25,000 |
| 5 | 5,000 | 10,000 | 15,000 | 12,000 |
| 7 | 12,000 | 24,000 | 36,000 | 30,000 |
| 8 | 6,000 | 12,000 | 18,000 | 15,000 |
| 78 | 15,000 | 30,000 | 50,000 | 40,000 |

> 임계값 단위: 슬라이딩 윈도우(60초) 내 누적 UL_RB_Usage 합계

---

## 9. 오류 처리

| 오류 조건 | 서버 동작 |
|----------|----------|
| 패킷 길이 ≠ 67 | 폐기, WARNING 로그 |
| Version 미지원 | 폐기, WARNING 로그 |
| Msg_Type 미지원 | 폐기, WARNING 로그 |
| Total_Length 불일치 | 폐기, WARNING 로그 |
| Primary RAT_Type 미지원 | 폐기, WARNING 로그 |
| ARFCN 미매핑 | 해당 RAT Block 이벤트 무시 |
| Secondary RAT_Type = 0x00 | 정상 — Secondary 블록 무시 |

---

## 10. 구현 체크리스트

단말 펌웨어 구현 시 아래 항목을 확인한다.

- [ ] 패킷 총 길이가 정확히 67바이트인가?
- [ ] 모든 멀티바이트 정수 필드가 Big-Endian으로 인코딩되었는가?
- [ ] Version = `0x01`, Msg_Type = `0x01`로 설정되었는가?
- [ ] Total_Length 필드 값이 `67` (`0x0043`)인가?
- [ ] Router_CTN이 ASCII 인코딩 + null padding으로 15바이트를 채우는가?
- [ ] PLMN_ID가 3GPP TS 24.008 BCD 형식인가?
- [ ] ARFCN 값이 해당 RAT와 Band에 맞는 범위에 있는가?
- [ ] Timestamp가 Unix epoch milliseconds (8바이트)인가?
- [ ] UL_RB_Usage 값이 0 ~ 100 범위인가?
- [ ] Secondary 미사용 시 해당 블록 전체를 0x00으로 채우는가?
- [ ] Reserved 2바이트가 0x00으로 채워져 있는가?
- [ ] 대상 서버 IP/포트(UDP 9000)가 올바르게 설정되었는가?

---

## 11. 개정 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2026-05-11 | 최초 작성 |
