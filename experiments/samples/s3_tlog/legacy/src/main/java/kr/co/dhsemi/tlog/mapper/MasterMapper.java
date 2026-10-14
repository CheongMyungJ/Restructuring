package kr.co.dhsemi.tlog.mapper;

import java.util.List;

import kr.co.dhsemi.tlog.vo.BinRuleVO;
import kr.co.dhsemi.tlog.vo.ProductInfo;

/**
 * 기준정보 조회 (조회 전용 - 기준정보팀 관리 테이블)
 */
public interface MasterMapper {

    List<ProductInfo> selectProductList();

    List<BinRuleVO> selectBinRuleList();
}
