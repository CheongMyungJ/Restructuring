package kr.co.dhsemi.tlog.judge;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.apache.commons.lang.StringUtils;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.item.ItemProcessor;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.mapper.DeviceBinMapper;
import kr.co.dhsemi.tlog.mapper.TestResultMapper;
import kr.co.dhsemi.tlog.vo.BinRuleVO;
import kr.co.dhsemi.tlog.vo.DeviceBinVO;
import kr.co.dhsemi.tlog.vo.TestResultVO;

/**
 * 디바이스(시리얼) 별 최종 BIN 판정
 *
 * <pre>
 * 판정 순서
 *  1. 이전 근무일에 폐기(BIN9) 판정 이력 있으면 BIN9 유지
 *  2. 유효 시도 중 ABORT 있으면 BIN8
 *  3. (임시) 엔터프라이즈 제품 불량블록 과다 BIN5
 *  4. BIN 룰 (우선순위 순, 첫번째 매칭)
 *  5. 전부 PASS 면 BIN1, 아니면 BIN7
 *
 * 2015.10 kimjh  최초작성
 * 2016.01 parksy 재테스트 횟수 제한 반영
 * 2016.03 parksy 엔터프라이즈 예외처리 (고객 클레임)
 * 2016.08 choimh ES 샘플 수율제외
 * </pre>
 */
public class BinJudgeProcessor implements ItemProcessor<String, DeviceBinVO> {

    private static final Logger logger = LoggerFactory.getLogger(BinJudgeProcessor.class);

    /** STEP 별 인정 시도 횟수 (공정기술팀 협의 2016.01) */
    private static final int MAX_RETEST = 3;

    @Autowired
    private TestResultMapper testResultMapper;

    @Autowired
    private DeviceBinMapper deviceBinMapper;

    @Autowired
    private BinRuleCache binRuleCache;

    private String workDt;

    public void setWorkDt(String workDt) {
        this.workDt = workDt;
    }

    public DeviceBinVO process(String serial) throws Exception {
        List<TestResultVO> list = testResultMapper.selectAttemptList(serial, workDt);
        if (list == null || list.size() == 0) {
            return null;
        }

        DeviceBinVO bin = new DeviceBinVO();
        bin.setSerial(serial);
        bin.setWorkDt(workDt);
        bin.setProdCd(list.get(0).getProdCd());
        bin.setLotId(list.get(0).getLotId());
        // 엔지니어링 샘플(ES) 은 판정은 하되 수율 집계에서 제외
        if (serial.startsWith("ES")) {
            bin.setExclYn(Constants.YES);
        } else {
            bin.setExclYn(Constants.NO);
        }

        List<TestResultVO> effList = getEffectiveList(list);

        // 1. 폐기 이력
        if (deviceBinMapper.countPrevScrap(serial, workDt) > 0) {
            bin.setBin(Constants.BIN_SCRAP, Constants.RULE_SCRAP_KEEP);
            return bin;
        }

        // 2. ABORT
        for (TestResultVO r : effList) {
            if (Constants.RSLT_ABORT.equals(r.getResultCd())) {
                bin.setBin(Constants.BIN_ABORT, Constants.RULE_ABORT);
                return bin;
            }
        }

        Map<String, BigDecimal> itemMap = summarize(effList);

        // 3. 임시 조치 2016.03 고객 클레임 대응 - 추후 룰테이블로 이관 예정
        //    엔터프라이즈 제품은 불량블록 20 초과시 무조건 BIN5
        BigDecimal maxBad = itemMap.get("BAD_BLK");
        if (bin.getProdCd() != null && bin.getProdCd().startsWith("E")
                && maxBad != null && maxBad.intValue() > 20) {
            bin.setBin(Constants.BIN_OVR_E, Constants.RULE_OVR_E);
            return bin;
        }

        // 4. BIN 룰
        for (BinRuleVO rule : binRuleCache.getRuleList()) {
            if (!"*".equals(rule.getProdCd()) && !rule.getProdCd().equals(bin.getProdCd())) {
                continue;
            }
            BigDecimal val = itemMap.get(rule.getItemCd());
            if (val == null) {
                continue;
            }
            if (compare(val, rule.getOperCd(), rule.getThreshold())) {
                bin.setBin(rule.getBinNo(), rule.getRuleId());
                return bin;
            }
        }

        // 5. 기본
        boolean allPass = true;
        for (TestResultVO r : effList) {
            if (!Constants.RSLT_PASS.equals(r.getResultCd())) {
                allPass = false;
                break;
            }
        }
        if (allPass) {
            bin.setBin(Constants.BIN_GOOD, Constants.RULE_DEFAULT);
        } else {
            bin.setBin(Constants.BIN_FAIL, Constants.RULE_DEFAULT_F);
        }
        return bin;
    }

    /**
     * STEP 별 유효 시도 추출.
     * 시작일시 순으로 MAX_RETEST 회까지만 인정하고, 인정된 시도 중 마지막 시도를 유효 시도로 본다.
     * (list 는 STEP_CD, START_DTM 순 정렬)
     */
    private List<TestResultVO> getEffectiveList(List<TestResultVO> list) {
        List<TestResultVO> effList = new ArrayList<TestResultVO>();
        String prevStep = null;
        TestResultVO eff = null;
        int tryCnt = 0;
        for (TestResultVO r : list) {
            if (!r.getStepCd().equals(prevStep)) {
                if (eff != null) {
                    effList.add(eff);
                }
                prevStep = r.getStepCd();
                eff = null;
                tryCnt = 0;
            }
            tryCnt++;
            if (tryCnt <= MAX_RETEST) {
                eff = r;
            } else {
                logger.debug("재테스트 횟수 초과 무시 : " + r);
            }
        }
        if (eff != null) {
            effList.add(eff);
        }
        return effList;
    }

    /**
     * 판정 항목 집계 (READ/WRITE 는 최소값, 나머지는 최대값)
     */
    private Map<String, BigDecimal> summarize(List<TestResultVO> effList) {
        Map<String, BigDecimal> map = new HashMap<String, BigDecimal>();
        for (TestResultVO r : effList) {
            putMin(map, "READ_MBPS", r.getReadMbps());
            putMin(map, "WRITE_MBPS", r.getWriteMbps());
            putMax(map, "LAT_US", toDecimal(r.getLatUs()));
            putMax(map, "BAD_BLK", toDecimal(r.getBadBlk()));
            putMax(map, "ECC_CNT", toDecimal(r.getEccCnt()));
            putMax(map, "TEMP_MAX", toDecimal(r.getMaxTempC()));
        }
        return map;
    }

    private void putMin(Map<String, BigDecimal> map, String key, BigDecimal val) {
        if (val == null) {
            return;
        }
        BigDecimal cur = map.get(key);
        if (cur == null || val.compareTo(cur) < 0) {
            map.put(key, val);
        }
    }

    private void putMax(Map<String, BigDecimal> map, String key, BigDecimal val) {
        if (val == null) {
            return;
        }
        BigDecimal cur = map.get(key);
        if (cur == null || val.compareTo(cur) > 0) {
            map.put(key, val);
        }
    }

    private BigDecimal toDecimal(Integer i) {
        if (i == null) {
            return null;
        }
        return new BigDecimal(i.intValue());
    }

    private boolean compare(BigDecimal val, String operCd, BigDecimal threshold) {
        String op = StringUtils.trim(operCd);
        int c = val.compareTo(threshold);
        if ("<".equals(op)) {
            return c < 0;
        } else if ("<=".equals(op)) {
            return c <= 0;
        } else if (">".equals(op)) {
            return c > 0;
        } else if (">=".equals(op)) {
            return c >= 0;
        }
        logger.warn("지원하지 않는 연산자 : " + operCd);
        return false;
    }
}
