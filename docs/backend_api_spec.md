# 백엔드 연동 규격서 (Backend API Integration Specification)

| 항목 | 내용 |
|------|------|
| 문서 번호 | NWLoad-API-001 |
| 버전 | 1.0 |
| 작성일 | 2026-05-12 |
| 적용 시스템 | Cell Traffic Optimizer |
| 관련 문서 | NWLoad-PKT-001 (단말-서버 패킷 연동 규격서) |

---

## 1. 개요

### 1.1 목적

본 규격서는 Cell Traffic Optimizer 백엔드 서버가 제공하는 HTTP REST API 및 WebSocket 인터페이스를 정의한다. 프론트엔드 대시보드, 외부 관리 도구, 통합 운영 시스템(NMS/OSS)이 본 규격에 따라 서버와 연동한다.

### 1.2 범위

- HTTP REST API: 셀/단말 상태 조회, 설정 변경, 카메라/매핑 관리, 이력 조회
- WebSocket: 실시간 상태 변경 및 알림 이벤트 푸시
- HTTP 패킷 인입 API: UDP 외 보조 인입 채널

UDP 단말 패킷 인입 규격은 [패킷 연동 규격서(NWLoad-PKT-001)](packet_interface_spec.md)를 참조한다.

### 1.3 용어

| 용어 | 설명 |
|------|------|
| CTN | Cellular Terminal Number — 단말 식별 전화번호 |
| ECGI | E-UTRAN Cell Global Identity — 셀 식별자 |
| GroupingKey | (ECGI, Band) 튜플로 식별되는 셀 단위 |
| Profile | 카메라 화질 프로필 (`NORMAL` / `DEGRADED`) |
| Cell State | 셀 부하 상태 (`NORMAL` / `WARNING` / `CONGESTION` / `OVERLOAD`) |
| Device State | 단말 운영 상태 (`NORMAL` / `DEGRADED` / `UNMANAGED`) |

---

## 2. 공통 사항

### 2.1 엔드포인트

| 채널 | 프로토콜 | 기본 포트 | 경로 prefix |
|------|----------|-----------|-------------|
| 관리 API | HTTP/1.1 | 8000 | `/api/...` |
| 실시간 이벤트 | WebSocket | 8000 | `/ws/events` |
| HTTP 패킷 인입 | HTTP/1.1 | 8000 | `/api/ingest/packet` |
| UDP 패킷 인입 | UDP | 9000 | — |

### 2.2 인코딩

| 항목 | 규칙 |
|------|------|
| 문자 인코딩 | UTF-8 |
| 요청/응답 본문 | `application/json` |
| 시간 표현 | ISO 8601 (UTC, `2026-05-12T10:30:00+00:00`) |
| 식별자 | UUID v4 또는 문자열 |
| 빈 응답 | HTTP 204 No Content |

### 2.3 CORS

현재 모든 Origin(`*`)에 대해 허용된다. 운영 환경에서는 화이트리스트로 제한할 것을 권장한다.

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: *
Access-Control-Allow-Headers: *
```

### 2.4 인증

본 버전(v1.0)에서는 인증/인가 메커니즘이 적용되지 않는다. 운영망 분리(VLAN/사설망)에 의해 접근을 통제하며, v2.0에서 API Key/JWT 기반 인증을 추가할 예정이다.

### 2.5 공통 오류 응답

FastAPI 기본 형식을 따른다.

| HTTP 상태 | 의미 |
|-----------|------|
| 200 OK | 정상 조회/수정 성공 |
| 201 Created | 자원 생성 성공 |
| 204 No Content | 삭제 성공 (응답 본문 없음) |
| 400 Bad Request | 잘못된 패킷/요청 |
| 404 Not Found | 자원 없음 |
| 409 Conflict | 자원 중복 |
| 422 Unprocessable Entity | 유효성 검증 실패 |
| 500 Internal Server Error | 서버 내부 오류 |

**오류 응답 본문 (예시)**

```json
{
  "detail": "Camera not found"
}
```

422 Unprocessable Entity의 경우 Pydantic 검증 오류 배열을 포함한다.

```json
{
  "detail": [
    {
      "loc": ["body", "thresholds", 0, "warning"],
      "msg": "must be positive",
      "type": "value_error"
    }
  ]
}
```

---

## 3. 데이터 모델

### 3.1 GroupingKey

```json
{
  "ecgi": 76677120,
  "band": 3
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `ecgi` | int | 셀 식별자 (LTE ECI 또는 NR NCI) |
| `band` | int | ARFCN으로부터 매핑된 Band 번호 |

### 3.2 CellStatus

```json
{
  "groupingKey": { "ecgi": 76677120, "band": 3 },
  "state": "OVERLOAD",
  "ulRbSum": 35421,
  "ctnList": ["[MASKED_PHONE_NUMBER]", "01099887766"],
  "stateEnteredAt": "2026-05-12T10:25:00+00:00",
  "nextEvalAt": "2026-05-12T10:26:00+00:00"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `groupingKey` | GroupingKey | 셀 식별 |
| `state` | string | `NORMAL` / `WARNING` / `CONGESTION` / `OVERLOAD` |
| `ulRbSum` | int | 현재 슬라이딩 윈도우 UL_RB 누적합 |
| `ctnList` | string[] | 셀에 결합된 단말 CTN 목록 |
| `stateEnteredAt` | ISO 8601 | 현재 상태 진입 시각 |
| `nextEvalAt` | ISO 8601 \| null | 다음 윈도우 평가 예정 시각 |

### 3.3 CellDeviceDetail

```json
{
  "routerCtn": "[MASKED_PHONE_NUMBER]",
  "band": 3,
  "ecgi": 76677120,
  "ulRbUsage": 80,
  "timestamp": "2026-05-12T10:25:55+00:00",
  "deviceState": "DEGRADED",
  "qualityProfile": "DEGRADED"
}
```

### 3.4 DeviceStatus

```json
{
  "routerCtn": "[MASKED_PHONE_NUMBER]",
  "state": "DEGRADED",
  "currentProfile": "DEGRADED",
  "cooldownStartTime": "2026-05-12T10:26:00+00:00",
  "cooldownRemainingSeconds": 45.3,
  "lastAction": "STEP_DOWN",
  "lastActionTime": "2026-05-12T10:26:00+00:00"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `routerCtn` | string | 단말 CTN |
| `state` | string | `NORMAL` / `DEGRADED` / `UNMANAGED` |
| `currentProfile` | string | `NORMAL` / `DEGRADED` |
| `cooldownStartTime` | ISO 8601 \| null | 복구 쿨다운 시작 시각 |
| `cooldownRemainingSeconds` | float \| null | 잔여 쿨다운(초) |
| `lastAction` | string \| null | `STEP_DOWN` / `STEP_UP` 등 |
| `lastActionTime` | ISO 8601 \| null | 마지막 액션 시각 |

### 3.5 Configuration

```json
{
  "thresholds": [
    { "band": 3, "warning": 10000, "congestion": 20000, "overloadEnter": 30000, "overloadExit": 25000 }
  ],
  "degradation": { "degradedRatio": 0.25, "stepUpRatio": 0.5 },
  "slidingWindowSeconds": 60,
  "recoveryCooldownSeconds": 60,
  "stepUpIntervalSeconds": 30,
  "maxOnvifRetries": 3
}
```

| 필드 | 타입 | 제약 |
|------|------|------|
| `thresholds[]` | BandThreshold[] | 최소 1개 필수, band 중복 불가 |
| `degradation.degradedRatio` | float | `0 < x < 1` |
| `degradation.stepUpRatio` | float | `0 < x < 1`, `degradedRatio < stepUpRatio` |
| `slidingWindowSeconds` | int | 윈도우 크기(초), 권장 60 |
| `recoveryCooldownSeconds` | int | OVERLOAD → NORMAL 복구 후 카메라 step-up 진입까지 대기 |
| `stepUpIntervalSeconds` | int | Step-up 시도 간격 |
| `maxOnvifRetries` | int | ONVIF 명령 재시도 횟수 |

### 3.6 BandThreshold

```json
{ "band": 3, "warning": 10000, "congestion": 20000, "overloadEnter": 30000, "overloadExit": 25000 }
```

제약: `warning < congestion < overloadExit ≤ overloadEnter`

### 3.7 CameraEntry

```json
{
  "cameraId": "CAM-001",
  "ipAddress": "192.168.10.21",
  "onvifPort": 80,
  "username": "admin",
  "profileToken": "Profile_1",
  "isReachable": true,
  "useTls": false,
  "mediaServicePath": "/onvif/media",
  "videoCodec": "H264"
}
```

| 필드 | 타입 | Default | 설명 |
|------|------|---------|------|
| `useTls` | bool | `false` | ONVIF 호출에 HTTPS 사용 여부 (false=http, true=https) |
| `mediaServicePath` | string | `/onvif/media` | ONVIF Media Service의 URL 경로. 제조사별 상이 가능 |
| `videoCodec` | string | `H264` | `H264` 또는 `H265` 중 하나. `SetVideoEncoderConfiguration`의 `<tt:Encoding>` 값 결정 |

> `password`는 응답에 포함되지 않는다. POST/PUT 요청에서도 위 3개 필드는 생략 가능하며, 생략 시 default 값이 적용된다. PUT에서 `null` 전송 시 기존 값 유지.

### 3.8 MappingEntry

```json
{
  "routerCtn": "[MASKED_PHONE_NUMBER]",
  "cameraIds": ["CAM-001", "CAM-002"]
}
```

한 단말(CTN)에 복수 카메라가 매핑될 수 있다.

### 3.9 Alert

```json
{
  "id": "9f0a1c40-...",
  "timestamp": "2026-05-12T10:26:00+00:00",
  "eventType": "CELL_OVERLOAD",
  "groupingKey": { "ecgi": 76677120, "band": 3 },
  "routerCtn": null,
  "message": "Cell ECGI:76677120 Band:3 overloaded (UL_RB=35421)"
}
```

**이벤트 타입(`eventType`)**

| 값 | 설명 | `groupingKey` | `routerCtn` |
|----|------|---------------|-------------|
| `CELL_OVERLOAD` | 셀 과부하 진입 | O | — |
| `CELL_RECOVERY` | 셀 정상 회복 | O | — |
| `DEVICE_DEGRADED` | 단말 화질 다운 | — | O |
| `DEVICE_RESTORED` | 단말 화질 복구 | — | O |
| `DEVICE_UNMANAGED` | 카메라 매핑 없음 | — | O |

### 3.10 CameraCommandLog

```json
{
  "timestamp": "2026-05-12T10:26:00+00:00",
  "cameraId": "CAM-001",
  "routerCtn": "[MASKED_PHONE_NUMBER]",
  "command": "SetVideoEncoderConfiguration",
  "profile": "DEGRADED",
  "bitrate": 512,
  "framerate": 10,
  "resolution": [640, 360],
  "success": true,
  "error": ""
}
```

---

## 4. API 엔드포인트 일람

| 카테고리 | Method | Path | 설명 |
|----------|--------|------|------|
| 설정 | GET | `/api/config` | 현재 설정 조회 |
|  | PUT | `/api/config` | 설정 갱신 및 영구 저장 |
| 셀 | GET | `/api/cells` | 셀 상태 목록 |
|  | GET | `/api/cells/{ecgi}/{band}/devices` | 특정 셀에 결합된 단말 상세 |
| 단말 | GET | `/api/devices` | 단말 상태 목록 |
| 이력 | GET | `/api/history/cells` | 셀 이벤트 이력 조회 |
|  | GET | `/api/history/devices` | 단말 이벤트 이력 조회 |
|  | GET | `/api/history/stats` | 이력 저장소 통계 |
|  | DELETE | `/api/history/reset` | 이력 초기화 |
| 카메라 | GET | `/api/cameras` | 카메라 목록 |
|  | POST | `/api/cameras` | 카메라 등록 |
|  | PUT | `/api/cameras/{camera_id}` | 카메라 수정 |
|  | DELETE | `/api/cameras/{camera_id}` | 카메라 삭제 |
|  | GET | `/api/cameras/command-log` | ONVIF 명령 이력 |
| 매핑 | GET | `/api/mappings` | 단말-카메라 매핑 목록 |
|  | POST | `/api/mappings` | 매핑 생성 |
|  | PUT | `/api/mappings/{router_ctn}` | 매핑 교체 |
|  | DELETE | `/api/mappings/{router_ctn}` | 매핑 삭제 |
| 인입 | POST | `/api/ingest/packet` | HTTP로 단말 패킷 인입 |
| 실시간 | WS | `/ws/events` | 실시간 이벤트 구독 |

---

## 5. 엔드포인트 상세

### 5.1 설정

#### 5.1.1 GET `/api/config`

현재 운영 중인 설정을 반환한다.

**Response 200**: [Configuration](#35-configuration)

#### 5.1.2 PUT `/api/config`

설정을 갱신하고 `config.yaml`에 영구 저장한 뒤, 파이프라인을 재구성한다.

**Request Body**: [Configuration](#35-configuration)

**Response 200**: 갱신된 [Configuration](#35-configuration)

**Validation 오류 (422)**

| 조건 | `detail` |
|------|----------|
| `band` 중복 | `Duplicate band: {n}` |
| 임계값 순서 위반 | `Band {n}: <원인>` |
| `thresholds` 비어있음 | `At least one band threshold is required` |
| `degradedRatio` 범위 외 | `degradedRatio must be between 0 and 1` |
| `stepUpRatio` 범위 외 | `stepUpRatio must be between 0 and 1` |
| `degradedRatio ≥ stepUpRatio` | `degradedRatio must be less than stepUpRatio` |

---

### 5.2 셀

#### 5.2.1 GET `/api/cells`

모든 활성 셀의 현재 상태를 반환한다.

**Response 200**: [CellStatus](#32-cellstatus)[]

#### 5.2.2 GET `/api/cells/{ecgi}/{band}/devices`

특정 셀(ECGI, Band)에 결합된 단말들의 최신 측정값을 반환한다. `ulRbUsage` 내림차순 정렬.

**Path Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `ecgi` | int | 셀 ECGI |
| `band` | int | Band 번호 |

**Response 200**: [CellDeviceDetail](#33-celldevicedetail)[]

**Response 404**: `{"detail": "Cell not found"}`

---

### 5.3 단말

#### 5.3.1 GET `/api/devices`

서버가 추적 중인 모든 단말의 현재 상태를 반환한다.

**Response 200**: [DeviceStatus](#34-devicestatus)[]

---

### 5.4 이력

#### 5.4.1 GET `/api/history/cells`

셀 이벤트 이력을 조회한다.

**Query Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `ecgi` | int (optional) | 필터 — 셀 ECGI |
| `band` | int (optional) | 필터 — Band |
| `from` | ISO 8601 (optional) | 시작 시각 (포함) |
| `to` | ISO 8601 (optional) | 종료 시각 (포함) |

**Response 200**: `CellHistoryItem[]`

```json
[
  {
    "id": "9f0a1c40-...",
    "timestamp": "2026-05-12T10:26:00+00:00",
    "eventType": "CELL_OVERLOAD",
    "ecgi": 76677120,
    "band": 3,
    "message": "Cell ECGI:76677120 Band:3 overloaded (UL_RB=35421)"
  }
]
```

#### 5.4.2 GET `/api/history/devices`

단말 이벤트 이력을 조회한다.

**Query Parameters**

| 파라미터 | 타입 | 설명 |
|----------|------|------|
| `ctn` | string (optional) | 필터 — 단말 CTN |
| `from` | ISO 8601 (optional) | 시작 시각 |
| `to` | ISO 8601 (optional) | 종료 시각 |

**Response 200**: `DeviceHistoryItem[]`

```json
[
  {
    "routerCtn": "[MASKED_PHONE_NUMBER]",
    "previousState": "NORMAL",
    "newState": "DEGRADED",
    "action": "STEP_DOWN",
    "timestamp": "2026-05-12T10:26:00+00:00",
    "profile": "DEGRADED"
  }
]
```

#### 5.4.3 GET `/api/history/stats`

이력 저장소 통계.

**Response 200**

```json
{ "rows": 12345, "bytes": 9876543 }
```

#### 5.4.4 DELETE `/api/history/reset`

이력 테이블을 비운다. (주의: 비가역)

**Response 200**

```json
{ "deleted": 12345, "rows": 0, "bytes": 8192 }
```

---

### 5.5 카메라

#### 5.5.1 GET `/api/cameras`

등록된 카메라 목록.

**Response 200**: [CameraEntry](#37-cameraentry)[]

#### 5.5.2 POST `/api/cameras`

카메라 등록.

**Request Body**

```json
{
  "cameraId": "CAM-001",
  "ipAddress": "192.168.10.21",
  "onvifPort": 80,
  "username": "admin",
  "password": "secret",
  "profileToken": "Profile_1"
}
```

**Response 201**: [CameraEntry](#37-cameraentry)

**Response 409**: `{"detail": "Camera ID already exists"}`

#### 5.5.3 PUT `/api/cameras/{camera_id}`

카메라 정보 수정. `password`를 `null`로 전송하면 기존 비밀번호가 유지된다.

**Request Body**

```json
{
  "ipAddress": "192.168.10.22",
  "onvifPort": 80,
  "username": "admin",
  "password": null,
  "profileToken": "Profile_1"
}
```

**Response 200**: [CameraEntry](#37-cameraentry)

**Response 404**: `{"detail": "Camera not found"}`

#### 5.5.4 DELETE `/api/cameras/{camera_id}`

카메라 삭제.

**Response 204**: (본문 없음)

**Response 404**: `{"detail": "Camera not found"}`

#### 5.5.5 GET `/api/cameras/command-log`

서버가 카메라에 전송한 ONVIF 명령 이력.

**Response 200**: [CameraCommandLog](#310-cameracommandlog)[]

---

### 5.6 단말-카메라 매핑

#### 5.6.1 GET `/api/mappings`

현재 매핑 전체를 반환한다.

**Response 200**: [MappingEntry](#38-mappingentry)[]

#### 5.6.2 POST `/api/mappings`

단말에 카메라를 추가 매핑한다. (이미 매핑이 있으면 카메라가 추가됨)

**Request Body**

```json
{ "routerCtn": "[MASKED_PHONE_NUMBER]", "cameraId": "CAM-001" }
```

**Response 201**: [MappingEntry](#38-mappingentry)

**Response 404**: `{"detail": "Camera not found"}`

#### 5.6.3 PUT `/api/mappings/{router_ctn}`

기존 매핑의 카메라 ID를 새 값으로 **교체**한다(기존 매핑은 모두 제거 후 신규 1건만 남김).

**Request Body**: POST와 동일

**Response 200**: [MappingEntry](#38-mappingentry)

**Response 404**: `{"detail": "Mapping not found"}` 또는 `Camera not found`

#### 5.6.4 DELETE `/api/mappings/{router_ctn}`

해당 단말의 매핑 전체를 삭제한다.

**Response 204**: (본문 없음)

**Response 404**: `{"detail": "Mapping not found"}`

---

### 5.7 패킷 인입 (HTTP)

#### 5.7.1 POST `/api/ingest/packet`

UDP 대신 HTTP로 단말 패킷을 인입할 때 사용한다. (테스트, 우회 경로)

- 요청 본문은 **67바이트 raw binary** ([패킷 규격서](packet_interface_spec.md) 참조).
- `Content-Type: application/octet-stream` 권장.

**Response 200**

```json
{
  "success": true,
  "routerCtn": "[MASKED_PHONE_NUMBER]",
  "eventsGenerated": 1,
  "cellTransitions": 0,
  "deviceActions": 0
}
```

**Response 400**

```json
{
  "errors": ["Invalid total_length: expected 67, got 66"]
}
```

---

## 6. 실시간 이벤트 (WebSocket)

### 6.1 연결

```
ws://<server>:8000/ws/events
```

- 서브프로토콜 없음
- 인증 없음 (현재 버전)
- 연결 후 서버는 모든 상태 변경/알림을 푸시한다
- 클라이언트의 송신 메시지는 무시되지만, 연결 유지를 위해 ping/pong 형태로 사용할 수 있다

### 6.2 메시지 포맷

모든 메시지는 다음 공통 envelope를 따른다.

```json
{ "type": "<event_type>", "data": { ... } }
```

### 6.3 이벤트 종류

#### 6.3.1 `cell_state_changed`

셀의 UL_RB 합산값이 갱신되었거나 셀 상태가 전이될 때 발생.

```json
{
  "type": "cell_state_changed",
  "data": {
    "groupingKey": { "ecgi": 76677120, "band": 3 },
    "state": "OVERLOAD",
    "ulRbSum": 35421,
    "ctnList": ["[MASKED_PHONE_NUMBER]"],
    "stateEnteredAt": "2026-05-12T10:25:00+00:00"
  }
}
```

#### 6.3.2 `device_state_changed`

단말의 운영 상태 또는 화질 프로필이 변경되었을 때.

```json
{
  "type": "device_state_changed",
  "data": {
    "routerCtn": "[MASKED_PHONE_NUMBER]",
    "state": "DEGRADED",
    "currentProfile": "DEGRADED",
    "cooldownStartTime": null,
    "cooldownRemainingSeconds": 45.3,
    "lastAction": "STEP_DOWN",
    "lastActionTime": "2026-05-12T10:26:00+00:00"
  }
}
```

#### 6.3.3 `alert`

이벤트 로그에도 저장되는 알림 메시지.

```json
{
  "type": "alert",
  "data": {
    "id": "9f0a1c40-...",
    "timestamp": "2026-05-12T10:26:00+00:00",
    "eventType": "CELL_OVERLOAD",
    "groupingKey": { "ecgi": 76677120, "band": 3 },
    "routerCtn": null,
    "message": "Cell ECGI:76677120 Band:3 overloaded (UL_RB=35421)"
  }
}
```

`data` 본문은 [Alert](#39-alert) 데이터 모델과 동일하다.

### 6.4 재연결 권고

- 클라이언트는 연결 끊김을 감지하면 지수 백오프(1s → 2s → 4s, 최대 30s)로 재연결한다.
- 재연결 후 누락된 상태를 보정하기 위해 `/api/cells`, `/api/devices`를 1회 호출하여 초기 상태를 동기화할 것을 권장.

---

## 7. 상태 전이 규칙 (참고)

### 7.1 Cell State

윈도우 만료 시점의 `ulRbSum`을 임계값과 비교하여 결정.

```
ulRbSum < warning                       → NORMAL
warning  ≤ ulRbSum < congestion         → WARNING
congestion ≤ ulRbSum < overloadEnter    → CONGESTION
ulRbSum ≥ overloadEnter                 → OVERLOAD
OVERLOAD 진입 후 ulRbSum < overloadExit → NORMAL (히스테리시스)
```

### 7.2 Device State / Profile

- 단말이 결합된 셀 중 하나라도 `OVERLOAD` → `DEGRADED` 진입 → ONVIF `SetVideoEncoderConfiguration` 호출(`degradedRatio` 적용)
- 모든 결합 셀이 `NORMAL` 회복 후 `recoveryCooldownSeconds` 경과 → `stepUpIntervalSeconds` 간격으로 `step_up_ratio`에 따라 화질 복구 → `NORMAL`
- 매핑된 카메라가 없는 단말 → `UNMANAGED`

---

## 8. 호출 시나리오 예시

### 8.1 대시보드 초기 로딩

```
GET /api/config         ← 임계값/설정 표시용
GET /api/cells          ← 셀 카드 목록
GET /api/devices        ← 단말 목록
GET /api/cameras        ← 카메라 목록
GET /api/mappings       ← 매핑 목록
WS  /ws/events          ← 이후 변경분은 실시간 수신
```

### 8.2 카메라 등록 → 단말 매핑

```
POST /api/cameras   { cameraId, ipAddress, ... }   → 201
POST /api/mappings  { routerCtn, cameraId }        → 201
```

### 8.3 운영 중 임계값 조정

```
PUT  /api/config    { thresholds: [...] , ... }    → 200
```

설정 변경 즉시 파이프라인이 재구성되고, 다음 윈도우 만료부터 새 임계값이 적용된다.

### 8.4 사후 분석

```
GET /api/history/cells?ecgi=76677120&band=3&from=2026-05-12T00:00:00Z&to=2026-05-12T23:59:59Z
GET /api/history/devices?ctn=[MASKED_PHONE_NUMBER]
GET /api/cameras/command-log
```

---

## 9. 운영 시 고려사항

| 항목 | 권고 |
|------|------|
| WebSocket 동시 접속 수 | 수십 클라이언트는 문제없음. 수백 단위 운영 시 별도 부하 테스트 필요 |
| `/api/ingest/packet` 사용 | 운영 환경은 UDP 9000 사용을 기본으로 하며, HTTP 인입은 진단/우회용 |
| `DELETE /api/history/reset` | 비가역적이므로 운영 환경에서 보호 필요 (역할 분리 또는 차후 인증 적용) |
| 시간 동기화 | 단말/서버/대시보드 모두 NTP 동기화 필수. 윈도우 만료 판정에 영향 |
| 비밀번호 | 카메라 비밀번호는 응답에서 제외되며, 변경하지 않으려면 `password: null`로 전송 |

---

## 10. 향후 확장 (Roadmap)

| 버전 | 추가 항목 |
|------|-----------|
| v1.1 | `/api/health`, `/api/version` 엔드포인트 |
| v1.2 | 페이지네이션 및 정렬 파라미터 (`limit`, `offset`, `sort`) |
| v2.0 | API Key / JWT 기반 인증, RBAC |
| v2.1 | OpenAPI 3.1 스키마 공개 (`/openapi.json`) 기반 클라이언트 자동 생성 |
| v2.2 | gRPC 스트리밍 기반 단말 인입 채널 (UDP 대체) |

---

## 11. 개정 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2026-05-12 | 최초 작성 (현행 v0.1.0 서버 구현 기준) |
| 1.1 | 2026-05-20 | `CameraEntry` 스키마에 `useTls`, `mediaServicePath`, `videoCodec` 필드 추가 (POST/PUT/GET 동일). Default 제공으로 기존 클라이언트 호환 |
