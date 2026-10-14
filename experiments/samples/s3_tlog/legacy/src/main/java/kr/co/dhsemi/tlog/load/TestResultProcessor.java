package kr.co.dhsemi.tlog.load;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.batch.item.ItemProcessor;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.common.TlogRecordException;
import kr.co.dhsemi.tlog.load.parser.AdvRecordParser;
import kr.co.dhsemi.tlog.load.parser.TerRecordParser;
import kr.co.dhsemi.tlog.mapper.TestResultMapper;
import kr.co.dhsemi.tlog.vo.FileInfo;
import kr.co.dhsemi.tlog.vo.RawLineDto;
import kr.co.dhsemi.tlog.vo.TestResultVO;

/**
 * 레코드 파싱/검증/중복체크
 *
 * - 검증 오류 : reject 파일 기록 후 skip (null 리턴)
 * - 중복 (SERIAL+STEP+START_DTM) : 정책에 따라 skip 또는 덮어쓰기
 */
public class TestResultProcessor implements ItemProcessor<RawLineDto, TestResultVO> {

    private static final Logger logger = LoggerFactory.getLogger(TestResultProcessor.class);

    @Autowired
    private LoadContext loadContext;

    @Autowired
    private ProductCache productCache;

    @Autowired
    private RejectFileWriter rejectFileWriter;

    @Autowired
    private TestResultMapper testResultMapper;

    private AdvRecordParser advParser = new AdvRecordParser();
    private TerRecordParser terParser = new TerRecordParser();

    public TestResultVO process(RawLineDto item) throws Exception {
        FileInfo info = item.getFileInfo();
        TestResultVO vo = null;
        try {
            if (info.isAdv()) {
                vo = advParser.parse(item.getLine(), info.getFileNm());
            } else {
                vo = terParser.parse(item.getLine(), info.getFileNm());
            }
            // 제품코드 (미등록/미사용)
            if (!productCache.isUsable(vo.getProdCd())) {
                throw new TlogRecordException(Constants.ERR_PRODUCT, vo.getProdCd());
            }
        } catch (TlogRecordException e) {
            if (logger.isDebugEnabled()) {
                logger.debug("reject " + info.getFileNm() + ":" + item.getLineNo() + " " + e.getMessage());
            }
            rejectFileWriter.write(info, item.getLineNo(), e.getErrCd(), item.getLine());
            info.addRejCnt();
            return null;
        }

        // 중복 체크 (금회 적재분 + 기 적재분)
        if (isDuplicate(vo)) {
            info.addDupCnt();
            if (isOverwrite()) {
                vo.setOverwriteYn(Constants.YES);
                return vo;
            }
            return null;
        }

        loadContext.addLoaded(vo.getKey());
        info.addLoadCnt();
        return vo;
    }

    private boolean isDuplicate(TestResultVO vo) {
        if (loadContext.isLoaded(vo.getKey())) {
            return true;
        }
        return testResultMapper.countByKey(vo) > 0;
    }

    /**
     * 중복건 처리 정책
     *   FIRST : 기존 데이터 유지 (기본)
     *   LAST  : 신규 데이터로 덮어씀
     */
    private boolean isOverwrite() {
        String policy = CommonUtil.getProperty(Constants.DUP_POLICY_KEY, Constants.DUP_FIRST);
        return Constants.DUP_LAST.equalsIgnoreCase(policy);
    }
}
