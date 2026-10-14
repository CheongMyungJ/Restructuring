package kr.co.dhsemi.tlog.yield;

import java.math.BigDecimal;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.core.StepContribution;
import org.springframework.batch.core.scope.context.ChunkContext;
import org.springframework.batch.core.step.tasklet.Tasklet;
import org.springframework.batch.repeat.RepeatStatus;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.load.ProductCache;
import kr.co.dhsemi.tlog.mapper.LotYieldMapper;
import kr.co.dhsemi.tlog.vo.LotYieldVO;
import kr.co.dhsemi.tlog.vo.ProductInfo;

/**
 * LOT 수율 집계 (TB_DEVICE_BIN -> TB_LOT_YIELD)
 *
 * 해당 근무일 데이터 삭제 후 재집계 (재실행 가능)
 */
public class YieldSummaryTasklet implements Tasklet {

    private static final Logger logger = LoggerFactory.getLogger(YieldSummaryTasklet.class);

    @Autowired
    private LotYieldMapper lotYieldMapper;

    @Autowired
    private ProductCache productCache;

    private String workDt;

    public void setWorkDt(String workDt) {
        this.workDt = workDt;
    }

    public RepeatStatus execute(StepContribution contribution, ChunkContext chunkContext) throws Exception {
        int delCnt = lotYieldMapper.deleteLotYield(workDt);
        logger.info("기존 수율 삭제 : " + delCnt + "건 (" + workDt + ")");

        List<LotYieldVO> list = lotYieldMapper.selectYieldBase(workDt);
        int alertCnt = 0;
        for (LotYieldVO vo : list) {
            vo.setWorkDt(workDt);

            // 수율(%) = 양품수 / 투입수 * 100 , 소수점 셋째자리에서 반올림
            BigDecimal yield = new BigDecimal(vo.getPassQty() * 100)
                    .divide(new BigDecimal(vo.getInQty()), 2, BigDecimal.ROUND_DOWN);
            vo.setYieldPct(yield);

            // 경보 : 제품별 기준수율 미달 (표본 10개 미만은 제외)
            ProductInfo prod = productCache.get(vo.getProdCd());
            if (prod != null && prod.getAlertYield() != null && vo.getInQty() >= 10
                    && yield.compareTo(prod.getAlertYield()) < 0) {
                vo.setAlertYn(Constants.YES);
                alertCnt++;
            } else {
                vo.setAlertYn(Constants.NO);
            }
            lotYieldMapper.insertLotYield(vo);
            contribution.incrementWriteCount(1);
        }
        logger.info("수율 집계 : " + list.size() + " LOT, 경보 " + alertCnt + "건");
        return RepeatStatus.FINISHED;
    }
}
