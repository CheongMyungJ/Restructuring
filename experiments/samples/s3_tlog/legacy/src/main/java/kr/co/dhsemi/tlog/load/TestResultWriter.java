package kr.co.dhsemi.tlog.load;

import java.util.List;

import org.springframework.batch.item.ItemWriter;
import org.springframework.beans.factory.annotation.Autowired;

import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.mapper.TestResultMapper;
import kr.co.dhsemi.tlog.vo.TestResultVO;

/**
 * TB_TEST_RESULT 저장
 */
public class TestResultWriter implements ItemWriter<TestResultVO> {

    @Autowired
    private TestResultMapper testResultMapper;

    public void write(List<? extends TestResultVO> items) throws Exception {
        for (TestResultVO vo : items) {
            if (Constants.YES.equals(vo.getOverwriteYn())) {
                testResultMapper.updateTestResult(vo);
            } else {
                testResultMapper.insertTestResult(vo);
            }
        }
    }
}
