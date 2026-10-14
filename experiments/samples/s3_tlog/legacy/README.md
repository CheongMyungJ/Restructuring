# TLOG Batch

SSD 양산 테스트(ADV 테스터) 로그 적재 / BIN 판정 / 수율 집계 배치

## 환경

- JDK 1.7
- Spring 4.1, Spring Batch 3.0, MyBatis 3.2
- Oracle 11g (TLOGDB)

## 빌드

```
mvn clean package
```

`target/tlog-batch.jar`, `target/lib/` 를 운영서버 `/app/tlog/batch` 로 복사

## 실행

```
bin/run_job.sh LOAD  20150921
bin/run_job.sh JUDGE 20150921
bin/run_job.sh YIELD 20150921
bin/run_job.sh ALERT 20150921
```

## 디렉토리

| 경로 | 설명 |
|---|---|
| /data/tlog/inbox | 장비 로그 수신 (ADV_*.dat) |
| /data/tlog/outbox | MES 리포트 |
| /data/tlog/reject | 오류 레코드 |
| /data/tlog/archive | 처리 완료 |

## DB

`sql/ddl.sql` 참고 (운영 반영은 DBA 요청)

## 담당

제조IT팀 김정훈
