package kr.co.dhsemi.tlog.judge;

import java.util.ArrayList;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import kr.co.dhsemi.tlog.mapper.MasterMapper;
import kr.co.dhsemi.tlog.vo.BinRuleVO;

/**
 * BIN 룰 캐시 (USE_YN='Y', 적용순서대로 정렬되어 있음)
 */
@Component
public class BinRuleCache {

    private static final Logger logger = LoggerFactory.getLogger(BinRuleCache.class);

    @Autowired
    private MasterMapper masterMapper;

    private List<BinRuleVO> ruleList;

    public synchronized List<BinRuleVO> getRuleList() {
        if (ruleList == null) {
            ruleList = masterMapper.selectBinRuleList();
            if (ruleList == null) {
                ruleList = new ArrayList<BinRuleVO>();
            }
            logger.info("BIN 룰 로딩 : " + ruleList.size() + "건");
            for (BinRuleVO r : ruleList) {
                logger.debug("  " + r);
            }
        }
        return ruleList;
    }
}
