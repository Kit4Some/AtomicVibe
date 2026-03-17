# knowledge.md — Accumulated Knowledge Base

> 자동 갱신 파일. Agent가 직접 수정하지 않고, Execute Engine의 KnowledgeManager가 관리한다.
> Supervisor의 Assigner, Diagnostician, Strategist가 참조한다.

---

## Format

```
### K{번호} | {category} | confidence: {0.0-1.0}
**Problem**: ...
**Solution**: ...
**Context**: ...
**Tags**: tag1, tag2
**Applied**: {적용횟수}/{성공횟수}
**Source**: Phase {N}, Sprint {M}
```

---

## Entries

(프로젝트 진행 시 자동 추가됨)

---

## Usage Guide

Assigner가 Agent 프롬프트에 지식을 주입할 때:
1. 현재 태스크의 tags와 매칭되는 knowledge 검색
2. confidence >= 0.7인 항목만 주입
3. 주입 형식: "이전에 이런 문제가 있었고 이렇게 해결했으니 참고: {solution}"

Diagnostician이 에러 진단 시:
1. error_category + tags로 유사 knowledge 검색
2. 이전 해결법이 있으면 recommendation에 포함
3. 이전 해결법이 실패한 기록도 포함 (반복 방지)
