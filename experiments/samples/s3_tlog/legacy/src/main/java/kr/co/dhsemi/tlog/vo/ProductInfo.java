package kr.co.dhsemi.tlog.vo;

import java.math.BigDecimal;

/**
 * TB_PRODUCT
 */
public class ProductInfo {

    private String prodCd;
    private String prodNm;
    private String prodGrp;
    private BigDecimal alertYield;
    private String useYn;

    public String getProdCd() { return prodCd; }
    public void setProdCd(String prodCd) { this.prodCd = prodCd; }
    public String getProdNm() { return prodNm; }
    public void setProdNm(String prodNm) { this.prodNm = prodNm; }
    public String getProdGrp() { return prodGrp; }
    public void setProdGrp(String prodGrp) { this.prodGrp = prodGrp; }
    public BigDecimal getAlertYield() { return alertYield; }
    public void setAlertYield(BigDecimal alertYield) { this.alertYield = alertYield; }
    public String getUseYn() { return useYn; }
    public void setUseYn(String useYn) { this.useYn = useYn; }
}
