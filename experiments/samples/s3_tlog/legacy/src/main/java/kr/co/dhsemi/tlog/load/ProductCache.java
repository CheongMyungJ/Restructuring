package kr.co.dhsemi.tlog.load;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import kr.co.dhsemi.tlog.common.Constants;
import kr.co.dhsemi.tlog.mapper.MasterMapper;
import kr.co.dhsemi.tlog.vo.ProductInfo;

/**
 * 제품 기준정보 캐시
 */
@Component
public class ProductCache {

    private static final Logger logger = LoggerFactory.getLogger(ProductCache.class);

    @Autowired
    private MasterMapper masterMapper;

    private Map<String, ProductInfo> cache = null;

    private synchronized void load() {
        if (cache != null) {
            return;
        }
        cache = new HashMap<String, ProductInfo>();
        try {
            List<ProductInfo> list = masterMapper.selectProductList();
            for (ProductInfo p : list) {
                cache.put(p.getProdCd(), p);
            }
            logger.info("제품 기준정보 로딩 : " + cache.size() + "건");
        } catch (Exception e) {
            logger.error("제품 기준정보 로딩 실패", e);
        }
    }

    public ProductInfo get(String prodCd) {
        load();
        if (prodCd == null) {
            return null;
        }
        return cache.get(prodCd);
    }

    /**
     * 사용가능 제품 여부 (미등록 or 미사용 이면 false)
     */
    public boolean isUsable(String prodCd) {
        ProductInfo p = get(prodCd);
        if (p == null) {
            return false;
        }
        return Constants.YES.equals(p.getUseYn());
    }
}
