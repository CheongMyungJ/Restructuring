#!/bin/bash
#======================================================================
# TLOG 배치 실행 스크립트
#
#  usage : run_job.sh <JOB_ID> <BIZ_DATE>
#          JOB_ID   : LOAD | JUDGE | YIELD | PURGE
#          BIZ_DATE : yyyyMMdd
#
#  필요 환경변수
#    TLOG_HOME         : 데이터 루트 (inbox/outbox/reject/archive)
#    TLOG_DB_URL       : JDBC URL
#    TLOG_DB_USER      : (기본 sa)
#    TLOG_DB_PASSWORD  : (기본 없음)
#    JAVA_OPTS         : JVM 옵션
#
#  2015.09 kimjh  최초작성
#  2016.04 parksy PURGE 추가
#  2017.02 leedw  run.ts 파라미터 추가 (동일 일자 재실행 가능하도록)
#======================================================================

if [ $# -lt 2 ]; then
    echo "usage: $0 <LOAD|JUDGE|YIELD|PURGE> <yyyyMMdd>"
    exit 1
fi

JOB_ID=$1
BIZ_DATE=$2

BASE_DIR=$(cd "$(dirname "$0")/.." && pwd)

case "$JOB_ID" in
    LOAD)
        JOB_XML=META-INF/batch/tlogLoadJob.xml
        JOB_NAME=tlogLoadJob
        ;;
    JUDGE)
        JOB_XML=META-INF/batch/binJudgeJob.xml
        JOB_NAME=binJudgeJob
        ;;
    YIELD)
        JOB_XML=META-INF/batch/yieldSummaryJob.xml
        JOB_NAME=yieldSummaryJob
        ;;
    PURGE)
        JOB_XML=META-INF/batch/purgeJob.xml
        JOB_NAME=purgeJob
        ;;
#    ALERT)
#        # 2017.04 YIELD 로 통합됨
#        JOB_XML=META-INF/batch/yieldAlertJob.xml
#        JOB_NAME=yieldAlertJob
#        ;;
    *)
        echo "[ERROR] unknown JOB_ID : $JOB_ID"
        exit 1
        ;;
esac

if ! echo "$BIZ_DATE" | grep -Eq '^[0-9]{8}$'; then
    echo "[ERROR] invalid BIZ_DATE : $BIZ_DATE"
    exit 1
fi

if [ -z "$TLOG_HOME" ]; then
    echo "[ERROR] TLOG_HOME is not set"
    exit 1
fi
if [ -z "$TLOG_DB_URL" ]; then
    echo "[ERROR] TLOG_DB_URL is not set"
    exit 1
fi
export TLOG_DB_USER=${TLOG_DB_USER:-sa}
export TLOG_DB_PASSWORD=${TLOG_DB_PASSWORD:-}

for d in inbox outbox reject archive; do
    if [ ! -d "$TLOG_HOME/$d" ]; then
        mkdir -p "$TLOG_HOME/$d"
    fi
done

if [ -n "$JAVA_HOME" ] && [ -x "$JAVA_HOME/bin/java" ]; then
    JAVA_CMD=$JAVA_HOME/bin/java
else
    JAVA_CMD=java
fi

CLASSPATH="$BASE_DIR/target/tlog-batch.jar:$BASE_DIR/target/lib/*"
#CLASSPATH="$CLASSPATH:/app/tlog/lib/ojdbc6.jar"

RUN_TS=$(date +%s%3N)

echo "[$(date '+%Y-%m-%d %H:%M:%S')] START $JOB_ID $BIZ_DATE (run.ts=$RUN_TS)"

$JAVA_CMD $JAVA_OPTS -cp "$CLASSPATH" \
    org.springframework.batch.core.launch.support.CommandLineJobRunner \
    $JOB_XML $JOB_NAME BIZ_DATE=$BIZ_DATE "run.ts(long)=$RUN_TS"
RC=$?

echo "[$(date '+%Y-%m-%d %H:%M:%S')] END   $JOB_ID $BIZ_DATE rc=$RC"
exit $RC
