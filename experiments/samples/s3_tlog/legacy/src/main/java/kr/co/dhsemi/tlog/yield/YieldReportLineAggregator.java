package kr.co.dhsemi.tlog.yield;

import org.apache.commons.lang.StringUtils;
import org.springframework.batch.item.file.transform.LineAggregator;

import kr.co.dhsemi.tlog.common.CommonUtil;
import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.vo.LotYieldVO;

/**
 * MES 수율 리포트 D 레코드 (60 byte, MS949)
 *
 * D(1) + 제품코드(8) + LOT(10) + 제품명(20) + 투입(7) + 양품(7) + 수율(6, 999.99) + 경보(1)
 */
public class YieldReportLineAggregator implements LineAggregator<LotYieldVO> {

    private static final String ENC = Constants.ENC_REPORT;

    public String aggregate(LotYieldVO vo) {
        StringBuffer sb = new StringBuffer();
        sb.append("D");
        sb.append(CommonUtil.rpadByte(vo.getProdCd(), 8, ENC));
        sb.append(CommonUtil.rpadByte(vo.getLotId(), 10, ENC));
        sb.append(CommonUtil.rpadByte(vo.getProdNm(), 20, ENC));   // 한글 2byte, 넘치면 자름
        sb.append(CommonUtil.lpadZero(vo.getInQty(), 7));
        sb.append(CommonUtil.lpadZero(vo.getPassQty(), 7));
        sb.append(StringUtils.leftPad(vo.getYieldPct().setScale(2).toPlainString(), 6, '0'));
        sb.append(CommonUtil.nvl(vo.getAlertYn(), Constants.NO));
        return sb.toString();
    }
}
