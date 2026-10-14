package kr.co.dhsemi.tlog.vo;

import java.math.BigDecimal;

/**
 * TB_LOT_YIELD (+ 리포트용 제품명)
 */
public class LotYieldVO {

    private String workDt;
    private String prodCd;
    private String prodNm;
    private String lotId;
    private int inQty;
    private int passQty;
    private BigDecimal yieldPct;
    private int bin1Qty;
    private int bin2Qty;
    private int bin3Qty;
    private int bin4Qty;
    private int bin5Qty;
    private int bin6Qty;
    private int bin7Qty;
    private int bin8Qty;
    private int bin9Qty;
    private String alertYn = "N";
    private BigDecimal alertYield;

    public String getWorkDt() { return workDt; }
    public void setWorkDt(String workDt) { this.workDt = workDt; }
    public String getProdCd() { return prodCd; }
    public void setProdCd(String prodCd) { this.prodCd = prodCd; }
    public String getProdNm() { return prodNm; }
    public void setProdNm(String prodNm) { this.prodNm = prodNm; }
    public String getLotId() { return lotId; }
    public void setLotId(String lotId) { this.lotId = lotId; }
    public int getInQty() { return inQty; }
    public void setInQty(int inQty) { this.inQty = inQty; }
    public int getPassQty() { return passQty; }
    public void setPassQty(int passQty) { this.passQty = passQty; }
    public BigDecimal getYieldPct() { return yieldPct; }
    public void setYieldPct(BigDecimal yieldPct) { this.yieldPct = yieldPct; }
    public int getBin1Qty() { return bin1Qty; }
    public void setBin1Qty(int bin1Qty) { this.bin1Qty = bin1Qty; }
    public int getBin2Qty() { return bin2Qty; }
    public void setBin2Qty(int bin2Qty) { this.bin2Qty = bin2Qty; }
    public int getBin3Qty() { return bin3Qty; }
    public void setBin3Qty(int bin3Qty) { this.bin3Qty = bin3Qty; }
    public int getBin4Qty() { return bin4Qty; }
    public void setBin4Qty(int bin4Qty) { this.bin4Qty = bin4Qty; }
    public int getBin5Qty() { return bin5Qty; }
    public void setBin5Qty(int bin5Qty) { this.bin5Qty = bin5Qty; }
    public int getBin6Qty() { return bin6Qty; }
    public void setBin6Qty(int bin6Qty) { this.bin6Qty = bin6Qty; }
    public int getBin7Qty() { return bin7Qty; }
    public void setBin7Qty(int bin7Qty) { this.bin7Qty = bin7Qty; }
    public int getBin8Qty() { return bin8Qty; }
    public void setBin8Qty(int bin8Qty) { this.bin8Qty = bin8Qty; }
    public int getBin9Qty() { return bin9Qty; }
    public void setBin9Qty(int bin9Qty) { this.bin9Qty = bin9Qty; }
    public String getAlertYn() { return alertYn; }
    public void setAlertYn(String alertYn) { this.alertYn = alertYn; }
    public BigDecimal getAlertYield() { return alertYield; }
    public void setAlertYield(BigDecimal alertYield) { this.alertYield = alertYield; }
}
