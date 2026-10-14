package kr.co.dhsemi.tlog.mapper;

import java.util.List;

import kr.co.dhsemi.tlog.vo.LotYieldVO;

public interface LotYieldMapper {

    int deleteLotYield(String workDt);

    List<LotYieldVO> selectYieldBase(String workDt);

    int insertLotYield(LotYieldVO vo);

    int countLotYield(String workDt);

    Long sumPassQty(String workDt);

    List<LotYieldVO> selectAlertList(String workDt);
}
