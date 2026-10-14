package kr.co.dhsemi.tlog.vo;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * TB_TEST_RESULT
 */
public class TestResultVO implements Serializable {

    private static final long serialVersionUID = 1L;

    private String serial;
    private String stepCd;
    private String startDtm;
    private String endDtm;
    private String workDt;
    private String lotId;
    private String prodCd;
    private String testerId;
    private String operNm;
    private String resultCd;
    private BigDecimal readMbps;
    private BigDecimal writeMbps;
    private Integer latUs;
    private Integer badBlk;
    private Integer eccCnt;
    private Integer maxTempC;
    private String fwVer;
    private String vendorCd;
    private String srcFileNm;

    /** 중복건 덮어쓰기 여부 (DB 컬럼 아님) */
    private String overwriteYn = "N";

    public String getSerial() { return serial; }
    public void setSerial(String serial) { this.serial = serial; }
    public String getStepCd() { return stepCd; }
    public void setStepCd(String stepCd) { this.stepCd = stepCd; }
    public String getStartDtm() { return startDtm; }
    public void setStartDtm(String startDtm) { this.startDtm = startDtm; }
    public String getEndDtm() { return endDtm; }
    public void setEndDtm(String endDtm) { this.endDtm = endDtm; }
    public String getWorkDt() { return workDt; }
    public void setWorkDt(String workDt) { this.workDt = workDt; }
    public String getLotId() { return lotId; }
    public void setLotId(String lotId) { this.lotId = lotId; }
    public String getProdCd() { return prodCd; }
    public void setProdCd(String prodCd) { this.prodCd = prodCd; }
    public String getTesterId() { return testerId; }
    public void setTesterId(String testerId) { this.testerId = testerId; }
    public String getOperNm() { return operNm; }
    public void setOperNm(String operNm) { this.operNm = operNm; }
    public String getResultCd() { return resultCd; }
    public void setResultCd(String resultCd) { this.resultCd = resultCd; }
    public BigDecimal getReadMbps() { return readMbps; }
    public void setReadMbps(BigDecimal readMbps) { this.readMbps = readMbps; }
    public BigDecimal getWriteMbps() { return writeMbps; }
    public void setWriteMbps(BigDecimal writeMbps) { this.writeMbps = writeMbps; }
    public Integer getLatUs() { return latUs; }
    public void setLatUs(Integer latUs) { this.latUs = latUs; }
    public Integer getBadBlk() { return badBlk; }
    public void setBadBlk(Integer badBlk) { this.badBlk = badBlk; }
    public Integer getEccCnt() { return eccCnt; }
    public void setEccCnt(Integer eccCnt) { this.eccCnt = eccCnt; }
    public Integer getMaxTempC() { return maxTempC; }
    public void setMaxTempC(Integer maxTempC) { this.maxTempC = maxTempC; }
    public String getFwVer() { return fwVer; }
    public void setFwVer(String fwVer) { this.fwVer = fwVer; }
    public String getVendorCd() { return vendorCd; }
    public void setVendorCd(String vendorCd) { this.vendorCd = vendorCd; }
    public String getSrcFileNm() { return srcFileNm; }
    public void setSrcFileNm(String srcFileNm) { this.srcFileNm = srcFileNm; }
    public String getOverwriteYn() { return overwriteYn; }
    public void setOverwriteYn(String overwriteYn) { this.overwriteYn = overwriteYn; }

    public String getKey() {
        return serial + "|" + stepCd + "|" + startDtm;
    }

    @Override
    public String toString() {
        return "TestResultVO[" + serial + "," + stepCd + "," + startDtm + "," + resultCd + "," + srcFileNm + "]";
    }
}
