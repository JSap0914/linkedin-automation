# LinkedIn 댓글 자동 답글 + DM 봇을 만들며 겪은 우여곡절

> "내 포스트에 달리는 댓글마다 한국어로 답글 달고 1촌이면 DM까지 자동으로"
> — 한 줄 요구사항으로 시작한 며칠간의 리버스 엔지니어링

---

## 1. 시작 — 단순한 소망

요구사항은 정말 단순했다.

- 내가 LinkedIn에 글 올림
- 사람들이 댓글 달음
- 봇이 한국어로 **3개 중 랜덤한 감사 답글** 자동 전송
- 더 나아가: 1촌이면 **DM까지** 자동 전송
- 되도록 **"OOO님"** 처럼 이름 개인화
- 설치 → 켜면 → 알아서 돌 것

실제로 돌아가는 것까지 **며칠** 걸렸다.

---

## 2. 첫 번째 벽 — LinkedIn 공식 API는 닫혀 있다

처음엔 당연히 **공식 API**부터 알아봤다.

결과: **데드 엔드.**

- `r_member_social` 스코프 (내 포스트의 댓글 읽기) → **2023년부터 닫혀있음**
- `w_member_social` (쓰기) → 열려 있지만 읽기 권한 없이는 무의미
- 기업 파트너십 + Marketing Developer Platform 승인 받아야 풀림
- 개인 개발자 계정으로는 사실상 **불가능**

### 교훈 1
> "공식 API가 가장 안전하다" — 는 **케이스 바이 케이스**. 어떤 API는 존재하지만 **사실상 너에게 닫혀 있다.**

---

## 3. 우회로 — Scrapling + Voyager API + StealthySession

공식 API가 막히면 남은 선택지는 셋:

1. **브라우저 자동화** (사람처럼 클릭)
2. **내부 API 리버스 엔지니어링** (LinkedIn 웹 자체가 쓰는 Voyager API)
3. **둘의 하이브리드** — 브라우저 세션으로 로그인 유지 + Voyager API로 실제 작업

최종 선택은 **3번**. 핵심 도구들:

- **Scrapling** (`D4Vinci/Scrapling`) — Patchright 기반 스텔스 브라우저
- **StealthySession** — 로그인 세션을 `user_data_dir` 에 영구 저장
- **page.evaluate(fetch)** — 브라우저 안에서 JavaScript `fetch()` 로 Voyager API 호출
  (CSRF/쿠키/세션이 자동 적용됨)

이 아키텍처로 가기 전에 **Momus (AI 플랜 리뷰어)** 를 거쳐 플랜을 한 번 검증받았다. 몇 번 reject 되다가 approve. 그 후 22개 태스크로 쪼개서 구현 시작.

### 교훈 2
> **계획을 세우고 리뷰를 받아라.** 혼자 생각한 설계는 대부분 구멍이 있다.

---

## 4. 첫 번째 삽질 — "댓글이 0개?"

초기 버전이 돌기 시작했다.

- ✅ 로그인 OK
- ✅ 포스트 1개 찾음
- ✅ 댓글 API 호출 성공 (HTTP 200)
- ❌ **파싱된 댓글: 0개**

분명 댓글은 있는데 0개? 응답을 까봤다.

### 우리가 가정한 응답 구조
```json
{
  "elements": [
    {
      "commentUrn": "...",
      "commenter": { "miniProfile": { ... } },
      "commentV2": { "text": "..." }
    }
  ]
}
```

### 실제 LinkedIn 응답 구조
```json
{
  "data": {
    "*elements": ["urn:li:fs_objectComment:(...)"]
  },
  "included": [
    {
      "entityUrn": "urn:li:fs_objectComment:(...)",
      "commentV2": { "text": "..." },
      "commenterForDashConversion": {
        "title": { "text": "John Doe" },
        "actorUnion": { "profileUrn": "urn:li:fsd_profile:..." }
      },
      "parentCommentUrn": null
    }
  ]
}
```

완전히 **다른 모양**. 우리가 `elements[]` 기준으로 파싱하니 당연히 0개.

### 무엇이 달랐나
- 🔴 최상위에 `elements` 없음 → `data["*elements"]` 에 URN **참조** 배열
- 🔴 실제 엔티티는 `included[]` 에 따로 들어있음 (LinkedIn의 "normalized" 응답 형식)
- 🔴 `commenter.miniProfile` 아님 → `commenterForDashConversion`

### 수정
파서를 실제 구조에 맞춤. 그러자 **즉시 댓글 1개 파싱 성공**.

### 교훈 3
> **외부 리서치 자료를 100% 믿지 마라.** LinkedIn은 내부 API를 수시로 갱신한다. 실제 응답을 찍어보고 맞춰라.

---

## 5. 두 번째 삽질 — **답글 POST의 500 에러 대장정**

이게 이번 프로젝트 최대 고비.

댓글은 읽었다. 이제 답글 POST. 결과:

```
HTTP 500 Internal Server Error
```

몇 번이나?  **7번 이상**.

### 반복 패턴
매번 "이건가?" 하고 고쳐서 다시 쏘면 다시 500. 원인을 하나씩 제거:

| 시도 | 변경 내용 | 결과 |
|------|-----------|------|
| 1 | 기본 payload `{actor, object, message, parentComment}` | **500** |
| 2 | `parentComment` URN 을 "full form"(`urn:li:comment:(urn:li:activity:X,Y)`)으로 | **500** |
| 3 | `object` 를 `activity URN` → `share URN` 으로 | **500** |
| 4 | 프리플라이트 signal + 메타데이터 헤더 (`x-li-pem-metadata`, `x-li-page-instance`, `x-li-track`) 추가 | **500** |
| 5 | Dash 스타일 엔드포인트 (`/voyagerSocialDashNormComments`) 시도, payload 도 Dash 스펙으로 | **400** (바뀌긴 했다!) |
| 6 | `parentComment` → `parentCommentUrn` (fsd_comment 형식) 으로 변환 | **400** |
| 7 | `decorationId=NormComment-43` 쿼리 파라미터 추가 | **400** |

**결국** 사용자가 직접 **Chrome DevTools Network 탭 → Payload 캡처**를 도와줬다.

### DevTools 캡처한 진짜 요청 body
```json
{
  "commentary": {
    "text": "reply",
    "attributesV2": [],
    "$type": "com.linkedin.voyager.dash.common.text.TextViewModel"
  },
  "threadUrn": "urn:li:comment:(activity:ACTIVITY_ID,COMMENT_ID)"
}
```

### 우리가 완전 틀리게 알고 있던 것
1. **`parentCommentUrn` 이라는 필드 자체가 없음**
2. **`threadUrn` = 답글 대상 댓글 URN** (post URN 아님!)
3. URN 포맷도 **SHORT form** (`urn:li:comment:(activity:X,Y)`)
4. `$type` 과 `attributesV2` 는 **유지**해야 함

즉, "답글의 thread"는 post가 아니라 **부모 댓글** 자체였다. 구조적 오해.

수정하자마자 → **HTTP 201 Created.**

### 교훈 4
> **"내가 아는 용어"와 "실제 시스템이 쓰는 용어"는 다를 수 있다.** "parent"인지 "thread"인지, 단어 선택 하나가 전체 구조를 바꾼다.

### 교훈 5
> **DevTools 캡처 한 번이면 일주일 걸릴 추측 중단된다.** 리버스 엔지니어링 정답은 언제나 "실제 웹 앱이 보내는 요청".

---

## 6. 보이지 않던 버그 — 확인 로직

답글이 실제로 달렸다. 그런데 봇은:

```
ERROR: Reply creation could not be confirmed
```

뭐지?

### 원인
답글 POST 성공 후, 확인하려고 **댓글을 다시 조회**해서 내 답글이 있는지 체크하는데…  
`/feed/comments` 는 **top-level 댓글만** 반환한다. **nested reply(답글의 답글)** 는 그 목록에 **안 들어있음**.

즉, 실제로는 답글이 달렸는데, 확인 로직이 잘못된 곳을 보고 있었다.

### 수정
POST 응답이 2xx + `data`/`included` 포함이면 **성공으로 인정**. 별도 확인 조회 불필요.  
(기존의 `x-restli-id` 헤더 기반 확인도 Dash 엔드포인트에선 안 내려옴 → 엔벨로프 자체로 판단)

---

## 7. DM 기능 추가 — 다시 한 번 여정

답글이 되니 욕심이 생겼다. "**댓글 단 1촌한테는 DM도 자동으로**".

### 설계
- 이름 개인화 (`{name}님 감사합니다`)
- 1촌 체크 (비-1촌한테 DM 보내면 실패 + spam flag 위험)
- DM 중복 방지 DB
- 하루 수량 제한 (설정 가능)
- 30-300초 랜덤 딜레이

### 플랜 작성 → Momus 리뷰 → 구현

이번에도 **DevTools 캡처**부터 요청. 실제 DM 요청 POST body:

```json
{
  "dedupeByClientGeneratedToken": false,
  "hostRecipientUrns": ["urn:li:fsd_profile:..."],
  "mailboxUrn": "urn:li:fsd_profile:<내 URN>",
  "message": {
    "body": { "attributes": [], "text": "..." },
    "originToken": "<uuid4>",
    "renderContentUnions": []
  },
  "trackingId": "<16바이트 랜덤>"
}
```

엔드포인트:
```
POST /voyager/api/voyagerMessagingDashMessengerMessages?action=createMessage
```

특이사항:
- `Content-Type: text/plain;charset=UTF-8` (body는 JSON인데 헤더는 text/plain)
- `decorationId` 없음
- `conversationUrn` 없음 → 첫 메시지면 LinkedIn이 자동 생성

이번엔 캡처 한 번에 **바로 구현 성공**. 답글 때처럼 헤매지 않음.

---

## 8. 마지막 벽 — 1촌 체크의 Rate Limit

DM 플로우가 다 붙었는데 **1촌 체크만** 안 됨.

기존 엔드포인트:
```
GET /identity/profiles/{id}/networkinfo
```
결과: **403 Rate Limited**

모든 댓글마다 호출해서 차단당한 상태.

### 대안 조사 → 5개 엔드포인트 후보
리서치로 LinkedIn 프론트엔드가 **실제 더 자주 쓰는** 엔드포인트를 찾음:

| 우선순위 | 엔드포인트 | 이유 |
|----------|-----------|------|
| 1 | `/identity/dash/profiles?q=memberIdentity&...&decorationId=TopCardSupplementary-175` | 프로필 열 때마다 LinkedIn이 호출 → rate limit 낮음 |
| 2 | `/graphql?queryId=voyagerIdentityDashProfiles.*` | GraphQL 변형 |
| 3 | `/graphql?queryId=voyagerSearchDashClusters.*` | 검색 (가장 많이 쓰임) |
| 4 | `/graphql?queryId=voyagerIdentityDashProfileCards.*` | 프로필 카드 |
| 5 | `/identity/dash/profiles/{URN}?decorationId=FullProfile-76` | 직접 URN 조회 |

1번으로 교체. **또 다른 복병**:

### 리서치가 틀렸다
리서치 자료는 `memberDistance.value = "DISTANCE_1"` 이라고 했다.

실제 응답에는 `memberDistance` 필드가 **없음**. 대신:

```json
{
  "$type": "com.linkedin.voyager.dash.relationships.MemberRelationship",
  "memberRelationshipUnion": {
    "*connection": "urn:li:fsd_connection:..."
  }
}
```

**패턴 매칭으로 판단**해야 했다:
- `memberRelationshipUnion["*connection"]` 존재 → **1촌 (DISTANCE_1)**
- `Connection` 엔트리에 `connectedMember` 존재 → **1촌**
- `*noConnection`, `*invited` 등 → 비-1촌

이게 최종 맞춘 모양.

### 결과
```
is_first_degree(urn:li:person:ACoAA...) = True ✅
```

DM 엔드포인트 호출 → 200 OK → 수신자의 받은편지함에 도착 ✅

### 교훈 6
> **문서화된 응답 구조는 오늘 안 맞을 수 있다.** 리서치는 출발점일 뿐, **실물** 을 보고 맞춰라.

---

## 9. 완성 — 전체 파이프라인

최종 동작:

```
1. launchd 가 1분마다 bot.py 실행
2. 저장된 브라우저 세션으로 로그인 유지
3. 내 최근 포스트들 조회
4. 각 포스트의 댓글 조회 (normalized Voyager API)
5. 타겟 필터:
   - top-level 댓글만
   - 내 댓글 아닌 것만
   - 이미 답글 단 댓글 아닌 것만
6. 각 타겟에:
   a) 30-120초 랜덤 딜레이
   b) 답글 POST (Dash contract)
   c) 2xx 확인 → DB 에 mark_seen
   d) 1촌 체크 (MemberRelationship 파싱)
   e) 1촌이면:
      - 60-300초 랜덤 딜레이
      - DM POST
      - DB 에 mark_dm_sent
7. 종료
```

### 스펙
- Python 3.11
- Scrapling 0.4.7 + Patchright
- SQLite (`seen_comments.db`) — 답글 + DM 중복 방지
- macOS launchd — 1분 주기
- 87개 unit test 전부 passing
- LSP diagnostics clean

### 이름 개인화 (`{name}` 치환)
```yaml
sentences:
  - "{name}님 댓글 감사합니다! 🙏"
  - "{name}님 관심 가져주셔서 감사해요 😊"
```

댓글 단 사람이 "Jisang Han"이면:
- `"Jisang Han님 댓글 감사합니다! 🙏"`

이름 추출 위해 별도 API 호출 **전혀 안 함**. 댓글 조회 응답에 이미 들어있던 `commenterForDashConversion.title.text` 를 재사용.

---

## 10. 배운 것들 (summary)

### 엔지니어링 교훈
1. **공식 API = 안전하다 ≠ 모두에게 열려있다**
2. **리서치는 출발점. 실물은 DevTools 에서만 정답 나옴**
3. **"parent"/"thread"/"object" 같은 용어는 서비스마다 의미가 다르다**
4. **plan → review → implement** 사이클. 특히 review는 혼자 못 보는 구멍을 잡아준다
5. **에러 메시지가 부정확할 때 → 더 세밀한 로그 먼저 추가** (우리도 "POST 성공인 줄 알았는데 사실 fail" 상황 여러 번)
6. **POST 와 CONFIRM 은 다른 문제.** POST 가 성공해도 CONFIRM 방식이 틀리면 false negative
7. **Rate limit 은 endpoint마다 다르다.** "별로 안 쓰이는" 엔드포인트가 먼저 막힘

### 프로덕트 교훈
1. **"DM 자동화"** 는 자동화 난이도보다 **LinkedIn ToS 리스크** 가 더 크다
2. **1촌 한정** 이라는 제약이 리스크 줄이는 핵심 설계
3. **하루 수량 제한** 은 필수 (기본은 무제한이어도, 언제든 제한 가능한 구조)
4. **중복 방지 DB** 없이는 절대 돌리면 안 됨 (같은 사람에게 여러 번 DM = 확실한 ban)

### 메타 교훈
1. **AI 플랜 리뷰어 (Momus 등)** 가 실제로 구멍을 잡아줬다
2. **장기적으로 Ralph Loop 같은 지속 실행 방식** 이 반복 iteration 의 모멘텀을 유지함
3. **"DevTools 캡처 한 번"** 이 며칠의 추측 작업을 대체

---

## 11. 다음 단계 (곧 추가할 기능)

### "일촌 요청 자동 승인 후 DM" 전략
현재 제약: 1촌이 아니면 DM 못 보냄.  
해결: 글 말미에 **"1촌 신청하고 댓글 남겨주세요"** 라고 유도 → 댓글 단 사람이 1촌 요청도 같이 보냄 → 봇이:

1. DM 시도
2. 실패 (비-1촌) 감지
3. **받은 초대 목록 조회** (`/relationships/invitationViews?q=receivedInvitation`)
4. 해당 사람의 초대 찾기
5. **자동 승인** (`/relationships/invitations/{id}` POST)
6. DM 재시도 → 이번엔 성공

이거 구현하면 **참여율 + 답글률 + 전환율** 다 올라감. 이미 설계 완료, 구현만 남음.

---

## 12. 마무리

뭐가 단순한 "자동 답글 봇" 인 줄 알았는데 알고 보니:

- LinkedIn 공식 API 의 정치적 맥락
- Normalized Voyager API 의 스키마 학습
- 2026년 기준 reverse-engineered 엔드포인트 생태계
- 스텔스 브라우저 자동화의 실제 운영
- LinkedIn 의 rate limiting / 탐지 메커니즘

**한 줄 요구사항은 항상 50줄짜리 스펙**이었고, 거기 담긴 **며칠의 삽질은 생각보다 많은 걸 가르쳐줬다.**

그리고 마지막에 `slit slit님 댓글 감사드립니다! 🙏` 이 메시지가 **실제로 상대방 받은편지함에 딱** 도착했을 때 — 그 한 줄의 무게는 정말 각별했다.

---

### 기술 스택 요약

| 영역 | 도구 |
|------|------|
| 언어 | Python 3.11 |
| 브라우저 자동화 | Scrapling (Patchright 기반) |
| 데이터 검증 | Pydantic v2 |
| 로컬 DB | SQLite (stdlib) |
| 스케줄러 | macOS launchd |
| 테스트 | pytest (87 passing) |
| 플랜 리뷰 | Momus (AI) |
| 세션 관리 | StealthySession `user_data_dir` |

### 소스 구조
```
bot/
├── auth.py              # Login, cookie extraction, own URN
├── runtime_session.py   # 1 StealthySession per run
├── voyager.py           # HTTP transport (browser-context fetch)
├── posts.py             # Post discovery
├── comments.py          # Comment fetch + filter
├── replies.py           # Reply POST (Dash contract)
├── messaging.py         # DM send
├── connections.py       # 1st-degree check
├── personalization.py   # {name} placeholder
├── db.py                # seen_comments + dm_sent
├── config.py            # DMConfig + RepliesConfig
├── orchestrator.py      # Main loop
└── logging_config.py    # Rotating logs
```

### 통계
- 작업 기간: 며칠 (정확한 시간 산정 불가 - iteration 이 많아서)
- 플랜 리뷰 (Momus) 에서 reject → 수정 → approve: 3회
- 답글 POST 실패 → 성공까지 500 에러 반복: **7회**
- DevTools 캡처: **2회** (답글, DM) — 이 두 번이 며칠을 줄였다
- 최종 테스트: **87개 passing, 0 diagnostics**

---

---

# 📖 Part 2 — "됐다" 다음에 터진 일들

> Part 1 을 썼을 때는 "이제 다 됐다" 싶었는데
> 실제 운영을 시작하니 **새로운 문제들이 줄줄이** 튀어나왔다.

---

## 13. 유령 답글 사건 — "분명 썼다고 하는데 왜 답글이 안 보여?"

Part 1 마지막에 봇이 잘 돌아가는 걸 확인했다. 그런데 실제로 스케줄 돌려보니 이상한 로그가 나왔다.

```text
[ERROR] Reply creation could not be confirmed for comment XXX
```

"생성 확인 못 했다" 는데 — LinkedIn 화면에 **답글이 이미 떡하니 달려 있음.**

### 원인
우리 `_confirm_reply_created` 로직은:
1. 답글 POST 하고
2. 다시 `fetch_comments()` 로 댓글 목록 조회
3. 거기서 내 답글이 있는지 찾음

근데 `/feed/comments` 는 **top-level 댓글만** 반환한다. **답글은 nested reply 로 따로 들어있는 곳**을 조회해야 나옴. 내가 잘못된 곳에서 찾고 있었던 것.

### 두 번째 단서
Dash POST 응답에 `x-restli-id` 헤더를 반환한다는 사실을 알게 됐다. 이게 서버가 "이 URN 으로 생성함" 이라고 확정해주는 신호. 근데 Dash 엔드포인트 (`/voyagerSocialDashNormComments`) 는 이 헤더를 **안 반환**.

대신 응답 body 에 `data`, `included`, `meta` 3개 키가 들어있음 — normalized 성공 응답의 전형적 형태.

### 수정
```python
if isinstance(response_data, dict) and not response_data.get("__error"):
    dash_created = bool(response_data.get("data")) or bool(response_data.get("included"))
    if dash_created:
        mark_seen(...)
        return  # 재조회 안 함, 2xx envelope 자체를 신뢰
```

"재조회로 검증" 을 **포기하고** 2xx 응답 자체를 성공으로 인정. 덜 paranoid 하지만 실제로는 더 정확함.

### 교훈 13
> **"완벽한 검증"** 을 고집하다가 **"멀쩡한 결과를 false failure 로 오판"** 하는 경우가 있다. 서버가 2xx 로 "됐다" 고 하면 **믿어라.**

---

## 14. 1촌 신청 자동 수락이라는 꿈 — 그리고 첫 번째 함정

"1촌이 아니면 DM 못 간다" 는 제약이 답답했다. 사용자가 아이디어를 냈다:

> "글 말미에 '1촌 신청하고 댓글 남겨주세요' 라고 써두면, 실제로 사람들이 1촌 신청 + 댓글 둘 다 보냄. 봇이 알아서 신청 수락하고 DM 보내면 전환율 훨씬 높아짐."

완벽한 시나리오. 구현 시작.

### 리서치 결과 vs 실제
리서치는 깔끔하게 알려줬다:

```
GET /voyager/api/relationships/invitationViews?q=receivedInvitation&start=0&count=50
→ 받은 초대 전체 목록

POST /voyager/api/relationships/invitations/{invitationId}?action=accept
body: {"invitationId", "invitationSharedSecret", "isGenericInvitation": false}
→ 수락
```

코드 짜서 실제 호출:

```text
total: 0
```

**"받은 초대가 0개"** 라고 LinkedIn 이 명시적으로 답함. 근데 사용자는 분명 "한 명 신청 보낸 사람 있다" 고 함.

### 미스터리
- UI 에는 "Pending Invitation" 표시가 분명 보임
- API 는 0 반환

한참 뒤져보다가 발견: **초대 정보는 초대 목록 엔드포인트가 아니라 "댓글 단 사람의 프로필 조회 응답"에 박혀있음.**

### "초대가 프로필 안에 있다고?"
새 commenter 의 프로필을 raw 로 까 봤다:

```json
{
  "included": [
    {
      "$type": "com.linkedin.voyager.dash.relationships.MemberRelationship",
      "memberRelationshipUnion": {
        "noConnection": {
          "memberDistance": "OUT_OF_NETWORK",
          "invitationUnion": {
            "*invitation": "urn:li:fsd_invitation:7451670452932059136"
          }
        }
      }
    },
    {
      "$type": "com.linkedin.voyager.dash.relationships.invitation.Invitation",
      "entityUrn": "urn:li:fsd_invitation:7451670452932059136",
      "sharedSecret": "ro1sHSxA",
      "invitationType": "RECEIVED",
      ...
    }
  ]
}
```

**찾았다.**
- `memberRelationshipUnion.noConnection.invitationUnion.*invitation` → invitation URN 참조
- `included` 배열 안에 실제 Invitation 객체 (with `sharedSecret`)

즉, **1촌 여부 확인 + 초대 정보 확보** 를 **한 번의 프로필 조회로 같이 해결** 할 수 있다는 것. 별도 list 호출 필요 없음.

### 교훈 14
> **LinkedIn 은 같은 데이터를 여러 경로로 나눠 반환한다.** 공식 리버스엔지니어링 자료는 "이 엔드포인트 쓰면 돼" 라고 하지만, 실물은 **전혀 다른 곳에 묻혀 있을 수 있다.**

---

## 15. URN Prefix 한 글자 — 또 한 번의 작은 지옥

Invitation 수락 로직 완성해서 돌렸다:

```text
WARNING: Refusing to accept invitation with missing fields: 
         entityUrn='urn:li:fsd_invitation:7451670452932059136' has_secret=True
```

URN 있음. secret 있음. 근데 거부. 왜?

```python
if not entity_urn.startswith("urn:li:invitation:"):
    return False
```

응. 리서치 자료 기준으로 `urn:li:invitation:` 로 필터링. 근데 **실제 반환값은 `urn:li:fsd_invitation:`** (Dash prefix `fsd_` 붙음).

수정:

```python
is_valid = entity_urn.startswith("urn:li:invitation:") or entity_urn.startswith("urn:li:fsd_invitation:")
```

바로 성공. `accept: True`, 그리고 바로 뒤에 `1촌 check AFTER accept: True` — 5초 만에 1촌 관계로 승격.

### 교훈 15
> **"Legacy" prefix 와 "Dash" prefix 는 URN 생태계 전체에서 계속 충돌한다.** 한 엔드포인트는 `urn:li:invitation:` 반환, 다른 엔드포인트는 `urn:li:fsd_invitation:` 반환. 파서는 **양쪽 다 받아들이도록** 짜는 게 안전하다.

---

## 16. "JSup undefined님 감사합니다"

자동 답글이 실제로 달렸다:

```
"JSup undefined님 관심 가져주셔서 감사해요 😊"
```

**"undefined"** 가 이름에 문자 그대로 들어감. 상대방 프로필의 `lastName` 필드가 실제로 문자열 `"undefined"` 로 직렬화되어 들어옴 — LinkedIn 프론트엔드의 JavaScript 직렬화 버그로 추정.

### 수정
```python
_GARBAGE_NAME_TOKENS = ("undefined", "null", "none", "nil")

def _sanitize_name(name: str) -> str:
    parts = [p for p in name.split() if p.lower() not in _GARBAGE_NAME_TOKENS]
    return " ".join(parts).strip()
```

"JSup undefined" → "JSup" 로 자동 정제.

### 교훈 16
> **외부 API 응답을 사용자에게 그대로 노출하지 마라.** LinkedIn 자기들도 가끔 `"undefined"` 같은 쓰레기 문자열을 정식 필드 값으로 반환한다.

---

## 17. 포스트마다 다른 템플릿 — "런칭 글이랑 일상 글은 답글이 달라야지"

사용자가 지적했다:

> "근데 포스트마다 자동화를 설정해야 될 수도 있는 거 아니야? 신제품 런칭 글이랑 채용 글에 같은 답글 달면 이상하잖아."

맞는 말. 원래는 **전역 3개 문장** 에서 랜덤 선택이었다. 포스트 성격이 달라도 항상 같은 답글.

### 설계 옵션 4가지
1. **Activity URN 직접 매핑** — 포스트마다 config 에 URN 추가 (명시적이지만 번거로움)
2. **키워드 자동 매칭** — 포스트 본문 읽어서 키워드 매칭 (편하지만 오분류 위험)
3. **CLI 로 바인딩** — `python bot.py bind <URN> <template>` (직관적이지만 매번 실행 필요)
4. **하이브리드** — 기본 + 키워드 자동 + 특수한 경우만 URN 수동 지정

**4번 채택.**

### 구현

```yaml
templates:
  product_launch:
    keywords: ["런칭", "출시", "launch"]
    sentences: ["{name}님 런칭 관심 감사합니다! 자료 DM 드릴게요 🙏"]
    dm_messages: ["{name}님, 런칭 자료 공유드릴게요 📎"]
  
  recruiting:
    keywords: ["채용", "hiring"]
    sentences: ["{name}님 지원 관심 감사합니다!"]

post_bindings:
  "urn:li:activity:7429135022256791552": product_launch  # 수동 override
```

### 매칭 순서
1. `post_bindings[activity_urn]` 있으면 → 그 템플릿 (최우선)
2. 포스트 본문에 어떤 템플릿의 `keywords` 가 있으면 → 그 템플릿
3. 아무것도 안 맞으면 → 전역 `sentences` / `dm.messages`

### 빈 필드 = root fallback
템플릿에 `sentences` 는 없고 `dm_messages` 만 있으면 → 답글은 전역, DM 만 템플릿 고유. Partial override 가능.

### 부수 효과: post body 추출
포스트 조회할 때 `commentary.text.text` 도 같이 파싱해서 `Post.body_text` 필드에 저장. 키워드 매칭에 씀. 추가 API 호출 없음.

### 교훈 17
> **"한 종류" 로 시작한 기능도 결국 "종류별 분기" 가 필요해진다.** 애초에 템플릿 시스템을 유연하게 짜두면 나중에 덜 아프다. 그리고 **데이터를 이미 가져오고 있으면 재사용해라** (post body 는 조회 응답에 이미 있었음).

---

## 18. 1촌 체크가 rate-limit 맞는 날

Invitation 자동 수락 플로우가 다 되고 돌렸더니 이번엔:

```text
networkinfo fetch failed for urn:li:person:XXX: Rate limited. Suggested wait: 3600s
```

모든 commenter 마다 1촌 체크 호출 → **`/identity/profiles/{id}/networkinfo` 엔드포인트가 403 rate limit.**

즉 DM 단계에서 항상 "1촌 아님" 판단 → DM 아예 못 보냄.

### 대안 조사
리서치 결과 5개 엔드포인트 후보:
1. `/identity/dash/profiles?q=memberIdentity&decorationId=TopCardSupplementary-175` — **프로필 페이지 열 때마다 호출됨 → rate limit 낮음**
2. GraphQL `voyagerIdentityDashProfiles.*` — 같은 데이터 다른 경로
3. GraphQL `voyagerSearchDashClusters.*` — 검색 API (가장 자주 쓰임)
4. GraphQL `voyagerIdentityDashProfileCards.*` — 프로필 카드
5. `/identity/dash/profiles/{URN}?decorationId=FullProfile-76` — 직접 조회

### 1번 선택 → 또 하나의 발견
1번으로 바꾸고 보니 **응답 구조가 또 리서치와 달랐다.**

리서치: `memberDistance.value == "DISTANCE_1"` 이 1촌 신호  
실물: `memberDistance` 필드 자체가 없고, 대신:

```json
"$type": "com.linkedin.voyager.dash.relationships.MemberRelationship",
"memberRelationshipUnion": {
  "noConnection": {"memberDistance": "OUT_OF_NETWORK"}
  // 또는 connection: {...} 이면 1촌
}
```

즉 1촌 판별은 `MemberRelationship` 타입의 `memberRelationshipUnion` 에 `connection` / `*connection` 이 있느냐 여부로 결정.

### 그리고 → 14장과 연결
17장의 **"Invitation 도 이 응답 안에 있다"** 발견이 바로 이 조사 과정에서 나왔다. 1촌 체크하는 응답 = invitation 이 들어있는 응답. **한 번의 호출로 둘 다 처리.**

### 교훈 18
> **API endpoint 교체 = 응답 파서 재작업 시작.** 리서치 자료만 믿지 말고 **실물 raw 를 까보라.** 그 과정에서 **보너스 정보** 도 발견된다.

---

## 19. 딜레이 논쟁 — "왜 한 번 돌리는 데 5분 걸려?"

사용자 질문:

> "봇이 한 번 돌릴 때 왜 이렇게 오래 걸려? 뭐 하고 있는 거야?"

분석:

| 단계 | 시간 |
|------|------|
| 브라우저 세션 부팅 | 20-30s |
| **답글 딜레이** (의도적) | **30-120s 랜덤** |
| 답글 POST + 확인 | 2-5s |
| 1촌 체크 | 1-2s |
| **DM 딜레이** (의도적) | **60-300s 랜덤** |
| DM POST | 2-3s |

한 댓글당 **2~8분**. 댓글 10개면 한 사이클 1시간+.

### 왜 딜레이를 넣었나
처음 설계할 때 **"봇 티 나지 않게, 사람처럼 보이게"** 라는 리서치 기반 가정으로 넣었다.

### 사용자 지적
> "근데 밴 거의 안 먹어. 이거 진짜 필요해?"

### 정직한 분석
개인 계정 + 저볼륨 + 본인 IP + 본인 디바이스 조합에서는:
- 답글 30-120s 딜레이 → **효과 거의 없음.** 실제 사람도 댓글 보자마자 답글 씀.
- DM 60-300s 딜레이 → **살짝은 의미 있지만 과함.** 하루 5명 DM 하는 수준이면 5-20s 면 충분.

### 결정
**전부 0 으로.**

```yaml
reply_delay_seconds_min: 0
reply_delay_seconds_max: 0
dm:
  delay_seconds_min: 0
  delay_seconds_max: 0
```

(근데 pydantic validator 가 `min < max` 강제해서 `min == max` 허용하도록 완화 필요.)

한 댓글당 실행 시간: **2-8분 → ~30-60초** (대부분 브라우저 부팅 시간).

### 부수적: DM 하루 한도 기본값
무제한은 위험. **기본 30개/일** 로 설정. 필요하면 `config set dm.max_per_day` 로 바꿀 수 있게.

### 교훈 19
> **"안전을 위한 설계" 가 반드시 실용적인 건 아니다.** 리서치 기반 안전 마진이 실제 운영 환경과 맞지 않을 수 있다. **측정하고 조정해라.** 필요 없으면 빼라.

---

## 20. "근본적으로 뜯어고쳐야 해 Windows에서는?"

사용자 질문:
> "Windows 에서도 돌아가게 하려면 근본적으로 뜯어고쳐야 해?"

**대답: 아니. 4가지만 고치면 됨.**

| 컴포넌트 | 현재 | Windows 이슈 |
|---------|------|--------------|
| `bot/lockfile.py` | `fcntl.flock` | Windows 에 fcntl 없음 → `filelock` 라이브러리로 교체 |
| `launchd` | macOS 전용 | Windows Task Scheduler 추가 |
| `bash launchd/install.sh` | shell script | `.ps1` 추가 or Python 자동 설치 |
| 경로 하드코딩 | 대부분 pathlib | 몇 군데 `/` 문자 확인 필요 |

나머지는 다 cross-platform:
- Scrapling / Patchright: ✅
- Typer / questionary / Rich: ✅
- SQLite, Pydantic, PyYAML: ✅
- `pathlib`: ✅
- `[project.scripts]` → Windows 에서 `linkedin-autoreply.exe` 자동 생성

### 설계 변경
`bot/scheduler/` 패키지 신설:
```
bot/scheduler/
├── __init__.py     # 플랫폼 감지 → 팩토리
├── base.py         # BaseScheduler ABC
├── macos.py        # launchd
└── windows.py      # Task Scheduler
```

CLI `linkedin-autoreply start/stop/status` 가 `sys.platform` 보고 적절한 구현 선택.

### 교훈 20
> **크로스 플랫폼 지원은 "나중에 대응" 하면 아파진다.** 애초부터 플랫폼 의존 코드를 **한 곳에 격리** 해두면 나중에 추가가 쉽다.

---

## 21. "NPM 패키지처럼 포장하자" — CLI 로의 마지막 변태

"git clone → python setup.py → bash install.sh" 의 여정은 잘 돌아가지만 **user-facing 제품** 같지 않았다.

사용자 요구:
1. **온보딩** 에서 계정 연결 + 설정 선택
2. **설정 수정 커맨드** (매번 yaml 직접 편집 말고)
3. **NPM 패키지 느낌** — 한 줄 설치 + 한 줄 실행

### Python 의 동등한 패턴
`[project.scripts]` in `pyproject.toml` → `linkedin-autoreply` 바이너리 자동 생성.

```toml
[project.scripts]
linkedin-autoreply = "bot.cli:app"
```

### 최종 CLI 설계 (계획)
```bash
linkedin-autoreply init              # 대화형 onboarding wizard
linkedin-autoreply run [--dry-run]   # 수동 1회 실행
linkedin-autoreply setup             # 재로그인만
linkedin-autoreply config show       # 현재 설정 출력
linkedin-autoreply config set dm.max_per_day 50
linkedin-autoreply config edit       # $EDITOR 로 열기
linkedin-autoreply config wizard     # 설정 부분만 다시
linkedin-autoreply config reset      # 기본값 복원
linkedin-autoreply start             # 플랫폼별 스케줄러 설치
linkedin-autoreply stop              # 스케줄러 unload
linkedin-autoreply uninstall         # 완전 제거
linkedin-autoreply status            # 상태 + 로그 snippet
linkedin-autoreply logs -n 50        # 로그 tail
```

### 기술 스택
- **Typer** (git-like subcommand, no argparse boilerplate)
- **questionary** (화살표 선택 + 검증)
- **rich** (컬러 출력)
- 플랜만 쓰고 승인받음. Momus [OKAY]. 구현은 후속.

### 교훈 21
> **기능이 완성된 것과 "제품" 이 된 것은 다르다.** "설치 → 설정 → 실행" 이 **한 줄씩** 으로 축약되지 않으면 다른 사람이 쓰기 어렵다.

---

## 📊 Part 2 누적 통계

| 항목 | 수치 |
|------|------|
| 해결된 비자명 버그 | **6 개** (재조회 confirm, URN prefix, undefined 이름, networkinfo rate limit, invitation location, 딜레이 과잉) |
| 추가된 피처 | **4 개** (per-post templates, invitation auto-accept, DM daily cap, name sanitization) |
| 테스트 수 변화 | 87 → **118 passing** |
| 새 플랜 (Momus 통과) | **3 개** (reply hardening, DM + invitation, CLI + onboarding) |
| 새 모듈 | `bot/templates.py`, `bot/invitations.py`, (예정: `bot/cli.py`, `bot/scheduler/`) |
| DevTools 캡처 | 누적 **3 번** (답글, DM, invitation payload) |

---

## 🔑 Part 2 에서 깨달은 7가지

1. **"완벽한 검증" 이 항상 더 정확한 건 아니다** — 서버가 2xx 라고 하면 믿어라
2. **같은 데이터가 여러 경로로 반환된다** — 별도 호출보다 **응답 한 번 잘 파싱** 이 효율적
3. **Legacy vs Dash URN prefix 충돌은 계속 발생한다** — 파서는 양쪽 다 받아라
4. **API 응답에 문자열 "undefined" 가 정식 값으로 올 수 있다** — 사용자 노출 전 sanitize
5. **"한 종류로 시작한 기능" 은 결국 분기가 필요해진다** — 유연하게 시작
6. **리서치 기반 안전 마진과 실운영 마진은 다르다** — 측정하고 조정
7. **"기능 완성" 과 "제품" 은 다르다** — CLI / onboarding 은 나중 아닌 필수

---

## 🗺️ 현재 상태 & 남은 것

### ✅ 구현 완료 + 라이브 검증됨
- 댓글 감지 → 답글 (Dash contract, 2xx envelope confirm)
- `{name}님` 이름 개인화 (+ "undefined" 정제)
- 1촌 체크 (Dash profile endpoint, `memberRelationshipUnion` 파싱)
- DM 전송 (profile URN 변환, exact DevTools-captured payload)
- **Invitation 자동 수락** (profile 응답에서 추출, `fsd_invitation` prefix 지원)
- Per-post 템플릿 (URN binding + keyword match + root fallback)
- DM 하루 한도 (기본 30)
- 중복 방지 (`seen_comments` + `dm_sent` DB)
- launchd 1분 주기 스케줄

### 📋 플랜만 완료, 구현 대기 중
- **CLI + onboarding wizard** (`.sisyphus/plans/cli-and-onboarding.md`, Momus approved)
  - `linkedin-autoreply init / run / setup / config / start / stop / status / logs`
  - Typer + questionary + rich
  - Step-based wizard 패턴

### 🧪 설계만 논의됨
- **Windows 지원** (Task Scheduler + filelock 라이브러리 + scheduler abstraction)
  - 근본 rewrite 아님, 4군데만 수정
  - CLI 플랜에 Task 6 으로 합치기 추천

---

## 기술 스택 (Part 2 기준)

| 영역 | 도구 |
|------|------|
| 언어 | Python 3.11 |
| 브라우저 자동화 | Scrapling (Patchright) |
| 데이터 검증 | Pydantic v2 |
| 로컬 DB | SQLite (stdlib) |
| 스케줄러 | macOS launchd (Windows 지원 계획됨) |
| CLI (계획) | Typer + questionary + rich |
| 테스트 | pytest (**118 passing**) |
| 플랜 리뷰 | Momus (AI) |
| 세션 관리 | StealthySession `user_data_dir` |
| 배포 | GitHub clone + `pip install -e .` |

## 소스 구조 (현재)
```
bot/
├── auth.py              # Login, cookie extraction, own URN
├── runtime_session.py   # 1 StealthySession per run, extra headers
├── voyager.py           # HTTP transport (browser-context fetch)
├── posts.py             # Post discovery (+ body_text extraction)
├── comments.py          # Comment fetch + filter
├── replies.py           # Reply POST + Dash envelope confirm
├── messaging.py         # DM send (exact captured contract)
├── connections.py       # 1st-degree check + invitation extraction
├── invitations.py       # list / find / accept
├── templates.py         # select_template (URN → keyword → root)
├── personalization.py   # {name} placeholder + name sanitize
├── db.py                # seen_comments + dm_sent
├── config.py            # RepliesConfig + DMConfig + TemplateConfig
├── orchestrator.py      # Main loop (reply → DM → invitation retry)
├── killswitch.py        # enabled: false guard
├── lockfile.py          # fcntl (will move to filelock lib for Windows)
├── logging_config.py    # Rotating logs
├── rate_limit.py        # 429/999/challenge detection
├── urn.py               # URN parsers + person_to_fsd_profile
└── browser_fallback.py  # (unused in practice — Dash path works)
```

---

**Part 2 의 본질**: Part 1 끝낸 뒤 **"됐다"** 는 순간부터 **실전** 이 시작된다. 제품은 마지막 10% 가 전체 여정의 절반이다.

"댓글에 답글 하나 다는 게 왜 이렇게 어려워?" 라는 원초적 질문 앞에서, **LinkedIn 의 내부 생태계 전체** 를 조금씩 벗겨내는 과정이었다. 그 과정에서 얻은 건 **한 줄의 자동 답글** 이 아니라, **"실물을 존중하는 태도"** 였다.


**P.S.** 이 글에서 공유한 엔드포인트/payload 는 오늘 기준 유효하지만, LinkedIn 은 수시로 바뀐다. 만약 이 구조로 직접 구현할 사람이 있다면: **DevTools 캡처부터 하시길.**
