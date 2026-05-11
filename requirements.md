# Requirements Document

## Introduction

본 문서는 이동통신망(LTE/5G)에 접속된 무선 CCTV 단말의 트래픽을 셀(Cell) 단위로 효율적으로 제어하여 네트워크 과부하를 방지하고 서비스 품질을 안정적으로 유지하기 위한 Cell Traffic Optimizer 시스템의 요구사항을 정의한다.

핵심 문제는 다수의 CCTV 단말이 특정 셀에 집중되는 환경에서 업링크 트래픽 폭증, 무선 자원(PRB) 부족, 사용자 체감 품질 저하가 발생하는 것이며, 이를 해결하기 위해 단말 기반 셀 상태 수집, 셀 부하 기반 중앙 제어, ONVIF 기반 카메라 화질 동적 제어를 수행한다.

## Glossary

- **Control_Server**: 다수의 CCTV 단말로부터 셀 상태 패킷을 수신·파싱·집계하고, 셀 부하 판단 및 화질 제어 명령을 발행하는 중앙 서버
- **CCTV_Terminal**: LTE/5G 모듈이 장착된 무선 CCTV 단말로, 셀 상태 패킷을 Control_Server로 전송하고 ONVIF 프로토콜로 화질 제어를 수신하는 장치
- **Cell_Status_Packet**: CCTV_Terminal이 Control_Server로 전송하는 67바이트 고정 길이 바이너리 패킷. Version, Message Type, Total Length, Router_CTN, RAT_Block(Primary), RAT_Block(Secondary), Reserved 필드로 구성된다
- **RAT_Block**: Cell_Status_Packet 내 23바이트 고정 길이 블록으로, RAT Type, PLMN ID, ECGI or NRCGI, EARFCN or NR ARFCN, Timestamp, UL_RB_Usage 필드를 포함한다. Primary 블록은 항상 유효한 값을 가지며, Secondary 블록은 NSA 환경에서만 유효하고 그 외에는 0으로 패딩된다
- **RAT_Type**: RAT_Block 내 1바이트 필드로, 무선 접속 기술 유형을 나타낸다. 0x01(LTE Primary), 0x02(NR SA 또는 NR Secondary), 0x03(RedCap), 0x00(없음/패딩)
- **Router_CTN**: Cell_Status_Packet 내 15바이트 문자열 필드로, 단말의 전화번호(CTN)를 나타낸다. 남는 바이트는 null(0x00)로 패딩된다
- **ECGI**: E-UTRAN Cell Global Identifier. LTE 네트워크에서 셀을 고유하게 식별하는 식별자
- **NRCGI**: NR Cell Global Identifier. 5G NR 네트워크에서 셀을 고유하게 식별하는 식별자
- **EARFCN**: E-UTRA Absolute Radio Frequency Channel Number. LTE 셀의 주파수 채널 번호
- **NR_ARFCN**: NR Absolute Radio Frequency Channel Number. 5G NR 셀의 주파수 채널 번호
- **UL_RB_Usage**: Uplink Resource Block Usage. RAT_Block 내 2바이트 필드로, 업링크 무선 자원 블록 사용량을 나타낸다
- **Traffic_Aggregator**: Raw 이벤트를 시간 윈도우 기반으로 집계하여 셀/밴드 그룹 통계를 생성하는 모듈
- **Cell_Load_Evaluator**: 셀 단위 UL_RB_Usage 합산 값을 실시간으로 평가하고, 임계치 정책에 따라 정상/주의/혼잡/과부하 상태를 판단하는 모듈
- **Quality_Controller**: ONVIF 프로토콜을 사용하여 CCTV_Terminal의 비트레이트, 프레임레이트, 해상도를 동적으로 조정하는 모듈
- **Band**: 이동통신 주파수 대역. EARFCN 또는 NR_ARFCN으로부터 도출되는 셀 운용 주파수 밴드 정보
- **PRB**: Physical Resource Block. LTE/5G 무선 자원의 기본 할당 단위
- **Sliding_Window**: 최근 5분간의 데이터를 기준으로 집계를 수행하는 시간 윈도우 방식
- **Grouping_Key**: (ECGI, Band) 조합으로 구성된 셀/밴드 그룹핑 키
- **Hysteresis**: 상태 전이 시 진동(flapping)을 방지하기 위해 상향/하향 임계치를 분리 적용하는 기법
- **Cell_State_Machine**: 셀/밴드 그룹(Grouping_Key) 단위의 부하 상태(정상, 주의, 혼잡, 과부하)의 전이를 관리하는 셀 레벨 상태 머신. UL_RB_Usage 합산 값을 기반으로 셀 전체의 무선 자원 상태를 판단한다
- **Device_State_Machine**: 개별 CCTV_Terminal(Router_CTN) 단위의 화질 제어 상태(NORMAL, DEGRADED, RECOVERY_PENDING)의 전이를 관리하는 단말 레벨 상태 머신. Cell_State_Machine의 셀 상태 변화에 따라 단말별 화질 제어 및 복구를 관리한다
- **Device_State**: 개별 CCTV_Terminal의 화질 제어 상태를 나타내는 열거형. NORMAL(원래 화질 적용 중), DEGRADED(강제 저화질 적용 중), RECOVERY_PENDING(복구 대기 중, Cooldown 타이머 동작 중) 세 가지 상태를 가진다
- **Recovery_Cooldown**: 셀 상태가 과부하에서 정상으로 전이된 후, 단말의 화질을 즉시 복구하지 않고 일정 시간 동안 안정성을 확인하는 대기 기간. 설정 파일에서 지정된 시간(기본값: 60분) 동안 셀이 정상 상태를 유지해야 복구가 진행된다
- **Step_Up_Recovery**: 화질 복구 시 한 번에 최고 화질로 복원하지 않고, Quality_Profile 단계를 순차적으로 올리는 단계적 복구 방식. 각 단계 사이에 Recovery_Cooldown을 적용하여 급격한 트래픽 증가를 방지한다
- **Quality_Profile**: 카메라 화질 수준을 정의하는 프로파일. LOW(저화질), MID(중화질), HIGH(고화질) 세 단계로 구성되며, 각 단계별 비트레이트, 프레임레이트, 해상도 조합이 사전 정의된다
- **Device_History**: 단말별 상태 변화 이력을 저장하는 데이터 구조. Router_CTN을 키로 하여 현재 Device_State, 마지막 수행 액션, 액션 수행 시각, Recovery_Cooldown 타이머 시작 시각, 현재 적용 중인 Quality_Profile을 관리한다
- **Cell_Stability_Record**: 셀별 안정성 추적 데이터 구조. Grouping_Key를 키로 하여 현재 셀 상태, 상태 진입 시각, 정상 상태 연속 유지 시간을 관리한다
- **ONVIF**: Open Network Video Interface Forum. IP 기반 영상 장비의 표준 프로토콜
- **Device_Registry**: Control_Server가 관리하는 단말 등록 정보 저장소. Router_CTN을 기본 키로 사용하여 단말의 등록 상태, 최종 수신 시각 등을 관리한다
- **Camera_Registry**: Control_Server가 관리하는 카메라 ONVIF 접속 정보 저장소. 카메라별 IP 주소, ONVIF 포트, 인증 정보(사용자명, 비밀번호), 프로파일 토큰 등을 저장한다
- **Device_Camera_Mapping**: 단말(Router_CTN)과 카메라(Camera_Registry 항목) 간의 매핑 관계를 저장하는 테이블. 하나의 단말에 하나 이상의 카메라가 매핑될 수 있다

## Requirements

### Requirement 1: 셀 상태 패킷 수신 및 파싱

**User Story:** As a Control_Server 운영자, I want CCTV_Terminal로부터 수신되는 셀 상태 패킷을 파싱하여 셀 정보를 추출하고자 한다, so that 셀 단위 트래픽 현황을 실시간으로 파악할 수 있다.

#### Acceptance Criteria

1. WHEN CCTV_Terminal로부터 Cell_Status_Packet이 수신되면, THE Control_Server SHALL 패킷의 Total Length가 67바이트인지 검증한다.
2. WHEN 유효한 Cell_Status_Packet이 수신되면, THE Control_Server SHALL 패킷을 다음 고정 구조로 파싱한다: Version(1B, uint8), Message Type(1B, uint8), Total Length(2B, uint16), Router_CTN(15B, string), RAT_Block Primary(23B), RAT_Block Secondary(23B), Reserved(2B, uint16).
3. WHEN RAT_Block을 파싱할 때, THE Control_Server SHALL 각 RAT_Block에서 RAT_Type(1B, uint8), PLMN ID(3B, uint8), ECGI or NRCGI(5B, uint32), EARFCN or NR_ARFCN(4B, uint32), Timestamp(8B, uint64), UL_RB_Usage(2B, uint16)를 추출한다.
4. THE Control_Server SHALL RAT_Block Primary의 RAT_Type 값으로 0x01(LTE Primary), 0x02(NR SA), 0x03(RedCap)을 유효한 값으로 인식한다.
5. WHEN RAT_Block Secondary의 RAT_Type이 0x00이면, THE Control_Server SHALL 해당 블록을 패딩으로 간주하고 무시한다.
6. WHEN RAT_Block Secondary의 RAT_Type이 0x02이면, THE Control_Server SHALL 해당 블록을 NR Secondary 셀 정보로 파싱한다.
7. IF 수신된 패킷의 Total Length가 67바이트가 아니면, THEN THE Control_Server SHALL 해당 패킷을 폐기하고 오류를 로그에 기록한다.
8. IF 수신된 패킷의 Version 또는 Message Type이 지원되지 않는 값이면, THEN THE Control_Server SHALL 해당 패킷을 폐기하고 오류를 로그에 기록한다.
9. IF RAT_Block Primary의 RAT_Type이 유효하지 않은 값이면, THEN THE Control_Server SHALL 해당 패킷을 폐기하고 오류를 로그에 기록한다.
10. WHEN Cell_Status_Packet 파싱이 완료되면, THE Control_Server SHALL 파싱된 데이터를 Raw 이벤트로 변환하여 Traffic_Aggregator에 전달한다.

### Requirement 2: 트래픽 데이터 집계

**User Story:** As a Control_Server 운영자, I want 수집된 Raw 이벤트를 시간 윈도우 기반으로 집계하고자 한다, so that 셀/밴드 그룹 단위의 의미 있는 통계를 생성할 수 있다.

#### Acceptance Criteria

1. THE Traffic_Aggregator SHALL Raw 이벤트를 Sliding_Window(최근 5분) 기준으로 집계한다.
2. THE Traffic_Aggregator SHALL 집계 시 Grouping_Key(ECGI, Band)를 기준으로 데이터를 그룹핑한다.
3. WHEN 새로운 Raw 이벤트가 수신되면, THE Traffic_Aggregator SHALL 해당 이벤트를 Sliding_Window에 추가하고 윈도우 범위를 초과한 이전 데이터를 제거한다.
4. THE Traffic_Aggregator SHALL 각 Grouping_Key별로 UL_RB_Usage 합산 값을 계산한다.
5. THE Traffic_Aggregator SHALL 각 Grouping_Key에 속한 Router_CTN 목록을 추적하여, 과부하 시 해당 셀의 단말을 식별할 수 있도록 한다.
6. IF Sliding_Window 내에 특정 Grouping_Key에 대한 데이터가 존재하지 않으면, THEN THE Traffic_Aggregator SHALL 해당 그룹의 통계를 0으로 초기화한다.
7. WHEN Raw 이벤트의 RAT_Block에 포함된 EARFCN 또는 NR_ARFCN 값을 수신하면, THE Traffic_Aggregator SHALL EARFCN/NR_ARFCN을 Band로 변환하여 Grouping_Key를 구성한다.
8. WHEN NSA 환경에서 하나의 Cell_Status_Packet에 Primary RAT_Block과 Secondary RAT_Block이 모두 유효한 경우, THE Traffic_Aggregator SHALL 각 RAT_Block으로부터 별도의 Raw 이벤트를 생성하여 총 2개의 Raw 이벤트를 처리한다.
9. THE Traffic_Aggregator SHALL 단말 식별 시 Cell_Status_Packet의 Router_CTN 필드를 단말 고유 식별자로 사용한다.

### Requirement 3: 셀 부하 판단 — 주의(Warning) 평가 (1단계)

**User Story:** As a Control_Server 운영자, I want 동일 셀과 동일 Band의 UL_RB_Usage 합산 값을 평가하고자 한다, so that 특정 셀/밴드 조합의 부하 증가 징후를 조기에 감지할 수 있다.

#### Acceptance Criteria

1. WHEN Traffic_Aggregator가 Grouping_Key별 통계를 갱신하면, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key의 UL_RB_Usage 합산 값을 주의 임계값과 비교한다.
2. WHEN 특정 Grouping_Key의 UL_RB_Usage 합산 값이 주의 임계값을 초과하면, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key를 "주의" 상태로 전이한다.
3. WHEN 특정 Grouping_Key의 UL_RB_Usage 합산 값이 주의 임계값 이하이면, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key를 "정상" 상태로 유지한다.

### Requirement 4: 셀 부하 판단 — 혼잡(Congestion) 판단 (2단계)

**User Story:** As a Control_Server 운영자, I want UL_RB_Usage 합산 값을 기반으로 셀 혼잡도를 판단하고자 한다, so that 실제 무선 자원 부족 상황을 정확하게 감지할 수 있다.

#### Acceptance Criteria

1. WHILE 특정 Grouping_Key가 "주의" 상태인 동안, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key의 UL_RB_Usage 합산 값을 혼잡 임계값과 비교한다.
2. WHEN UL_RB_Usage 합산 값이 혼잡 임계값을 초과하면, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key를 "혼잡" 상태로 전이한다.
3. WHEN UL_RB_Usage 합산 값이 혼잡 임계값 이하이면, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key를 "주의" 상태로 유지한다.

### Requirement 5: 셀 부하 판단 — 히스테리시스 적용 (3단계)

**User Story:** As a Control_Server 운영자, I want 상태 전이 시 히스테리시스를 적용하고자 한다, so that 임계값 경계에서의 상태 진동(flapping)을 방지할 수 있다.

#### Acceptance Criteria

1. THE Cell_Load_Evaluator SHALL 과부하 진입 임계값과 과부하 해제 임계값을 별도로 관리한다.
2. WHEN Grouping_Key의 UL_RB_Usage 합산 값이 과부하 진입 임계값을 초과하면, THE Cell_Load_Evaluator SHALL 해당 Grouping_Key를 "과부하" 상태로 전이한다.
3. WHILE Grouping_Key가 "과부하" 상태인 동안, THE Cell_Load_Evaluator SHALL UL_RB_Usage 합산 값이 과부하 해제 임계값 미만으로 떨어져야만 "정상" 상태로 전이한다.
4. THE Cell_Load_Evaluator SHALL 과부하 진입 임계값을 과부하 해제 임계값보다 높게 설정한다.
5. WHEN Cell_State_Machine의 상태가 전이되면, THE Cell_Load_Evaluator SHALL 전이 이벤트(이전 상태, 새 상태, Grouping_Key, 타임스탬프)를 기록한다.

### Requirement 6: ONVIF 기반 카메라 화질 동적 제어

**User Story:** As a Control_Server 운영자, I want 셀 과부하 시 해당 셀에 접속된 CCTV_Terminal의 화질을 자동으로 낮추고, 복구 시에는 Device_State_Machine과 연동하여 단계적으로 복원하고자 한다, so that 네트워크 부하를 줄이고 플래핑 없이 서비스 품질을 안정적으로 유지할 수 있다.

#### Acceptance Criteria

1. WHEN Device_State_Machine이 특정 CCTV_Terminal의 Device_State를 DEGRADED로 전이하면, THE Quality_Controller SHALL 해당 CCTV_Terminal의 Router_CTN을 기반으로 Device_Camera_Mapping을 조회하여 연결된 모든 카메라에 Quality_Profile LOW에 해당하는 화질 저하 명령을 전송한다.
2. THE Quality_Controller SHALL ONVIF 프로토콜을 사용하여 CCTV_Terminal의 비트레이트, 프레임레이트, 해상도를 조정한다.
3. WHEN Device_State_Machine이 Step_Up_Recovery에 의해 Quality_Profile 상향을 요청하면, THE Quality_Controller SHALL 해당 CCTV_Terminal에 연결된 모든 카메라에 요청된 Quality_Profile(MID 또는 HIGH)에 해당하는 화질 조정 명령을 전송한다.
4. WHEN Device_State_Machine이 특정 CCTV_Terminal의 Device_State를 NORMAL로 전이하면, THE Quality_Controller SHALL 해당 CCTV_Terminal에 연결된 모든 카메라에 Quality_Profile HIGH에 해당하는 화질 복원 명령을 전송한다.
5. IF ONVIF 화질 제어 명령이 CCTV_Terminal에 전달되지 않으면, THEN THE Quality_Controller SHALL 해당 실패를 로그에 기록하고 설정된 재시도 횟수만큼 재시도한다.
6. THE Quality_Controller SHALL 화질 조정 시 비트레이트, 프레임레이트, 해상도의 목표 값을 Quality_Profile(LOW, MID, HIGH)에서 선택한다.
7. WHEN Quality_Controller가 카메라에 ONVIF 명령을 전송할 때, THE Quality_Controller SHALL Camera_Registry에서 해당 카메라의 IP 주소, ONVIF 포트, 인증 정보를 조회하여 접속한다.

### Requirement 7: 셀 레벨 상태 머신 관리

**User Story:** As a Control_Server 운영자, I want 셀/밴드 그룹별 상태 전이를 체계적으로 관리하고자 한다, so that 부하 판단 과정의 일관성과 추적 가능성을 확보할 수 있다.

#### Acceptance Criteria

1. THE Cell_State_Machine SHALL 각 Grouping_Key에 대해 "정상", "주의", "혼잡", "과부하" 상태를 관리한다.
2. THE Cell_State_Machine SHALL "정상" → "주의" → "혼잡" → "과부하" 순서의 상태 전이 경로를 따른다.
3. WHEN 과부하 해제 조건이 충족되면, THE Cell_State_Machine SHALL "과부하" → "정상" 상태로 전이한다.
4. THE Cell_State_Machine SHALL 정의되지 않은 상태 전이 요청을 거부하고 해당 요청을 로그에 기록한다.
5. WHEN Cell_State_Machine이 초기화되면, THE Cell_State_Machine SHALL 모든 Grouping_Key의 상태를 "정상"으로 설정한다.
6. WHEN Cell_State_Machine의 상태가 "과부하"로 전이되면, THE Cell_State_Machine SHALL 해당 Grouping_Key에 속한 모든 CCTV_Terminal의 Router_CTN 목록을 Device_State_Machine에 전달하여 단말별 상태 전이를 트리거한다.
7. WHEN Cell_State_Machine의 상태가 "과부하"에서 "정상"으로 전이되면, THE Cell_State_Machine SHALL 해당 Grouping_Key에 속한 모든 CCTV_Terminal의 Router_CTN 목록을 Device_State_Machine에 전달하여 복구 프로세스를 트리거한다.
8. THE Cell_State_Machine SHALL 각 Grouping_Key에 대해 Cell_Stability_Record를 관리하며, 상태 진입 시각과 정상 상태 연속 유지 시간을 기록한다.

### Requirement 8: 데이터 처리 파이프라인

**User Story:** As a Control_Server 운영자, I want Raw 이벤트부터 화질 제어까지의 데이터 처리 파이프라인이 순차적으로 동작하고자 한다, so that 데이터 흐름의 정합성을 보장할 수 있다.

#### Acceptance Criteria

1. THE Control_Server SHALL "Cell_Status_Packet 수신 → 파싱 → Raw 이벤트 변환 → 시간 윈도우 집계 → 셀/밴드 그룹 통계 → Cell_State_Machine 평가 → Device_State_Machine 평가 → Quality_Controller 화질 제어" 순서로 데이터를 처리한다.
2. WHEN 파이프라인의 특정 단계에서 오류가 발생하면, THE Control_Server SHALL 해당 오류를 로그에 기록하고 다음 처리 주기에서 재처리한다.
3. THE Control_Server SHALL 각 파이프라인 처리 단계의 소요 시간을 측정하고 기록한다.
4. THE Control_Server SHALL 주기적으로 Recovery_Cooldown 타이머를 확인하여 만료된 타이머에 대해 Device_State_Machine의 복구 프로세스를 트리거한다.

### Requirement 9: 임계값 설정 관리

**User Story:** As a Control_Server 운영자, I want 부하 판단에 사용되는 임계값을 설정 파일로 관리하고자 한다, so that 운영 환경에 따라 유연하게 정책을 조정할 수 있다.

#### Acceptance Criteria

1. THE Control_Server SHALL 주의 임계값, 혼잡 임계값, 과부하 진입 임계값, 과부하 해제 임계값을 설정 파일에서 로드한다.
2. THE Control_Server SHALL Quality_Profile(LOW, MID, HIGH 각 단계별 비트레이트, 프레임레이트, 해상도 조합)을 설정 파일에서 로드한다.
3. WHEN 설정 파일의 임계값이 유효하지 않으면(예: 과부하 해제 임계값이 과부하 진입 임계값보다 높은 경우), THEN THE Control_Server SHALL 설정 오류를 로그에 기록하고 기본 임계값을 적용한다.
4. THE Control_Server SHALL Sliding_Window 크기를 설정 파일에서 로드한다.
5. THE Control_Server SHALL Recovery_Cooldown 시간(기본값: 60분)을 설정 파일에서 로드한다.
6. THE Control_Server SHALL Step_Up_Recovery 단계 간 대기 시간을 설정 파일에서 로드한다.
7. WHEN 설정 파일의 Recovery_Cooldown 시간이 0 이하이면, THEN THE Control_Server SHALL 설정 오류를 로그에 기록하고 기본값(60분)을 적용한다.

### Requirement 10: 설정 파일 파싱 및 직렬화

**User Story:** As a Control_Server 운영자, I want 설정 파일을 구조화된 형식으로 파싱하고 다시 직렬화할 수 있기를 원한다, so that 설정의 무결성을 검증하고 프로그래밍 방식으로 설정을 관리할 수 있다.

#### Acceptance Criteria

1. WHEN 유효한 설정 파일이 제공되면, THE Config_Parser SHALL 설정 파일을 Configuration 객체로 파싱한다.
2. WHEN 유효하지 않은 설정 파일이 제공되면, THE Config_Parser SHALL 오류 위치와 원인을 포함한 설명적 오류를 반환한다.
3. THE Config_Printer SHALL Configuration 객체를 유효한 설정 파일 형식으로 포맷한다.
4. FOR ALL 유효한 Configuration 객체에 대해, 파싱 후 출력 후 다시 파싱하면 동등한 객체를 생성한다 (라운드트립 속성).

### Requirement 11: 단말 식별 정보 관리

**User Story:** As a Control_Server 운영자, I want Router_CTN 기반으로 단말을 등록하고 관리하고자 한다, so that 셀 과부하 시 해당 셀에 접속된 단말을 정확하게 식별할 수 있다.

#### Acceptance Criteria

1. THE Control_Server SHALL Device_Registry에 Router_CTN을 기본 키로 사용하여 단말 등록 정보를 저장한다.
2. THE Device_Registry SHALL 각 단말에 대해 Router_CTN, 등록 상태, 최종 패킷 수신 시각, 등록 일시를 관리한다.
3. WHEN 신규 Router_CTN이 포함된 Cell_Status_Packet이 수신되면, THE Control_Server SHALL 해당 Router_CTN을 Device_Registry에 자동 등록한다.
4. WHEN 기존 등록된 Router_CTN의 Cell_Status_Packet이 수신되면, THE Control_Server SHALL Device_Registry의 최종 패킷 수신 시각을 갱신한다.
5. IF Device_Registry에 존재하지 않는 Router_CTN에 대해 조회 요청이 발생하면, THEN THE Control_Server SHALL 해당 단말이 미등록 상태임을 반환한다.

### Requirement 12: 카메라 ONVIF 접속 정보 관리

**User Story:** As a Control_Server 운영자, I want 카메라의 ONVIF 접속 정보를 중앙에서 관리하고자 한다, so that 화질 제어 시 카메라에 정확하게 접속할 수 있다.

#### Acceptance Criteria

1. THE Control_Server SHALL Camera_Registry에 카메라별 ONVIF 접속 정보를 저장한다.
2. THE Camera_Registry SHALL 각 카메라에 대해 카메라 식별자, IP 주소, ONVIF 포트, 인증 사용자명, 인증 비밀번호, ONVIF 프로파일 토큰을 관리한다.
3. WHEN 새로운 카메라 접속 정보가 등록되면, THE Control_Server SHALL 해당 카메라의 ONVIF 접속 가능 여부를 검증한다.
4. IF Camera_Registry에 저장된 카메라의 ONVIF 접속 정보가 유효하지 않으면(접속 실패), THEN THE Control_Server SHALL 해당 카메라를 "접속 불가" 상태로 표시하고 오류를 로그에 기록한다.
5. THE Camera_Registry SHALL 인증 비밀번호를 암호화하여 저장한다.

### Requirement 13: 단말-카메라 매핑 관리

**User Story:** As a Control_Server 운영자, I want 단말(Router_CTN)과 카메라(ONVIF 접속 정보) 간의 매핑 관계를 관리하고자 한다, so that 과부하 셀의 단말에 연결된 카메라를 식별하여 화질 제어를 수행할 수 있다.

#### Acceptance Criteria

1. THE Control_Server SHALL Device_Camera_Mapping에 Router_CTN과 카메라 식별자 간의 매핑 관계를 저장한다.
2. THE Device_Camera_Mapping SHALL 하나의 Router_CTN에 하나 이상의 카메라가 매핑되는 1:N 관계를 지원한다.
3. WHEN Quality_Controller가 특정 Grouping_Key에 속한 단말의 카메라를 조회하면, THE Control_Server SHALL Device_Camera_Mapping에서 해당 Router_CTN에 매핑된 모든 카메라 식별자를 반환하고, Camera_Registry에서 각 카메라의 ONVIF 접속 정보를 조회한다.
4. IF Device_Camera_Mapping에 매핑되지 않은 Router_CTN에 대해 카메라 조회가 요청되면, THEN THE Control_Server SHALL 매핑 없음을 반환하고 해당 단말에 대한 화질 제어를 건너뛴다.
5. WHEN Device_Camera_Mapping의 매핑 관계가 변경되면, THE Control_Server SHALL 변경 이력(이전 매핑, 새 매핑, 변경 시각)을 로그에 기록한다.

### Requirement 14: 단말 레벨 상태 머신 관리

**User Story:** As a Control_Server 운영자, I want 개별 CCTV_Terminal 단위로 화질 제어 상태를 관리하고자 한다, so that 셀 상태 변화에 따른 단말별 화질 저하 및 복구를 체계적으로 추적하고 플래핑을 방지할 수 있다.

#### Acceptance Criteria

1. THE Device_State_Machine SHALL 각 CCTV_Terminal(Router_CTN)에 대해 NORMAL, DEGRADED, RECOVERY_PENDING 세 가지 Device_State를 관리한다.
2. THE Device_State_Machine SHALL NORMAL → DEGRADED → RECOVERY_PENDING → NORMAL 순서의 상태 전이 경로를 따른다.
3. WHEN Cell_State_Machine이 특정 Grouping_Key를 "과부하" 상태로 전이하면, THE Device_State_Machine SHALL 해당 Grouping_Key에 속한 Device_State가 NORMAL인 모든 CCTV_Terminal의 상태를 DEGRADED로 전이한다.
4. WHEN Cell_State_Machine이 특정 Grouping_Key를 "과부하"에서 "정상"으로 전이하면, THE Device_State_Machine SHALL 해당 Grouping_Key에 속한 Device_State가 DEGRADED인 모든 CCTV_Terminal의 상태를 RECOVERY_PENDING으로 전이하고 Recovery_Cooldown 타이머를 시작한다.
5. WHEN Recovery_Cooldown 타이머가 만료되고 해당 CCTV_Terminal이 속한 Grouping_Key의 셀 상태가 "정상"을 유지하고 있으면, THE Device_State_Machine SHALL 해당 CCTV_Terminal의 Step_Up_Recovery 프로세스를 진행한다.
6. WHILE CCTV_Terminal의 Device_State가 RECOVERY_PENDING인 동안 해당 Grouping_Key가 다시 "과부하" 상태로 전이하면, THE Device_State_Machine SHALL Recovery_Cooldown 타이머를 취소하고 해당 CCTV_Terminal의 Device_State를 DEGRADED로 전이한다.
7. THE Device_State_Machine SHALL 정의되지 않은 상태 전이 요청을 거부하고 해당 요청을 로그에 기록한다.
8. WHEN Device_State_Machine이 초기화되면, THE Device_State_Machine SHALL 모든 CCTV_Terminal의 Device_State를 NORMAL로 설정하고 Quality_Profile을 HIGH로 설정한다.
9. WHEN Device_State가 전이되면, THE Device_State_Machine SHALL 전이 이벤트(Router_CTN, 이전 상태, 새 상태, 타임스탬프, 현재 Quality_Profile)를 로그에 기록한다.

### Requirement 15: 지연 복구 (Recovery Cooldown)

**User Story:** As a Control_Server 운영자, I want 셀 상태가 정상으로 전이된 후 일정 시간 동안 안정성을 확인한 뒤에 화질을 복구하고자 한다, so that 셀 상태가 불안정한 상황에서 즉시 복구로 인한 재혼잡(플래핑)을 방지할 수 있다.

#### Acceptance Criteria

1. WHEN CCTV_Terminal의 Device_State가 DEGRADED에서 RECOVERY_PENDING으로 전이되면, THE Device_State_Machine SHALL 해당 CCTV_Terminal에 대해 Recovery_Cooldown 타이머를 시작한다.
2. THE Device_State_Machine SHALL Recovery_Cooldown 타이머의 지속 시간을 설정 파일에서 로드된 값(기본값: 60분)으로 설정한다.
3. WHILE Recovery_Cooldown 타이머가 동작 중인 동안, THE Device_State_Machine SHALL 해당 CCTV_Terminal의 현재 Quality_Profile을 변경하지 않고 유지한다.
4. WHEN Recovery_Cooldown 타이머가 만료되고 해당 CCTV_Terminal이 속한 Grouping_Key의 Cell_State_Machine 상태가 "정상"이면, THE Device_State_Machine SHALL Step_Up_Recovery의 다음 단계 Quality_Profile 상향을 Quality_Controller에 요청한다.
5. WHEN Recovery_Cooldown 타이머가 만료되었으나 해당 CCTV_Terminal이 속한 Grouping_Key의 Cell_State_Machine 상태가 "정상"이 아니면, THE Device_State_Machine SHALL 해당 CCTV_Terminal의 Device_State를 DEGRADED로 전이하고 Recovery_Cooldown 타이머를 취소한다.
6. WHILE Recovery_Cooldown 타이머가 동작 중인 동안 해당 Grouping_Key가 다시 "과부하" 상태로 전이하면, THE Device_State_Machine SHALL Recovery_Cooldown 타이머를 즉시 취소하고 해당 CCTV_Terminal의 Device_State를 DEGRADED로 전이한다.
7. THE Device_State_Machine SHALL 각 CCTV_Terminal의 Recovery_Cooldown 타이머 시작 시각과 남은 시간을 Device_History에 기록한다.

### Requirement 16: 단계적 복구 (Step-Up Recovery)

**User Story:** As a Control_Server 운영자, I want 화질 복구 시 한 번에 최고 화질로 복원하지 않고 단계적으로 올리고자 한다, so that 급격한 트래픽 증가로 인한 재혼잡을 방지하고 안정적으로 원래 화질을 복원할 수 있다.

#### Acceptance Criteria

1. THE Device_State_Machine SHALL Quality_Profile을 LOW → MID → HIGH 순서로 단계적으로 상향한다.
2. WHEN CCTV_Terminal의 Device_State가 DEGRADED로 전이되면, THE Device_State_Machine SHALL 해당 CCTV_Terminal의 Quality_Profile을 LOW로 설정하고 Quality_Controller에 LOW 프로파일 적용을 요청한다.
3. WHEN Step_Up_Recovery의 첫 번째 Recovery_Cooldown이 만료되고 셀 상태가 "정상"이면, THE Device_State_Machine SHALL 해당 CCTV_Terminal의 Quality_Profile을 MID로 상향하고 Quality_Controller에 MID 프로파일 적용을 요청한 후 새로운 Recovery_Cooldown 타이머를 시작한다.
4. WHEN Step_Up_Recovery의 두 번째 Recovery_Cooldown이 만료되고 셀 상태가 "정상"이면, THE Device_State_Machine SHALL 해당 CCTV_Terminal의 Quality_Profile을 HIGH로 상향하고 Quality_Controller에 HIGH 프로파일 적용을 요청하며 Device_State를 NORMAL로 전이한다.
5. WHILE Step_Up_Recovery가 진행 중인 동안(Quality_Profile이 MID인 상태) 해당 Grouping_Key가 다시 "과부하" 상태로 전이하면, THE Device_State_Machine SHALL Step_Up_Recovery를 중단하고 Quality_Profile을 LOW로 재설정하며 Device_State를 DEGRADED로 전이한다.
6. THE Device_State_Machine SHALL Step_Up_Recovery의 각 단계 전이 시 현재 Quality_Profile, 목표 Quality_Profile, 타임스탬프를 로그에 기록한다.
7. IF Step_Up_Recovery 중 Quality_Controller의 화질 조정 명령이 실패하면, THEN THE Device_State_Machine SHALL 현재 Quality_Profile을 유지하고 다음 Recovery_Cooldown 주기에서 재시도한다.

### Requirement 17: 단말별 이력 데이터 관리

**User Story:** As a Control_Server 운영자, I want 각 CCTV_Terminal의 상태 변화 이력과 셀별 안정성 데이터를 체계적으로 관리하고자 한다, so that 장애 분석, 운영 최적화, 플래핑 패턴 감지에 활용할 수 있다.

#### Acceptance Criteria

1. THE Control_Server SHALL 각 CCTV_Terminal에 대해 Device_History를 관리하며, Router_CTN, 현재 Device_State, 마지막 수행 액션(DOWNGRADE, STEP_UP, RESTORE), 액션 수행 시각, Recovery_Cooldown 타이머 시작 시각, 현재 Quality_Profile을 저장한다.
2. WHEN Device_State_Machine이 CCTV_Terminal의 상태를 전이하면, THE Control_Server SHALL Device_History의 해당 필드를 갱신한다.
3. THE Control_Server SHALL 각 Grouping_Key에 대해 Cell_Stability_Record를 관리하며, 현재 셀 상태, 상태 진입 시각, 정상 상태 연속 유지 시간을 저장한다.
4. WHEN Cell_State_Machine의 상태가 전이되면, THE Control_Server SHALL Cell_Stability_Record의 상태 진입 시각을 갱신하고, "정상" 상태로 전이된 경우 정상 상태 연속 유지 시간 측정을 시작한다.
5. WHEN Cell_State_Machine의 상태가 "정상"에서 다른 상태로 전이되면, THE Control_Server SHALL Cell_Stability_Record의 정상 상태 연속 유지 시간을 0으로 초기화한다.
6. THE Control_Server SHALL Device_History와 Cell_Stability_Record를 영속적으로 저장하여 Control_Server 재시작 시에도 데이터를 유지한다.
7. IF Control_Server가 재시작되면, THEN THE Control_Server SHALL 저장된 Device_History와 Cell_Stability_Record를 로드하여 Device_State_Machine과 Cell_State_Machine의 상태를 복원한다.
