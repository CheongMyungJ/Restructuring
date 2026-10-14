package kr.co.dhsemi.tlog.mapper;

import java.util.List;

import org.apache.ibatis.annotations.Param;

import kr.co.dhsemi.tlog.vo.TestResultVO;

public interface TestResultMapper {

    int insertTestResult(TestResultVO vo);

    int updateTestResult(TestResultVO vo);

    int countByKey(TestResultVO vo);

    List<TestResultVO> selectAttemptList(@Param("serial") String serial, @Param("workDt") String workDt);

    int deleteBeforeWorkDt(@Param("cutoffDt") String cutoffDt);
}
