package kr.co.dhsemi.tlog.vo;

/**
 * TB_DEVICE_BIN
 */
public class DeviceBinVO {

    private String serial;
    private String workDt;
    private String prodCd;
    private String lotId;
    private int binNo;
    private String ruleId;
    private String exclYn = "N";

    public String getSerial() { return serial; }
    public void setSerial(String serial) { this.serial = serial; }
    public String getWorkDt() { return workDt; }
    public void setWorkDt(String workDt) { this.workDt = workDt; }
    public String getProdCd() { return prodCd; }
    public void setProdCd(String prodCd) { this.prodCd = prodCd; }
    public String getLotId() { return lotId; }
    public void setLotId(String lotId) { this.lotId = lotId; }
    public int getBinNo() { return binNo; }
    public void setBinNo(int binNo) { this.binNo = binNo; }
    public String getRuleId() { return ruleId; }
    public void setRuleId(String ruleId) { this.ruleId = ruleId; }
    public String getExclYn() { return exclYn; }
    public void setExclYn(String exclYn) { this.exclYn = exclYn; }

    public void setBin(int binNo, String ruleId) {
        this.binNo = binNo;
        this.ruleId = ruleId;
    }

    @Override
    public String toString() {
        return serial + "/" + workDt + " BIN" + binNo + "(" + ruleId + ")" + ("Y".equals(exclYn) ? " EXCL" : "");
    }
}
