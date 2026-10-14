#!/bin/bash
#======================================================================
# TLOG 배치 빌드
#   결과물 : target/tlog-batch.jar , target/lib/*.jar
#   배포   : target 디렉토리를 운영서버 /app/tlog/batch 로 복사 (수동)
#======================================================================
cd "$(dirname "$0")" || exit 1

MVN=mvn
if [ -x /opt/maven/bin/mvn ]; then
    MVN=/opt/maven/bin/mvn
fi

$MVN -q -B package
RC=$?
if [ $RC -ne 0 ]; then
    echo "[BUILD] FAIL rc=$RC"
    exit $RC
fi
echo "[BUILD] OK : target/tlog-batch.jar"
exit 0
