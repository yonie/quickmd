# Brewing Guide

A quick reference for making better coffee at home. This file doubles as a
rendering demo for QuickMD.

## Ratios

The golden ratio is **1:16** coffee to water by weight. Stronger or weaker to
taste:

| Style      | Ratio | Grind        | Time    |
|------------|-------|--------------|---------|
| Espresso   | 1:2   | Fine         | 25–30 s |
| Moka pot   | 1:10  | Fine-medium  | ~5 min  |
| Pour-over  | 1:16  | Medium       | 3–4 min |
| French press | 1:15 | Coarse      | 4 min   |
| Cold brew  | 1:8   | Extra coarse | 12–18 h |

> Water quality matters more than most gear upgrades. If your tap water
> tastes bad on its own, it will not taste better with coffee in it.

## Dose calculator

```python
def dose(water_ml, ratio=16):
    """Grams of coffee for a given amount of water."""
    return round(water_ml / ratio, 1)

print(dose(250))   # 15.6 g for one mug
print(dose(500))   # 31.2 g for a shared pot
```

## Pour-over checklist

- [x] Boil water, let it settle to ~93 °C
- [x] Rinse the paper filter
- [x] Grind 15 g, medium
- [ ] Bloom with 45 g of water for 30 s
- [ ] Pour in slow circles to 250 g
- [ ] Total brew time between *3:00* and *4:00*

## Notes

Beans go stale ~~after a month~~ noticeably after two weeks. Buy small bags,
whole bean, roasted recently — the roast date should be printed on the bag,
not a `best before` guess two years out.
