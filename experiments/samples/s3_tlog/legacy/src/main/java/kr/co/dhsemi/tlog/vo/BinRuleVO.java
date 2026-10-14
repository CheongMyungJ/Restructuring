package kr.co.dhsemi.tlog.vo;

import java.math.BigDecimal;

/**
 * TB_BIN_RULE
 */
public class BinRuleVO {

    private String ruleId;
    private String prodCd;
    private String itemCd;
    private String operCd;
    private BigDecimal threshold;
    private int binNo;
    private int priority;
    private String useYn;
    private String ruleDesc;

    public String getRuleId() { return ruleId; }
    public void setRuleId(String ruleId) { this.ruleId = ruleId; }
    public String getProdCd() { return prodCd; }
    public void setProdCd(String prodCd) { this.prodCd = prodCd; }
    public String getItemCd() { return itemCd; }
    public void setItemCd(String itemCd) { this.itemCd = itemCd; }
    public String getOperCd() { return operCd; }
    public void setOperCd(String operCd) { this.operCd = operCd; }
    public BigDecimal getThreshold() { return threshold; }
    public void setThreshold(BigDecimal threshold) { this.threshold = threshold; }
    public int getBinNo() { return binNo; }
    public void setBinNo(int binNo) { this.binNo = binNo; }
    public int getPriority() { return priority; }
    public void setPriority(int priority) { this.priority = priority; }
    public String getUseYn() { return useYn; }
    public void setUseYn(String useYn) { this.useYn = useYn; }
    public String getRuleDesc() { return ruleDesc; }
    public void setRuleDesc(String ruleDesc) { this.ruleDesc = ruleDesc; }

    @Override
    public String toString() {
        return ruleId + "[" + prodCd + " " + itemCd + " " + operCd + " " + threshold + " -> BIN" + binNo + " P" + priority + "]";
    }
}
